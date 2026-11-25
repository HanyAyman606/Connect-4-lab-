"""Options package: configuration data only. Depends on nothing."""

from options.board_dimension import DEFAULT_COLS, DEFAULT_ROWS, MIN_COLS, MIN_ROWS
from options.color_options import AVAILABLE_COLOR_KEYS, COMPUTER_COLOR_KEY, HUMAN_COLOR_KEY
from options.connect_length import DEFAULT_CONNECT_LENGTH
from options.first_player import (
    DEFAULT_FIRST_PLAYER,
    FIRST_COMPUTER,
    FIRST_HUMAN,
    FIRST_PLAYER_CHOICES,
    FIRST_RANDOM,
)
from options.search_limits import DEFAULT_K, MAX_SLIDER_K, MIN_K

__all__ = [
    "MIN_COLS",
    "MIN_ROWS",
    "DEFAULT_COLS",
    "DEFAULT_ROWS",
    "DEFAULT_CONNECT_LENGTH",
    "HUMAN_COLOR_KEY",
    "COMPUTER_COLOR_KEY",
    "AVAILABLE_COLOR_KEYS",
    "FIRST_HUMAN",
    "FIRST_COMPUTER",
    "FIRST_RANDOM",
    "FIRST_PLAYER_CHOICES",
    "DEFAULT_FIRST_PLAYER",
    "MIN_K",
    "MAX_SLIDER_K",
    "DEFAULT_K",
]
