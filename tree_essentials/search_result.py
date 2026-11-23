"""SearchResult: everything one search hands back to the game, the printer,
the GUI and the experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from tree_essentials.formatting import format_number
from tree_essentials.node import TreeNode
from tree_essentials.search_stats import SearchStats


@dataclass(frozen=True, slots=True, eq=False)
class SearchResult:
    """The outcome of one search.

    best_column ..... the column to play (None if there was no legal move).
    value ........... the backed-up value of the root.
    k ............... the depth limit that was used.
    algorithm ....... a short name such as "alpha-beta" or "minimax".
    stats ........... the counters (see SearchStats for the definitions).
    root ............ the recorded tree, or None when recording was off.
    tree_truncated .. True when recording limits hid part of the tree.
    """

    best_column: Optional[int]
    value: float
    k: int
    algorithm: str
    stats: SearchStats
    root: Optional[TreeNode] = None
    tree_truncated: bool = False

    @property
    def has_tree(self) -> bool:
        return self.root is not None

    @property
    def time_sec(self) -> float:
        return self.stats.elapsed

    @property
    def nodes_visited(self) -> int:
        return self.stats.visited

    @property
    def nodes_expanded(self) -> int:
        return self.stats.expanded

    @property
    def principal_columns(self) -> Tuple[int, ...]:
        """The line of play the search expects (needs the recorded tree).
        Without a tree it is just the chosen column."""
        if self.root is not None:
            return self.root.principal_columns()
        return () if self.best_column is None else (self.best_column,)

    def summary(self) -> str:
        """One readable line describing the search."""
        return (f"{self.algorithm} K={self.k} best_column={self.best_column} "
                f"value={format_number(self.value)} {self.stats.summary()}")

    def to_row(self) -> dict:
        """A flat dictionary for experiment tables (CSV-friendly)."""
        row = {"algorithm": self.algorithm, "k": self.k,
               "best_column": self.best_column, "value": self.value}
        row.update(self.stats.as_dict())
        return row
