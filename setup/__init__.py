"""Setup package: builds a ready game from the start-screen choices. The only package that wires the others together."""

from setup.game_builder import build_session
from setup.game_session import GameSession, TurnRecord
from setup.player_factory import GUIHumanPlayer, ORDERING_MODELS, create_players
from setup.session_settings import SessionSettings
from setup.settings_validation import VALID_ORDERING_KEYS, validate_settings

__all__ = [
    "SessionSettings",
    "VALID_ORDERING_KEYS",
    "validate_settings",
    "GUIHumanPlayer",
    "ORDERING_MODELS",
    "create_players",
    "TurnRecord",
    "GameSession",
    "build_session",
]
