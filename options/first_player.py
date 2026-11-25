"""First player: allowed choices (human, computer, random) and the default."""

from __future__ import annotations

FIRST_HUMAN: str = "human"
FIRST_COMPUTER: str = "computer"
FIRST_RANDOM: str = "random"

FIRST_PLAYER_CHOICES: tuple[str, ...] = (FIRST_HUMAN, FIRST_COMPUTER, FIRST_RANDOM)
DEFAULT_FIRST_PLAYER: str = FIRST_HUMAN

__all__ = [
    "FIRST_HUMAN",
    "FIRST_COMPUTER",
    "FIRST_RANDOM",
    "FIRST_PLAYER_CHOICES",
    "DEFAULT_FIRST_PLAYER",
]
