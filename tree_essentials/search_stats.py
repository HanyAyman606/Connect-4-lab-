"""SearchStats: the counters of one search (or of several, merged).

Definitions (state them in the report)
--------------------------------------
visited ........ every node the search entered: the root, internal nodes and
                 leaves (one per call of the search function).
expanded ....... nodes whose children were generated, i.e. the non-leaf nodes.
evaluations .... leaves scored by the heuristic (depth K reached).
terminal_leaves  leaves scored by the exact utility (board full).
cache_hits ..... leaves whose value came from a transposition table.
cutoffs ........ nodes where pruning skipped at least one move.
pruned_branches  total number of skipped moves over all cutoffs.
max_depth ...... deepest level reached (optional).
elapsed ........ seconds measured with start_timer / stop_timer.

Always: visited == expanded + evaluations + terminal_leaves + cache_hits.

The counters are plain public attributes on purpose: the search increments
them directly (`stats.visited += 1`), which is faster than calling a method
in the hot loop.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True, eq=False)
class SearchStats:
    """Mutable counters for a search (identity equality, like a node)."""

    visited: int = 0
    expanded: int = 0
    evaluations: int = 0
    terminal_leaves: int = 0
    cache_hits: int = 0
    cutoffs: int = 0
    pruned_branches: int = 0
    max_depth: int = 0
    elapsed: float = 0.0
    _started_at: Optional[float] = field(default=None, init=False, repr=False)

    @property
    def leaves(self) -> int:
        """All leaves, whatever the reason the search stopped there."""
        return self.evaluations + self.terminal_leaves + self.cache_hits

    def is_consistent(self) -> bool:
        """The invariant visited == expanded + leaves (handy in tests)."""
        return self.visited == self.expanded + self.leaves

    def start_timer(self) -> None:
        """Start (or restart) the stopwatch."""
        self._started_at = time.perf_counter()

    def stop_timer(self) -> float:
        """Add the time since start_timer to `elapsed` and return `elapsed`."""
        if self._started_at is None:
            raise RuntimeError("start_timer was not called")
        self.elapsed += time.perf_counter() - self._started_at
        self._started_at = None
        return self.elapsed

    def merge(self, other: "SearchStats") -> None:
        """Add another search's counters to this one (e.g. a whole game)."""
        self.visited += other.visited
        self.expanded += other.expanded
        self.evaluations += other.evaluations
        self.terminal_leaves += other.terminal_leaves
        self.cache_hits += other.cache_hits
        self.cutoffs += other.cutoffs
        self.pruned_branches += other.pruned_branches
        self.max_depth = max(self.max_depth, other.max_depth)
        self.elapsed += other.elapsed

    def reset(self) -> None:
        """Set every counter back to zero."""
        self.visited = self.expanded = self.evaluations = 0
        self.terminal_leaves = self.cache_hits = 0
        self.cutoffs = self.pruned_branches = self.max_depth = 0
        self.elapsed = 0.0
        self._started_at = None

    def as_dict(self) -> dict:
        """The counters as a flat dictionary (one row of an experiment table)."""
        return {
            "visited": self.visited,
            "expanded": self.expanded,
            "evaluations": self.evaluations,
            "terminal_leaves": self.terminal_leaves,
            "cache_hits": self.cache_hits,
            "cutoffs": self.cutoffs,
            "pruned_branches": self.pruned_branches,
            "max_depth": self.max_depth,
            "elapsed_sec": self.elapsed,
        }

    def summary(self) -> str:
        """One readable line for logs and console output."""
        return (f"visited={self.visited} expanded={self.expanded} "
                f"evaluations={self.evaluations} cutoffs={self.cutoffs} "
                f"time={self.elapsed:.4f}s")
