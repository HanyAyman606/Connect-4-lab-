"""Session settings: plain data for what the user chose (K, first player, colors, optional seed)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from options.board_dimension import DEFAULT_COLS, DEFAULT_ROWS
from options.color_options import COMPUTER_COLOR_KEY, HUMAN_COLOR_KEY
from options.connect_length import DEFAULT_CONNECT_LENGTH
from options.first_player import DEFAULT_FIRST_PLAYER
from options.search_limits import DEFAULT_K


@dataclass(frozen=True, slots=True)
class SessionSettings:
    """Configuration chosen on the pre-fight screen before a match begins."""

    k: int = DEFAULT_K
    first_player: str = DEFAULT_FIRST_PLAYER
    heuristic_key: str = "windows"
    ordering_key: str = "four_gain_center"
    pruning_enabled: bool = True
    rows: int = DEFAULT_ROWS
    cols: int = DEFAULT_COLS
    connect_length: int = DEFAULT_CONNECT_LENGTH
    human_color: str = HUMAN_COLOR_KEY
    computer_color: str = COMPUTER_COLOR_KEY
    devil_name: str = "Shriek"
    console_trace: bool = True
    console_max_depth: Optional[int] = None
    seed: Optional[int] = None
