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

**Language:** Python (GUI with pygame).

**Scoring.** At a full board the exact result (the *utility*) is the computer's number of fours minus the human's. Every window of 4 cells counts, so overlapping fours count separately (5 in a row = 2 fours).

**Search.** The computer is MAX and the human is MIN. Alpha-beta pruning runs to depth K, or until the board is full. Only the best first move is played, and a new search runs after each human reply.

**Leaf values in the printed tree:**

| Label | Meaning |
|---|---|
| `TERMINAL score=+2` | Board is full; exact result |
| `LEAF eval=13` | Depth K reached; the heuristic's estimate |

**Heuristic.** A weighted sum of board features, always computer minus human: connected-fours, open threes, open twos, and center control. The weights are tuned by self-play (hill climbing and a genetic algorithm).

**Move ordering.** Center columns are tried first to improve pruning.

**Bonus targets:** GUI (Brawlhalla-inspired, original art), tree shown in the GUI, and a tuned heuristic.

## Project structure

```
connect4/
├── core/            Game world: board, discs, players, rules, game interface
├── options/         Configuration data: board size, connect length, color options
├── setup/           Builds a ready game from the start-screen choices
├── ui/              Theme, screens, animation, tree panel
├── algorithms/      Alpha-beta search, heuristics, move ordering, tree, tuning
├── experiments/     Scripts for the report (time and nodes per K, tournaments)
├── tests/           Unit tests
├── docs/            Report, sample trees, tables
├── main.py          Entry point
└── README.md
```

**Dependency rules:** `core` depends on nothing; `algorithms` depends only on `core`; `ui` depends on `core` and the tree data classes; `setup` wires the pieces together.

## Getting started

*(Commands may change while the project is in development.)*

```bash
git clone <repository-url>
cd connect4
pip install -r requirements.txt

# Play (asks for K before starting)
python main.py

# Time and nodes per K
python -m experiments.k_analysis

# Tests
python -m unittest discover tests
```

## Team

| Member | Responsibility |
|---|---|
| `<Name 1>` | Board and initialization, game loop, GUI |
| `<Name 2>` | Alpha-beta search, heuristic, tuning, experiments |
| Both | Tests, report |

## Progress

- [ ] Board and rules
- [ ] Alpha-beta search with depth K
- [ ] Heuristic evaluation
- [ ] Console tree printing (with heuristic values)
- [ ] Time and nodes analysis for different K
- [ ] GUI
- [ ] Tree shown in the GUI
- [ ] Heuristic tuning
- [ ] Report
