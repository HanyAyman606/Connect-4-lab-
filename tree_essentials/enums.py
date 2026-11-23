"""Enumerations shared by the search, the tree printer and the GUI.

They live in their own module so that every other module (node, recorder,
printer, search, GUI) can import them without importing each other.
"""

from enum import Enum


class Role(Enum):
    """Who moves from a position.

    MAX is the computer (it picks the highest value); MIN is the human (it
    picks the lowest). The role belongs to the *position*, so the children of
    a MAX node are MIN nodes and vice versa.
    """

    MAX = "MAX"
    MIN = "MIN"

    @property
    def opposite(self) -> "Role":
        """The role of the next position down the tree."""
        return Role.MIN if self is Role.MAX else Role.MAX


class LeafKind(Enum):
    """Why the search stopped at a node (and where its value came from)."""

    EVAL = "eval"          # depth K reached, game not over: heuristic estimate
    TERMINAL = "terminal"  # board is full: exact utility (fours difference)
    CACHED = "cached"      # value reused from a transposition table


class Bound(Enum):
    """How much a node's value can be trusted (fail-soft alpha-beta).

    EXACT: the value is the true minimax value of the node.
    LOWER: the true value is at least the stored value ("value >= v").
    UPPER: the true value is at most the stored value ("value <= v").

    Lecture 6 writes these as "= 4", ">= 6" and "<= 2" next to the nodes.
    """

    EXACT = "exact"
    LOWER = "lower"
    UPPER = "upper"

    @property
    def symbol(self) -> str:
        """The comparison symbol used when printing: '=', '>=' or '<='."""
        return _BOUND_SYMBOLS[self]


_BOUND_SYMBOLS = {Bound.EXACT: "=", Bound.LOWER: ">=", Bound.UPPER: "<="}
