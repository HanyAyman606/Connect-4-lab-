"""tree_essentials: what a search records and how it is shown.

This package holds the *data* of a search (nodes, counters, results), the
*recorder* the search talks to, and the *printer* that shows or exports the
tree. It never runs a search itself, so any algorithm (plain minimax,
alpha-beta, ...) can reuse it. It depends only on `core` (and only for typing).

Columns are 0-based everywhere in this package; the GUI maps them to what the
user sees.
"""

from tree_essentials.enums import Bound, LeafKind, Role
from tree_essentials.formatting import format_columns, format_number
from tree_essentials.node import TreeNode
from tree_essentials.search_recorder import (
    NULL_RECORDER,
    NullRecorder,
    SearchRecorder,
    TreeRecorder,
    create_recorder,
)
from tree_essentials.search_result import SearchResult
from tree_essentials.search_stats import SearchStats
from tree_essentials.tree_printer import PrintOptions, TreePrinter

__all__ = [
    "Bound", "LeafKind", "Role",
    "format_columns", "format_number",
    "TreeNode",
    "NULL_RECORDER", "NullRecorder", "SearchRecorder", "TreeRecorder", "create_recorder",
    "SearchResult", "SearchStats",
    "PrintOptions", "TreePrinter",
]
