"""Game builder: builds the board, resolves a random first player, and wires everything into a session."""

from __future__ import annotations

import random

from core.game import Game
from core.owner import Owner
from core.rules import Rules
from options.first_player import FIRST_COMPUTER, FIRST_HUMAN
from setup.game_session import GameSession
from setup.player_factory import create_players
from setup.session_settings import SessionSettings
from setup.settings_validation import validate_settings


def build_session(settings: SessionSettings) -> GameSession:
    """Validate settings, resolve who moves first, and return a ready ``GameSession``."""
    validate_settings(settings)
    human, computer = create_players(settings)
    rules = Rules(
        rows=settings.rows,
        cols=settings.cols,
        connect_length=settings.connect_length,
    )

    if settings.first_player == FIRST_HUMAN:
        first_owner = Owner.HUMAN
    elif settings.first_player == FIRST_COMPUTER:
        first_owner = Owner.COMPUTER
    else:
        rng = random.Random(settings.seed)
        first_owner = rng.choice((Owner.HUMAN, Owner.COMPUTER))

    game = Game(human=human, computer=computer, rules=rules, first=first_owner)
    return GameSession(game=game, settings=settings)
