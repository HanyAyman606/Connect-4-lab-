"""Player factory: creates the human and AI players and assigns their discs and colors."""

from __future__ import annotations

from typing import Iterable, Tuple

from algorithms.alpha_beta import AlphaBetaSearcher
from algorithms.ordering import (
    MoveOrderer,
    center_first,
    four_gain_center_first,
    tactical_center_first,
    threat_center_first,
)
from core.disc import Disc
from core.game import Game, GameState
from core.owner import Owner
from game.ai_player import AIPlayer
from game.player import Player
from heuristics.evaluation import HEURISTIC_MODELS
from setup.session_settings import SessionSettings


def left_to_right_ordering(
    game: Game, state: GameState, legal_columns: Iterable[int]
) -> Tuple[int, ...]:
    """Natural column order (0..6), useful for comparing against center-first."""
    return tuple(legal_columns)


ORDERING_MODELS: dict[str, MoveOrderer] = {
    "four_gain_center": four_gain_center_first,
    "center": center_first,
    "threat_center": threat_center_first,
    "tactical": tactical_center_first,
    "left_to_right": left_to_right_ordering,
}


class GUIHumanPlayer(Player):
    """Human player marker for event-driven GUI sessions (clicks drive moves)."""

    def get_move(self, game: Game, state: GameState) -> int:
        raise RuntimeError("GUIHumanPlayer moves are supplied interactively by UI events")


def create_players(settings: SessionSettings) -> tuple[GUIHumanPlayer, AIPlayer]:
    """Instantiate the human and AI players from validated session settings."""
    human_disc = Disc(Owner.HUMAN, settings.human_color)
    computer_disc = Disc(Owner.COMPUTER, settings.computer_color)

    evaluator = HEURISTIC_MODELS[settings.heuristic_key]
    orderer = ORDERING_MODELS[settings.ordering_key]
    searcher = AlphaBetaSearcher(evaluator=evaluator, move_orderer=orderer)

    human = GUIHumanPlayer(human_disc, "Spirit Bearer")
    computer = AIPlayer(
        disc=computer_disc,
        searcher=searcher,
        k=settings.k,
        name=settings.devil_name,
    )
    return human, computer
