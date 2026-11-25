# Connect 4 AI Agent: Minimax with Alpha-Beta Pruning

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Status](https://img.shields.io/badge/status-in%20development-orange)

**Alexandria University, Faculty of Engineering, Computer and Systems Department**
**Course:** Artificial Intelligence | **Assignment 2**
**Assigned:** November 16, 2026 | **Due:** Wednesday, November 25, 2026
**Team:** `<Name 1>`, `<Name 2>` (group of 2)

---

## Table of contents

1. [About the lab](#about-the-lab)
2. [Game description](#game-description)
3. [Lab requirements](#lab-requirements)
4. [Deliverables](#deliverables)
5. [Our approach](#our-approach)
6. [Project structure](#project-structure)
7. [Getting started](#getting-started)
8. [Team](#team)
9. [Progress](#progress)

---

## About the lab

The goal of this lab is to build an **AI agent that plays Connect 4** against a human, using **Minimax with alpha-beta pruning**. Because the full game tree is far too large to search to the end (on the order of 10^35 states), the search is **cut off after K levels** and boards at the cutoff are scored by a **heuristic evaluation function** that we design.

The lab practices:

- Adversarial (two-player, zero-sum) search
- Alpha-beta pruning and move ordering
- Real-time decisions with a depth cutoff and an evaluation function
- Designing and comparing heuristics

## Game description

Connect 4 is a two-player game. Each player picks a color, then they take turns dropping a disc into a column of a grid. The disc falls straight down and lands in the lowest free cell of that column. A **connected-four** is four discs of the same color next to each other, horizontally, vertically, or diagonally.

**This lab uses a different ending rule from the standard game:**

- The game does **not** end when someone first connects four.
- Players keep playing **until the board is full**.
- The winner is the player with the **greater number of connected-fours**.

The board must be at least **7 columns wide and 6 rows long**. Any acceptable fixed size may be chosen (we use 7 x 6).

## Lab requirements

### 1. The game

- One mode only: **human vs. computer**.
- The computer's moves come from Minimax with alpha-beta pruning.
- Play continues until the board is full.
- A console interface is enough. A **graphical interface earns a bonus**.

### 2. The algorithm

- The computer runs **Minimax with alpha-beta pruning** on every turn.
- On every turn the program must **print the minimax tree to the console** in a readable form that can be traced.
- Showing the tree in a GUI earns a bonus.

### 3. Heuristic and depth cutoff

- The search tree is truncated after **K levels**, and boards at that depth are scored by a heuristic function.
- The game must take **K as a parameter before it begins**.
- The heuristic returns a **larger number when the computer is closer to winning** and a **smaller number when the human is closer to winning**.
- It should consider several factors, such as the current scores and the number of candidate (still possible) fours for each player.
- **The heuristic value of the boards must be shown in the printed tree** (marks are lost otherwise).
- The three best heuristics earn a bonus.

## Deliverables

1. **Well-commented code.**
2. **A report** containing:
   - Sample runs and their corresponding minimax trees
   - Analysis of time taken and nodes expanded by alpha-beta pruning at different K values
   - The data structures and algorithms used
   - Assumptions and any details that need clarifying
   - Any extra work

**Rules:** Java, Python, or C++ may be used. Work may be done in groups of 2. Copied work is severely penalized.

## Our approach

**Language:** Python (GUI with PySide6).

**Scoring.** At a full board the exact result (the *utility*) is the computer's number of fours minus the human's. Every window of 4 cells counts, so overlapping fours count separately (5 in a row = 2 fours).

**Search.** The computer is MAX and the human is MIN. Alpha-beta pruning runs to depth K, or until the board is full. Only the best first move is played, and a new search runs after each human reply.

**Leaf values in the printed tree:**

| Label | Meaning |
|---|---|
| `TERMINAL score=+2` | Board is full; exact result |
| `LEAF eval=13` | Depth K reached; the heuristic's estimate |

**Heuristic.** A weighted sum of board features, always computer minus human: connected-fours, open threes, open twos, and center control. The weights are tuned by self-play (hill climbing and a genetic algorithm).

**Move ordering.** Center columns are tried first to improve pruning.

**Bonus targets:** Dark-myth PySide6 GUI (*Connect 4: vs The Devils*), interactive 2D $\triangle$/$\triangledown$ Minimax tree with step-by-step $\alpha\text{-}\beta$ playback & Sheet-6 trace tables, and self-play tuned heuristics.

## Project structure

```
connect_four/
├── core/             Game world: immutable Disc, Board, 69-window Rules, Game
├── algorithms/       Minimax with Alpha-Beta pruning & composable move ordering
├── heuristics/       Three candidate evaluators (Opportunities, Gravity, GA-Tuned Windows)
├── tree_essentials/  TreeNode, SearchRecorder, SearchStats, SearchResult, TreePrinter
├── game/             Player hierarchy, AIPlayer, and terminal console runner
├── options/          Board dimensions, connect length, colors, first player, K limits
├── setup/            SessionSettings validation, player factory, and GameSession builder
├── ui/               PySide6 GUI, 2D △/▽ Minimax tree canvas, playback & Sheet-6 tables
├── assets/           Scene artwork and extracted carved-board & orb sprites
├── experiments/      k_analysis, compare_heuristics, tune_heuristic & CSV benchmarks
├── tests/            Unit test suite (142 tests)
├── main.py           Main entry point (GUI by default, --console for terminal)
├── requirements.txt  Python package dependencies
└── README.md
```

**Dependency rules:** `core` depends on nothing; `tree_essentials` depends only on `core`; `algorithms` and `heuristics` depend on `core` and `tree_essentials`; `ui` renders `core`, `heuristics`, and `tree_essentials` data; `setup` wires sessions together.

## Getting started

```bash
git clone https://github.com/HanyAyman606/Connect-4-lab-.git
cd Connect-4-lab-
pip install -r requirements.txt

# Launch Graphical User Interface (default)
python main.py

# Launch Console Interface
python main.py --console

# Experiments for the report
python -m experiments.k_analysis
python -m experiments.compare_heuristics --mode all --ks 2 3 4
python -m experiments.tune_heuristic

# Run full unit test suite (142 tests)
python -m unittest discover tests
```

## Team

| Member | Responsibility |
|---|---|
| `<Name 1>` | Board and initialization, game loop, GUI |
| `<Name 2>` | Alpha-beta search, heuristic, tuning, experiments |
| Both | Tests, report |

## Progress

- [x] Board and rules
- [x] Alpha-beta search with depth K
- [x] Heuristic evaluation
- [x] Console tree printing (with heuristic values)
- [x] Time and nodes analysis for different K
- [x] GUI
- [x] Tree shown in the GUI
- [x] Heuristic tuning
- [ ] Report
