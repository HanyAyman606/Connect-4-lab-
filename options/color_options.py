"""Color options: the available disc color choices, stored as keys (RGB values live in ui/theme)."""

from __future__ import annotations

HUMAN_COLOR_KEY: str = "spirit_light"
COMPUTER_COLOR_KEY: str = "devil_ember"

AVAILABLE_COLOR_KEYS: tuple[str, ...] = (HUMAN_COLOR_KEY, COMPUTER_COLOR_KEY)

__all__ = ["HUMAN_COLOR_KEY", "COMPUTER_COLOR_KEY", "AVAILABLE_COLOR_KEYS"]
