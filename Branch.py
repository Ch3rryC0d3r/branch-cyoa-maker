""" 
Branch, a CYOA (Choose-Your-Own-Adventure) Maker.
Version: v1.0.02.01

******************************************To Do******************************************
@1@ Fix zooming. Calling 'redraw()' never drawed the nodes with sizes based on the 'current_zoom', I've tried before, however, the click detection was offset each time I dragged a node.
********************************************************************************************
"""

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

    return _eval(node)

# constants and whatnot
nodes: Dict[int, Dict] = {}  
comments = {}
vars_store: Dict[str, Any] = {}
inventory: List[str] = []
START_NODE = 1
BASE_FONT_SIZE = 11
SETTINGS_PATH = "./settings.json"
THEME_PATH = "./theme.json"
MIN_W, MIN_H = 30, 20 # minimum size for comments

# A "LEAF" is simply a name for an option line in the Node Inspector.

def parse_option_line(line: str) -> Optional[Dict]: # parses an option line (or a "LEAF")
    raw = line.strip()
    if not raw:
        return None
    parts = [p.strip() for p in raw.split("|")]

    # ensure 4 parts: text | next | condition | actions
    while len(parts) < 4:
        parts.append("")
    text, nxt, cond, acts = parts[0], parts[1], parts[2], parts[3]

    # actions can be separated by & or ;
    actions = [a.strip() for a in re.split(r'[&;]', acts) if a.strip()] if acts else []
    cond = cond if cond else None
    nxt = nxt if nxt else None
    return {"text": text, "next": nxt, "condition": cond, "actions": actions}

def format_option_line(opt: Dict) -> str: # fix format in option line(s)
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

def execute_actions(actions: List[str]): # execute a LEAF action such as 'CLICKS+=1' (add 1 to the variable 'CLICKS')
    for act in actions:
        if not act:
            continue
        subs = [s.strip() for s in re.split(r'[&;]', act) if s.strip()]
        for sub in subs:
            try:
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
                            try:
                                val = int(raw)
                            except Exception:
                                try:
                                    val = float(raw)
                                except Exception:
                                    val = raw.strip('"').strip("'")
                    vars_store[name] = val

                elif sub.startswith("add_item:"):
                    name = sub.split(":",1)[1].strip()
                    if name and name not in inventory:
                        inventory.append(name)

                elif sub.startswith("remove_item:"):
                    name = sub.split(":",1)[1].strip()
                    if name in inventory:
                        inventory.remove(name)

                elif sub.startswith("rand_set:"):
                    payload = sub.split(":",1)[1]
                    if ":" not in payload:
                        continue
                    name, opts = payload.split(":",1)
                    choices = [o.strip() for o in opts.split(",") if o.strip()]
                    if choices:
                        vars_store[name.strip()] = random.choice(choices)

                elif sub.startswith("goto:"):
                    vars_store["__goto"] = sub.split(":",1)[1].strip()

                m2 = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*([\+\-\*/%]?=)\s*(.+)$", sub)
                if m2:
                    name, op, rhs = m2.group(1), m2.group(2), m2.group(3)
                    # evaluate RHS safely
                    try:
                        rhs_val = safe_eval_expr(rhs, vars_store)
                    except Exception:
                        try:
                            rhs_val = int(rhs)
                        except Exception:
                            try:
                                rhs_val = float(rhs)
                            except Exception:
                                rhs_val = rhs.strip('"').strip("'")
                    cur = vars_store.get(name, 0)
                    # apply operator
                    if op == "=":
                        vars_store[name] = rhs_val
                    elif op == "+=":
                        try:
                            vars_store[name] = (cur or 0) + rhs_val
                        except Exception:
                            vars_store[name] = rhs_val
                    elif op == "-=":
                        try:
                            vars_store[name] = (cur or 0) - rhs_val
                        except Exception:
                            vars_store[name] = cur
                    elif op == "*=":
                        try:
                            vars_store[name] = (cur or 0) * rhs_val
                        except Exception:
                            vars_store[name] = cur
                    elif op == "/=":
                        try:
                            vars_store[name] = (cur or 0) / rhs_val
                        except Exception:
                            vars_store[name] = cur
                    elif op == "%=":
                        try:
                            vars_store[name] = (cur or 0) % rhs_val
                        except Exception:
                            vars_store[name] = cur
                    # handled — skip further checks for this sub
                    continue

                elif sub.startswith("var:"):
                    payload = sub.split(":",1)[1].strip()
                    # match var:x+=expr  var:x=expr etc.
                    m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*([\+\-\*/]?=)\s*(.+)$", payload)
                    if m:
                        name, op, rhs = m.group(1), m.group(2), m.group(3)
                        try:
                            rhs_val = safe_eval_expr(rhs, vars_store)
                        except Exception:
                            try:
                                rhs_val = int(rhs)
                            except Exception:
                                try:
                                    rhs_val = float(rhs)
                                except Exception:
                                    rhs_val = rhs.strip('"').strip("'")
                        cur = vars_store.get(name, 0)
                        if op == "=":
                            vars_store[name] = rhs_val
                        elif op == "+=":
                            vars_store[name] = (cur or 0) + rhs_val
                        elif op == "-=":
                            vars_store[name] = (cur or 0) - rhs_val
                        elif op == "*=":
                            vars_store[name] = (cur or 0) * rhs_val
                        elif op == "/=":
                            try:
                                vars_store[name] = (cur or 0) / rhs_val
                            except Exception:
                                vars_store[name] = cur
                    else:
                        # fallback: var:NAME=RHS or var:NAME (ignored)
                        if "=" in payload:
                            name, rhs = payload.split("=",1)
                            name, rhs = name.strip(), rhs.strip()
                            try:
                                val = safe_eval_expr(rhs, vars_store)
                            except Exception:
                                val = rhs
                            vars_store[name] = val
                        else:
                            # plain var name - set truthy 1?
                            vars_store[payload] = vars_store.get(payload, 0)

                else:
                    # try generic name=val update
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

NODE_W = 180 # node width
NODE_H = 80 # node height
COMMENT_W, COMMENT_H = 150, 50 # comment width, comment height
HANDLE_SIZE = 8  # size of draggable corner handles on comments

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
        self.multi_selected_nodes = set()
        self.undo_stack = [] # undo stack, or 'undo list'
        self.theme = {} # define 'self.theme' for later use

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
        self.settings = {
            "disable_delete_confirm": False,
            "show_path": False,
            "udtdnc": False,
            "keybinds": {
                "undo": "<Control-z>",
                "redo": "<Control-Shift-Z>",
                "redo_alt": "<Control-y>",
                "save": "<Control-s>"
            }
        }
        self.load_settings() # load settings if path settings.json exists

        tk.Button(self.toolbar, text="Settings", command=self.open_settings).pack(side=tk.LEFT) # settings button
        tk.Button(self.toolbar, text="Theme Control", command=self.open_themecontrol).pack(side=tk.LEFT) # theme control button
        
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
            # convert pixels → approx characters (roughly)
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
        for t in (self.header_text, self.options_text, self.vars_list):
            t.bind("<<Modified>>", self._on_modified)
            t.bind("<FocusOut>", self._on_focus_out)

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

        #self.master.bind("<Control-0>", lambda e: self.reset_zoom())

    def apply_comment_text(self):
        if self.selected_comment is None:
            return
        new_text = self.header_text.get("1.0", tk.END).strip()
        comments[self.selected_comment]["text"] = new_text
        self.redraw()

    def start_canvas_or_comment(self, event):
        # First, check if we clicked on a comment
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
            if self.selected_comment is not None:
                self.apply_comment_edits()
            elif self.selected_node is not None:
                self.apply_edits()
            self.apply_vars_text()  # always apply vars if needed
            w.edit_modified(False)

    def _on_focus_out(self, event):
        if self.selected_comment is not None:
            self.apply_comment_edits()
        elif self.selected_node is not None:
            self.apply_edits()
        self.apply_vars_text()

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

                    "preset_canvas_bg": "#ffffff",
                    "preset_inner_bg": "#ffffff",
                    "preset_frame_bg": "#ffffff",
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
        #print(self.settings['show_path'])
        win = tk.Toplevel(self)
        win.title("Settings")
        ######################
        var1 = tk.BooleanVar(value=self.settings["show_path"])
        chk2 = tk.Checkbutton(win, text="Show path", variable=var1,
                            command=lambda: self.settings.update(show_path=var1.get()))
        chk2.pack(anchor="w", pady=4)
        ######################
        var = tk.BooleanVar(value=self.settings["disable_delete_confirm"])
        chk2 = tk.Checkbutton(win, text="Disable deletion confirmation", variable=var,
                            command=lambda: self.settings.update(disable_delete_confirm=var.get()))
        chk2.pack(anchor="w", pady=4)
        ######################
        var2 = tk.BooleanVar(value=self.settings["udtdnc"])
        chk3 = tk.Checkbutton(win, text="Use default themes' default node color, always.", variable=var2,
                            command=lambda: self.settings.update(udtdnc=var2.get()))
        chk3.pack(anchor="w", pady=4)
        ######################
        #var3 = tk.BooleanVar(value=self.settings["disable_zooming"])
        #chk4 = tk.Checkbutton(win, text="Disable zooming", variable=var3,
        #                    command=lambda: self.settings.update(disable_zooming=var3.get()))
        #chk4.pack(anchor="w", pady=4)
        ######################
        tk.Label(win, text="Keybinds:").pack(anchor="w", pady=(10,0))
        for action, seq in self.settings["keybinds"].items():
            frame = tk.Frame(win)
            frame.pack(anchor="w", pady=2)
            tk.Label(frame, text=action.capitalize()).pack(side=tk.LEFT, padx=4)
            entry = tk.Entry(frame)
            entry.insert(0, seq)
            entry.pack(side=tk.LEFT)

            def save_bind(a=action, e=entry):
                self.settings["keybinds"][a] = e.get()
                self.apply_keybinds()

            tk.Button(frame, text="Apply", command=save_bind).pack(side=tk.LEFT, padx=4)
                
    def open_themecontrol(self):
        self.win = tk.Toplevel(self)
        self.win.title("Theme")
        self.win.geometry('205x300')
        self.win.winfo_x = 0
        self.win.winfo_y = 0

        tk.Label(self.win, text='Presets', font=("TkDefaultFont", 11)).pack()
        tk.Button(self.win, text='Default', command=lambda: self.themepreset('default', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Cherries', command=lambda: self.themepreset('cherries', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Ocean', command=lambda: self.themepreset('ocean', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Forest', command=lambda: self.themepreset('forest', 1)).pack(side=tk.TOP, pady=4)
        tk.Button(self.win, text='Ocean (v2)', command=lambda: self.themepreset('ocean 2', 1)).pack(side=tk.TOP, pady=4)

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
        self.save_settings(); self.save_theme()
        self.master.destroy()

    def update_settings(self):
        self.settings["disable_delete_confirm"] = self.delete_confirm_var.get()    
        self.settings["show_path"] = self.show_path.get()    
        self.settings["udtdnc"] = self.udtdnc.get() 
        #self.settings["disable_zooming"] = self.disable_zooming.get() 

    def add_node_prompt(self):
        nid = simpledialog.askinteger("Add Node", "Node ID (int):", minvalue=1)
        if nid is None:
            return
        if nid in nodes:
            if not messagebox.askyesno("Overwrite?", f"Node {nid} exists — overwrite?"):
                return
        create_node(nid, header=f"Node {nid}", x=100, y=100)
        self.selected_node = nid
        self.redraw()
        self.load_selected_into_inspector()
        self.update_node_count()

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

    def search_node(self, event=None):
        nid_str = self.search_var.get().strip()
        if not nid_str.isdigit():
            return
        nid = int(nid_str)
        if nid in nodes:
            self.selected_node = nid
            self.load_selected_into_inspector()
            self.redraw()
            
            x = nodes[nid]["x"]
            y = nodes[nid]["y"]
            self.canvas.xview_moveto(max(0, (x-200)/self.canvas.winfo_width()))
            self.canvas.yview_moveto(max(0, (y-100)/self.canvas.winfo_height()))
        #self.canvas.scale("all", 0, 0, self.current_zoom, self.current_zoom)
            
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
        self.push_undo()
        targets = self.multi_selected_nodes if self.multi_selected_nodes else {self.selected_node}
        if not targets:
            return
        if not self.settings.get("disable_delete_confirm", False):
            if not messagebox.askyesno("Delete", f"Delete {len(targets)} node(s)?"):
                return
        for nid in targets:
            delete_node(nid)
        self.selected_node = None
        self.multi_selected_nodes.clear()
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

    def apply_edits(self): # apply edits for options_text and header_text
        if self.selected_node is None:
            #messagebox.showinfo("No node", "Select a node first.")
            return
        header = self.header_text.get("1.0", tk.END).strip()
        opts_raw = self.options_text.get("1.0", tk.END).strip().splitlines()
        opts = []
        for line in opts_raw:
            parsed = parse_option_line(line)
            if parsed:
                opts.append(parsed)
        nodes[self.selected_node]["header"] = header
        nodes[self.selected_node]["options"] = opts
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

    def quick_add_node(self, x=None, y=None): # quick add a node (quick add means it adds the latest node ID)
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        cx, cy = self.canvas.canvasx(w/2), self.canvas.canvasy(h/2)
        #print(self.drag_offset[0], self.drag_offset[1])
        self.push_undo()
        new_id = max(nodes.keys(), default=0) + 1
        if x is None: x = cx
        if y is None: y = cy
        if self.settings['udtdnc'] == True:
            color = '#222222'
        else:
            color = self.theme['default_node_color']
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
        linespace = font.metrics("linespace")
        max_lines = max(1, max_h // max(1, linespace))
        words = text.split(' ')
        lines = []
        current_line = ""
        truncated = False

        for word in words:
            test_line = (current_line + " " + word).strip() if current_line else word
            if font.measure(test_line) <= max_w:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
                if len(lines) >= max_lines:
                    truncated = True
                    break

        if current_line:
            if len(lines) < max_lines:
                lines.append(current_line)
            else:
                truncated = True

        if len(lines) > max_lines:
            lines = lines[:max_lines]
            truncated = True

        # final check: last line too wide?
        if lines:
            last_line = lines[-1]
            if font.measure(last_line) > max_w:
                truncated = True

            if truncated:
                while font.measure(last_line + "…") > max_w and last_line:
                    last_line = last_line[:-1]
                lines[-1] = last_line + "…" if last_line else "…"

        return "\n".join(lines)

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
        seen_edges = set()
        COLOR1 = self.theme.get('from_lines', '#00ced1')
        COLOR2 = self.theme.get('to_lines', '#ffa500')
        RANDOM_EDGE_COLOR = self.theme.get('randomEdgeFromColor', '#8e44ff')

        # --- Update or create nodes ---
        for nid, data in nodes.items():
            x = data.get("x", 50)
            y = data.get("y", 50)
            node_color = data.get("color", self.theme['default_node_color'])

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
                self.canvas.itemconfig(self.node_texts[nid], text=display_text)
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
        # Delete old edges only once
        for item in self.edge_items:
            self.canvas.delete(item)
        self.edge_items.clear()

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

        # clear stale handles from previous frame so they don't accumulate
        for cid in list(comments.keys()):
            self.clear_comment_handles(cid)

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

    def apply_comment_edits(self): # apply comment edits to the comment
        if self.selected_comment is None: return
        comments[self.selected_comment]["text"] = self.header_text.get("1.0", tk.END).strip()
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

    def add_comment(self, text="New comment", x=None, y=None):  # add a comment
        self.push_undo()
        global comments
        if x is None or y is None:
            w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
            x, y = self.canvas.canvasx(w/2), self.canvas.canvasy(h/2)

        cid = max(comments.keys(), default=0) + 1
        comments[cid] = {
            "text": text,
            "x": x,
            "y": y,
            "w": COMMENT_W,
            "h": COMMENT_H
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
        for opt in data.get("options",[]):
            self.options_text.insert(tk.END, format_option_line(opt) + "\n")
        
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

    def toggle_mode(self): # toggle mode (play>editor, editor>play)
        if self.mode == "editor":
            self.enter_play_mode()
        else:
            self.enter_editor_mode()

    def enter_play_mode(self): # enter play mode
        self.mode = "play"
        self.mode_button.config(text="Switch to Editor Mode")
        self.reset_state()
        self.play_window = tk.Toplevel(self.master)
        self.play_window.title("Play Mode")
        self.play_window.geometry("480x360")
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
        #tk.Button(ctrl, text="Reset vars/inv", command=self.reset_state).pack(side=tk.LEFT)
        tk.Button(ctrl, text="Close Play", command=self.close_play).pack(side=tk.RIGHT)
        self.play_current = START_NODE
        self.play_path = []
        self.play_render_current()

    def enter_editor_mode(self): # enter editor mode
        self.mode = "editor"
        self.mode_button.config(text="Switch to Play Mode")
        try:
            self.play_window.destroy()
        except Exception:
            pass

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
        if vars_store.get("__goto"):
            maybe = vars_store.pop("__goto")
            nxt_try = resolve_next(maybe)
            if nxt_try is not None:
                self.play_current = nxt_try

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

        header_text = self.substitute_vars(node.get("header", ""))
        self.play_header.config(text=header_text)

        visible = []
        for opt in node.get("options", []):
            if evaluate_condition(opt.get("condition")):
                visible.append(opt)

        for w in self.choice_frame.winfo_children():
            w.destroy()

        if not visible:
            tk.Label(self.choice_frame, text="[THE END]").pack()
            if self.settings.get('show_path', True):
                tk.Label(
                    self.choice_frame,
                    text="Path: " + " -> ".join(map(str, self.play_path))
                ).pack()
            tk.Button(self.choice_frame, text="Play Again", command=self.play_restart).pack(pady=(6, 0))
            tk.Button(self.choice_frame, text="Close Play", command=self.close_play).pack(pady=(6, 0))
            return

        for i, opt in enumerate(visible, start=1):
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
        execute_actions(opt.get("actions",[]))
        nxt = resolve_next(opt.get("next"))
        if nxt is None:
            self.play_header.config(text="[THE END]")
            for w in self.choice_frame.winfo_children():
                w.destroy()
            if not self.settings.get("show_path", False):
                pass
                #tk.Label(self.choice_frame, text="Path: " + " -> ".join(map(str,self.play_path))).pack()
            tk.Button(self.choice_frame, text="Play Again", command=self.play_restart).pack(pady=(6,0))
            return
        self.play_current = nxt
        self.play_render_current()

    def build_example(self): # builds an example scene
        nodes.clear(); vars_store.clear(); inventory.clear()
        create_node(1, "You were met with a fork in the path.", x=60, y=80, options=[
            {"text":"Go left", "next":"2", "condition":None, "actions":[]},
            {"text":"Go right", "next":"3", "condition":None, "actions":[]}
        ])
        create_node(2, "You find a river blocking your path.", x=300, y=80, options=[
            {"text":"Swim across", "next":"4", "condition":None, "actions":["set:wet=True"]},
            {"text":"Turn back", "next":"1", "condition":None, "actions":[]}
        ])
        create_node(3, "You encounter a sleeping dragon.", x=300, y=240, options=[
            {"text":"Sneak past", "next":"4", "condition":None, "actions":[]},
            {"text":"Attack it", "next":"5", "condition":"has_item:sword", "actions":[]}
        ])
        create_node(4, "You made it to a small village. The end.", x=540, y=150, options=[])
        create_node(5, "The dragon wakes up and roasts you. Oops.", x=540, y=280, options=[])
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
