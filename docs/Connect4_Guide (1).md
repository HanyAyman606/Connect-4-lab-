# Connect 4 AI Agent: Project Guide

**Course:** Artificial Intelligence, Alexandria University
**Assignment 2:** Using Minimax Algorithm to Make a Connect 4 AI Agent
**Assigned:** Nov 16, 2026 | **Due: Wednesday, Nov 25, 2026**
**Team:** 2 people | **Target:** all requirements plus all bonuses

## Contents

1. [The lab explained part by part (with our discussions)](#1-the-lab-explained-part-by-part)
2. [Mapping to our lectures](#2-mapping-to-our-lectures)
3. [Main features and task split](#3-main-features-and-task-split)
4. [Assumptions](#4-assumptions)
5. [Main comparisons (experiments for the report)](#5-main-comparisons)

---

# 1. The lab explained part by part

## 1.1 Section 1: Game description

**What the lab says:** Two players pick colors and take turns dropping discs into a grid. A disc falls straight down to the next free cell in that column. The goal is to connect four of your own discs horizontally, vertically, or diagonally. The two players keep playing **until the board is full**, and the winner is the player with the **greater number of connected-fours**.

**What it means (important):** this is **not** standard Connect 4.
- The game does **not** stop when someone gets the first four.
- We count **all** the fours each player has when the board is full.
- So the "terminal state" is a **full board**, not "someone connected four".

**Decisions we made:**
- Every window of 4 consecutive same-color cells counts as one four. So 5 in a row = 2 fours, 6 in a row = 3 fours.
- Equal number of fours = draw.
- The final result is `computer's fours - human's fours`.

**How the fours are counted:** check every window of 4 cells. On a 7x6 board there are **69 windows**:

| Direction | Windows |
|---|---|
| Horizontal | 4 per row x 6 rows = 24 |
| Vertical | 3 per column x 7 columns = 21 |
| Diagonal down-right | 4 x 3 = 12 |
| Diagonal up-right | 4 x 3 = 12 |
| **Total** | **69** |

A window counts as a four for a player if all 4 cells hold that player's disc.

```python
def build_windows():
    wins = []
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):   # horiz, vert, 2 diagonals
                if 0 <= r + 3*dr < ROWS and 0 <= c + 3*dc < COLS:
                    wins.append([(r + i*dr, c + i*dc) for i in range(4)])
    return wins

WINDOWS = build_windows()      # computed once, reused by score() and evaluate()

def count_fours(self, player):
    return sum(all(self.grid[r][c] == player for r, c in win) for win in WINDOWS)

def score(self):               # exact utility of a FULL board
    return self.count_fours(AI) - self.count_fours(HUMAN)
```

---

## 1.2 Section 2.1: Game requirements

**What the lab says:** Provide a full game with **only one mode, human vs. computer**. The AI uses minimax with alpha-beta pruning. Play until the board is full. Console is fine, and a **GUI gives a bonus**. Dimensions: width at least 7, length at least 6; we can fix any acceptable dimensions.

**What it means for us:**
- One mode only. No human-vs-human and no computer-vs-computer in the delivered game (a computer-vs-computer runner is allowed only as our own testing tool).
- We fix the board at **7 columns x 6 rows**.
- The game loop: ask for K, then alternate human and computer turns until the board is full, then announce the winner by number of fours.
- Console version first (required), GUI second (bonus).

**Our data structure discussion: how to build the board**

- **Name:** `Board`.
- **Representation:** a **tuple of tuples of integers**, with `0 = empty`, `1 = human`, `2 = computer`.
- **Dimensions** are constants (`ROWS = 6`, `COLS = 7`), not stored in the grid.
- Row 0 is the top, row 5 is the bottom. A drop searches from the bottom up for the first empty cell.

```python
EMPTY, HUMAN, AI = 0, 1, 2
ROWS, COLS = 6, 7

class Board:
    def __init__(self, grid=None):
        self.grid = grid or tuple(tuple([EMPTY] * COLS) for _ in range(ROWS))

    def valid_moves(self):
        return [c for c in range(COLS) if self.grid[0][c] == EMPTY]

    def is_full(self):
        return not self.valid_moves()

    def drop(self, col, player):            # returns a NEW Board
        for r in range(ROWS - 1, -1, -1):
            if self.grid[r][col] == EMPTY:
                new_row = self.grid[r][:col] + (player,) + self.grid[r][col + 1:]
                return Board(self.grid[:r] + (new_row,) + self.grid[r + 1:])
        raise ValueError("column full")
```

**Why tuple of tuples:**
- Immutable, so every child node has its own board and backtracking can't corrupt anything.
- Cheap to copy: only the changed row is rebuilt, the other rows are shared.
- Hashable, so a transposition table is possible later.
- Integers are fast to compare in the heuristic.

The alternative (mutable list of lists with `make_move` / `undo_move`) is faster at high K but easier to get wrong.

**Main classes (OOP):**

| Class | Responsibility |
|---|---|
| `Board` | Grid and rules: drop, valid moves, full check, count fours, score |
| `Player` (base) with `HumanPlayer` and `AIPlayer` | `get_move(board)`; polymorphism lets the game loop treat both the same |
| `Minimax` / `Searcher` | Alpha-beta with depth K, node counter, timer, builds the tree |
| `Heuristic` | `evaluate(board)`; swappable so versions can be compared |
| `TreeNode`, `TreePrinter` | Tree data and console output |
| `Game` | Main loop |
| `GUI` | Window, board, tree panel |

OOP principles for the report: encapsulation (Board hides the grid), inheritance (Player subclasses), polymorphism (`player.get_move(board)`).

---

## 1.3 Section 2.2: Algorithms

**What the lab says:** Implement the AI agent using **minimax with alpha-beta pruning**. The agent runs the algorithm each turn and **must print the minimax tree to the console in a readable, traceable form**. Showing the tree in the GUI gives a bonus.

### Minimax

- The computer is **MAX** (picks the highest value). The human is **MIN** (picks the lowest). It is a zero-sum game and both play optimally.
- `MAX-VALUE` and `MIN-VALUE` call each other and return a (value, move) pair. The root returns the best move.
- Time O(b^m), space O(b*m) (depth-first). Here b is at most 7.

### Alpha-beta pruning

- **alpha** = best value MAX is already guaranteed on the path. **beta** = best value MIN is already guaranteed.
- In MAX: after updating v, `alpha = max(alpha, v)`; if **v >= beta**, stop (prune).
- In MIN: `beta = min(beta, v)`; if **v <= alpha**, stop (prune).
- Start with alpha = -inf, beta = +inf.
- It gives the **same answer** as plain minimax but expands fewer nodes.

### Move ordering (affects how much is pruned)

| Ordering | Complexity | Effect |
|---|---|---|
| Worst (best moves last) | O(b^m) | No pruning |
| Ideal (best moves first) | O(b^(m/2)) | About twice the depth in the same time |

How we get a good order:
1. **Center first:** try columns in order `3, 2, 4, 1, 5, 0, 6`.
2. Moves that complete a four, or block one, first.
3. Remember the best moves from shallower searches.
4. Optionally a transposition table for repeated states (the tuple board is hashable).

### Important point from our discussion: the search picks only the first move

At the root you get one value per column and you play the column with the highest value. The rest of the predicted line is only what the computer **expects**. After the human actually replies, the search runs **from scratch** on the new board:

```
Turn n:   search K moves ahead  ->  play only the best FIRST column
Human replies (maybe not as predicted)
Turn n+1: new search from the new board  ->  play only the best first column
```

### The code

```python
def alphabeta(board, depth, alpha, beta, maximizing, k, stats):
    stats.nodes += 1                          # "nodes expanded"
    if board.is_full():
        return board.score(), None            # TERMINAL: exact utility
    if depth == k:
        return heuristic(board), None         # LEAF: eval at the cutoff

    best_move = None
    moves = ordered_moves(board)              # center-first
    if maximizing:
        v = float("-inf")
        for c in moves:
            v2, _ = alphabeta(board.drop(c, AI), depth + 1, alpha, beta, False, k, stats)
            if v2 > v:
                v, best_move = v2, c
            alpha = max(alpha, v)
            if v >= beta:
                break                         # prune
        return v, best_move
    else:
        v = float("inf")
        for c in moves:
            v2, _ = alphabeta(board.drop(c, HUMAN), depth + 1, alpha, beta, True, k, stats)
            if v2 < v:
                v, best_move = v2, c
            beta = min(beta, v)
            if v <= alpha:
                break                         # prune
        return v, best_move
```

The order of the checks matters: **terminal first**. If the board is full at exactly depth K, we use the true score and don't guess.

### Printing the tree (mandatory)

Printed to the console **every computer turn**. Each node shows its type (MAX/MIN), the column played, its value, alpha and beta, and pruned branches. Leaves are labeled by their kind:

| Label | Why the search stopped | Where the number comes from | Exact? |
|---|---|---|---|
| `LEAF eval=13` | Depth K reached, game **not** over | `evaluate(board)` | No, a guess |
| `TERMINAL score=+2` | Board is **full** | `board.score()` | Yes |

```
MAX (root)  value=+5
  col 3 -> MIN  value=+4  [a=-inf, b=+inf]
     col 2 -> MAX  value=+4
        col 1 -> LEAF  eval=+4
        col 4 -> LEAF  eval=+3
  col 4 -> MIN  value=+2  [a=4, b=+inf]
     col 0 -> LEAF  eval=+2
     (pruned: cols 1,2,3,5,6)
  ...
  col 6 -> MIN  value=+1
     col 5 -> TERMINAL  score=+1
```

Practical points: a full tree at K = 5 or 6 is huge, so add a **print depth limit** and a **write-to-file** option. Use a small K for the report's sample trees.

---

## 1.4 Section 2.3: Heuristic pruning (cutoff search)

**What the lab says:** The full game tree is about 10^35 nodes, so we can't reach terminal states. Instead we design a **heuristic function** that returns a number (bigger when the computer is nearer to win, smaller when the human is) and **truncate the tree after K levels**. The game **takes K as input before it begins**. The best 3 heuristics get a bonus. **We lose marks if we don't show the heuristic values of boards; tree printing is a must.**

### Utility, K, and eval (our discussion)

**Utility** is the exact value of a finished game:

```
utility(board) = (computer's connected-fours) - (human's connected-fours)
```
Computer 5, human 3 gives +2. It exists only at a full board.

**K** is how many levels (moves) ahead the computer searches. The user enters it before the game.

| K | Looks ahead | Speed | Strength |
|---|---|---|---|
| 1 | Its own move only | Instant | Weak |
| 3 | Move, reply, move | Fast | Decent |
| 5 | 5 moves | Slower | Good |
| 7+ | 7 moves | Can be slow | Stronger |

Without pruning the nodes grow roughly as 7^K.

```python
def ask_for_k():
    while True:
        text = input("Enter search depth K (e.g. 1 to 8): ")
        if text.isdigit() and int(text) >= 1:
            return int(text)
        print("Please enter a whole number of at least 1.")
```
In the GUI this becomes a selector on the start screen.

**Eval** is an educated guess of how good a board is for the computer, used when the search stops at depth K and the game isn't over.

| | Utility | Eval |
|---|---|---|
| When used | Board is full | Depth K reached, game not over |
| Accuracy | Exact | A guess |
| Built from | Final fours count | Board features |

### Does K affect accuracy?

Yes, generally, with nuances:
1. A larger K usually plays better, because more of the tree is judged by real consequences.
2. Not guaranteed: a weak heuristic searched deeply can still choose badly.
3. **Horizon effect:** anything bad beyond depth K is invisible.
4. **Odd vs even K** can behave differently. With odd K the last level is the computer's own move (slightly optimistic); with even K it is the human's reply.
5. Minimax is exact only if K reaches the end of the game (late game, few empty cells).

### The key point: eval does NOT look ahead

| | Who does it | What it does |
|---|---|---|
| Looking K moves ahead | The **search** | Plays out "I move, he replies, I move..." on copies of the board |
| Judging a board | The **heuristic** | Looks at **one board as it is** and returns **one number** |

`evaluate(board)` receives one board and returns one number, then it is finished. It knows nothing about other boards or levels. The **search** does the walking and the min/max backing up, depth-first, one branch at a time, holding only the current path in memory.

Example: computer is second player, K = 5.
```
depth 0  current board, computer's turn
depth 1  computer drops    (MAX)
depth 2  human replies     (MIN)
depth 3  computer drops    (MAX)
depth 4  human replies     (MIN)
depth 5  computer drops    -> STOP, call evaluate()
```
Without pruning that is 7 + 49 + 343 + 2,401 + 16,807 = 19,607 nodes, with up to **16,807 leaf boards**, and eval is called on each one separately. With alpha-beta (especially with center-first ordering) far fewer are visited. The nodes-expanded counter will give the real numbers for the report.

**The heuristic itself does not change with K.** Only the distance between the real board and the judged board changes. A better heuristic plus a larger K plays better.

### Heuristic design

A **weighted sum of features**, always from the computer's point of view (computer minus human). Look at every window of 4 cells; a window containing both colors is dead and worth nothing.

```
eval = w1 * (computer fours        - human fours)
     + w2 * (computer open threes  - human open threes)    # 3 discs + 1 empty
     + w3 * (computer open twos    - human open twos)      # 2 discs + 2 empty
     + w4 * (computer center discs - human center discs)
```

Worked example with w = (100, 10, 3, 2): computer 1 four vs 0, open threes 2 vs 1, open twos 4 vs 5, center discs 3 vs 1:
```
eval = 100*(1-0) + 10*(2-1) + 3*(4-5) + 2*(3-1) = 111
```
Positive means the computer is ahead.

```python
def evaluate(board, w=(100, 10, 3, 2)):
    score = 0
    for win in WINDOWS:
        cells = [board.grid[r][c] for r, c in win]
        ai, hu = cells.count(AI), cells.count(HUMAN)
        if ai and hu:
            continue                                  # dead window
        if   ai == 4: score += w[0]
        elif ai == 3: score += w[1]
        elif ai == 2: score += w[2]
        elif hu == 4: score -= w[0]
        elif hu == 3: score -= w[1]
        elif hu == 2: score -= w[2]
    for r in range(ROWS):                             # center column
        v = board.grid[r][COLS // 2]
        if v == AI:    score += w[3]
        elif v == HUMAN: score -= w[3]
    return score
```

Design notes:
- Fours already made carry the biggest weight (they count at the end).
- Keep eval on a scale compatible with utility so a guess is never mistaken for a final score.
- More features to test: threes that are immediately playable, odd/even row threats, column heights, mobility.

### Improving the heuristic: tuning by local search (extra work, bonus)

The weights were guessed. Local search (Lecture 5) can improve them by self-play. **State** = a weight vector. **Neighbor** = a small change to one weight. **Fitness** = result of N games (win rate or score difference).

| Method | Pros | Cons | Fit for us |
|---|---|---|---|
| Hill climbing | Simplest, cheapest, easy to explain | Local maxima, plateaus, noisy | Good baseline |
| **Random-restart hill climbing** | Fixes local maxima, still simple | A few full runs | **Best value for time** |
| Simulated annealing | Escapes local maxima | Needs a cooling schedule | Alternative |
| **Genetic algorithm** | In the course, explores widely, good report material | Most games needed; crossover helps little with about 5 weights | Good second method |
| Evolution strategy (1+lambda) | Very effective for numeric weights | Not in lectures | Strong practical choice |

**Verdict:** there is no universal winner. For about 5 numeric weights, noisy game-based fitness and 4 days, use **random-restart hill climbing as the main method** and a **genetic algorithm as the comparison**. Run both with the same game budget and pick the winner by a larger head-to-head match (for example 100 games).

**Rules for fair tuning:**
- The agent is deterministic, so use **random opening moves** and **alternate who goes first**.
- Evaluate against several opponents (random player, K=2 baseline, previous best) to avoid overfitting.
- **Train at low K (2 or 3)**, validate at higher K (5).
- Use multiprocessing and run long jobs in the background; time a K=3 game first to size the runs.
- Output: a fixed weight vector hard-coded in the final game.

---

## 1.5 Section 3: Deliverables and notes

**What the lab says:**
- Well-commented code.
- A report with: **sample runs and their minimax trees**, **analysis of time and nodes expanded by alpha-beta at different K values**, the **data structures and algorithms used**, **assumptions and details**, and **any extra work**.
- Use Java, Python, or C++. Copied assignments are severely penalized. Groups of 2 are allowed.

**What it means for us:**
- Comment every class and function (what it does, inputs, outputs).
- Report outline: (1) problem and special rule, (2) mapping to minimax, (3) data structures, (4) algorithms (minimax, alpha-beta, cutoff, ordering), (5) heuristic design, (6) tuning and results, (7) sample runs with trees, (8) time and nodes vs K, (9) GUI and extra work, (10) assumptions, (11) conclusion.
- Language: **Python** proposed.
- Original work only. The GUI uses original art; the Brawlhalla-inspired style means a similar feel, **not** the game's official art, characters, logos, or audio (copyrighted, and copying is penalized).

---

## 1.6 Bonuses (we go for all)

| Bonus | What we do |
|---|---|
| GUI for the game | Brawlhalla-inspired look (design discussed in a separate `GUI_Plan.md`) |
| Tree shown in the GUI | Tree panel with values, alpha/beta, pruned branches |
| Best-3 heuristic | Multi-factor heuristic, tuned and validated by tournaments |

---

# 2. Mapping to our lectures

| Lecture | Topic | What we take from it | Where it appears in the project |
|---|---|---|---|
| **2.1 Intelligent Agents** | Agents, PEAS, environment types, agent types | Our program is an agent that perceives (reads the board), thinks (minimax), acts (drops a disc). It is a **utility-based agent**. | Report intro, PEAS, `AIPlayer` |
| **4 Informed Search** | Heuristics, greedy, A\*, admissibility | Only the **idea of a heuristic** (a number estimating how good a state is). A\*, f = g + h, and admissibility do **not** apply. | `evaluate(board)` |
| **5 Local Search** | Hill climbing and variants, local beam, genetic algorithms | Tune the heuristic weights: state = weight vector, neighbor = small change, fitness = game results. | Tuning (extra work) |
| **6 Adversarial Search** (main) | Zero-sum games, minimax, alpha-beta, move ordering, real-time cutoff | **The core algorithm**: minimax, alpha-beta, cutoff at depth K with eval, move ordering. | `alphabeta`, K, ordering, tree |

### PEAS (for the report)

- **Performance:** number of connected-fours (computer minus human)
- **Environment:** the Connect 4 board, 7x6, two players
- **Actuators:** dropping a disc into a column
- **Sensors:** reading the board state

Environment type (like the Chess row in Lecture 2.1): fully observable, multi-agent, deterministic, (semi) static, discrete.

### Mapping the Connect 4 world to minimax

| Minimax concept | Connect 4 equivalent | In code |
|---|---|---|
| State | Board + whose turn | `Board` |
| Initial state | The current board on the computer's turn | `game.board` |
| Player to move | MAX = computer (2), MIN = human (1) | `maximizing` flag |
| Actions(s) | Columns that aren't full | `valid_moves()` |
| Result(s, a) | Drop a disc in column `a` | `drop(col, player)` |
| Terminal test | Board full **or** depth == K | `is_full()`, `depth == k` |
| Utility(s) | Computer's fours minus human's fours (exact) | `score()` |
| Eval(s) | Heuristic estimate at the cutoff | `evaluate(board)` |
| Branching factor | Up to 7 | |
| Node | A board reached by a sequence of moves | `TreeNode` |
| Expansion | Generating a node's children (we count them) | `stats.nodes` |
| Output | The best column | `(value, best_col)` |

### Why the path-finding terms (Lectures 3 and 4) mostly don't apply

BFS and A\* solve single-agent problems: find a path from a start state to a goal state with minimum cost. Connect 4 has two opposing players and no single goal.

| Search term | In our minimax |
|---|---|
| Initial state | Yes: the current board |
| Goal state | No: a **terminal test** (board full or depth K) instead |
| Path / path cost g(n) | No: we only need the best first move; **utility** replaces cost |
| Heuristic h(n) | Yes, as the **evaluation function** (admissibility does not apply) |
| Frontier / explored set | No: depth-first recursion, the call stack is the frontier |
| Expansion | Yes, as the **nodes counter** the report needs |

---

# 3. Main features and task split

**Person A (you) begins:** you build the **board and its initialization first** (everything else depends on it), then the **GUI**. **Person B (partner)** builds the **search, heuristic, and tuning**.

## 3.1 Interface contract (agree on Day 1)

So both can work in parallel, we agree on these before coding:

```python
# Person A provides (you)
ROWS, COLS, EMPTY, HUMAN, AI      # constants
WINDOWS                           # the 69 windows of 4 cells
Board                             # drop(col, player), valid_moves(), is_full(),
                                  # count_fours(player), score(), grid
Game                              # K input, turn loop, winner (console and GUI)

# Person B provides (partner)
evaluate(board) -> int            # heuristic, computer minus human, bigger = better for computer
AIPlayer.choose_move(board, k) -> SearchResult

@dataclass
class TreeNode:
    col: int | None            # move that led here (None at root)
    player: str                # "MAX" or "MIN"
    depth: int
    value: float | None        # backed-up value, or eval/score at a leaf
    alpha: float
    beta: float
    leaf_kind: str | None      # "eval", "terminal", or None
    pruned_cols: list[int]     # columns skipped by pruning
    children: list["TreeNode"]
    board: Board | None        # kept at leaves for display

@dataclass
class SearchResult:
    best_col: int
    value: float
    root: TreeNode
    nodes_expanded: int
    time_sec: float
```

- **Person B** starts with a stub `Board` until yours is ready (your Board is due early on Day 1).
- **You** test the GUI with a stub `AIPlayer` that picks a random valid column and returns a small fake `TreeNode`, until B's search is ready.

## 3.2 Person A (you): Board, Initialization, GUI

| ID | Feature | Difficulty | Est. (h) | Status |
|---|---|---|---|---|
| A1 | **Board and data initialization**: constants, tuple-of-tuples grid, `drop`, `valid_moves`, `is_full`, console display. **Do this first; B depends on it.** | Easy | 2 | [ ] |
| A2 | **Counting fours**: build the 69-window `WINDOWS` list, `count_fours`, `score()` (utility) | Easy | 2 | [ ] |
| A3 | **Game loop**: ask for K, human and computer turns, winner announcement; console version first, same loop reused by the GUI | Easy | 2 | [ ] |
| A4 | **GUI (Brawlhalla-inspired)**: start screen (K, who starts), board, click input, drop animation, score panel, winner screen; search runs without freezing the window | Medium | 8 | [ ] |
| A5 | **Tree in the GUI**: panel showing values, alpha/beta, `LEAF` / `TERMINAL` labels, pruned branches (start with a simple scrollable tree) | Medium to hard | 6 | [ ] |
| A6 | **Unit tests**: board rules, four counting on hand-made boards | Easy | 2 | [ ] |
| A7 | **Report sections**: board and data structures, GUI, assumptions, sample screenshots | Easy | 4 | [ ] |

**Total about 26 h.**

## 3.3 Person B (partner): Search, Heuristic, Tuning

| ID | Feature | Difficulty | Est. (h) | Status |
|---|---|---|---|---|
| B1 | **Minimax with alpha-beta and cutoff**: depth K, terminal-first check, node counter, timer | Medium | 3 | [ ] |
| B2 | **Tree data and console printer**: `TreeNode`, `SearchResult`, indentation, `LEAF eval` / `TERMINAL score` labels, pruned columns, print depth limit, file output | Medium | 3 | [ ] |
| B3 | **Move ordering**: center-first, then wins/blocks | Easy | 1.5 | [ ] |
| B4 | **Heuristic `evaluate`**: window features (fours, open threes, open twos, center), weight vector, hand-made board tests; at least 2 versions to compare | Medium | 5 | [ ] |
| B5 | **Match runner and experiments**: computer-vs-computer runner (random openings, alternate starts), time and nodes per K, with/without pruning, with/without ordering | Medium | 4 | [ ] |
| B6 | **Weight tuning**: random-restart hill climbing, then genetic algorithm, final head-to-head validation | Medium to hard | 6 | [ ] |
| B7 | **Report sections**: minimax, alpha-beta, ordering, tree printing, heuristic, tuning, experiments | Easy | 4 | [ ] |

**Total about 26.5 h.**

## 3.4 Shared

- [ ] Day 1: agree the contract (3.1), board size and assumptions (section 4).
- [ ] Shared Git repo, merge at least once a day; short daily sync.
- [ ] Cross-review each other's code and comments.
- [ ] Integration: plug B's `AIPlayer` into A's `Game` and GUI.
- [ ] Final test: a full game in console and in the GUI.
- [ ] Final report assembly and proofreading by both.

## 3.5 Timeline

| Day | Person A (you) | Person B (partner) | Checkpoint |
|---|---|---|---|
| **Sat Nov 21** | **A1, A2 first (hand the Board to B early)**, A3, GUI tech and theme | Agree contract, B1 with a stub board, start B4 | Board and four counting correct |
| **Sun Nov 22** | A6, A4 (start screen, board, input) | B1, B2, B3, B4 | Console game with minimax and printed tree |
| **Mon Nov 23** | A4 (animation, score, winner), start A5, integrate B's `AIPlayer` | B5, start B6 (run tuning in the background) | GUI plays full games against the real AI |
| **Tue Nov 24** | A5, A7, screenshots and sample runs | B6, validation, B7 | Final weights locked; experiments and report drafted |
| **Wed Nov 25 (due)** | Final checks and submit | Final checks and submit | **Buffer day, no new features** |

**Risks:** the Board is the first dependency (finish it early on Day 1); Python can be slow at high K (ordering, low K for tuning, multiprocessing); the GUI can freeze during search (run it in a thread); the tree panel can overrun (ship a simple version first); copyrighted assets (use original art).

---

# 4. Assumptions

| # | Topic | Assumption |
|---|---|---|
| 1 | Language | Python (pygame for the GUI); to confirm |
| 2 | Board size | 7 columns x 6 rows |
| 3 | Colors and players | Human = 1, Computer = 2; computer is MAX, human is MIN |
| 4 | Who plays first | Chosen on the start screen (default: human) |
| 5 | End of game | Only when the board is **full**; a four does not end the game |
| 6 | Counting fours | Every window of 4 counts, so overlaps count (5 in a row = 2 fours) |
| 7 | Winner | More fours wins; equal fours is a draw |
| 8 | Utility | Computer's fours minus human's fours at a full board |
| 9 | K | Entered once before the game, used every computer turn |
| 10 | Level counting | One move = one level; the root is depth 0; K levels below the root |
| 11 | Terminal vs cutoff | A full board returns utility; otherwise depth K returns eval. Terminal is checked first |
| 12 | Eval perspective | Always computer minus human; larger = better for the computer |
| 13 | Move ordering | Center-first by default (`3,2,4,1,5,0,6`) |
| 14 | Tree printing | Every computer turn, with a print depth limit and optional file output |
| 15 | Search each turn | Fresh search from the current board; only the first move is played |
| 16 | Tuning | Weights tuned offline by self-play; final weights are fixed in the submitted game |
| 17 | GUI art | Original, Brawlhalla-inspired style; no official assets |
| 18 | Team | Group of 2 |

---

# 5. Main comparisons

These form the report's analysis and extra-work sections.

| # | Comparison | How to measure | What we expect to show |
|---|---|---|---|
| C1 | **Time and nodes vs K** (required) | K = 1 to 6 (or 7): average time per move and nodes expanded, with alpha-beta | Growth is exponential in K |
| C2 | **Alpha-beta vs plain minimax** | Nodes and time at small K (for example 1 to 4) | Same chosen move, far fewer nodes |
| C3 | **Move ordering** | Left-to-right vs center-first: nodes at each K | Center-first prunes more; closer to O(b^(m/2)) |
| C4 | **Strength vs K** | Win rate / fours difference of K vs a baseline (K=1 or a random player) over many games | Larger K generally plays better, with diminishing returns |
| C5 | **Odd vs even K** | Compare results at K = 3, 4, 5, 6 | Possible parity effect from the last level being the computer's or the human's |
| C6 | **Heuristic versions** | Head-to-head games between version 1, version 2, and tuned weights (same K) | The tuned multi-factor heuristic wins |
| C7 | **Hill climbing vs genetic algorithm** | Same game budget; final strength by a 100-game head-to-head; number of games used | Pick the better method with data |
| C8 | **Hand-picked vs tuned weights** | Table of weight vectors and match results | Tuning improves strength |
| C9 | **Utility vs eval leaves** | Count of `TERMINAL` vs `LEAF` leaves as the board fills up | Terminal leaves appear near the end of the game |

**Table template for C1 and C4:**

| K | Avg time per move (s) | Avg nodes expanded | Win rate vs baseline |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |
| 6 | | | |

---

*Next file: `GUI_Plan.md` (Brawlhalla-inspired GUI design).*
