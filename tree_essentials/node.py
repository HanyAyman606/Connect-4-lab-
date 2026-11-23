"""TreeNode: one position visited by a search.

A node is a whole board position plus the role (MAX or MIN) of whoever moves
from it. The root is the real position on the table; every other node is the
position after one column move from its parent, and `column` is that move.

What a node stores and why
--------------------------
* column / role / depth ........ where the node is and who moves.
* alpha, beta (on ENTRY) ....... the window the search received. Entry values
  are enough: they explain every cutoff and classify the value as exact or a
  bound. They are None for algorithms without a window (plain minimax).
* value, bound ................. the value passed back up, and how much to
  trust it (see enums.Bound).
* leaf_kind, board ............. why the search stopped here; the board is
  kept at leaves only, so the printer can show the evaluated position.
* best_column, pruned_columns .. the move chosen at this node, and the moves
  that were skipped by pruning (pruned moves never become nodes).
* children ..................... the explored moves, in exploration order.
* truncated .................... some descendants were not recorded (limits).

The node makes no decisions: the pruning rules live in the search.

Mutability
----------
A node is filled while the search runs (add_child / mark_leaf / finish) and is
read-only by convention afterwards. It defines no value-based equality, so it
keeps the default identity equality and identity hash: it is hashable (the GUI
can use nodes as dictionary keys to attach widgets) and two nodes are never
"equal" just because their fields match.

There is no parent link and no visited set: the search is a depth-first
recursion, so the call stack is the frontier. All traversals here are
iterative, so they cannot hit Python's recursion limit.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable, Iterator, Optional, Sequence, Tuple

from tree_essentials.enums import Bound, LeafKind, Role

if TYPE_CHECKING:
    from core.board import Board


class TreeNode:
    """One visited position of the search tree (see the module docstring)."""

    __slots__ = (
        "column", "role", "depth", "alpha", "beta",
        "value", "bound", "leaf_kind", "best_column",
        "pruned_columns", "children", "board", "truncated", "finished",
    )

    def __init__(self, column: Optional[int], role: Role, depth: int,
                 alpha: Optional[float] = None, beta: Optional[float] = None) -> None:
        if not isinstance(role, Role):
            raise TypeError("role must be a Role")
        if depth < 0:
            raise ValueError("depth cannot be negative")
        if (alpha is None) != (beta is None):
            raise ValueError("alpha and beta must be given together")
        self.column = column            # move that led here (None for the root)
        self.role = role                # who moves from this position
        self.depth = depth              # root = 0
        self.alpha = alpha              # window received on entry
        self.beta = beta
        self.value: Optional[float] = None
        self.bound = Bound.EXACT
        self.leaf_kind: Optional[LeafKind] = None
        self.best_column: Optional[int] = None
        self.pruned_columns: Tuple[int, ...] = ()
        self.children: list = []
        self.board: Optional["Board"] = None
        self.truncated = False          # some descendants were not recorded
        self.finished = False

    # ------------------------------------------------------------ filling it
    def add_child(self, child: "TreeNode") -> None:
        """Attach an explored child (called by the recorder, in order)."""
        if self.finished:
            raise RuntimeError("cannot add a child to a finished node")
        if child.depth != self.depth + 1:
            raise ValueError("a child must be exactly one level below its parent")
        self.children.append(child)

    def mark_leaf(self, kind: LeafKind, value: float, board: Optional["Board"] = None,
                  bound: Bound = Bound.EXACT) -> None:
        """Close the node as a leaf. A leaf value is exact unless a cached
        value says otherwise (pass the stored bound for CACHED leaves)."""
        if self.finished:
            raise RuntimeError("node is already finished")
        if self.children:
            raise RuntimeError("a leaf cannot have children")
        if not isinstance(kind, LeafKind):
            raise TypeError("kind must be a LeafKind")
        self.leaf_kind = kind
        self.value = value
        self.board = board
        self.bound = bound
        self.finished = True

    def finish(self, value: float, best_column: Optional[int],
               pruned_columns: Iterable[int] = ()) -> None:
        """Close the node as an internal node and classify its value.

        Classification rule (fail-soft alpha-beta):
        * no window (plain minimax) ............................ EXACT
        * every move explored, nothing pruned or unrecorded, and
          every child value exact ............................... EXACT
        * otherwise: a value at or below the entry alpha is only an UPPER
          bound, at or above the entry beta only a LOWER bound, and strictly
          inside the window it is EXACT.
        """
        if self.finished:
            raise RuntimeError("node is already finished")
        self.value = value
        self.best_column = best_column
        self.pruned_columns = tuple(pruned_columns)
        self.bound = self._classify(value)
        self.finished = True

    def _fully_explored(self) -> bool:
        """True when the value was computed from complete, exact information."""
        return (bool(self.children) and not self.truncated and not self.pruned_columns
                and all(child.bound is Bound.EXACT for child in self.children))

    def _classify(self, value: float) -> Bound:
        if self.alpha is None or self.beta is None:
            return Bound.EXACT
        if self._fully_explored():
            return Bound.EXACT
        if value <= self.alpha:
            return Bound.UPPER
        if value >= self.beta:
            return Bound.LOWER
        return Bound.EXACT

    # ------------------------------------------------------------ quick facts
    @property
    def is_root(self) -> bool:
        return self.column is None

    @property
    def is_leaf(self) -> bool:
        return self.leaf_kind is not None

    @property
    def is_max(self) -> bool:
        return self.role is Role.MAX

    @property
    def is_min(self) -> bool:
        return self.role is Role.MIN

    @property
    def has_cutoff(self) -> bool:
        """True when pruning skipped at least one move at this node."""
        return bool(self.pruned_columns)

    # -------------------------------------------------------------- traversal
    def iter_nodes(self) -> Iterator["TreeNode"]:
        """Yield this node and all descendants, pre-order, without recursion."""
        stack = [self]
        while stack:
            node = stack.pop()
            yield node
            stack.extend(reversed(node.children))

    def iter_with_path(self) -> Iterator[Tuple["TreeNode", Tuple[int, ...]]]:
        """Like iter_nodes, but also yield the columns played from this node."""
        stack = [(self, ())]
        while stack:
            node, path = stack.pop()
            yield node, path
            for child in reversed(node.children):
                stack.append((child, path + (child.column,)))

    def count_nodes(self) -> int:
        """Number of recorded nodes in this subtree (including this one)."""
        return sum(1 for _ in self.iter_nodes())

    def height(self) -> int:
        """Levels below this node (0 for a leaf)."""
        return max(node.depth for node in self.iter_nodes()) - self.depth

    def level_sizes(self) -> Tuple[int, ...]:
        """Recorded nodes per level, starting with this node (useful for layout)."""
        sizes: dict = {}
        for node in self.iter_nodes():
            sizes[node.depth - self.depth] = sizes.get(node.depth - self.depth, 0) + 1
        return tuple(sizes[level] for level in range(len(sizes)))

    # ---------------------------------------------------------------- lookups
    def child_for(self, column: int) -> Optional["TreeNode"]:
        """The explored child reached by `column`, or None (pruned / not recorded)."""
        for child in self.children:
            if child.column == column:
                return child
        return None

    def best_child(self) -> Optional["TreeNode"]:
        """The child the search chose at this node, or None."""
        if self.best_column is None:
            return None
        return self.child_for(self.best_column)

    def principal_variation(self) -> Tuple["TreeNode", ...]:
        """This node followed by the best child at each level: the line of play
        the search expects (the GUI can highlight it)."""
        line = [self]
        node = self
        while True:
            node = node.best_child()
            if node is None:
                return tuple(line)
            line.append(node)

    def principal_columns(self) -> Tuple[int, ...]:
        """The columns of the principal variation (without this node's own)."""
        return tuple(node.column for node in self.principal_variation()[1:])

    def find(self, path: Sequence[int]) -> Optional["TreeNode"]:
        """Follow a list of columns down from this node; None if it leaves the tree."""
        node: Optional[TreeNode] = self
        for column in path:
            node = node.child_for(column)
            if node is None:
                return None
        return node

    # ----------------------------------------------------------------- export
    def to_dict(self) -> dict:
        """A JSON-friendly copy of this subtree (built without recursion).

        Infinities become the strings "+inf" / "-inf" because JSON has no
        infinity; boards become lists of text rows.
        """
        root = self._summary()
        stack = [(self, root)]
        while stack:
            node, data = stack.pop()
            for child in node.children:
                child_data = child._summary()
                data["children"].append(child_data)
                stack.append((child, child_data))
        return root

    def _summary(self) -> dict:
        return {
            "column": self.column,
            "role": self.role.value,
            "depth": self.depth,
            "alpha": _json_number(self.alpha),
            "beta": _json_number(self.beta),
            "value": _json_number(self.value),
            "bound": self.bound.value,
            "leaf_kind": self.leaf_kind.value if self.leaf_kind else None,
            "best_column": self.best_column,
            "pruned_columns": list(self.pruned_columns),
            "truncated": self.truncated,
            "board": str(self.board).splitlines() if self.board is not None else None,
            "children": [],
        }

    def __repr__(self) -> str:
        where = "root" if self.is_root else f"col={self.column}"
        return f"TreeNode({where}, {self.role.value}, depth={self.depth}, value={self.value})"


def _json_number(value):
    """Make a number JSON-safe (infinities become strings)."""
    if isinstance(value, float) and math.isinf(value):
        return "+inf" if value > 0 else "-inf"
    return value
