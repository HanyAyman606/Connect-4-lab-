from __future__ import annotations

from algorithms.alpha_beta import AlphaBetaSearcher
from core.disc import Disc
from core.game import Game, GameState
from core.owner import Owner
from game.player import Player
from tree_essentials import SearchResult


class AIPlayer(Player):

    #It receives the computer’s disc, an alpha-beta searcher, search depth k, and an optional display name.
    def __init__(self, disc: Disc, searcher: AlphaBetaSearcher, k: int,name: str = "Computer") -> None:
        #check that The disc belongs to Owner.COMPUTER.
        if disc.owner is not Owner.COMPUTER:
            raise ValueError("AIPlayer must own the COMPUTER disc")

        #check that The searcher is an AlphaBetaSearcher
        if not isinstance(searcher, AlphaBetaSearcher):
            raise TypeError("searcher must"
                            " be an AlphaBetaSearcher")

        #k is a positive integer. It specifically rejects True and False.
        if isinstance(k, bool) or not isinstance(k, int) or k < 1:
            raise ValueError("K must be a positive integer")

        #initialize the shared Player details.
        super().__init__(disc, name)

        #The AI saves the searcher and depth, and initializes last_search to None.
        self._searcher = searcher
        self._k = k
        self.last_search: SearchResult | None = None

    #lets other code read the AI’s search depth as computer.k without changing it.
    @property
    def k(self) -> int:
        return self._k

    #The game calls this when it’s the computer’s turn.
    def get_move(self, game: Game, state: GameState) -> int:

        #Checks that the current turn belongs to the computer.
        if game.to_move(state) is not Owner.COMPUTER:
            raise ValueError("it is not the computer's turn")

        #Runs alpha-beta at the saved depth, with record=True so the search tree is available
        #Saves the returned SearchResult in last_search.
        self.last_search = self._searcher.search(game, state, self._k, record=True)

        #If there is no chosen column in a non-terminal position, it raises an error rather than silently making an invalid move.
        if self.last_search.best_column is None:
            raise RuntimeError("alpha-beta returned no move in a non-terminal state")

        #Returns the best column, which is zero-based: column 0 is the first column.
        return self.last_search.best_column
