"""Small text helpers shared by the printer, the result summary and the GUI."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Union

Number = Union[int, float]

INFINITY_SYMBOL = "\u221e"      # the infinity sign
MISSING_TEXT = "N/A"            # shown when there is no value (yet)


def format_number(value: Optional[Number]) -> str:
    """Format a node value, alpha or beta for display.

    Integers and whole floats get an explicit sign ("+4", "-3"); zero is "0";
    other floats use two decimals; infinities print with the infinity sign
    ("+\u221e" / "-\u221e"); a missing value prints as "N/A".
    """
    if value is None:
        return MISSING_TEXT
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return f"+{INFINITY_SYMBOL}" if value > 0 else f"-{INFINITY_SYMBOL}"
        if not value.is_integer():
            return f"{value:+.2f}"
        value = int(value)
    return "0" if value == 0 else f"{value:+d}"


def format_columns(columns: Iterable[int]) -> str:
    """Format a list of columns as "1, 2, 5" (0-based, as stored)."""
    return ", ".join(str(column) for column in columns)