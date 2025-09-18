""" 
Branch, a CYOA (Choose-Your-Own-Adventure) Maker.
Version: v0.5.08

******************************************To-Do******************************************

@1@ Fix zooming and fully re-add it [zooming]. Calling 'redraw()' never drawed the nodes with sizes based on the 'current_zoom', 
    I've tried before, however, the node offset way too far (~ 1,-1) each time I tried to dragged a node.
    
@2@ Add a 'Change ID' in the node right-click menu. 

@3@ Add a setting field for 'default comment width' and 'default comment height' 
    (added, however, I didn't add visual fields in the 'open_settings()' 
    only the actual settings in the default settings.json{})

@4@ Option line template button (adds a template like, line1:'Template | 1 |  | ', or the next available 
    (not max+1, the min available) line due to the user might have some already written lines.)

@6@ add a setting, 'disable text truncation'.

@7@ add a setting, 'pan speed'.

@8@ make it where you can't move nodes while you're panning, I think you can as of now.
********************************************************************************************

Changelog:
@ v0.5.08 - 
    * Fixed "Variables & Inventory" to be default variable values, as intended.

@ v0.5.07 -
    * Added `clamp(VAR:MIN,MAX)` action to constrain a variable within a numeric range.
    * Added `consume(ITEM:ACTION)` shortcut to remove an item and then run an action.
    * Updated documentation for new actions.

@ v0.5.06 - 
    * Added a new flexible 'if' statement syntax: `if(cond):<conditional_actions>unconditional_actions`.
    * The colon and unconditional actions are optional, allowing for `if(cond)<conditional_actions>`.
    * Updated documentation to reflect the new syntax.

@ v0.5.05 - [removed 4th number for simplicity in version labels]
    * Fixed text truncation.

...
"""
VERSION = 'v0.5.08'

# built-ins
import os, re, ast, math, json, copy, random, operator
from typing import Any, Dict, List, Optional, Tuple, Union

# tkinter
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, colorchooser
import tkinter.font as tkFont
import tkinter.ttk as ttk

_ALLOWED_MATH_FUNCS = { # allowed (math) functions
    'sin': math.sin, 'cos': math.cos, 'tan': math.tan, 'sqrt': math.sqrt,
    'abs': abs, 'min': min, 'max': max, 'round': round, 'int': int, 'float': float
}
_ALLOWED_OPERATORS = { # allowed (math) operators
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.FloorDiv: operator.floordiv,
}

def safe_eval_expr(expr: str, names: dict): # evaluates an expression safely
    expr = expr.strip()
    if not expr:
        return None

    # parse
    node = ast.parse(expr, mode='eval')

    def _eval(n):
        if isinstance(n, ast.Expression):
            return _eval(n.body)
        if isinstance(n, ast.Constant): # for newer py (users)
            return n.value
        if isinstance(n, ast.BinOp):
            left = _eval(n.left)
            right = _eval(n.right)
            op = type(n.op)
            if op in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[op](left, right)
            raise ValueError(f"Operator {op} not allowed")
        if isinstance(n, ast.UnaryOp):
            operand = _eval(n.operand)
            op = type(n.op)
            if op in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[op](operand)
            raise ValueError(f"Unary operator {op} not allowed")
        if isinstance(n, ast.Name):
            # allow names from provided names dict
            if n.id in names:
                return names[n.id]
            # allow numeric-looking strings? No - return 0 or raise
            raise ValueError(f"Name '{n.id}' not defined")
        if isinstance(n, ast.Call):
            # only allow simple function calls (no attribute calls)
            if isinstance(n.func, ast.Name):
                fname = n.func.id
                if fname in _ALLOWED_MATH_FUNCS:
                    args = [_eval(a) for a in n.args]
                    return _ALLOWED_MATH_FUNCS[fname](*args)
            raise ValueError("Function calls not allowed or not whitelisted")
        if isinstance(n, ast.Compare):
            left = _eval(n.left)
            results = []
            for op, comparator in zip(n.ops, n.comparators):
                right = _eval(comparator)
                if isinstance(op, ast.Eq):
                    results.append(left == right)
                elif isinstance(op, ast.NotEq):
                    results.append(left != right)
                elif isinstance(op, ast.Gt):
                    results.append(left > right)
                elif isinstance(op, ast.GtE):
                    results.append(left >= right)
                elif isinstance(op, ast.Lt):
                    results.append(left < right)
                elif isinstance(op, ast.LtE):
                    results.append(left <= right)
                else:
                    raise ValueError("Comparison operator not allowed")
                left = right
            return all(results)
        raise ValueError(f"Unsupported AST: {type(n)}")

    ret = _eval(node)
    return ret

# dictionaries and whatnot
nodes: Dict[int, Dict] = {}
comments = {}
vars_store: Dict[str, Any] = {} # variable storage
inventory: List[str] = [] # inventory list
# constants
START_NODE = 1 # default start node
BASE_FONT_SIZE = 11 # font size
SETTINGS_PATH = "./settings.json" # path for 'settings.json' (saves your in-app settings on exit)
THEME_PATH = "./theme.json" # path for 'theme.json' (saves your in-app theme on exit)
MIN_W, MIN_H = 30, 20 # minimum size for comments

# A "LEAF" (it doesn't matter if it's uppercased) is simply a name for an option line in the Node Inspector.

def parse_option_line(line: Union[str, Dict]) -> Optional[Dict]:
    if isinstance(line, dict):
        return line  # already parsed, just return it

    if not isinstance(line, str):
        return None  # invalid input

    raw = line.strip()
    if not raw or raw.startswith("#"):
        return None

    # instant leaf (starts with @) → no text/next/cond, only actions
    if raw.startswith("@"):
        return {"instant": True, "actions": [raw[1:].strip()]}

    parts = [p.strip() for p in raw.split("|")]
    while len(parts) < 4:
        parts.append("")
    text, nxt, cond, acts = parts[0], parts[1], parts[2], parts[3]
    # The action string should be processed by `execute_actions`, which has the
    # necessary logic to handle complex `if` statements containing semicolons.
    # Splitting the action string here breaks that logic by prematurely separating
    # parts of a single `if` command.
    # We pass the entire action string as a single item in the list.
    actions = [acts] if acts.strip() else []
    cond = cond if cond else None
    nxt = nxt if nxt else None
    return {"text": text, "next": nxt, "condition": cond, "actions": actions, "instant": False}

def format_option_line(opt: Dict) -> str:
    if opt.get("instant"):
        # For instant leaves, prepend '@' to the first action
        acts = ";".join(opt.get("actions", []))
        return f"@{acts}" if acts else "@"
    
    acts = ";".join(opt.get("actions", [])) if opt.get("actions") else ""
    cond = opt.get("condition") or ""
    nxt = "" if opt.get("next") is None else str(opt.get("next"))
    return f"{opt.get('text','')} | {nxt} | {cond} | {acts}"

def evaluate_condition(cond: Optional[str]) -> bool: # evaluate the condition 'cond' (string). Example: 'CLICKS==1' (checks if the variable 'CLICKS' is equal to 1.)
    if not cond:
        return True
    parts = [p.strip() for p in re.split(r'[&;]', cond) if p.strip()]
    for part in parts:
        try:
            if part.startswith("has_item:"):
                name = part.split(":", 1)[1].strip()
                if name not in inventory:
                    return False
                continue
            if part.startswith("not_has_item:"):
                name = part.split(":", 1)[1].strip()
                if name in inventory:
                    return False
                continue
            # allow both var:EXPR and bare EXPR
            expr = part[4:].strip() if part.startswith("var:") else part
            try:
                res = safe_eval_expr(expr, vars_store)
            except Exception:
                return False
            if isinstance(res, bool):
                if not res:
                    return False
            else:
                if not res:
                    return False
        except Exception:
            return False
    return True

def execute_actions(actions: List[str]):
    for act in actions:
        if not act:
            continue
        
        # If the action is an 'if' statement, treat it as a single unit to handle complex actions.
        # Otherwise, split into sub-actions.
        if act.strip().startswith('if('):
            subs = [act.strip()]
        else:
            subs = [s.strip() for s in re.split(r'[&;]', act) if s.strip()]

        for sub in subs:
            try:
                # ------------------ instant @ action ------------------
                if sub.startswith("@"):
                    instant_act = sub[1:].strip()
                    execute_actions([instant_act])
                    continue

                # ------------------ if(COND):<CONDITIONAL>UNCONDITIONAL ------------------
                m_new_if = re.match(r"^if\((.+?)\):?<(.+?)>(.*)$", sub)
                if m_new_if:
                    cond_expr, conditional_expr, unconditional_expr = m_new_if.groups()
                    if evaluate_condition(cond_expr.strip()):
                        execute_actions([conditional_expr.strip()])
                    if unconditional_expr.strip():
                        execute_actions([unconditional_expr.strip()])
                    continue

                # ------------------ if(COND)>ACT or if(COND)>>ACTS ------------------
                # This now correctly handles multi-step actions with '>>'
                m_if = re.match(r"^if\((.+?)\)(>>?)(.+)$", sub)
                if m_if:
                    cond_expr = m_if.group(1).strip()
                    separator = m_if.group(2)  # '>' or '>>'
                    act_expr = m_if.group(3).strip()

                    if separator == '>':
                        # only the first action after '>' is executed
                        first_act = re.split(r'[&;]', act_expr, 1)[0].strip()
                        if evaluate_condition(cond_expr):
                            execute_actions([first_act])
                    else:  # separator == '>>'
                        # everything after '>>' is executed as a single block
                        if evaluate_condition(cond_expr):
                            execute_actions([act_expr])
                    continue

                # ------------------ once:ACT ------------------
                if sub.startswith("once:"):
                    act_expr = sub.split(":", 1)[1].strip()
                    if "__once_memory" not in vars_store:
                        vars_store["__once_memory"] = set()
                    once_mem = vars_store["__once_memory"]

                    if act_expr not in once_mem:
                        once_mem.add(act_expr)
                        execute_actions([act_expr])
                    continue

                # ------------------ chance(CHANCE)>ACT(>ELSE) ------------------
                m_chance = re.match(r"^chance\((.+)\)>(.+?)(?:>(.+))?$", sub)
                if m_chance:
                    chance_expr, act_expr, else_expr = (
                        m_chance.group(1).strip(),
                        m_chance.group(2).strip(),
                        m_chance.group(3).strip() if m_chance.group(3) else None
                    )
                    try:
                        chance_val = float(safe_eval_expr(chance_expr, vars_store))
                    except Exception:
                        chance_val = float(chance_expr) if chance_expr.replace('.','',1).isdigit() else 0
                    roll = random.uniform(0, 100)
                    if roll <= chance_val:
                        execute_actions([act_expr])
                    elif else_expr:
                        execute_actions([else_expr])
                    continue

                # ------------------ repeat:TIMES>ACT ------------------
                m_repeat = re.match(r"^repeat:(.+)>(.+)$", sub)
                if m_repeat:
                    times_expr = m_repeat.group(1).strip()
                    act_expr = m_repeat.group(2).strip()
                    try:
                        times = int(safe_eval_expr(times_expr, vars_store))
                    except Exception:
                        try:
                            times = int(times_expr)
                        except:
                            times = 0
                    for _ in range(max(0, times)):
                        execute_actions([act_expr])
                    continue

                # ------------------ weighted(VAR: item=weight, ...) ------------------
                if sub.startswith("weighted(") and sub.endswith(")"):
                    payload = sub[9:-1].strip()
                    if ":" in payload:
                        varname, items = payload.split(":", 1)
                        varname = varname.strip()
                        choices, weights = [], []
                        for pair in items.split(","):
                            if "=" in pair:
                                item, weight = pair.split("=", 1)
                                item, weight = item.strip(), weight.strip()
                                try:
                                    w = float(safe_eval_expr(weight, vars_store))
                                except Exception:
                                    try: w = float(weight)
                                    except: w = 1.0
                                choices.append(item)
                                weights.append(w)
                        if choices and weights:
                            vars_store[varname] = random.choices(choices, weights=weights, k=1)[0]
                    continue

                # ------------------ clamp(VAR:MIN,MAX) ------------------
                m_clamp = re.match(r"^clamp\((.+?):(.+?),(.+?)\)$", sub)
                if m_clamp:
                    var_name, min_expr, max_expr = m_clamp.groups()
                    var_name = var_name.strip()
                    try:
                        min_val = float(safe_eval_expr(min_expr.strip(), vars_store))
                        max_val = float(safe_eval_expr(max_expr.strip(), vars_store))
                        
                        current_val = vars_store.get(var_name)
                        if current_val is not None:
                            try:
                                current_val_num = float(current_val)
                                clamped_val = max(min_val, min(current_val_num, max_val))
                                # Preserve type if original was int
                                if isinstance(current_val, int):
                                    vars_store[var_name] = int(clamped_val)
                                else:
                                    vars_store[var_name] = clamped_val
                            except (ValueError, TypeError):
                                pass # Can't clamp a non-numeric value
                    except Exception:
                        pass # Ignore if min/max can't be evaluated
                    continue

                # ------------------ consume(ITEM:ACTION) ------------------
                m_consume = re.match(r"^consume\((.+?):(.+)\)$", sub)
                if m_consume:
                    item_name, action_expr = m_consume.groups()
                    item_name = item_name.strip()
                    action_expr = action_expr.strip()
                    if item_name in inventory:
                        inventory.remove(item_name)
                        execute_actions([action_expr])
                    continue

                # ------------------ clamp(VAR:MIN,MAX) ------------------
                m_clamp = re.match(r"^clamp\((.+?):(.+?),(.+?)\)$", sub)
                if m_clamp:
                    var_name, min_expr, max_expr = m_clamp.groups()
                    var_name = var_name.strip()
                    try:
                        min_val = float(safe_eval_expr(min_expr.strip(), vars_store))
                        max_val = float(safe_eval_expr(max_expr.strip(), vars_store))
                        
                        current_val = vars_store.get(var_name)
                        if current_val is not None:
                            try:
                                current_val_num = float(current_val)
                                clamped_val = max(min_val, min(current_val_num, max_val))
                                # Preserve type if original was int
                                if isinstance(current_val, int):
                                    vars_store[var_name] = int(clamped_val)
                                else:
                                    vars_store[var_name] = clamped_val
                            except (ValueError, TypeError):
                                pass # Can't clamp a non-numeric value
                    except Exception:
                        pass # Ignore if min/max can't be evaluated
                    continue

                # ------------------ consume(ITEM:ACTION) ------------------
                m_consume = re.match(r"^consume\((.+?):(.+)\)$", sub)
                if m_consume:
                    item_name, action_expr = m_consume.groups()
                    item_name = item_name.strip()
                    action_expr = action_expr.strip()
                    if item_name in inventory:
                        inventory.remove(item_name)
                        execute_actions([action_expr])
                    continue

                # ------------------ clearinv ------------------
                if sub == "clearinv":
                    inventory.clear()
                    continue

                # ------------------ assignment without var: (X=5, Y+=2, etc) ------------------
                m_var = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*([\+\-\*/]?=)\s*(.+)$", sub)
                if m_var:
                    name, op, rhs = m_var.group(1), m_var.group(2), m_var.group(3)
                    try:
                        rhs_val = safe_eval_expr(rhs, vars_store)
                    except Exception:
                        rhs_val = rhs.strip('"').strip("'")
                        try: rhs_val = int(rhs_val)
                        except:
                            try: rhs_val = float(rhs_val)
                            except: pass
                    cur = vars_store.get(name, 0)
                    if op == "=":
                        vars_store[name] = rhs_val
                    elif op == "+=":
                        try: vars_store[name] = (cur or 0) + rhs_val
                        except: vars_store[name] = rhs_val
                    elif op == "-=":
                        try: vars_store[name] = (cur or 0) - rhs_val
                        except: vars_store[name] = cur
                    elif op == "*=":
                        try: vars_store[name] = (cur or 0) * rhs_val
                        except: vars_store[name] = cur
                    elif op == "/=":
                        try: vars_store[name] = (cur or 0) / rhs_val
                        except: vars_store[name] = cur
                    continue

                # add_item/remove_item
                if sub.startswith("add_item:"):
                    name = sub.split(":",1)[1].strip()
                    if name and name not in inventory:
                        inventory.append(name)
                    continue

                if sub.startswith("remove_item:"):
                    name = sub.split(":",1)[1].strip()
                    if name in inventory:
                        inventory.remove(name)
                    continue

                # goto:target
                if sub.startswith("goto:"):
                    vars_store["__goto"] = sub.split(":",1)[1].strip()
                    continue

                # randr(variable: min, max)
                if sub.startswith("randr(") and sub.endswith(")"):
                    payload = sub[6:-1].strip()
                    if ":" in payload and "," in payload:
                        varname, range_vals = payload.split(":", 1)
                        varname = varname.strip()
                        try:
                            min_val, max_val = [float(v.strip()) for v in range_vals.split(",", 1)]
                            vars_store[varname] = random.uniform(min_val, max_val)
                        except Exception:
                            continue
                    continue

                # rands(variable: item1, item2, ...)
                if sub.startswith("rands(") and sub.endswith(")"):
                    payload = sub[6:-1].strip()
                    if ":" in payload:
                        varname, items = payload.split(":", 1)
                        varname = varname.strip()
                        choices = [i.strip() for i in re.split(r'[,/]', items) if i.strip()]
                        if choices:
                            vars_store[varname] = random.choice(choices)
                    continue

                # set:variable=value (legacy)
                if sub.startswith("set:"):
                    payload = sub.split(":", 1)[1]
                    if "=" not in payload:
                        continue
                    name, raw = payload.split("=", 1)
                    name, raw = name.strip(), raw.strip()
                    try:
                        val = safe_eval_expr(raw, vars_store)
                    except Exception:
                        if raw.lower() == "true":
                            val = True
                        elif raw.lower() == "false":
                            val = False
                        else:
                            try: val = int(raw)
                            except:
                                try: val = float(raw)
                                except: val = raw.strip('"').strip("'")
                    vars_store[name] = val
                    continue

                # fallback: generic name=val
                if "=" in sub:
                    name, val_expr = sub.split("=",1)
                    name, val_expr = name.strip(), val_expr.strip()
                    try:
                        vars_store[name] = safe_eval_expr(val_expr, vars_store)
                    except Exception:
                        vars_store[name] = val_expr

            except Exception:
                continue

def resolve_next(next_ref: Union[int, str]) -> Optional[int]: # resolve the next node for options
    if isinstance(next_ref, int):
        return next_ref
    if isinstance(next_ref, str):
        s = next_ref.strip()
        if not s:
            return None

        if "/" in s:
            choices = [part.strip() for part in s.split("/") if part.strip()]
            resolved = []
            for c in choices:
                try:
                    resolved.append(int(c))
                except Exception:
                    val = vars_store.get(c)
                    try:
                        resolved.append(int(val))
                    except Exception:
                        try:
                            # try evaluating expression
                            ev = safe_eval_expr(c, vars_store)
                            resolved.append(int(ev))
                        except Exception:
                            continue
            if not resolved:
                return None
            return random.choice(resolved)
        else:
            try:
                return int(s)
            except Exception:
                val = vars_store.get(s)
                try:
                    return int(val)
                except Exception:
                    try:
                        ev = safe_eval_expr(s, vars_store)
                        return int(ev)
                    except Exception:
                        return None
    return None

def create_node(num: int, header: str = "", x: int = 50, y: int = 50, options: Optional[List[Dict]] = None, color: str = '#222222'): # self-explanatory: creates a node
    nodes[num] = {"header": header, "options": options or [], "x": x, "y": y, "color": color}

def delete_node(num: int): # deletes node with node id of 'num' (int)
    if num in nodes:
        del nodes[num]
    
def list_nodes() -> List[int]: # lists nodes, pretty self-explanatory
    return sorted(nodes.keys())

def find_dead_ends() -> List[Tuple[int, Dict]]: # finds dead ends in nodes
    bad = []
    for nid, data in nodes.items():
        for opt in data["options"]:
            if opt.get("next") is None or opt.get("next") == "":
                continue
            if resolve_next(opt.get("next")) is None:
                bad.append((nid, opt))
    return bad

def run_instant_leaves(node_id: int) -> int:
    current = node_id
    while True:
        node = nodes.get(current)
        if not node:
            return current
        changed = False
        for opt_raw in node.get("options", []):
            # parse if it's a string
            if isinstance(opt_raw, str):
                opt = parse_option_line(opt_raw)
            elif isinstance(opt_raw, dict):
                opt = opt_raw
            else:
                continue

            if opt and opt.get("instant"):
                execute_actions(opt.get("actions", []))
                # handle cascading goto
                if "__goto" in vars_store:
                    nxt = resolve_next(vars_store.pop("__goto"))
                    if nxt is not None and nxt != current:
                        current = nxt
                        changed = True
                        break  # restart processing instant leaves in new node
        if not changed:
            break
    return current

NODE_W = 180 # node width
NODE_H = 80 # node height
COMMENT_W, COMMENT_H = 150, 50 # comment width, comment height
HANDLE_SIZE = 8  # size of draggable corner handles on comments
DEFAULT_SETTINGS = {
    "disable_delete_confirm": False,
    "show_path": False,
    "udtdnc": False,
    "change_node_colors": False,
    "keybinds": {
        "undo": "<Control-z>",
        "redo": "<Control-Shift-Z>",
        "redo_alt": "<Control-y>",
        "save": "<Control-s>"
    },
    "default_comment_w": 150,
    "default_comment_h": 50,
    'disable_text_truncation': False
}

class VisualEditor(tk.Frame):
    def make_collapsible_section(self, parent, title): # makes a collpasible section, such as what you see in the Node Inspector.
        container = tk.Frame(parent, bg=self.theme['inspector_container'])
        
        header = tk.Frame(container, bg=self.theme['inspector_header'])
        header.pack(fill=tk.X)

        label = tk.Label(header, text=title, bg=self.theme['inspector_label_bg2'],
                        font=("TkDefaultFont", 10, "bold"))
        label.pack(side=tk.LEFT, padx=4)

        
        toggle_btn = tk.Button(header, text="-", width=2,
                            relief="flat", bg=self.theme['inspector_toggle_btn'])
        toggle_btn.pack(side=tk.LEFT, padx=2)   

        
        body = tk.Frame(container, bg=self.theme['inspector_body'])
        body.pack(fill=tk.X)

        def toggle():
            if body.winfo_ismapped():
                body.forget()
                toggle_btn.config(text="+")
            else:
                body.pack(fill=tk.X)
                toggle_btn.config(text="-")

        toggle_btn.config(command=toggle)

        return container, body

    def __init__(self, master): # init
        self.root = master
        super().__init__(master)
        self.master.title("Branch -- Visual CYOA Editor") # title
        self.pack(fill=tk.BOTH, expand=True)
        self.mode = "editor" # initalize mode
        self.selected_node: Optional[int] = None
        self.dragging = False
        self.drag_offset = (0,0)
        self.node_base_fonts: Dict[int, tkFont.Font] = {}  
        self.current_zoom = 1.0 # all zoom features are commented out due to bugs that will be worked on in the future.
        self.multi_select_rect = None
        self.multi_selected_nodes = set() # set of multi selected nodes
        self.undo_stack = [] # undo stack, or 'undo list'
        self._highlight_job = None # For debouncing syntax highlighting
        self.theme = {} # define 'self.theme' for later use
        self.editor_vars_backup = None
        self.editor_inventory_backup = None

        # --- comment system state ---
        self.selected_comment = None
        self.resizing_comment = False
        self.comment_rects = {}
        self.comment_texts = {}
        
        # load theme.json if existing, otherwise, load 'default' theme.
        if not os.path.exists(THEME_PATH):
            self.themepreset('default')
        else:
            self.load_theme()          
        self.redo_stack = []

        # Toolbar definition
        self.toolbar = tk.Frame(self)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)

        # Font
        default_font = tkFont.nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=10)
        self.root.option_add("*Font", default_font)

        # Focus Canvas
        tk.Button(self.toolbar, text="Focus Canvas", command=self.focus_canvas).pack(side=tk.LEFT) # focuses the canvas so you can use WASD (to move around)

        # Search node input
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.toolbar, textvariable=self.search_var, width=8)
        self.search_entry.pack(side=tk.LEFT, padx=4)

        # Return (aka, enter) searches for the node if you typed a number in the search.
        self.search_entry.bind("<Return>", self.search_node)

        # Ctrl+F Bind = Find Node
        self.master.bind("<Control-f>", lambda e: self.search_entry.focus_set())

        # Play/Edit mode button
        self.mode_button = tk.Button(self.toolbar, text="Switch to Play Mode", command=self.toggle_mode)
        self.mode_button.pack(side=tk.RIGHT)

        # Node Counter
        self.node_count_label = tk.Label(self.toolbar, text="Nodes: 0")
        self.node_count_label.pack(side=tk.RIGHT, padx=6)

        # default settings
        self.settings = DEFAULT_SETTINGS.copy()
        self.load_settings() # load settings if path settings.json exists

        tk.Button(self.toolbar, text="Settings", command=self.open_settings).pack(side=tk.LEFT) # settings button
        tk.Button(self.toolbar, text="Theme Control", command=self.open_themecontrol).pack(side=tk.LEFT) # theme control button
        tk.Label(self.toolbar, text=f'{VERSION}').pack(side=tk.RIGHT)

        self.menubar = tk.Menu(self.master)
        self.master.config(menu=self.menubar)
        self.master.protocol("WM_DELETE_WINDOW", self.on_exit)

        # App Menu
        self.app_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="App", menu=self.app_menu)
        self.apply_keybinds()
        self.app_menu.add_command(label="Undo (Ctrl+Z)", command=self.undo)
        self.app_menu.add_command(label="Redo (Ctrl+Shift+Z / Ctrl+Y)", command=self.redo)
        self.app_menu.add_separator()
        self.app_menu.add_command(label="Clear all saves", command=self.clear_all_saves)
        self.app_menu.add_command(label="Save (Ctrl+S)", command=self.save_story_dialog)
        self.app_menu.add_command(label="Load", command=self.load_story_dialog)
        self.app_menu.add_separator()
        self.app_menu.add_command(label="Quit", command=self.master.quit)
        self.app_menu.add_separator()
        self.app_menu.add_command(label="Clear all nodes.", command=self.reset_all)
         
        self.paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Canvas Frame Definition
        canvas_frame = tk.Frame(self.paned)
        self.canvas = tk.Canvas(canvas_frame, bg='#101010', width=900, height=600,
                                scrollregion=(-100000,-100000,100000,100000))
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Setup Controls
        self.setup_controls()

        # Node Menu (right clicking on a node)
        self.node_menu = tk.Menu(self.canvas, tearoff=0)
        self.node_menu.add_command(label="Delete Node", command=self.delete_selected_node)

        # Inspector Frame Definition
        self.inspector_frame = tk.Frame(self.paned, bg="#dcdcdc", width=100)
        self.inspector_frame.pack_propagate(False)  

        # Inspector Canvas Defintion
        self.inspector_canvas = tk.Canvas(self.inspector_frame, bg="#dcdcdc", highlightthickness=0)
        self.inspector_canvas.pack(side="left", fill="both", expand=True)

        # Inspector Definition
        self.inspector = tk.Frame(self.inspector_canvas, bg="#dcdcdc")
        self.inspector_canvas.create_window((0, 0), window=self.inspector, anchor="nw")

        # Make canvas_frame and self.inspector_frame a paned frame
        self.paned.add(canvas_frame)       
        self.paned.add(self.inspector_frame)  

        def set_default_sash(event=None):
            total = self.paned.winfo_width()
            if total > 500:
                self.paned.sashpos(0, total - 400)  
            else:
                self.paned.sashpos(0, total // 2)
        self.after_idle(set_default_sash)

        # Node Inspector
        self.master.bind("<Configure>", set_default_sash)
        self.title_lbl = tk.Label(self.inspector, text="Node Inspector", font=("TkDefaultFont", 12, "bold"), bg=self.theme['inspector_label_bg'])
        self.title_lbl.pack(anchor="w", pady=(8, 4))
        
        # ***************************Node Info Section***************************
        node_sec, node_body = self.make_collapsible_section(self.inspector, "Node Info")
        node_sec.pack(fill="x", expand=False, pady=(4,0))
        # ID Label
        self.id_label = tk.Label(node_body, text="ID: -", bg=self.theme['inspector_label_bg'])
        self.id_label.pack(anchor="w")
        # Header stuff
        tk.Label(node_body, width=10, text="Header:", bg=self.theme['inspector_label_bg']).pack(anchor="w")
        self.header_text = tk.Text(
            node_body,
            height=3,
            wrap="word",  # wrap properly at words
            bg=self.theme['inspector_textbox_bg']
        )
        self.header_text.pack(fill="x", expand=True, padx=4, pady=2)  # let it expand horizontally

        # ***************************Options Section***************************
        opt_sec, opt_body = self.make_collapsible_section(self.inspector, "Options")
        opt_sec.pack(fill=tk.X, pady=(4,0))
        tk.Label(opt_body, text="text | next | condition | actions", bg=self.theme['inspector_label_bg']).pack(anchor="w")
        self.options_text = tk.Text(opt_body, height=8, wrap="word", bg=self.theme['inspector_textbox_bg'])
        self.options_text.pack(fill="x", expand=True, padx=4, pady=2)
        tk.Button(opt_body, text="Set as Start Node", command=self.set_start_node, bg=self.theme['inspector_button_bg']).pack(anchor="w", pady=(6,0))
       
        # ***************************Variables and Inventory section.***************************
        vars_sec, vars_body = self.make_collapsible_section(self.inspector, "Variables & Inventory")
        vars_sec.pack(fill=tk.X, pady=(4,0))

        # Vars List
        self.vars_list = tk.Text(vars_body, height=5, wrap="word", bg=self.theme['inspector_textbox_bg'])
        self.vars_list.pack(fill="x", expand=True, padx=4, pady=2)

        def sync_text_width(event):
            text_widget = event.widget
            # get current width of the frame in pixels
            width_px = text_widget.winfo_width()
            # convert pixels > approx characters (roughly)
            char_width = text_widget.winfo_fpixels("1c")
            new_width = max(int(width_px / char_width), 1)
            text_widget.config(width=new_width)

        self.header_text.bind("<Configure>", sync_text_width)
        self.options_text.bind("<Configure>", sync_text_width)
        self.vars_list.bind("<Configure>", sync_text_width)

        # ***************************Color Section***************************        
        color_sec, color_body = self.make_collapsible_section(self.inspector, "Colors")
        color_sec.pack(fill=tk.X, pady=(4,0))

        # Pick Node Color (you can pick any color on Tkinters' default 'colorchooser' for the currently selected node)
        tk.Button(color_body, text="Pick Node Color", command=self.pick_node_color, bg=self.theme['inspector_button_bg']).pack(anchor="w", pady=(4,0))
        # Node Color Presets
        preset_frame = tk.Frame(color_body, bg=self.theme['preset_frame_bg'])
        preset_frame.pack(anchor="w", pady=(4,0))
        tk.Label(preset_frame, text="Presets:", bg=self.theme['inspector_label_bg']).pack(side=tk.LEFT)
        preset_canvas = tk.Canvas(preset_frame, height=30, width=300, bg=self.theme['preset_canvas_bg'])
        h_scroll = tk.Scrollbar(preset_frame, orient=tk.HORIZONTAL, command=preset_canvas.xview, bg=self.theme['preset_canvas_bg'])
        preset_canvas.configure(xscrollcommand=h_scroll.set, bg=self.theme['preset_canvas_bg'])
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        preset_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.preset_inner = tk.Frame(preset_canvas, bg=self.theme['preset_inner_bg'])
        preset_canvas.create_window((0,0), window=self.preset_inner, anchor='nw')
        self.color_presets = [
            "#e6194B","#f58231","#ffe119","#bfef45","#3cb44b","#42d4f4","#4363d8",
            "#911eb4","#f032e6","#a9a9a9","#555555","#222222","#ffffff"
        ]
        for c in self.color_presets:
            btn = tk.Button(self.preset_inner, bg=c, width=2,
                            command=lambda col=c: self.apply_preset_color(col))
            btn.pack(side=tk.LEFT, padx=1)
        self.preset_inner.update_idletasks()
        preset_canvas.config(scrollregion=preset_canvas.bbox("all"))

        # Canvas Keybinds
        self.canvas.bind("<ButtonPress-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.tag_bind("node", "<Button-3>", self.node_right_click)
        self.canvas.bind("<Shift-ButtonPress-1>", self.multi_select_start)
        self.canvas.bind("<Shift-B1-Motion>", self.multi_select_drag)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.multi_select_end)
        self.canvas.bind("<ButtonPress-1>", self.start_resize, add="+")
        self.canvas.bind("<B1-Motion>", self.do_resize, add="+")
        self.canvas.bind("<ButtonRelease-1>", self.stop_resize, add="+")
        self.canvas.tag_bind("comment", "<Button-3>", self.comment_right_click)
        self.canvas.bind("<ButtonPress-1>", self.start_canvas_or_comment, add="+")  # move comments
        self.canvas.bind("<ButtonPress-1>", self.canvas_mouse_down, add="+")        # move nodes
        self.canvas.bind("<B1-Motion>", self.canvas_mouse_move, add="+")
        self.canvas.bind("<ButtonRelease-1>", self.canvas_mouse_up, add="+")

        # Auto-application stuff
        self.updating = False
        self.header_text.bind("<<Modified>>", self._on_modified)
        self.vars_list.bind("<<Modified>>", self._on_modified)

        self.header_text.bind("<FocusOut>", self._on_focus_out)
        self.options_text.bind("<FocusOut>", self._on_focus_out)
        self.vars_list.bind("<FocusOut>", self._on_focus_out)

        # Background Right Click Menu
        self.bg_menu = tk.Menu(self.canvas, tearoff=0)
        self.bg_menu.add_command(label="(Quick) Add Node", command=lambda: self.quick_add_node())
        self.bg_menu.add_command(label="(Specific ID) Add Node", command=self.add_node_prompt)  
        self.bg_menu.add_command(label="Add Comment", command=self.add_comment_prompt) 
        self.canvas.bind("<Button-3>", self.background_right_click)

        # Define nodes and edges initally
        self.node_rects: Dict[int, int] = {}
        self.node_texts: Dict[int, int] = {}
        self.edge_items: List[int] = []

        # Load theme.json if the path exists, otherwise, load 'default' theme.
        if not os.path.exists(THEME_PATH):
            self.themepreset('default')
        else:
            self.load_theme()

        # Configure syntax highlighting
        self._configure_syntax_highlighting()

        # Build an example
        self.build_example()

        # Draw everything
        self.redraw()
        
        # Update the node count
        self.update_node_count()

        # Master binds
        self.master.bind("<Control-z>", lambda e: self.undo())
        self.master.bind("<Control-Shift-Z>", lambda e: self.redo())
        self.master.bind("<Control-y>", lambda e: self.redo())

    def apply_comment_text(self):
        if self.selected_comment is None:
            return
        new_text = self.header_text.get("1.0", tk.END).strip()
        comments[self.selected_comment]["text"] = new_text
        self.redraw()

    def start_canvas_or_comment(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.moving_comment = None
        for cid, data in comments.items():
            w, h = data.get("w", COMMENT_W), data.get("h", COMMENT_H)
            if data["x"] <= x <= data["x"] + w and data["y"] <= y <= data["y"] + h:
                self.moving_comment = cid
                self.comment_drag_start = (x, y)
                self.comment_orig_pos = (data["x"], data["y"])
                break

    def move_comment(self, event):
        if self.moving_comment is None:
            return
        cid = self.moving_comment
        data = comments[cid]
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        dx = x - self.comment_drag_start[0]
        dy = y - self.comment_drag_start[1]
        orig_x, orig_y = self.comment_orig_pos
        data["x"] = orig_x + dx
        data["y"] = orig_y + dy
        self.redraw()

    def stop_moving_comment(self, event):
        self.moving_comment = None

    def _on_modified(self, event):
        if self.updating:
            event.widget.edit_modified(False)
            return
        w = event.widget
        if w.edit_modified():
            if w is self.header_text:
                if self.selected_comment is not None:
                    self.apply_comment_edits()
                elif self.selected_node is not None:
                    self.apply_edits()
            elif w is self.vars_list:
                self.apply_vars_text()
            w.edit_modified(False)

    def _on_focus_out(self, event):
        if self.selected_comment is not None:
            self.apply_comment_edits()
        elif self.selected_node is not None:
            self.apply_edits()
        self.apply_vars_text()

    def change_every_node_color(self, color: str):
        self.push_undo()
        targets = nodes
        for nid in targets:
            if nid is not None:
                nodes[nid]["color"] = color
        self.redraw()        

    def themepreset(self, preset: str, changetype=None):
        if preset:
            if preset == 'default':
                self.theme = { 
                    "canvas_background": "#1e1e2e", 
                    "from_lines": "#89dceb", 
                    "to_lines": "#f38ba8",
                    "randomEdgeFromColor": "#fab387",

                    "default_node_color": "#313244",
                    "node_outline": "#585b70",
                    "node_selected_outline": "#fab387",
                    "multi_selected_outline": "#f9e2af",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#2e2e3e",
                    "inspector_canvas_bg": "#2e2e3e",
                    "title_lbl_bg": "#2e2e3e",
                    "inspector_frame_bg": "#2e2e3e",
                    "inspector_container": "#313244",
                    "inspector_body": "#313244",
                    "inspector_label_bg": "#313244",
                    "inspector_label_bg2": "#45475a",
                    "inspector_header": "#45475a",
                    "inspector_toggle_btn": "#45475a",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#a6e3a1",

                    "syntax_keyword": "#c586c0", # magenta
                    "syntax_comment": "#6A9955",
                    "syntax_string": "#ce9178",
                    "syntax_number": "#b5cea8",
                    "syntax_variable": "#9cdcfe",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f44747",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'cherries':
                self.theme = { 
                    "canvas_background": "#2e1e1f", 
                    "from_lines": "#f38ba8", 
                    "to_lines": "#fab387",
                    "randomEdgeFromColor": "#89b4fa",

                    "default_node_color": "#4a2c31",
                    "node_outline": "#6e2f3c",
                    "node_selected_outline": "#fab387",
                    "multi_selected_outline": "#f9e2af",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#3c2a2e",
                    "inspector_canvas_bg": "#3c2a2e",
                    "title_lbl_bg": "#3c2a2e",
                    "inspector_frame_bg": "#3c2a2e",
                    "inspector_container": "#5a3a40",
                    "inspector_body": "#5a3a40",
                    "inspector_label_bg": "#5a3a40",
                    "inspector_label_bg2": "#704348",
                    "inspector_header": "#704348",
                    "inspector_toggle_btn": "#704348",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#f38ba8",

                    "syntax_keyword": "#f38ba8", # red
                    "syntax_comment": "#7f849c",
                    "syntax_string": "#fab387",
                    "syntax_number": "#a6e3a1",
                    "syntax_variable": "#89b4fa",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f38ba8",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'ocean':
                self.theme = { 
                    "canvas_background": "#1e1e2e", 
                    "from_lines": "#74c7ec", 
                    "to_lines": "#1e66f5",
                    "randomEdgeFromColor": "#f9e2af",

                    "default_node_color": "#1e2a40",
                    "node_outline": "#3a4c6e",
                    "node_selected_outline": "#89dceb",
                    "multi_selected_outline": "#fab387",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#223449",
                    "inspector_canvas_bg": "#223449",
                    "title_lbl_bg": "#223449",
                    "inspector_frame_bg": "#223449",
                    "inspector_container": "#304c66",
                    "inspector_body": "#304c66",
                    "inspector_label_bg": "#304c66",
                    "inspector_label_bg2": "#436585",
                    "inspector_header": "#436585",
                    "inspector_toggle_btn": "#436585",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#89b4fa",

                    "syntax_keyword": "#cba6f7", # lavender
                    "syntax_comment": "#7f849c",
                    "syntax_string": "#fab387",
                    "syntax_number": "#a6e3a1",
                    "syntax_variable": "#89b4fa",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f38ba8",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'forest':
                self.theme = { 
                    "canvas_background": "#232e25", 
                    "from_lines": "#a6e3a1", 
                    "to_lines": "#e5c890",
                    "randomEdgeFromColor": "#89b4fa",

                    "default_node_color": "#2e4630",
                    "node_outline": "#4f6f56",
                    "node_selected_outline": "#a6e3a1",
                    "multi_selected_outline": "#fab387",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#2a3e2f",
                    "inspector_canvas_bg": "#2a3e2f",
                    "title_lbl_bg": "#2a3e2f",
                    "inspector_frame_bg": "#2a3e2f",
                    "inspector_container": "#36543d",
                    "inspector_body": "#36543d",
                    "inspector_label_bg": "#36543d",
                    "inspector_label_bg2": "#4a6b51",
                    "inspector_header": "#4a6b51",
                    "inspector_toggle_btn": "#4a6b51",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#a6e3a1",

                    "syntax_keyword": "#dfa00d", # dark yellow
                    "syntax_comment": "#7f849c",
                    "syntax_string": "#fab387",
                    "syntax_number": "#a6e3a1",
                    "syntax_variable": "#89b4fa",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f38ba8",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'ocean 2':
                self.theme = { 
                    "canvas_background": "#1e1e2e", 
                    "from_lines": "#74c7ec", 
                    "to_lines": "#cba6f7",
                    "randomEdgeFromColor": "#fab387",

                    "default_node_color": "#403347",
                    "node_outline": "#5b4f63",
                    "node_selected_outline": "#fab387",
                    "multi_selected_outline": "#f9e2af",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#2f2b3a",
                    "inspector_canvas_bg": "#2f2b3a",
                    "title_lbl_bg": "#2f2b3a",
                    "inspector_frame_bg": "#2f2b3a",
                    "inspector_container": "#473c57",
                    "inspector_body": "#473c57",
                    "inspector_label_bg": "#473c57",
                    "inspector_label_bg2": "#5e4e71",
                    "inspector_header": "#5e4e71",
                    "inspector_toggle_btn": "#5e4e71",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#cba6f7",

                    "syntax_keyword": "#cba6f7", # lavender
                    "syntax_comment": "#7f849c",
                    "syntax_string": "#fab387",
                    "syntax_number": "#a6e3a1",
                    "syntax_variable": "#89b4fa",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f38ba8",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'bubblegum':
                self.theme = {
                    "canvas_background": "#663e5e", 
                    "from_lines": "#ff97c9", 
                    "to_lines": "#9C2071",
                    "randomEdgeFromColor": "#a970d7",

                    "default_node_color": "#B773AB",
                    "node_outline": "#d6afd2",
                    "node_selected_outline": "#ffffff",
                    "multi_selected_outline": "#f9e2af",
                    "node_text_fill": "#f5f5f5",

                    "inspector_bg": "#3a2b37",
                    "inspector_canvas_bg": "#3a2b37",
                    "title_lbl_bg": "#3a2b37",
                    "inspector_frame_bg": "#3a2b37",
                    "inspector_container": "#573c52",
                    "inspector_body": "#573c52",
                    "inspector_label_bg": "#573c51",
                    "inspector_label_bg2": "#714e6f",
                    "inspector_header": "#714e6f",
                    "inspector_toggle_btn": "#714e6f",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#f7a6e4",

                    "syntax_keyword": "#f7a6e4", # pink
                    "syntax_comment": "#7f849c",
                    "syntax_string": "#fab387",
                    "syntax_number": "#a6e3a1",
                    "syntax_variable": "#89b4fa",
                    "syntax_separator": "#888888",
                    "syntax_operator": "#888888",
                    "syntax_error": "#f38ba8",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",                    
                }
            elif preset == 'underground':
                self.theme = {
                    "canvas_background": "#292522",
                    "from_lines": "#ffd700",
                    "to_lines": "#cd853f",
                    "randomEdgeFromColor": "#b87333",

                    "default_node_color": "#4d4540",
                    "node_outline": "#6b5f58",
                    "node_selected_outline": "#ffd700",
                    "multi_selected_outline": "#ffec8b",
                    "node_text_fill": "#f5deb3",

                    "inspector_bg": "#3d3530",
                    "inspector_canvas_bg": "#3d3530",
                    "title_lbl_bg": "#3d3530",
                    "inspector_frame_bg": "#3d3530",
                    "inspector_container": "#524841",
                    "inspector_body": "#524841",
                    "inspector_label_bg": "#524841",
                    "inspector_label_bg2": "#61564f",
                    "inspector_header": "#61564f",
                    "inspector_toggle_btn": "#61564f",
                    "inspector_textbox_bg": "#f5f5f5",
                    "inspector_button_bg": "#cd853f",

                    "syntax_keyword": "#cd853f", # peru
                    "syntax_comment": "#928374",
                    "syntax_string": "#d65d0e",
                    "syntax_number": "#b5cea8",
                    "syntax_variable": "#83a598",
                    "syntax_separator": "#7c6f64",
                    "syntax_operator": "#7c6f64",
                    "syntax_error": "#fb4934",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'sky':
                self.theme = {
                    "canvas_background": "#a0d2eb",
                    "from_lines": "#ffdb58",
                    "to_lines": "#4682b4",
                    "randomEdgeFromColor": "#ffa500",

                    "default_node_color": "#f5f5f5",
                    "node_outline": "#dcdcdc",
                    "node_selected_outline": "#ffdb58",
                    "multi_selected_outline": "#f0e68c",
                    "node_text_fill": "#333333",

                    "inspector_bg": "#e0f2fe",
                    "inspector_canvas_bg": "#e0f2fe",
                    "title_lbl_bg": "#e0f2fe",
                    "inspector_frame_bg": "#e0f2fe",
                    "inspector_container": "#bde0fe",
                    "inspector_body": "#bde0fe",
                    "inspector_label_bg": "#bde0fe",
                    "inspector_label_bg2": "#90c8f8",
                    "inspector_header": "#90c8f8",
                    "inspector_toggle_btn": "#90c8f8",
                    "inspector_textbox_bg": "#ffffff",
                    "inspector_button_bg": "#ffdb58",

                    "syntax_keyword": "#4682b4", # steelblue
                    "syntax_comment": "#3b82f6",
                    "syntax_string": "#fb923c",
                    "syntax_number": "#34d399",
                    "syntax_variable": "#2563eb",
                    "syntax_separator": "#6b7280", # grey
                    "syntax_operator": "#6b7280", # grey
                    "syntax_error": "#ef4444",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'night sky':
                self.theme = {
                    "canvas_background": "#0b1120",
                    "from_lines": "#fde047",
                    "to_lines": "#93c5fd",
                    "randomEdgeFromColor": "#a5b4fc",

                    "default_node_color": "#1e293b",
                    "node_outline": "#475569",
                    "node_selected_outline": "#fde047",
                    "multi_selected_outline": "#f8fafc",
                    "node_text_fill": "#e2e8f0",

                    "inspector_bg": "#1c2436",
                    "inspector_canvas_bg": "#1c2436",
                    "title_lbl_bg": "#1c2436",
                    "inspector_frame_bg": "#1c2436",
                    "inspector_container": "#2a364e",
                    "inspector_body": "#2a364e",
                    "inspector_label_bg": "#2a364e",
                    "inspector_label_bg2": "#3a4a66",
                    "inspector_header": "#3a4a66",
                    "inspector_toggle_btn": "#3a4a66",
                    "inspector_textbox_bg": "#f8fafc",
                    "inspector_button_bg": "#93c5fd",

                    "syntax_keyword": "#60a5fa",
                    "syntax_comment": "#64748b",
                    "syntax_string": "#f59e0b",
                    "syntax_number": "#34d399",
                    "syntax_variable": "#818cf8",
                    "syntax_separator": "#94a3b8",
                    "syntax_operator": "#94a3b8",
                    "syntax_error": "#f87171",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == 'lemon':
                self.theme = {
                    "canvas_background": "#fefce8",
                    "from_lines": "#4ade80",
                    "to_lines": "#a3e635",
                    "randomEdgeFromColor": "#f97316",

                    "default_node_color": "#fef9c3",
                    "node_outline": "#fde68a",
                    "node_selected_outline": "#4ade80",
                    "multi_selected_outline": "#84cc16",
                    "node_text_fill": "#422006",

                    "inspector_bg": "#fefce8",
                    "inspector_canvas_bg": "#fefce8",
                    "title_lbl_bg": "#fefce8",
                    "inspector_frame_bg": "#fefce8",
                    "inspector_container": "#fef9c3",
                    "inspector_body": "#fef9c3",
                    "inspector_label_bg": "#fef9c3",
                    "inspector_label_bg2": "#fde68a",
                    "inspector_header": "#fde68a",
                    "inspector_toggle_btn": "#fde68a",
                    "inspector_textbox_bg": "#ffffff",
                    "inspector_button_bg": "#a3e635",

                    "syntax_keyword": "#f97316", # orange
                    "syntax_comment": "#ca8a04",
                    "syntax_string": "#2563eb",
                    "syntax_number": "#16a34a",
                    "syntax_variable": "#4f46e5",
                    "syntax_separator": "#44403c",
                    "syntax_operator": "#44403c",
                    "syntax_error": "#dc2626",

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
                }
            elif preset == '90s':
                self.theme = {
                    "canvas_background": "#111111",
                    "from_lines": "#cccccc",
                    "to_lines": "#999999",
                    "randomEdgeFromColor": "#eeeeee",

                    "default_node_color": "#222222",
                    "node_outline": "#555555",
                    "node_selected_outline": "#ffffff",
                    "multi_selected_outline": "#dddddd",
                    "node_text_fill": "#eeeeee",

                    "inspector_bg": "#181818",
                    "inspector_canvas_bg": "#181818",
                    "title_lbl_bg": "#181818",
                    "inspector_frame_bg": "#181818",
                    "inspector_container": "#282828",
                    "inspector_body": "#282828",
                    "inspector_label_bg": "#282828",
                    "inspector_label_bg2": "#383838",
                    "inspector_header": "#383838",
                    "inspector_toggle_btn": "#383838",
                    "inspector_textbox_bg": "#cccccc",
                    "inspector_button_bg": "#444444",
                    "inspector_text_fg": "#000000",

                    "syntax_keyword": "#222222",
                    "syntax_comment": "#666666",
                    "syntax_string": "#333333",
                    "syntax_number": "#333333",
                    "syntax_variable": "#333333",
                    "syntax_separator": "#555555",
                    "syntax_operator": "#555555",
                    "syntax_error": "#000000",

                    "preset_canvas_bg": "#333333",
                    "preset_inner_bg": "#333333",
                    "preset_frame_bg": "#333333",
                }
            
        try:
            #self.theme.setdefault('randomEdgeFromColor', '#8e44ff')
            self.canvas.config(bg=self.theme['canvas_background'])
            self.inspector.config(bg=self.theme['inspector_bg'])
            self.inspector_canvas.config(bg=self.theme['inspector_canvas_bg'])
            self.title_lbl.config(bg=self.theme['title_lbl_bg'])
            self.inspector_frame.config(bg=self.theme['inspector_frame_bg'])
            self.redraw()

            def apply_theme_recursive(widget):
                # background keys
                bg_keys = [
                    "inspector_bg", "inspector_canvas_bg", "inspector_frame_bg",
                    "inspector_container", "inspector_body",
                    "inspector_label_bg", "inspector_label_bg2",
                    "inspector_header", "inspector_toggle_btn",
                    "inspector_textbox_bg", "inspector_button_bg",
                    "preset_canvas_bg", "preset_inner_bg", "preset_frame_bg"
                ]

                for child in widget.winfo_children():
                    # Pick a bg depending on widget type
                    if isinstance(child, tk.Label):
                        child.config(bg=self.theme.get("inspector_label_bg", "#2e2e3e"),
                                    fg=self.theme.get("node_text_fill", "#ffffff"))
                    elif isinstance(child, tk.Button):
                        if child.winfo_parent() != str(self.preset_inner):
                            child.config(bg=self.theme.get("inspector_button_bg", "#a6e3a1"))
                    elif isinstance(child, tk.Text):
                        child.config(
                            bg=self.theme.get("inspector_textbox_bg", "#f5f5f5"),
                            fg=self.theme.get("inspector_text_fg", "#000000")
                        )
                    elif isinstance(child, tk.Frame):
                        child.config(bg=self.theme.get("inspector_body", "#313244"))
                    elif isinstance(child, tk.Canvas):
                        child.config(bg=self.theme.get("inspector_canvas_bg", "#2e2e3e"))

                    # Recurse
                    apply_theme_recursive(child)

            apply_theme_recursive(self.inspector)
            if self.settings['change_node_colors']:
                self.change_every_node_color(self.theme.get('default_node_color', '#222222'))
            
            self._configure_syntax_highlighting() # Re-apply tag colors

        except Exception:
            pass

    def add_comment_prompt(self):
        self.add_comment()

    def setup_controls(self):
        self.pressed_keys = set()

        self.canvas.focus_set()

        self.canvas.bind("<KeyPress-w>", lambda e: self.pressed_keys.add("w"))
        self.canvas.bind("<KeyRelease-w>", lambda e: self.pressed_keys.discard("w"))

        self.canvas.bind("<KeyPress-a>", lambda e: self.pressed_keys.add("a"))
        self.canvas.bind("<KeyRelease-a>", lambda e: self.pressed_keys.discard("a"))

        self.canvas.bind("<KeyPress-s>", lambda e: self.pressed_keys.add("s"))
        self.canvas.bind("<KeyRelease-s>", lambda e: self.pressed_keys.discard("s"))

        self.canvas.bind("<KeyPress-d>", lambda e: self.pressed_keys.add("d"))
        self.canvas.bind("<KeyRelease-d>", lambda e: self.pressed_keys.discard("d"))        

        self.update_cam()

    def focus_canvas(self, event=None):
        try:
            self.canvas.confgure(takeFocus=1)
        except Exception:
            pass
        self.canvas.focus_set()

    def reset_all(self):
        if messagebox.askyesno('Reset All?', f'Continuing will delete all {len(self.node_rects)} nodes. Are you SURE?'):
            self.push_undo()
            nodes.clear(); vars_store.clear(); inventory.clear()
            self.redraw()

    def update_cam(self):
        dx = dy = 0
        step = 1

        if "w" in self.pressed_keys: dy -= step
        if "s" in self.pressed_keys: dy += step
        if "a" in self.pressed_keys: dx -= step
        if "d" in self.pressed_keys: dx += step

        if dx or dy:
            self.canvas.xview_scroll(dx, "units")
            self.canvas.yview_scroll(dy, "units")
        self.canvas.after(16, self.update_cam)

    def apply_keybinds(self):
        for seq in list(self.master.bind()):
            if seq in self.settings["keybinds"].values():
                self.master.unbind(seq)
        self.master.bind(self.settings["keybinds"]["undo"], lambda e: self.undo())
        self.master.bind(self.settings["keybinds"]["redo"], lambda e: self.redo())
        self.master.bind(self.settings["keybinds"]["redo_alt"], lambda e: self.redo())
        #self.master.bind(self.settings["keybinds"]["reset_zoom"], lambda e: self.reset_zoom())
        self.master.bind(self.settings["keybinds"]["save"], lambda e: self.save_story_dialog())        
        self.app_menu.entryconfig(0, label=f"Undo ({self.pretty_key(self.settings['keybinds']['undo'])})")
        self.app_menu.entryconfig(1, label=f"Redo ({self.pretty_key(self.settings['keybinds']['redo'])} / {self.pretty_key(self.settings['keybinds']['redo_alt'])})")
        #self.app_menu.entryconfig(3, label=f"Reset Zoom ({self.pretty_key(self.settings['keybinds']['reset_zoom'])})")
        self.app_menu.entryconfig(5, label=f"Save ({self.pretty_key(self.settings['keybinds']['save'])})")
        
    def pretty_key(self, seq: str) -> str:
        return seq.replace("<Control-", "Ctrl+").replace("<Shift-", "Shift+").replace(">", "").upper()

    def open_settings(self):
        win = tk.Toplevel(self)
        win.title("Settings")
        win.minsize(500, 250)

        # --- Checkbox settings ---
        checkbox_settings = [
            ("show_path", "Show path in play mode at the end."),
            ("disable_delete_confirm", "Disable deletion confirmation dialogs."),
            ("disable_text_truncation", "Disable text truncation in nodes ('...')."),
            ("udtdnc", "Use theme's default node color when creating a new node."),
            ("change_node_colors", "Apply theme's default node color to all nodes when switching themes.")
        ]

        for key, text in checkbox_settings:
            var = tk.BooleanVar(value=self.settings.get(key, False))
            command = lambda k=key, v=var: self.settings.update({k: v.get()})
            chk = tk.Checkbutton(win, text=text, variable=var, command=command, wraplength=480, justify=tk.LEFT)
            chk.pack(anchor="w", pady=2, padx=4)

        ttk.Separator(win).pack(fill='x', pady=10, padx=5)

        # --- Keybind settings ---
        tk.Label(win, text="Keybinds:").pack(anchor="w", padx=4)
        
        keybind_frame = tk.Frame(win)
        keybind_frame.pack(fill='x', padx=4, pady=2)
        keybind_frame.columnconfigure(1, weight=1) # Make entry expand

        for i, (action, seq) in enumerate(self.settings["keybinds"].items()):
            tk.Label(keybind_frame, text=action.capitalize()).grid(row=i, column=0, sticky='w', padx=4, pady=2)
            
            entry = tk.Entry(keybind_frame)
            entry.insert(0, seq)
            entry.grid(row=i, column=1, sticky='ew', padx=4, pady=2)

            def save_bind(a=action, e=entry):
                self.settings["keybinds"][a] = e.get()
                self.apply_keybinds()

            tk.Button(keybind_frame, text="Apply", command=save_bind).grid(row=i, column=2, sticky='e', padx=4, pady=2)
                
    def is_valid_action(self, s: str) -> bool:
        """Checks if a single action string is syntactically valid."""
        s = s.strip()
        if not s: return True

        # Check against known action patterns
        if re.match(r"^if\(", s): return True
        if s.startswith("chance(") and s.endswith(")"): return True
        if s.startswith("weighted(") and s.endswith(")"): return True
        if s.startswith("randr(") and s.endswith(")"): return True
        if s.startswith("rands(") and s.endswith(")"): return True
        if s.startswith("clamp(") and s.endswith(")"): return True
        if s.startswith("consume(") and s.endswith(")"): return True
        if s == "clearinv": return True
        # Assignment: var=... var+=...
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*([\+\-\*/]?=)", s): return True
        
        # Check for keyword:value patterns
        m = self.error_pattern.match(s)
        if m:
            keyword = m.group(1)
            # Only certain keywords are valid as top-level actions
            return keyword in {'add_item', 'remove_item', 'goto', 'once', 'repeat', 'set'}
        
        return False

    def highlight_line_errors(self, line: str, line_num: int):
        """Applies 'syntax_error' tags to a line for various errors."""
        stripped_line = line.strip()
        if not stripped_line or stripped_line.startswith('#'):
            return

        # --- Check 1: Too many pipe separators ---
        if line.count('|') > 3:
            self.options_text.tag_add("syntax_error", f"{line_num}.0", f"{line_num}.{len(line)}")
            return

        # --- Check 2: Unbalanced brackets/parentheses ---
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        for idx, char in enumerate(line):
            if char in pairs:
                stack.append((char, idx))
            elif char in pairs.values():
                if not stack or pairs[stack.pop()[0]] != char:
                    self.options_text.tag_add("syntax_error", f"{line_num}.{idx}", f"{line_num}.{idx+1}")
        for _, idx in stack: # Highlight unclosed opening brackets
            self.options_text.tag_add("syntax_error", f"{line_num}.{idx}", f"{line_num}.{idx+1}")

        # --- Check 3: Invalid actions in the action part ---
        parts = line.split('|')
        if len(parts) > 3:
            actions_string = parts[3]
            pipe_indices = [i for i, char in enumerate(line) if char == '|']
            if len(pipe_indices) >= 3:
                actions_start_index = pipe_indices[2] + 1
                for match in re.finditer(r'[^;&]+', actions_string):
                    action = match.group(0).strip()
                    if not action: continue
                    
                    if not self.is_valid_action(action):
                        start, end = match.span()
                        self.options_text.tag_add("syntax_error", f"{line_num}.{actions_start_index + start}", f"{line_num}.{actions_start_index + end}")

    def _configure_syntax_highlighting(self):
        self.syntax_tags = [
            "syntax_keyword", "syntax_comment", "syntax_string", "syntax_number",
            "syntax_variable", "syntax_separator", "syntax_operator", "syntax_error"
        ]
        
        # Define colors for tags from theme
        self.options_text.tag_configure("syntax_keyword", foreground=self.theme.get("syntax_keyword", "#c586c0"))
        self.options_text.tag_configure("syntax_comment", foreground=self.theme.get("syntax_comment", "#6A9955"))
        self.options_text.tag_configure("syntax_string", foreground=self.theme.get("syntax_string", "#ce9178"))
        self.options_text.tag_configure("syntax_number", foreground=self.theme.get("syntax_number", "#b5cea8"))
        self.options_text.tag_configure("syntax_variable", foreground=self.theme.get("syntax_variable", "#9cdcfe"))
        self.options_text.tag_configure("syntax_separator", foreground=self.theme.get("syntax_separator", "#d4d4d4"))
        self.options_text.tag_configure("syntax_operator", foreground=self.theme.get("syntax_operator", "#d4d4d4"))
        self.options_text.tag_configure("syntax_error", foreground=self.theme.get("syntax_error", "#f44747"), underline=True)
        
        self.known_keywords = {
            'if', 'once', 'repeat', 'chance', 'weighted', 'randr', 'rands', 'goto',
            'add_item', 'remove_item', 'clearinv', 'set', 'not_has_item', 'has_item',
            'clamp', 'consume'
        }
        
        # Patterns for highlighting. Order matters.
        self.highlight_patterns = [
            ("syntax_comment", re.compile(r'#.*')),
            ("syntax_variable", re.compile(r'\{[A-Za-z_][A-Za-z0-9_]*\}')),
            ("syntax_string", re.compile(r'"[^"]*"|\'[^\']*\'')),
            ("syntax_keyword", re.compile(r'\b(' + '|'.join(self.known_keywords) + r')\b')),
            ("syntax_number", re.compile(r'\b-?\d+(\.\d+)?\b')),
            ("syntax_separator", re.compile(r'\||>>?|[:&;]')),
            ("syntax_operator", re.compile(r'[\+\-\*/]?=')),
        ]
        
        self.error_pattern = re.compile(r'\b([a-zA-Z_]+)(?=:)\b')
        self.known_action_prefixes = {'add_item', 'remove_item', 'goto', 'once', 'repeat', 'set', 'var', 'has_item', 'not_has_item', 'weighted', 'randr', 'rands', 'clamp', 'consume'}

        # Bind events
        self.options_text.bind("<<Modified>>", self._schedule_highlight, add="+")

    def _schedule_highlight(self, event=None):
        if self.updating:
            self.options_text.edit_modified(False)
            return

        # Only proceed if the widget was actually modified.
        if self.options_text.edit_modified():
            # Reset the flag so we can catch the next modification.
            self.options_text.edit_modified(False)
            
            # Debounce the actual highlighting work.
            if self._highlight_job:
                self.after_cancel(self._highlight_job)
            self._highlight_job = self.after(150, self._highlight_syntax)

    def _highlight_syntax(self):
        if not self.options_text.winfo_exists(): return
        self._highlight_job = None
        
        for tag in self.syntax_tags:
            self.options_text.tag_remove(tag, "1.0", "end")

        for i, line in enumerate(self.options_text.get("1.0", "end-1c").splitlines()):
            line_num = i + 1
            for tag, pattern in self.highlight_patterns:
                for match in pattern.finditer(line):
                    start, end = match.span()
                    self.options_text.tag_add(tag, f"{line_num}.{start}", f"{line_num}.{end}")
            self.highlight_line_errors(line, line_num)

    def open_themecontrol(self):
        self.win = tk.Toplevel(self)
        self.win.title("Theme")
        self.win.geometry('205x500')
        self.win.winfo_x = 0
        self.win.winfo_y = 0

        tk.Label(self.win, text='Presets', font=("TkDefaultFont", 11)).pack()
        tk.Button(self.win, text='Default', command=lambda: self.themepreset('default', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Cherries', command=lambda: self.themepreset('cherries', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Ocean', command=lambda: self.themepreset('ocean', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Ocean (v2)', command=lambda: self.themepreset('ocean 2', 1)).pack(side=tk.TOP, pady=4) 
        tk.Button(self.win, text='Forest', command=lambda: self.themepreset('forest', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Bubblegum', command=lambda: self.themepreset('bubblegum', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Underground', command=lambda: self.themepreset('underground', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Sky', command=lambda: self.themepreset('sky', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Night Sky', command=lambda: self.themepreset('night sky', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Lemon', command=lambda: self.themepreset('lemon', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='90s', command=lambda: self.themepreset('90s', 1)).pack(side=tk.TOP, pady=4)

    def update_node_count(self):
        self.node_count_label.config(text=f"Nodes: {len(self.node_rects)}")

    def save_theme(self):
        try:
            with open(THEME_PATH, "w") as f:
                json.dump(self.theme, f, indent=4)
        except Exception as e:
            print("Failed to save settings:", e)      

    def load_theme(self):
        if os.path.exists(THEME_PATH):
            try:
                with open(THEME_PATH, "r") as f:
                    data = json.load(f)
                    self.theme.update(data)  
            except Exception as e:
                print("Failed to load settings:", e)    
        self.themepreset(None)
                
    def on_exit(self):
        try:
            self.close_play()   # stop play mode cleanly
        except Exception as e:
            print("close_play failed:", e)

        self.save_settings()
        self.save_theme()
        self.master.destroy()

    def update_settings(self):
        self.settings["disable_delete_confirm"] = self.delete_confirm_var.get()    
        self.settings["show_path"] = self.show_path.get()    
        self.settings["udtdnc"] = self.udtdnc.get() 
        self.settings["change_node_colors"] = self.change_node_colors.get() 
        self.settings['default_comment_w'] = self.default_comment_w.get()
        self.settings['default_comment_h'] = self.default_comment_h.get()
        #self.settings["disable_zooming"] = self.disable_zooming.get() 

    def add_node_prompt(self):
        self._apply_pending_inspector_edits()
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        x, y = self.canvas.canvasx(w / 2), self.canvas.canvasy(h / 2)        
        nid = simpledialog.askinteger("Add Node", "Node ID (int):", minvalue=1)
        if nid is None:
            return
        if nid in nodes:
            if not messagebox.askyesno("Overwrite?", f"Node {nid} exists — overwrite?"):
                return
        self.selected_node = nid

        # Color logic
        if self.settings.get('udtdnc', False) == False:
            color = '#222222'
        else:
            color = self.theme['default_node_color']

        # Create node
        nodes[nid] = {
            "x": x,
            "y": y,
            "header": f"Node {nid}",
            "options": [],
            "color": color     
        }
        #create_node(nid, f'Node {nid}', x, y, )
        self.push_undo()
        self.redraw()

    def push_undo(self):
        state = {
            "nodes": copy.deepcopy(nodes),
            "vars": vars_store.copy(),
            "inventory": inventory.copy(),
            "comments": copy.deepcopy(comments),
            "selected_node": self.selected_node,
            "selected_comment": self.selected_comment
        }
        self.undo_stack.append(state)
        self.redo_stack.clear()

    def undo(self):
        global nodes, vars_store, inventory, comments
        if not self.undo_stack:
            return
        
        # save current state to redo
        self.redo_stack.append({
            "nodes": copy.deepcopy(nodes),
            "vars": vars_store.copy(),
            "inventory": inventory.copy(),
            "comments": copy.deepcopy(comments),
            "selected_node": self.selected_node,
            "selected_comment": self.selected_comment
        })

        # restore undo state
        state = self.undo_stack.pop()
        nodes = {int(k): v for k, v in state["nodes"].items()}
        vars_store = state["vars"]
        inventory[:] = state["inventory"]
        comments = {int(k): v for k, v in state["comments"].items()}
        self.selected_node = state["selected_node"]
        self.selected_comment = state["selected_comment"]

        self.redraw()

    def redo(self):
        global nodes, vars_store, inventory, comments
        if not self.redo_stack:
            return
        
        # save current state to undo
        self.undo_stack.append({
            "nodes": copy.deepcopy(nodes),
            "vars": vars_store.copy(),
            "inventory": inventory.copy(),
            "comments": copy.deepcopy(comments),
            "selected_node": self.selected_node,
            "selected_comment": self.selected_comment
        })

        # restore redo state
        state = self.redo_stack.pop()
        nodes = {int(k): v for k, v in state["nodes"].items()}
        vars_store = state["vars"]
        inventory[:] = state["inventory"]
        comments = {int(k): v for k, v in state["comments"].items()}
        self.selected_node = state["selected_node"]
        self.selected_comment = state["selected_comment"]

        self.redraw()

    def center_canvas_on(self, cx, cy):
        # ensure geometry & items are up to date
        self.canvas.update_idletasks()

        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        bbox = self.canvas.bbox("all")
        if not bbox:
            return

        left, top, right, bottom = bbox
        total_w = right - left
        total_h = bottom - top

        # make sure scrollregion matches actual content bbox so fractions are computed consistently
        try:
            # configure accepts a tuple fine
            self.canvas.configure(scrollregion=(left, top, right, bottom))
        except Exception:
            # ignore if configure fails for some reason
            pass

        # target top-left of view so (cx,cy) becomes centered
        target_left = cx - (canvas_w / 2)
        target_top  = cy - (canvas_h / 2)

        # compute maximum scrollable offset (in canvas coords)
        max_x = max(0.0, total_w - canvas_w)
        max_y = max(0.0, total_h - canvas_h)

        # convert target_left/top into a fraction [0..1] relative to bbox left/top
        if max_x > 0.0:
            frac_x = (target_left - left) / max_x
        else:
            frac_x = 0.0

        if max_y > 0.0:
            frac_y = (target_top - top) / max_y
        else:
            frac_y = 0.0

        # clamp
        frac_x = max(0.0, min(1.0, frac_x))
        frac_y = max(0.0, min(1.0, frac_y))

        self.canvas.xview_moveto(frac_x)
        self.canvas.yview_moveto(frac_y)

    def search_node(self, event=None):
        self._apply_pending_inspector_edits()
        nid_str = self.search_var.get().strip()
        if not nid_str.isdigit():
            return
        nid = int(nid_str)
        if nid not in nodes:
            return

        # select & show in inspector
        self.selected_node = nid
        self.load_selected_into_inspector()
        # redraw so the node rect/text exist with correct coords
        self.redraw()

        # make sure canvas geometry is ready
        self.canvas.update_idletasks()

        node = nodes[nid]
        # nodes store top-left x,y — center on node center
        cx = node.get("x", 50) + (NODE_W / 2)
        cy = node.get("y", 50) + (NODE_H / 2)

        # center (this will also set scrollregion to bbox("all") internally)
        self.center_canvas_on(cx, cy)

        # optional: flash a highlight rectangle so it's obvious which node was found
        try:
            hl = self.canvas.create_rectangle(
                node.get("x",50), node.get("y",50),
                node.get("x",50) + NODE_W, node.get("y",50) + NODE_H,
                outline=self.theme.get('node_selected_outline', '#00ff00'),
                width=3, tags=("search_highlight",)
            )
            self.canvas.after(800, lambda: self.canvas.delete(hl))
        except Exception:
            pass

    def multi_select_start(self, event): # start multi-selection.
        self.multi_select_start_pos = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.multi_selected_nodes.clear()
        if self.multi_select_rect:
            self.canvas.delete(self.multi_select_rect)
        self.multi_select_rect = self.canvas.create_rectangle(
            *self.multi_select_start_pos, *self.multi_select_start_pos,
            outline="#ffcc00", dash=(3,3)
        )

    def multi_select_drag(self, event): # start multi-selection drag (move)
        x0, y0 = self.multi_select_start_pos
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.multi_select_rect, x0, y0, x1, y1)

    def multi_select_end(self, event): # end multi-selection
        x0, y0 = self.multi_select_start_pos
        x1, y1 = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0

        self.multi_selected_nodes.clear()
        for nid, data in nodes.items():
            nx, ny = data["x"], data["y"]
            if (nx + NODE_W >= x0 and nx <= x1) and (ny + NODE_H >= y0 and ny <= y1):
                self.multi_selected_nodes.add(nid)

        if self.multi_select_rect:
            self.canvas.delete(self.multi_select_rect)
            self.multi_select_rect = None

        self.redraw()

    def enter_disconnect_mode(self, nid): # opposite of 'enter_connection_mode()'.
        self.disconnect_source = nid
        self.mode = "disconnect"
        self.canvas.config(cursor="X_cursor")  
        
    def node_right_click(self, event): # this is called when you right-click a node
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked = self.canvas.find_overlapping(cx, cy, cx, cy)
        clicked_node = None
        for item in clicked:
            for t in self.canvas.gettags(item):
                if t.isdigit():
                    clicked_node = int(t)
                    break
            if clicked_node:
                break

        if clicked_node is None:
            return "break"  

        
        if clicked_node not in self.multi_selected_nodes:
            self.selected_node = clicked_node
            self.multi_selected_nodes.clear()
        else:
            self.selected_node = None

        
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Duplicate", command=self.duplicate_multi_nodes)
        menu.add_command(label="Connect", command=lambda: self.enter_connection_mode(clicked_node))
        menu.add_command(label="Disconnect", command=lambda: self.enter_disconnect_mode(clicked_node))
        menu.add_command(label="Delete", command=self.delete_multi_nodes)

        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def comment_right_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        clicked = self.canvas.find_overlapping(cx, cy, cx, cy)
        clicked_comment = None

        for item in clicked:
            for t in self.canvas.gettags(item):
                if t.startswith("comment"):
                    # tags look like ("comment", "3"), so grab second tag
                    for tag in self.canvas.gettags(item):
                        if tag.isdigit():
                            clicked_comment = int(tag)
                            break
            if clicked_comment is not None:
                break

        if clicked_comment is None:
            return "break"

        self.selected_comment = clicked_comment

        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Delete", command=lambda: self.delete_comment(clicked_comment))

        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def background_right_click(self, event): # this is called when you right-click the background.
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        clicked = self.canvas.find_overlapping(cx, cy, cx, cy)
        for item in clicked:
            if any(t.isdigit() for t in self.canvas.gettags(item)):
                return "break"  

        self.bg_menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def delete_comment(self, cid):
        if cid not in comments:
            return
        # clear handles, canvas items, and stored refs
        self.clear_comment_handles(cid)
        if hasattr(self, "comment_rects") and cid in self.comment_rects:
            try: self.canvas.delete(self.comment_rects[cid])
            except: pass
            del self.comment_rects[cid]
        if hasattr(self, "comment_texts") and cid in self.comment_texts:
            try: self.canvas.delete(self.comment_texts[cid])
            except: pass
            del self.comment_texts[cid]
        # finally remove from the dict
        del comments[cid]
        if self.selected_comment == cid:
            self.selected_comment = None

    def delete_multi_nodes(self): # delete multiple nodes, happens when multi-selecting nodes.
        self.push_undo() # Added for undo functionality
        targets = self.multi_selected_nodes if self.multi_selected_nodes else {self.selected_node}
        if not targets:
            return
        if not self.settings.get("disable_delete_confirm", False):
            if not messagebox.askyesno("Delete", f"Delete {len(targets)} node(s)?"):
                return
        for nid in targets:
            # Delete from the global nodes dictionary
            if nid in nodes:
                del nodes[nid]
            # Delete associated canvas items immediately to prevent visual glitches
            if nid in self.node_rects:
                self.canvas.delete(self.node_rects[nid])
                del self.node_rects[nid]
            if nid in self.node_texts:
                self.canvas.delete(self.node_texts[nid])
                del self.node_texts[nid]
            if nid in self.node_base_fonts:
                del self.node_base_fonts[nid]

        self.selected_node = None
        self.multi_selected_nodes.clear() # Ensure this is cleared
        self.redraw()
        self.clear_inspector()
        self.update_node_count()

    def clear_all_saves(self): # clears all saves in the save path (by default [the save path is]: ./saves/)
        import shutil
        from tkinter import messagebox

        if not os.path.exists("./saves"):
            messagebox.showinfo("No saves", "The ./saves/ folder does not exist.")
            return

        if messagebox.askyesno("Dangerous!", "This will delete EVERYTHING in ./saves/. Are you sure?"):
            try:
                shutil.rmtree("./saves")
                os.makedirs("./saves", exist_ok=True)
                messagebox.showinfo("Cleared", "All saves have been deleted.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear saves: {e}")

    def load_settings(self): # load settings at settings path. (default settings path is: ./settings.json)
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, "r") as f:
                    data = json.load(f)
                    self.settings.update(data)  
            except Exception as e:
                print("Failed to load settings:", e)

    def save_settings(self): # save self.settings 
        try:
            with open(SETTINGS_PATH, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print("Failed to save settings:", e)

    def duplicate_multi_nodes(self): # duplicate multiple nodes at once, happens when you're multi-selecting
        self._apply_pending_inspector_edits()
        targets = self.multi_selected_nodes if self.multi_selected_nodes else {self.selected_node}
        new_ids = []
        for nid in targets:
            new_id = max(nodes.keys(), default=0) + 1
            data = nodes[nid].copy()
            data["x"] += 20; data["y"] += 20
            nodes[new_id] = data
            new_ids.append(new_id)
        self.selected_node = new_ids[0] if new_ids else None
        self.multi_selected_nodes.clear()
        self.redraw()

    def duplicate_node(self, nid): # duplicate a node
        new_id = max(nodes.keys()) + 1
        data = nodes[nid].copy()
        data["x"] += 20; data["y"] += 20  
        nodes[new_id] = data
        self.redraw()

    def enter_connection_mode(self, nid): # enter 'connection' mode (clicking a node will connect the original selected node to that [node])
        self.connection_source = nid
        self.mode = "connect"  
        self.canvas.config(cursor="cross")

    def canvas_zoom(self, event): # do 'zoom'
        if self.settings['disable_zooming'] == False:
            x = self.canvas.canvasx(event.x)
            y = self.canvas.canvasy(event.y)
            factor = 1.1 if event.delta > 0 else 0.9
            self.current_zoom *= factor

            
            self.canvas.scale("all", x, y, factor, factor)
            #self.canvas.configure(scrollregion=self.canvas.bbox("all"))

            
            for nid, txt_id in self.node_texts.items():
                font_obj = self.node_base_fonts[nid]
                new_size = max(6, int(BASE_FONT_SIZE * self.current_zoom))
                font_obj.configure(size=new_size)
                
                if self.current_zoom < 0.6:
                    self.canvas.itemconfig(txt_id, text=str(nid))
                else:
                    header = nodes[nid].get("header", "")
                    self.canvas.itemconfig(txt_id, text=f"{nid}: {header}")
        else:
            pass
            #self.reset_zoom() 

    def reset_zoom(self): # resets zoom.
        #if self.settings['disable_zoom'] == False: 
        factor = 1.0 / self.current_zoom
        self.current_zoom = 1.0
        cx = self.canvas.canvasx(self.canvas.winfo_width() / 2)
        cy = self.canvas.canvasy(self.canvas.winfo_height() / 2)
        self.canvas.scale("all", cx, cy, factor, factor)
        #self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        for nid, font_obj in self.node_base_fonts.items():
            font_obj.configure(size=BASE_FONT_SIZE)  
        for nid, txt_id in self.node_texts.items():
            header = nodes[nid].get("header", "")
            self.canvas.itemconfig(txt_id, text=f"{nid}: {header}")
    
    def apply_preset_color(self, color: str): # apply preset color (in the inspector there's "Preset Colors".)
        targets = self.multi_selected_nodes if self.multi_selected_nodes else {self.selected_node}
        for nid in targets:
            if nid is not None:
                nodes[nid]["color"] = color
        self.redraw()

    def pick_node_color(self): # picks the node color
        if self.selected_node is None:
            return
        node = nodes[self.selected_node]
        color = colorchooser.askcolor(color=node.get("color","#222222"))[1]  
        if color:
            node["color"] = color
            self.redraw()

    def start_pan(self, event): # start panning
        self.canvas.scan_mark(event.x, event.y)

    def do_pan(self, event): # do panning
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def delete_selected_node(self): # delete the selected node
        if self.selected_node is None:
            #messagebox.showinfo("No node", "Select a node first.")
            return
        
        if not self.settings.get("disable_delete_confirm", False):
            if not messagebox.askyesno("Delete node", f"Delete node {self.selected_node}?"):
                return

        delete_node(self.selected_node)
        self.selected_node = None
        self.redraw()
        self.clear_inspector()
        self.update_node_count()        

    def set_start_node(self): # set a node as the start node (the start node is the first node that appears in Play Mode)
        global START_NODE
        if self.selected_node is not None:
            START_NODE = self.selected_node
            #messagebox.showinfo("Start node", f"Start node set to {START_NODE}")
    
    def _apply_pending_inspector_edits(self):
        """Saves any text currently in the inspector to the selected object without redrawing."""
        if self.updating: return
        
        if self.selected_node is not None:
            self.apply_edits(redraw_canvas=False)
        elif self.selected_comment is not None:
            self.apply_comment_edits(redraw_canvas=False)

    def apply_edits(self, redraw_canvas=True): # apply edits for options_text and header_text
        if self.selected_node is None:
            return
        
        if self.selected_node not in nodes:
            return

        header = self.header_text.get("1.0", tk.END).strip()
        opts_text = self.options_text.get("1.0", tk.END).strip()
        
        nodes[self.selected_node]["raw_options"] = opts_text # Store raw text to preserve comments

        opts_raw = opts_text.splitlines()
        opts = []
        for line in opts_raw:
            parsed = parse_option_line(line)
            if parsed:
                opts.append(parsed)

        nodes[self.selected_node]["header"] = header
        nodes[self.selected_node]["options"] = opts
        if redraw_canvas:
            self.redraw()

    def apply_vars_text(self): # apply edits for vars_list
        raw = self.vars_list.get("1.0", tk.END).strip().splitlines()
        vars_store.clear(); inventory.clear()
        for line in raw:
            line = line.strip()
            if not line: continue
            if line.startswith("inv:"):
                name = line.split(":",1)[1].strip()
                if name: inventory.append(name)
            else:
                
                if "=" in line:
                    name, val = line.split("=",1)
                    name=name.strip(); val=val.strip()
                    if val.lower()=="true":
                        parsed=True
                    elif val.lower()=="false":
                        parsed=False
                    else:
                        try:
                            parsed=int(val)
                        except Exception:
                            try:
                                parsed=float(val)
                            except Exception:
                                parsed = val.strip('"').strip("'")
                    vars_store[name]=parsed
        #messagebox.showinfo("Vars", "Vars & inventory applied.")

    def quick_add_node(self, event=None, x=None, y=None):  
        self._apply_pending_inspector_edits()
        self.push_undo()

        # Find the lowest available node ID
        new_id = 1
        while new_id in nodes:
            new_id += 1

        # Cursor position if event is provided
        if event is not None:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        else:
            # Fallback: center of canvas
            if x is None or y is None:
                w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
                x, y = self.canvas.canvasx(w / 2), self.canvas.canvasy(h / 2)

        # Color logic
        if self.settings.get('udtdnc', False) == False:
            color = '#222222'
        else:
            color = self.theme['default_node_color']

        # Create node
        nodes[new_id] = {
            "x": x,
            "y": y,
            "header": f"Node {new_id}",
            "options": [],
            "color": color     
        }

        self.selected_node = new_id
        self.load_selected_into_inspector()
        self.redraw()
        self.update_node_count()

    def truncate_text_to_fit(self, text, font, max_w, max_h):
        if self.settings.get('disable_text_truncation', False):
            return text

        linespace = font.metrics("linespace")
        max_lines = max(1, int(max_h / linespace))
        
        final_lines = []
        truncated = False

        paragraphs = text.split('\n')
        for paragraph in paragraphs:
            if len(final_lines) >= max_lines:
                truncated = True
                break

            words = paragraph.split(' ')
            current_line = ""
            
            for word in words:
                if not word:
                    continue

                # If the word itself is too long, it must be broken down.
                if font.measure(word) > max_w:
                    # Finish the current line before dealing with the long word
                    if current_line:
                        if len(final_lines) < max_lines:
                            final_lines.append(current_line)
                        else:
                            truncated = True; break
                    current_line = "" # Reset for after the long word

                    # Break the long word into fitting parts
                    temp_word = word
                    while temp_word:
                        if len(final_lines) >= max_lines:
                            truncated = True; break
                        
                        split_idx = len(temp_word)
                        for i in range(1, len(temp_word) + 1):
                            if font.measure(temp_word[:i]) > max_w:
                                split_idx = i - 1
                                break
                        
                        split_idx = max(1, split_idx)
                        final_lines.append(temp_word[:split_idx])
                        temp_word = temp_word[split_idx:]
                    if truncated: break
                    continue # The long word is fully processed, move to the next word

                # Normal word wrapping
                test_line = (current_line + " " + word).strip() if current_line else word
                if font.measure(test_line) <= max_w:
                    current_line = test_line
                else:
                    if len(final_lines) < max_lines:
                        final_lines.append(current_line)
                        current_line = word
                    else:
                        truncated = True; break
            
            if truncated: break

            # Add the last line of the paragraph
            if current_line:
                if len(final_lines) < max_lines:
                    final_lines.append(current_line)
                else:
                    truncated = True

        # Final truncation and ellipsis logic
        if len(final_lines) > max_lines:
            final_lines = final_lines[:max_lines]
            truncated = True
        
        if truncated and final_lines:
            last_line = final_lines[-1]
            
            if not last_line.endswith("..."):
                while font.measure(last_line + "...") > max_w and last_line:
                    last_line = last_line[:-1]
                final_lines[-1] = (last_line + "...") if last_line else "..."

        return "\n".join(final_lines)

    def clear_comment_handles(self, cid):
        data = comments.get(cid)
        if not data:
            return
        handles = data.get("handles") or {}
        for hid in list(handles.values()):
            try:
                self.canvas.delete(hid)
            except Exception:
                pass
        data["handles"] = {}

    def redraw(self):
        # Clear all existing edges
        for item in self.edge_items:
            self.canvas.delete(item)
        self.edge_items.clear()

        # Clear all existing node rectangles and texts, then re-create only for existing nodes
        for nid in list(self.node_rects.keys()): # Iterate over a copy of keys to allow modification
            if nid not in nodes:
                self.canvas.delete(self.node_rects.pop(nid, None))
                self.canvas.delete(self.node_texts.pop(nid, None))
                self.node_base_fonts.pop(nid, None)

        # --- Update or create nodes ---
        for nid, data in nodes.items():
            x = data.get("x", 50)
            y = data.get("y", 50)
            node_color = data.get("color") or self.theme.get('default_node_color', '#222222')

            # Node rectangle
            if nid in self.node_rects:
                self.canvas.coords(self.node_rects[nid], x, y, x + NODE_W, y + NODE_H)
                self.canvas.itemconfig(self.node_rects[nid], fill=node_color)
            else:
                rect = self.canvas.create_rectangle(
                    x, y, x + NODE_W, y + NODE_H,
                    fill=node_color, outline=self.theme['node_outline'], width=2,
                    tags=("node", str(nid))
                )
                self.node_rects[nid] = rect

            # Node text
            font_obj = self.node_base_fonts.get(nid) or tkFont.Font(family="TkDefaultFont", size=11)
            self.node_base_fonts[nid] = font_obj
            full_text = f"{nid}: {data.get('header','')}"
            display_text = self.truncate_text_to_fit(full_text, font_obj, NODE_W-12, NODE_H-4)

            if nid in self.node_texts:
                self.canvas.itemconfig(self.node_texts[nid], text=display_text, fill=self.theme['node_text_fill'])
                self.canvas.coords(self.node_texts[nid], x + 10, y + 10)
            else:
                txt = self.canvas.create_text(
                    x + 10, y + 10, anchor="nw",
                    text=display_text,
                    fill=self.theme['node_text_fill'],
                    width=NODE_W - 12,
                    font=font_obj,
                    tags=("node_text", str(nid))
                )
                self.node_texts[nid] = txt

            # Selection outlines
            if nid == self.selected_node:
                self.canvas.itemconfig(self.node_rects[nid], outline=self.theme['node_selected_outline'], width=3)
            elif nid in self.multi_selected_nodes:
                self.canvas.itemconfig(self.node_rects[nid], outline=self.theme['multi_selected_outline'], width=3)
            else:
                self.canvas.itemconfig(self.node_rects[nid], outline=self.theme['node_outline'], width=2)

        # --- Update edges ---
        # (The clearing of old edges is moved to the beginning of the function)
        seen_edges = set()
        COLOR1 = self.theme.get('from_lines', '#00ced1')
        COLOR2 = self.theme.get('to_lines', '#ffa500')
        RANDOM_EDGE_COLOR = self.theme.get('randomEdgeFromColor', '#8e44ff')

        for nid, data in nodes.items():
            x1 = data.get("x", 50) + NODE_W // 2
            y1 = data.get("y", 50) + NODE_H // 2
            for opt in data.get("options", []):
                nxt_raw = opt.get("next")
                if not nxt_raw:
                    continue
                is_multi_choice = isinstance(nxt_raw, str) and "/" in nxt_raw
                next_nodes = []

                if isinstance(nxt_raw, str) and "/" in nxt_raw:
                    for part in nxt_raw.split("/"):
                        try:
                            next_nodes.append(int(part.strip()))
                        except:
                            val = vars_store.get(part.strip())
                            if val is not None:
                                try: next_nodes.append(int(val))
                                except: pass
                else:
                    try:
                        next_nodes.append(int(nxt_raw))
                    except:
                        val = vars_store.get(nxt_raw)
                        if val is not None:
                            try: next_nodes.append(int(val))
                            except: pass

                for tgt in next_nodes:
                    if tgt not in nodes or (nid, tgt) in seen_edges:
                        continue
                    x2 = nodes[tgt].get("x", 50) + NODE_W // 2
                    y2 = nodes[tgt].get("y", 50) + NODE_H // 2

                    reverse_exists = False
                    for ropt in nodes[tgt].get("options", []):
                        rnext = ropt.get("next")
                        if rnext is None: continue
                        if isinstance(rnext, str) and "/" in rnext:
                            if str(nid) in [p.strip() for p in rnext.split("/")]:
                                reverse_exists = True
                                break
                        else:
                            if str(nid) == str(rnext):
                                reverse_exists = True
                                break

                    from_color = RANDOM_EDGE_COLOR if is_multi_choice else COLOR1
                    if reverse_exists:
                        line = self.canvas.create_line(x1, y1, x2, y2, width=3, fill=from_color, smooth=True)
                        self.edge_items.append(line)
                        self.canvas.tag_lower(line)
                        seen_edges.add((nid, tgt))
                        seen_edges.add((tgt, nid))
                    else:
                        mid_x = (x1 + x2) / 2
                        mid_y = (y1 + y2) / 2
                        line1 = self.canvas.create_line(x1, y1, mid_x, mid_y, width=3, fill=from_color, smooth=True)
                        line2 = self.canvas.create_line(mid_x, mid_y, x2, y2, width=3, fill=COLOR2, smooth=True, arrow=tk.LAST)
                        self.edge_items.extend([line1, line2])
                        self.canvas.tag_lower(line1)
                        self.canvas.tag_lower(line2)
                        seen_edges.add((nid, tgt))

        # --- Update comments ---

        # Clear stale handles from previous frame so they don't accumulate
        for cid in list(comments.keys()):
            self.clear_comment_handles(cid)

        # Clear canvas items for comments that no longer exist
        for cid_item in list(self.comment_rects.keys()):
            if cid_item not in comments:
                self.canvas.delete(self.comment_rects.pop(cid_item, None))
                self.canvas.delete(self.comment_texts.pop(cid_item, None))

        # --- Update comments ---
        for cid, data in comments.items():
            x, y = data["x"], data["y"]
            w, h = max(30, data.get("w", COMMENT_W)), max(20, data.get("h", COMMENT_H))
            data["w"], data["h"] = w, h

            # Rectangle (reuse if exists)
            if cid in getattr(self, "comment_rects", {}):
                self.canvas.coords(self.comment_rects[cid], x, y, x + w, y + h)
            else:
                if not hasattr(self, "comment_rects"):
                    self.comment_rects = {}
                rect_id = self.canvas.create_rectangle(
                    x, y, x + w, y + h,
                    fill="#FFA500", outline="#FFCC66", width=2,
                    tags=("comment", str(cid))
                )
                self.comment_rects[cid] = rect_id

            # Text (truncated)
            font_obj = tkFont.Font(family="Arial", size=10)
            display_text = self.truncate_text_to_fit(data.get("text",""), font_obj, w-10, h-10)

            if cid in getattr(self, "comment_texts", {}):
                self.canvas.itemconfig(self.comment_texts[cid], text=display_text)
                self.canvas.coords(self.comment_texts[cid], x + 5, y + 5)
            else:
                if not hasattr(self, "comment_texts"):
                    self.comment_texts = {}
                text_id = self.canvas.create_text(
                    x + 5, y + 5, anchor="nw", text=display_text,
                    font=font_obj, width=w-10, fill="#333333",
                    tags=("comment_text", str(cid))
                )
                self.comment_texts[cid] = text_id

            # Create handles only for the selected comment
            if cid == self.selected_comment:
                handles = {}
                # Handles are created relative to the comment's current position and size
                handles["nw"] = self.canvas.create_rectangle(x-HANDLE_SIZE, y-HANDLE_SIZE, x+HANDLE_SIZE, y+HANDLE_SIZE, fill="#222", tags=(f"handle_{cid}", "nw"))
                handles["ne"] = self.canvas.create_rectangle(x+w-HANDLE_SIZE, y-HANDLE_SIZE, x+w+HANDLE_SIZE, y+HANDLE_SIZE, fill="#222", tags=(f"handle_{cid}", "ne"))
                handles["sw"] = self.canvas.create_rectangle(x-HANDLE_SIZE, y+h-HANDLE_SIZE, x+HANDLE_SIZE, y+h+HANDLE_SIZE, fill="#222", tags=(f"handle_{cid}", "sw"))
                handles["se"] = self.canvas.create_rectangle(x+w-HANDLE_SIZE, y+h-HANDLE_SIZE, x+w+HANDLE_SIZE, y+h+HANDLE_SIZE, fill="#222", tags=(f"handle_{cid}", "se"))
                data["handles"] = handles
            else:
                # ensure no handles stored for unselected comments
                data["handles"] = {}

    def select_comment(self, event): # selects a comment
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        for cid, data in comments.items():
            w, h = data.get("w", COMMENT_W), data.get("h", COMMENT_H)
            if data["x"] <= x <= data["x"] + w and data["y"] <= y <= data["y"] + h:
                self.selected_comment = cid
                self.load_comment_into_inspector()
                break

    def load_comment_into_inspector(self):
        if self.selected_comment is None: 
            return
        comment = comments[self.selected_comment]
        self.header_text.delete("1.0", tk.END)
        self.header_text.insert(tk.END, comment["text"])

    def apply_comment_edits(self, redraw_canvas=True): # apply comment edits to the comment
        if self.selected_comment is None: return
        comments[self.selected_comment]["text"] = self.header_text.get("1.0", tk.END).strip()
        if redraw_canvas:
            self.redraw()

    def get_node_at(self, x, y): # gets node at (usually at mouse)
        scale = self.current_zoom
        for nid, data in nodes.items():
            nx, ny = data.get("x", 50) * scale, data.get("y", 50) * scale
            if nx <= x <= nx + NODE_W * scale and ny <= y <= ny + NODE_H * scale:
                return nid
        return None

    def start_resize(self, event): # start resizing (comment)
        self.resizing_comment = None
        self.resize_dir = None

        # convert mouse coords to canvas coords
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Check if clicked on handle
        clicked = self.canvas.find_overlapping(x, y, x, y)
        for item in clicked:
            for t in self.canvas.gettags(item):
                if t.startswith("handle_"):
                    self.resizing_comment = int(t.split("_")[1])
                    for dir_tag in ("nw","ne","sw","se"):
                        if dir_tag in self.canvas.gettags(item):
                            self.resize_dir = dir_tag
                            break

        if self.resizing_comment:
            self.resize_start = (x, y)  # canvas coords
            comment = comments[self.resizing_comment]
            self.orig_pos = (comment["x"], comment["y"], comment["w"], comment["h"])

    def do_resize(self, event): # do resizing (comment)
        if not self.resizing_comment: return

        # convert mouse coords to canvas coords
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        dx = x - self.resize_start[0]
        dy = y - self.resize_start[1]

        cid = self.resizing_comment
        x0, y0, w, h = self.orig_pos
        comment = comments[cid]

        if "nw" in self.resize_dir:
            new_w = max(w - dx, MIN_W)
            new_h = max(h - dy, MIN_H)
            comment["x"] = x0 + (w - new_w)
            comment["y"] = y0 + (h - new_h)
            comment["w"] = new_w
            comment["h"] = new_h
        elif "ne" in self.resize_dir:
            new_w = max(w + dx, MIN_W)
            new_h = max(h - dy, MIN_H)
            comment["y"] = y0 + (h - new_h)
            comment["w"] = new_w
            comment["h"] = new_h
        elif "sw" in self.resize_dir:
            new_w = max(w - dx, MIN_W)
            new_h = max(h + dy, MIN_H)
            comment["x"] = x0 + (w - new_w)
            comment["w"] = new_w
            comment["h"] = new_h
        elif "se" in self.resize_dir:
            new_w = max(w + dx, MIN_W)
            new_h = max(h + dy, MIN_H)
            comment["w"] = new_w
            comment["h"] = new_h

        self.redraw()

    def stop_resize(self, event): # stop resizing (comment)
        self.resizing_comment = None
        self.resize_dir = None

    def canvas_mouse_down(self, event): # called on mouse_down
        self._apply_pending_inspector_edits()
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        clicked_node = self.get_node_at(cx, cy)

        self.selected_comment = None
        self.dragging_comment = False
        
        # Check if clicked on a comment
        for cid, c in comments.items():
            if c["x"] <= cx <= c.get("x", 0) + c.get("w", 150) and c["y"] <= cy <= c.get("y", 0) + c.get("h", 50):
                self.selected_comment = cid
                self.dragging_comment = True
                self.comment_offset = (cx - c["x"], cy - c["y"])
                self.selected_node = None        # deselect any node
                self.multi_selected_nodes.clear()  # clear multi-selection
                self.load_comment_into_inspector()
                self.redraw()
                return

        if getattr(self, "mode", None) == "disconnect" and hasattr(self, "disconnect_source"):
            if clicked_node is not None and clicked_node != self.disconnect_source:
                src_opts = nodes[self.disconnect_source]["options"]
                self.push_undo()  
                nodes[self.disconnect_source]["options"] = [
                    o for o in src_opts if resolve_next(o.get("next")) != clicked_node
                ]
                self.redraw()
                self.load_selected_into_inspector()
            self.mode = "editor"
            self.disconnect_source = None
            self.canvas.config(cursor="")
            return
        
        if getattr(self, "mode", None) == "connect" and hasattr(self, "connection_source"):
            source = self.connection_source
            target = clicked_node
            if target is not None and target != source:
                self.push_undo()  
                nodes[source]["options"].append({
                    "text": "Placeholder",
                    "next": str(target),
                    "condition": "",
                    "actions": []
                })
                self.selected_node = source
                self.load_selected_into_inspector()
                self.redraw()
            self.mode = "editor"
            self.connection_source = None
            self.canvas.config(cursor="")
            return

        if clicked_node:
            self.selected_node = clicked_node
            self.dragging = True

            if clicked_node in self.multi_selected_nodes:
                
                self.dragging_multi = True
                self.drag_offsets_multi = {
                    nid: (cx - nodes[nid]["x"], cy - nodes[nid]["y"])
                    for nid in self.multi_selected_nodes
                }
            else:
                
                self.dragging_multi = False
                node_x, node_y = nodes[clicked_node].get("x", 50), nodes[clicked_node].get("y", 50)
                self.drag_offset = (cx - node_x, cy - node_y)
                self.multi_selected_nodes.clear()
            self.push_undo()
            self.load_selected_into_inspector()
            self.redraw()
        else:
            self.selected_node = None
            self.selected_comment = None
            self.multi_selected_nodes.clear()
            self.dragging_multi = False
            self.clear_inspector(True)
            self.redraw()

    def on_close(self):
        try:
            self.close_play()   # cleanup play mode
        except Exception:
            pass
        self.destroy()          # actually close the main window

    def add_comment(self, text="New comment", event=None, x=None, y=None):  
        self.push_undo()
        global comments

        # Cursor position if event is provided
        if event is not None:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        else:
            # Fallback: center of canvas
            if x is None or y is None:
                w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
                x, y = self.canvas.canvasx(w / 2), self.canvas.canvasy(h / 2)

        cid = max(comments.keys(), default=0) + 1
        width = self.settings.get('default_comment_w', COMMENT_W)
        height = self.settings.get('default_comment_h', COMMENT_H)
        comments[cid] = {
            "text": text,
            "x": x,
            "y": y,
            "w": width,
            "h": height
        }
        self.selected_comment = cid
        self.redraw()

    def start_comment_action(self, event): # start comment action
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        clicked = self.canvas.find_overlapping(x, y, x, y)
        self.active_comment = None
        self.resizing_comment = None

        for item in clicked:
            tags = self.canvas.gettags(item)
            for t in tags:
                if t.startswith("handle_"):
                    self.resizing_comment = int(t.split("_")[1])
                    for dir_tag in ("nw","ne","sw","se"):
                        if dir_tag in tags:
                            self.resize_dir = dir_tag
                            break
                    break
                elif t.startswith("comment"):
                    self.active_comment = int(t[7:])  # 'comment' + id
                    self.move_start = (x, y)
                    c = comments[self.active_comment]
                    self.orig_pos = (c["x"], c["y"])
                    break
            if self.active_comment or self.resizing_comment:
                break

    def canvas_mouse_move(self, event): # called on mouse_move
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        scale = self.current_zoom

        # comment drag first
        if getattr(self, "dragging_comment", False) and self.selected_comment is not None:
            if getattr(self, "resizing_comment", None) is None:  # only drag if NOT resizing
                ox, oy = self.comment_offset
                comments[self.selected_comment]["x"] = cx - ox
                comments[self.selected_comment]["y"] = cy - oy
                self.redraw()
            return

        if not getattr(self, "dragging", False) or (self.selected_node is None and not self.dragging_multi):
            return

        if getattr(self, "dragging_multi", False):
            for nid, (ox, oy) in self.drag_offsets_multi.items():
                nodes[nid]["x"] = int((cx - ox) / scale)
                nodes[nid]["y"] = int((cy - oy) / scale)
        elif self.selected_node is not None:
            ox, oy = self.drag_offset
            nodes[self.selected_node]["x"] = int((cx - ox) / scale)
            nodes[self.selected_node]["y"] = int((cy - oy) / scale)

        self.redraw()

    def canvas_mouse_up(self, event): # called on mouse_up
        self.dragging_comment = False
        self.dragging = False

    def load_selected_into_inspector(self): # load selected node into inspector
        if self.selected_node is None:
            return
        data = nodes.get(self.selected_node)
        if not data:
            return
        self.id_label.config(text=f"ID: {self.selected_node}")
        self.header_text.delete("1.0", tk.END); self.header_text.insert(tk.END, data.get("header",""))
        self.options_text.delete("1.0", tk.END)
        # If raw_options exists, use it to preserve comments. Otherwise, format from parsed options.
        if "raw_options" in data:
            self.options_text.insert(tk.END, data.get("raw_options", ""))
        else:
            for opt in data.get("options",[]):
                self.options_text.insert(tk.END, format_option_line(opt) + "\n")
        
        self._schedule_highlight()
        
        self.vars_list.delete("1.0", tk.END)
        for k,v in vars_store.items():
            self.vars_list.insert(tk.END, f"{k}={v}\n")
        if inventory:
            for it in inventory:
                self.vars_list.insert(tk.END, f"inv:{it}\n")

    def clear_inspector(self, keepVarsList: bool=False): # clear inspector (keepVarsList is usually True)
        self.id_label.config(text="ID: -")
        self.header_text.delete("1.0", tk.END)
        self.options_text.delete("1.0", tk.END)
        self._schedule_highlight()
        if keepVarsList == False:
            self.vars_list.delete("1.0", tk.END)

    def save_story_dialog(self): # save story 
        os.makedirs("./saves", exist_ok=True)
        save_name = simpledialog.askstring("Save Name", "Enter save name:", initialvalue="my_story")
        if not save_name:
            return
        path = f"./saves/{save_name}.json"
        if os.path.exists(path):
            if not messagebox.askyesno("Overwrite?", f"{save_name}.json already exists. Overwrite?"):
                return
        payload = {"nodes": nodes, "vars": vars_store, "inventory": inventory, "start": START_NODE}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        messagebox.showinfo("Saved", f"Saved to {path}")

    def load_story_dialog(self): # load story
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path:
            return
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        
        global nodes, vars_store, inventory, START_NODE
        nodes = {int(k): v for k,v in payload.get("nodes",{}).items()}
        vars_store = payload.get("vars", {})
        inventory[:] = payload.get("inventory", [])
        START_NODE = payload.get("start", START_NODE)
        
        for nid, v in nodes.items():
            v.setdefault("x", 50 + (nid%5)*60)
            v.setdefault("y", 50 + (nid%7)*40)
            v.setdefault("options", v.get("options", []))
        messagebox.showinfo("Loaded", f"Loaded {path}")
        self.selected_node = None
        self.redraw()
        self.update_node_count()
        self.selected_node = 1
        self.load_selected_into_inspector()

    def toggle_mode(self): # toggle mode (play>editor, editor>play)
        if self.mode == "editor":
            self.enter_play_mode()
        else:
            self.enter_editor_mode()

    def enter_play_mode(self): # enter play mode
        # Backup the editor's variable state before starting play mode
        self._apply_pending_inspector_edits() # Ensure globals are up-to-date with UI
        self.editor_vars_backup = copy.deepcopy(vars_store)
        self.editor_inventory_backup = inventory.copy()

        self.mode = "play"
        self.mode_button.config(text="Switch to Editor Mode")
        self.reset_state()
        self.play_window = tk.Toplevel(self.master)
        self.play_window.title("Play Mode")
        self.play_window.geometry("480x360")

        self.play_window.protocol("WM_DELETE_WINDOW", self.close_play)       

        tk.Label(self.play_window, text=f"Play Mode").pack()
        self.play_area = tk.Frame(self.play_window)
        self.play_area.pack(fill=tk.BOTH, expand=True)
        self.play_header = tk.Label(self.play_area, text="", wraplength=440, justify="left", font=("TkDefaultFont", 11))
        self.play_header.pack(pady=(10,5))
        self.choice_frame = tk.Frame(self.play_area)
        self.choice_frame.pack(pady=(6,10))
        ctrl = tk.Frame(self.play_window)
        ctrl.pack(fill=tk.X)
        tk.Button(ctrl, text="Restart", command=self.play_restart).pack(side=tk.LEFT)
        self.play_current = START_NODE
        self.play_path = []
        self.play_render_current()

    def enter_editor_mode(self): # enter editor mode
        global vars_store, inventory
        self.mode = "editor"
        self.mode_button.config(text="Switch to Play Mode")

        # Restore the editor's variable state from backup
        if self.editor_vars_backup is not None:
            vars_store = self.editor_vars_backup
            self.editor_vars_backup = None
        if self.editor_inventory_backup is not None:
            inventory = self.editor_inventory_backup
            self.editor_inventory_backup = None

        try:
            self.play_window.destroy()
        except Exception:
            pass

        # Refresh the inspector to show the restored values
        self.load_selected_into_inspector()

    def close_play(self): # close play
        self.enter_editor_mode()

    def reset_state(self): # reset state (variables and inventory for play mode)
        vars_store.clear()
        inventory.clear()
        defaults = self.vars_list.get("1.0", tk.END).strip().splitlines()
        for line in defaults:
            line = line.strip()
            if not line:
                continue
            if line.startswith("inv:"):
                item = line.split(":", 1)[1].strip()
                if item:
                    inventory.append(item)
            elif "=" in line:
                name, val = line.split("=", 1)
                name, val = name.strip(), val.strip()
                try:
                    vars_store[name] = safe_eval_expr(val, vars_store)
                except Exception:
                    vars_store[name] = val

    def play_restart(self): # restart the play [mode] session
        self.reset_state()
        self.play_current = START_NODE; self.play_path = []; self.play_render_current()

    @staticmethod
    def substitute_vars(text: str) -> str: # substitute variables, used for inline variable support such as "Clicks: {CLICSKS}" ({CLICKS} gets replaced with the variable 'CLICKS' if it exists)
        if not text:
            return ""
        def repl(match):
            key = match.group(1)
            return str(vars_store.get(key, f"{{{key}}}"))
        return re.sub(r"\{(\w+)\}", repl, text)
 
    def play_render_current(self):
        # Run instant leaves (cascading gotos included)
        self.play_current = run_instant_leaves(self.play_current)

        if self.play_current not in nodes:
            if self.settings.get('show_path', True):
                self.play_header.config(
                    text=f"[END] Node {self.play_current} not found. Path: {' -> '.join(map(str,self.play_path))}"
                )
            else:
                self.play_header.config(text=f"[END] Node {self.play_current} not found.")
            for w in self.choice_frame.winfo_children():
                w.destroy()
            return

        node = nodes[self.play_current]
        self.play_path.append(self.play_current)

        # substitute variables in header
        self.play_header.config(text=self.substitute_vars(node.get("header", "")))

        # Gather visible normal leaves
        visible = []
        for opt_raw in node.get("options", []):
            opt = parse_option_line(opt_raw)
            if not opt or opt.get("instant"):
                continue
            if evaluate_condition(opt.get("condition")):
                visible.append(opt)

        for w in self.choice_frame.winfo_children():
            w.destroy()

        if not visible:
            tk.Label(self.choice_frame, text="[THE END]").pack()
            if self.settings.get('show_path', True):
                tk.Label(
                    self.choice_frame,
                    text="Path: " + " -> ".join(map(str,self.play_path))
                ).pack()
            tk.Button(self.choice_frame, text="Play Again", command=self.play_restart).pack(pady=(6, 0))
            tk.Button(self.choice_frame, text="Close Play", command=self.close_play).pack(pady=(6, 0))
            return

        for opt in visible:
            opt_text = self.substitute_vars(opt.get("text", "choice"))
            btn = tk.Button(
                self.choice_frame,
                text=opt_text,
                width=50,
                anchor="w",
                command=lambda o=opt: self.play_pick(o)
            )
            btn.pack(pady=2)

    def play_pick(self, opt):
        execute_actions(opt.get("actions", []))
        nxt = resolve_next(opt.get("next"))
        if nxt is None:
            self.play_header.config(text="[THE END]")
            for w in self.choice_frame.winfo_children():
                w.destroy()
            tk.Button(self.choice_frame, text="Play Again", command=self.play_restart).pack(pady=(6,0))
            tk.Button(self.choice_frame, text="Close Play", command=self.close_play).pack(pady=(6,0))
            return

        # run instant leaves in the next node (cascading)
        self.play_current = run_instant_leaves(nxt)
        self.play_render_current()

    def build_example(self): # builds an example scene
        nodes.clear(); vars_store.clear(); inventory.clear()

        node_color = self.theme.get('default_node_color', '#222222')

        create_node(1, "You were met with a fork in the path.", x=60, y=80, options=[
            {"text":"Go left", "next":"2", "condition":None, "actions":[]},
            {"text":"Go right", "next":"3", "condition":None, "actions":[]}
        ], color=node_color)
        create_node(2, "You find a river blocking your path.", x=300, y=80, options=[
            {"text":"Swim across", "next":"4", "condition":None, "actions":["set:wet=True"]},
            {"text":"Turn back", "next":"1", "condition":None, "actions":[]}
        ], color=node_color)
        create_node(3, "You encounter a sleeping dragon.", x=300, y=240, options=[
            {"text":"Sneak past", "next":"4", "condition":None, "actions":[]},
            {"text":"Attack it", "next":"5", "condition":"has_item:sword", "actions":[]}
        ], color=node_color)
        create_node(4, "You made it to a small village. The end.", x=540, y=150, options=[], color=node_color)
        create_node(5, "The dragon wakes up and roasts you. Oops.", x=540, y=280, options=[], color=node_color)
        inventory.append("rope")
        vars_store["mysterious_path"] = 7
        self.update_node_count()
        self.redraw()
        
def main(): # main
    root = tk.Tk()
    root.geometry("1200x700")
    app = VisualEditor(root)
    root.mainloop()

if __name__ == "__main__":
    main()
