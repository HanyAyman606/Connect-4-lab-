"""Recorders: how a search reports the tree it explores.

The search never builds nodes itself. It talks to a recorder:

    node = recorder.enter(column, role, depth, alpha, beta)   # entering a position
    ... decide whether it is a leaf ...
    recorder.leaf(node, kind, value, board)                   # a leaf: done
    ... or loop over the moves, calling enter / leaf / exit for each ...
    recorder.exit(node, value, best_column, pruned_columns)   # an internal node: done

Two recorders share this protocol, so the search has no `if recording`
checks (Liskov / Dependency Inversion):

* NullRecorder ... does nothing. Use it for timing experiments, so that the
                   measurements do not include the cost of building the tree.
* TreeRecorder ... builds the TreeNode tree. It keeps its own stack of open
                   nodes, so nodes need no parent link, and it can limit the
                   recording by depth and by number of nodes to bound memory.

A recorder handles one search; call `reset()` (or create a new one) before the
next. `enter` may return None (nothing recorded); pass that None back to
`leaf` / `exit` unchanged and they ignore it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterable, Optional

from tree_essentials.enums import Bound, LeafKind, Role
from tree_essentials.node import TreeNode

if TYPE_CHECKING:
    from core.board import Board


class SearchRecorder(ABC):
    """The protocol every recorder follows."""

    @abstractmethod
    def enter(self, column: Optional[int], role: Role, depth: int,
              alpha: Optional[float] = None, beta: Optional[float] = None
              ) -> Optional[TreeNode]:
        """A position is being entered. Returns a handle (or None)."""

    @abstractmethod
    def leaf(self, node: Optional[TreeNode], kind: LeafKind, value: float,
             board: Optional["Board"] = None, bound: Bound = Bound.EXACT) -> None:
        """The entered position is a leaf with this value."""

    @abstractmethod
    def exit(self, node: Optional[TreeNode], value: float, best_column: Optional[int],
             pruned_columns: Iterable[int] = ()) -> None:
        """The entered position is finished (an internal node)."""

    @property
    @abstractmethod
    def root(self) -> Optional[TreeNode]:
        """The recorded tree (None when nothing is recorded)."""

    @property
    def truncated(self) -> bool:
        """True when a limit hid part of the tree."""
        return False

    @property
    def recorded_nodes(self) -> int:
        """How many nodes were recorded."""
        return 0


class NullRecorder(SearchRecorder):
    """Records nothing. It has no state, so one shared instance is enough."""

    def enter(self, column, role, depth, alpha=None, beta=None):
        return None

    def leaf(self, node, kind, value, board=None, bound=Bound.EXACT):
        return None

    def exit(self, node, value, best_column, pruned_columns=()):
        return None

    @property
    def root(self) -> None:
        return None


NULL_RECORDER = NullRecorder()


class TreeRecorder(SearchRecorder):
    """Builds the tree of one search.

    max_depth ... record only nodes at this depth or above (None = no limit).
    max_nodes ... stop recording after this many nodes (None = no limit).
    Hidden parts are flagged: the parent node gets `truncated = True`.
    """

    def __init__(self, max_depth: Optional[int] = None,
                 max_nodes: Optional[int] = None) -> None:
        if max_depth is not None and max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if max_nodes is not None and max_nodes < 1:
            raise ValueError("max_nodes must be >= 1")
        self._max_depth = max_depth
        self._max_nodes = max_nodes
        self.reset()

    def reset(self) -> None:
        """Forget the recorded tree so the recorder can be reused."""
        self._root: Optional[TreeNode] = None
        self._open: list = []          # nodes entered but not yet closed
        self._count = 0
        self._truncated = False

    def _limit_reached(self, depth: int) -> bool:
        too_deep = self._max_depth is not None and depth > self._max_depth
        too_many = self._max_nodes is not None and self._count >= self._max_nodes
        return too_deep or too_many

    def enter(self, column, role, depth, alpha=None, beta=None):
        if self._limit_reached(depth):
            self._truncated = True
            if self._open:
                self._open[-1].truncated = True
            return None
        node = TreeNode(column, role, depth, alpha, beta)
        if self._open:
            self._open[-1].add_child(node)       # the open node is the parent
        elif self._root is None:
            self._root = node
        else:
            raise RuntimeError("this recorder already holds a tree; call reset() first")
        self._open.append(node)
        self._count += 1
        return node

    def _close(self, node: TreeNode) -> None:
        # Calls must be properly nested: the node closed is the innermost open one.
        if not self._open or self._open[-1] is not node:
            raise RuntimeError("recorder calls are out of order")
        self._open.pop()

    def leaf(self, node, kind, value, board=None, bound=Bound.EXACT):
        if node is None:
            return
        self._close(node)
        node.mark_leaf(kind, value, board, bound)

    def exit(self, node, value, best_column, pruned_columns=()):
        if node is None:
            return
        self._close(node)
        node.finish(value, best_column, pruned_columns)

    @property
    def root(self) -> Optional[TreeNode]:
        return self._root

    @property
    def truncated(self) -> bool:
        return self._truncated

    @property
    def recorded_nodes(self) -> int:
        return self._count

    @property
    def is_balanced(self) -> bool:
        """True when every entered node was closed (a sanity check after a search)."""
        return not self._open


def create_recorder(record: bool = True, max_depth: Optional[int] = None,
                    max_nodes: Optional[int] = None) -> SearchRecorder:
    """Choose a recorder: the shared NullRecorder when `record` is False,
    otherwise a new TreeRecorder with the given limits."""
    if not record:
        return NULL_RECORDER
    return TreeRecorder(max_depth, max_nodes)
