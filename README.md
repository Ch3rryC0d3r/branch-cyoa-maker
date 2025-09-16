# 🌿 Branch — Visual CYOA Maker

> A powerful, visual, and self-contained editor for creating complex Choose-Your-Own-Adventure (CYOA) stories.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellowgreen.svg)](LICENSE)
[![Made with Tkinter](https://img.shields.io/badge/made%20with-Tkinter-red)](https://docs.python.org/3/library/tkinter.html)

---

## ✨ What is Branch?

Branch is a standalone tool that lets you build branching narratives visually, without needing to write complex code. It combines a node-based editor with a powerful logic system, allowing you to create dynamic stories with variables, conditions, and an inventory system. When you're ready, you can instantly playtest your creation right inside the app.

<p align="center">
  <img src="Interface.png" alt="Editor Screenshot" width="800">
</p>

---

## ⚡ Features

Branch is packed with features to make story creation intuitive and powerful.

#### Core Editing
- **Visual Node Editor:** Drag and drop nodes to build your story flow.
- **Live Inspector:** Instantly edit node content, options, and colors.
- **Undo/Redo:** Full undo/redo support for nearly all actions.
- **Multi-Select:** Select, move, and delete multiple nodes at once.
- **Comments:** Add resizable comment boxes to organize your canvas.
- **Search:** Quickly find and center on any node by its ID (`Ctrl+F`).
- **Easy Navigation:** Pan the canvas with the middle mouse button or `WASD` keys.

#### Powerful Logic System
- **Variables & Inventory:** Use variables and a player inventory to track story state.
- **Conditions:** Show or hide choices based on variables or items (`gold > 10 & has_item:key`).
- **Actions:** Modify variables, grant items, or force jumps (`gold+=10`, `add_item:sword`).
- **Conditional Actions:** Run an action only if a condition is met (`if(HP<=0)>goto:GameOver`).
- **Instant Actions:** Trigger logic as soon as a node is entered, before the player chooses (`@HP-=5`).

#### Dynamic Content
- **Variable Substitution:** Display variable values directly in your story text (`Your gold: {gold}`).
- **Randomization:** Create unpredictable outcomes with **Random Branching** (`next: 1/2/3`) and **Random Actions** (`rands(mood:happy,sad)`).

#### Workflow & Customization
- **Integrated Play Mode:** Instantly playtest your story in a separate window.
- **Customizable Themes:** Includes several built-in themes (dark, light, and colorful). Your last used theme is saved automatically.
- **Custom Keybinds:** Modify keybinds and editor behavior via `settings.json`.
- **Simple Data Format:** Save and load stories as human-readable **JSON** files.

---

## 🛠️ Installation

⚠️ To enable sound support (`play:SOUND`), you’ll also need the [`playsound`](https://pypi.org/project/playsound/) library:

1. ```bash
    pip install playsound
    ```
2.  **Clone the repository:**
    ```bash
    git clone https://github.com/Ch3rryC0d3r/branch-cyoa-maker.git
    cd branch-cyoa-maker
    ```
    Alternatively, you can just download `Branch.py` directly.

3.  **Run the script:**
    Make sure you have **Python 3.8+** installed (Tkinter is usually included).
    ```bash
    python Branch.py
    ```

---

## 🚀 Getting Started

### Editor Controls

| Action | Control |
| :--- | :--- |
| Pan Canvas | `Middle Mouse Drag` or `WASD` |
| Add Node (Quick) | `Right-click Canvas` → `(Quick) Add Node` |
| Add Comment | `Right-click Canvas` → `Add Comment` |
| Select Node/Comment | `Left-click` |
| Move Node/Comment | `Left-click + Drag` |
| Multi-Select (Box) | `Shift + Left-click + Drag` |
| Open Node Menu | `Right-click Node` |
| Connect Nodes | `Right-click Node` → `Connect`, then `Left-click` target node |
| Find Node | `Ctrl + F` |

### Leaves: The Core of Your Story

Each choice in a node is called a **Leaf**. A Leaf is a single line of text in the "Options" box in the inspector, structured with four parts separated by `|`.

```
Text | Next | Condition | Actions
```

👉 For a quick reference, check out the **Leaves Documentation**.

#### 1. Text
This is the text the player sees for the choice. You can embed variables using curly braces.

`"Hello, {player_name}!"`

#### 2. Next
The ID of the node to go to when this option is chosen.

- **Single Node:** `5` (goes to node 5)
- **Random Node:** `5/6/7` (randomly goes to node 5, 6, or 7)
- **End of Path:** Leave this blank to end the story here.

#### 3. Condition
An optional rule that must be true for the option to be visible. You can chain multiple conditions with `&` or `;`.

| Type | Example | Description |
| :--- | :--- | :--- |
| Has Item | `has_item:key` | Player has "key" in their inventory. |
| Not Has Item | `not_has_item:sword` | Player does *not* have "sword". |
| Variable Check | `gold >= 10` | The `gold` variable is 10 or more. |
| Chained | `has_item:key & gold>5` | Both conditions must be true. |

#### 4. Actions
A list of actions to execute when the option is chosen, separated by `&` or `;`.

| Type | Example | Description |
| :--- | :--- | :--- |
| **Variable** | | |
| Set | `gold = 100` | Sets `gold` to 100. |
| Modify | `gold += 10` | Adds 10 to `gold`. Also supports `-=`, `*=`, `/=`. |
| **Inventory** | | |
| Add Item | `add_item:potion` | Adds "potion" to inventory. |
| Remove Item | `remove_item:key` | Removes "key" from inventory. |
| **Flow Control** | | |
| Go To | `goto:50` | Immediately jumps to node 50. |
| **Random** | | |
| Random String | `rands(mood:happy,sad)` | Sets `mood` to either "happy" or "sad". |
| Random Range | `randr(damage:5,20)` | Sets `damage` to a random number between 5 and 20. |
| **Advanced** | | |
| Instant Action | `@stamina -= 1` | Runs when the node is *entered*, not chosen. |
| Conditional Action | `if(is_tired==1)>stamina=0` | Runs the action only if the `if` condition is met. |

---

### Example Leaf

Here is a complex leaf that uses all the parts:

```
Attack the guard | 15 | has_item:sword & stamina>20 | @stamina-=10; if(boss_is_weak==1)>goto:16
```

- **Text:** "Attack the guard"
- **Next:** Goes to node `15`.
- **Condition:** Only visible if the player has a `sword` and `stamina` is greater than 20.
- **Actions:**
  1.  `@stamina-=10`: The player loses 10 stamina just for entering the node this leaf is in.
  2.  `if(boss_is_weak==1)>goto:16`: If the variable `boss_is_weak` is 1, the player is immediately redirected to node `16` instead of `15`.

---

## 💾 Saving & Loading

-   **Save:** Go to `App → Save (Ctrl+S)`. Your story, including node positions, variables, and inventory defaults, will be saved to a `.json` file in the `./saves/` folder.
-   **Load:** Go to `App → Load` and select a `.json` story file.

## 🎨 Customization

#### Theming
Open the **Theme Control** window from the toolbar to switch between several built-in visual styles. Your current theme is automatically saved to `theme.json` and will be loaded the next time you open the app.

#### Settings
Open the **Settings** window from the toolbar to configure:
-   **Keybinds:** Change the default keyboard shortcuts for actions like Undo, Redo, and Save.
-   **Editor Behavior:** Toggle confirmation dialogs, default node colors, and more.

Your settings are saved to `settings.json`.

---

## 📜 License

This project is licensed under the MIT License.


