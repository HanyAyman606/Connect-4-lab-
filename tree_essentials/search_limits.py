"""Rules for K, the search depth the user chooses before the game.

This module only *checks and describes* K. It never reads the keyboard and
never draws anything, so the GUI selector and the search entry point can both
share it.

* Hard rule ... K is a whole number of at least 1 (MIN_K). There is no maximum.
* Indicator ... for large K, `assess_k` returns a level (NORMAL, SLOW,
                VERY_SLOW), a worst-case node estimate and a message to show
                the user. The user is warned, never blocked.

The two thresholds are plain constants. Tune them once real timings of the
search are known.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

MIN_K = 1
SLOW_FROM_K = 9          # from this K on, the search may be slow in Python
VERY_SLOW_FROM_K = 12    # from this K on, it may take a very long time
DEFAULT_COLUMNS = 7      # branching factor of a standard board

__all__ = [
    "MIN_K", "SLOW_FROM_K", "VERY_SLOW_FROM_K", "InvalidKError", "KLevel",
    "KAssessment", "validate_k", "parse_k", "assess_k",
]


class InvalidKError(ValueError):
    """K is not a whole number of at least MIN_K."""


class KLevel(Enum):
    """How heavy a depth is expected to be."""

    NORMAL = "normal"
    SLOW = "slow"
    VERY_SLOW = "very slow"


@dataclass(frozen=True, slots=True)
class KAssessment:
    """The indicator for one K.

    k ................... the validated depth.
    level ............... NORMAL, SLOW or VERY_SLOW.
    estimated_nodes ..... upper bound on the positions visited without
                          pruning (every column playable at every level).
    reaches_game_end .... True when K covers every remaining move, so the
                          search is exact (only known if the number of moves
                          left was given).
    message ............. one line to show next to the K selector.
    """

    k: int
    level: KLevel
    estimated_nodes: int
    reaches_game_end: bool
    message: str

    @property
    def is_warning(self) -> bool:
        return self.level is not KLevel.NORMAL


def validate_k(k: object) -> int:
    """Return K if it is a whole number of at least MIN_K, else raise
    InvalidKError. Booleans are rejected on purpose (True is not a depth)."""
    if isinstance(k, bool) or not isinstance(k, int):
        raise InvalidKError(f"K must be a whole number of at least {MIN_K}")
    if k < MIN_K:
        raise InvalidKError(f"K must be at least {MIN_K}")
    return k


def parse_k(text: object) -> int:
    """Turn what the user typed into a valid K (for the console and GUI text
    fields). Surrounding spaces are ignored; anything else that is not a whole
    number of at least MIN_K raises InvalidKError."""
    if not isinstance(text, str):
        raise InvalidKError(f"K must be a whole number of at least {MIN_K}")
    cleaned = text.strip()
    if not cleaned.isdecimal():
        raise InvalidKError(f"K must be a whole number of at least {MIN_K}")
    return validate_k(int(cleaned))


def estimate_nodes(depth: int, columns: int = DEFAULT_COLUMNS) -> int:
    """Worst-case positions visited down to `depth` without pruning."""
    return sum(columns ** level for level in range(depth + 1))


def assess_k(k: int, columns: int = DEFAULT_COLUMNS,
             moves_left: Optional[int] = None) -> KAssessment:
    """Validate K and describe how heavy it is.

    columns ..... playable columns per level (7 on a standard board).
    moves_left .. empty cells on the board; when given, the search cannot go
                  deeper than this, so the estimate uses the smaller depth.
    """
    k = validate_k(k)
    depth = k if moves_left is None else min(k, moves_left)
    reaches_end = moves_left is not None and k >= moves_left
    nodes = estimate_nodes(depth, columns)

    if k >= VERY_SLOW_FROM_K:
        level = KLevel.VERY_SLOW
    elif k >= SLOW_FROM_K:
        level = KLevel.SLOW
    else:
        level = KLevel.NORMAL

    size = f"at most about {nodes:,} positions without pruning"
    if level is KLevel.NORMAL:
        message = f"K={k}: {size}."
    elif level is KLevel.SLOW:
        message = f"K={k} may be slow ({size}); alpha-beta pruning cuts this a lot."
    else:
        message = (f"K={k} may take a very long time per move ({size}); "
                   "consider a smaller K.")
    if reaches_end:
        message += " This reaches the end of the game, so the result is exact."
    return KAssessment(k, level, nodes, reaches_end, message)
