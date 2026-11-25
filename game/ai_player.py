"""Computer player that chooses moves with depth-limited alpha-beta search."""

from __future__ import annotations

from algorithms.alpha_beta import AlphaBetaSearcher
from core.disc import Disc
from core.game import Game, GameState
from core.owner import Owner
from core.player import Player
from tree_essentials import SearchResult


class AIPlayer(Player):
    """A computer-controlled player with a fixed search depth K.

    The most recent result is kept so the caller can display its search tree
    and statistics after the AI chooses a move.
    """

    def __init__(self, disc: Disc, searcher: AlphaBetaSearcher, k: int,
                 name: str = "Computer") -> None:
        if disc.owner is not Owner.COMPUTER:
            raise ValueError("AIPlayer must own the COMPUTER disc")
        if not isinstance(searcher, AlphaBetaSearcher):
            raise TypeError("searcher must be an AlphaBetaSearcher")
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("K must be a positive integer")
        super().__init__(disc, name)
        self._searcher = searcher
        self._k = k
        self.last_search: SearchResult | None = None

    @property
    def k(self) -> int:
        return self._k

    def get_move(self, game: Game, state: GameState) -> int:
        """Run alpha-beta and return the selected zero-based column."""
        if game.to_move(state) is not Owner.COMPUTER:
            raise ValueError("it is not the computer's turn")
        self.last_search = self._searcher.search(game, state, self._k, record=True)
        if self.last_search.best_column is None:
            raise RuntimeError("alpha-beta returned no move in a non-terminal state")
        return self.last_search.best_column
