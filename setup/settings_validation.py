"""Settings validation: checks the user choices against the options limits."""

from __future__ import annotations

from heuristics.evaluation import HEURISTIC_MODELS
from options.board_dimension import MIN_COLS, MIN_ROWS
from options.color_options import AVAILABLE_COLOR_KEYS
from options.first_player import FIRST_PLAYER_CHOICES
from setup.session_settings import SessionSettings
from tree_essentials.search_limits import validate_k

VALID_ORDERING_KEYS: tuple[str, ...] = (
    "four_gain_center",
    "center",
    "threat_center",
    "tactical",
    "left_to_right",
)


def validate_settings(settings: SessionSettings) -> SessionSettings:
    """Validate all fields of ``SessionSettings`` and return it if valid."""
    validate_k(settings.k)
    if settings.rows < MIN_ROWS or settings.cols < MIN_COLS:
        raise ValueError(f"board must be at least {MIN_COLS}x{MIN_ROWS}")
    if settings.first_player not in FIRST_PLAYER_CHOICES:
        raise ValueError(f"first_player must be one of {FIRST_PLAYER_CHOICES}")
    if settings.heuristic_key not in HEURISTIC_MODELS:
        raise ValueError(f"unknown heuristic_key: {settings.heuristic_key!r}")
    if settings.ordering_key not in VALID_ORDERING_KEYS:
        raise ValueError(f"unknown ordering_key: {settings.ordering_key!r}")
    if settings.human_color not in AVAILABLE_COLOR_KEYS:
        raise ValueError(f"unknown human_color: {settings.human_color!r}")
    if settings.computer_color not in AVAILABLE_COLOR_KEYS:
        raise ValueError(f"unknown computer_color: {settings.computer_color!r}")
    if settings.human_color == settings.computer_color:
        raise ValueError("human and computer discs must use distinct colors")
    return settings
