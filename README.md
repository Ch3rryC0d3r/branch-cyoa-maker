# 🌿 Branch — Visual CYOA Maker

> A powerful, visual, and self-contained editor for creating complex Choose-Your-Own-Adventure (CYOA) stories.

[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellowgreen.svg)](LICENSE)
[![Made with Tkinter](https://img.shields.io/badge/made%20with-Tkinter-red)](https://docs.python.org/3/library/tkinter.html)

---

## ✨ What is Branch?

Branch is a standalone tool that lets you build branching narratives visually, without needing to write complex code. It combines a node-based editor with a powerful logic system, allowing you to create dynamic stories with variables, conditions, inventory, and even sound effects. When you're ready, you can instantly playtest your creation right inside the app.

<p align="center">
  <img src="Interface.png" alt="Editor Screenshot" width="800">
</p>

---

## ⚡ Features

Branch is packed with features to make story creation intuitive and powerful.

#### Core Editing
- **Visual Node Editor:** Drag and drop nodes to build your story flow.
- **Live Inspector:** Instantly edit node content, options, and colors.
- **Undo/Redo:** Full undo/redo support.
- **Multi-Select & Comments:** Organize your canvas easily.
- **Search & Navigation:** `Ctrl+F` to jump to nodes, pan with `WASD` or middle drag.

#### Powerful Logic System
- **Variables & Inventory:** Track player state.
- **Conditions:** Control option visibility.
- **Actions:** Modify variables, grant/remove items, or redirect story.
- **Advanced Actions:** Support for instant (`@`), conditional (`if`), once-only (`once:`), delays, loops, weighted choices, chance-based actions, and more.

#### Dynamic Content
- **Variable Substitution:** Embed `{var}` directly into text.
- **Randomization:** Supports random branching, random variables, weighted distributions, and chance checks.
- **Sound Support:** Play background music or sound effects (`play`, `loop_sound`, `stop_sound`) with `pygame`.

#### Workflow & Customization
- **Integrated Play Mode** for instant testing.
- **Customizable Themes & Keybinds** via JSON configs.
- **Simple JSON Save Format** for your projects.

---

## 🛠️ Installation

⚠️ For sound support (`play:SOUND`), install [`pygame`](https://pypi.org/project/pygame/):

```bash
pip install pygame
```

Clone the repo and run:

```bash
git clone https://github.com/Ch3rryC0d3r/branch-cyoa-maker.git
cd branch-cyoa-maker
python Branch.py
```

Requires **Python 3.8+** (Tkinter is included by default).

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

Examples:
- `Take sword | 5 | has_item:key | add_item:sword`
- `Attack | 10 | stamina>5 | @stamina-=5; randr(damage:1,6)`
- `Explore | 2 | | play:steps.wav; delay:500; goto:3`
- `Treasure | | | weighted(Loot, Gold=70, Gem=30)`

👉 Full list of actions is documented in [Leaves Documentation](Leaves.html).

---

## 💾 Saving & Loading

- **Save:** `App → Save (Ctrl+S)` saves your story into `./saves/`.
- **Load:** `App → Load` lets you pick a `.json` file to load.

## 🎨 Customization

#### Theming
Switch themes in the **Theme Control** window. Saved in `theme.json`.

#### Settings
Configure keybinds and editor behavior in **Settings**. Saved in `settings.json`.

---

## 📜 License

This project is licensed under the MIT License.
