"""TreePrinter: shows a recorded tree in the console and exports it to a file.

The printer only reads. It never touches the search, and it walks the tree
with an explicit stack (no recursion), so it works for any tree size.

Output format (ASCII by default, so every console can show it):

    Search result ...                       <- header (only for a SearchResult)
    ROOT [MAX] value=+5 (a=-\u221e, b=+\u221e)
    |-- * col 2 [MIN] value=+5 (a=+4, b=+\u221e)
    |   |-- col 0 [MAX] value=+5 (a=+4, b=+5)
    |   |   |-- col 0 LEAF eval=+5
    |   |   \\-- col 1 LEAF eval=+4
    |   \\-- col 1 [MAX] value>=+7 (a=+4, b=+5)
    |       |-- col 0 LEAF eval=+7
    |       \\-- x pruned columns: 1
    \\-- col 0 [MIN] value<=+2 (a=+4, b=+\u221e)

Legend:  *  the move chosen at that node        = / >= / <=  exact value,
         lower bound, upper bound               x  pruned (never explored)
         a, b  alpha and beta on entry          LEAF eval  heuristic estimate
         TERMINAL score  exact result (board full)
         CACHED value  reused from a transposition table
Columns are 0-based. Infinite alpha/beta print as +\u221e / -\u221e and a missing
value prints as N/A.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Iterator, List, Optional, Tuple, Union

from tree_essentials.enums import LeafKind
from tree_essentials.formatting import format_columns, format_number
from tree_essentials.node import TreeNode
from tree_essentials.search_result import SearchResult

LEGEND = ("legend: * best move | = exact, >= lower bound, <= upper bound | "
          "x pruned | a,b = alpha,beta on entry")

_ASCII = ("|-- ", "\\-- ", "|   ", "    ")                 # branch, last, pipe, blank
_UNICODE = ("\u251c\u2500\u2500 ", "\u2514\u2500\u2500 ", "\u2502   ", "    ")


@dataclass(frozen=True, slots=True)
class PrintOptions:
    """How the tree is printed.

    max_depth .... do not print below this depth (None = print everything).
    show_window .. show alpha and beta on internal nodes (ignored for minimax,
                   where they do not exist).
    show_pruned .. show the "x pruned columns" line under a cutoff node.
    show_boards .. print the evaluated board under every leaf that kept one.
    mark_best .... put "*" in front of the move chosen at each node.
    ascii_only ... ASCII connectors (safe everywhere) instead of box drawing.
    """

    max_depth: Optional[int] = None
    show_window: bool = True
    show_pruned: bool = True
    show_boards: bool = False
    mark_best: bool = True
    ascii_only: bool = True

    def __post_init__(self) -> None:
        if self.max_depth is not None and self.max_depth < 0:
            raise ValueError("max_depth must be >= 0")


Printable = Union[TreeNode, SearchResult]


class TreePrinter:
    """Formats, prints and exports search trees."""

    def __init__(self, options: Optional[PrintOptions] = None) -> None:
        self._options = options or PrintOptions()
        connectors = _ASCII if self._options.ascii_only else _UNICODE
        self._branch, self._last, self._pipe, self._blank = connectors

    # -------------------------------------------------------------- one node
    def describe(self, node: TreeNode, is_best: bool = False) -> str:
        """The text of one node (without connectors); the GUI can reuse it."""
        label = "ROOT" if node.is_root else f"col {node.column}"
        if is_best:
            label = "* " + label
        if node.is_leaf:
            return f"{label} {self._leaf_text(node)}"
        text = f"{label} [{node.role.value}] value{node.bound.symbol}{format_number(node.value)}"
        if self._options.show_window and node.alpha is not None:
            text += f" (a={format_number(node.alpha)}, b={format_number(node.beta)})"
        return text

    @staticmethod
    def _leaf_text(node: TreeNode) -> str:
        value = format_number(node.value)
        if node.leaf_kind is LeafKind.EVAL:
            return f"LEAF eval={value}"
        if node.leaf_kind is LeafKind.TERMINAL:
            return f"TERMINAL score={value}"
        return f"CACHED value{node.bound.symbol}{value}"

    # ------------------------------------------------------------- the tree
    def lines(self, root: TreeNode) -> Iterator[str]:
        """Yield the tree line by line (depth-first, in exploration order)."""
        # Each stack entry: (node or note text, prefix, is_last, is_root, is_best).
        stack: List[Tuple[Union[TreeNode, str], str, bool, bool, bool]] = [
            (root, "", True, True, False)
        ]
        while stack:
            item, prefix, is_last, is_root, is_best = stack.pop()
            connector = "" if is_root else (self._last if is_last else self._branch)
            if isinstance(item, str):                       # a note line
                yield prefix + connector + item
                continue
            yield prefix + connector + self.describe(item, is_best)
            child_prefix = prefix if is_root else prefix + (self._blank if is_last else self._pipe)
            if self._options.show_boards and item.board is not None:
                for row in str(item.board).splitlines():
                    yield child_prefix + "  " + row
            entries = self._entries_below(item)
            for index in range(len(entries) - 1, -1, -1):   # reversed: stack pops in order
                entry, entry_is_best = entries[index]
                stack.append((entry, child_prefix, index == len(entries) - 1, False, entry_is_best))

    def _entries_below(self, node: TreeNode) -> List[Tuple[Union[TreeNode, str], bool]]:
        """The children and note lines printed under a node."""
        options = self._options
        children = node.children
        if options.max_depth is not None and node.depth >= options.max_depth and children:
            return [(f"... {len(children)} subtree(s) hidden by the print depth limit", False)]
        entries: List[Tuple[Union[TreeNode, str], bool]] = [
            (child, options.mark_best and node.best_column is not None
             and child.column == node.best_column)
            for child in children
        ]
        if options.show_pruned and node.pruned_columns:
            entries.append((f"x pruned columns: {format_columns(node.pruned_columns)}", False))
        if node.truncated:
            entries.append(("... deeper levels were not recorded", False))
        return entries

    # ------------------------------------------------------- result + output
    def result_lines(self, result: SearchResult) -> Iterator[str]:
        """Yield a header describing the search, then its tree."""
        stats = result.stats
        yield "Search result"
        yield f"  algorithm : {result.algorithm}"
        yield f"  K         : {result.k}"
        yield f"  best col  : {result.best_column}"
        yield f"  value     : {format_number(result.value)}"
        yield (f"  visited   : {stats.visited}   expanded: {stats.expanded}   "
               f"evaluations: {stats.evaluations}   terminal leaves: {stats.terminal_leaves}   "
               f"cache hits: {stats.cache_hits}")
        yield f"  cutoffs   : {stats.cutoffs}   pruned branches: {stats.pruned_branches}"
        yield f"  time      : {stats.elapsed:.4f} s"
        if result.tree_truncated:
            yield "  note      : recording was limited, some subtrees are not shown"
        yield f"  {LEGEND}"
        yield ""
        if result.root is None:
            yield "(the tree was not recorded)"
        else:
            yield from self.lines(result.root)

    def _lines_for(self, target: Printable) -> Iterator[str]:
        if isinstance(target, SearchResult):
            return self.result_lines(target)
        return self.lines(target)

    def render(self, target: Printable) -> str:
        """The whole output as one string (fine for small trees)."""
        return "\n".join(self._lines_for(target))

    def show(self, target: Printable, stream: Optional[IO[str]] = None,
             max_lines: Optional[int] = None) -> None:
        """Print to the console (or any stream), optionally stopping after
        `max_lines` lines so a huge tree cannot flood the screen."""
        stream = stream or sys.stdout
        for count, line in enumerate(self._lines_for(target), start=1):
            if max_lines is not None and count > max_lines:
                stream.write(f"... output stopped after {max_lines} lines "
                             "(use export() for the full tree)\n")
                return
            stream.write(line + "\n")

    def export(self, target: Printable, path: Union[str, Path], append: bool = False,
               title: Optional[str] = None) -> Path:
        """Write the output to a UTF-8 text file and return its path.

        append=True adds to an existing file (one section per turn); `title`
        is written first, which is handy to label each turn.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a" if append else "w", encoding="utf-8") as handle:
            if append and path.stat().st_size > 0:
                handle.write("\n")
            if title:
                handle.write(title + "\n" + "=" * len(title) + "\n")
            for line in self._lines_for(target):
                handle.write(line + "\n")
        return path