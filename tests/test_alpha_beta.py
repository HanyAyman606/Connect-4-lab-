import unittest

from algorithms.alpha_beta import AlphaBetaSearcher
from core.game import Game, GameState
from core.owner import Owner
from core.rules import Rules
from helpers import RED, YELLOW, ScriptedPlayer, board_from


class AlphaBetaTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(
            ScriptedPlayer(RED, "Human"),
            ScriptedPlayer(YELLOW, "Computer"),
            Rules(6, 7, 4),
            Owner.COMPUTER,
        )

    def test_default_searcher_prioritizes_a_four_making_move(self):
        searcher = AlphaBetaSearcher(lambda board: 0.0)
        state = GameState(board_from(["......."] * 5 + ["O.OO..."]),
                          Owner.COMPUTER)

        result = searcher.search(self.game, state, 1, record=False)

        self.assertEqual(result.best_column, 1)
        self.assertEqual(result.stats.expanded, 1)
        self.assertEqual(result.stats.evaluations, 7)
        self.assertIsNone(result.root)

    def test_full_board_uses_exact_utility_before_cutoff_evaluation(self):
        state = GameState(board_from(["XXXXXXX"] * 6), Owner.COMPUTER)
        searcher = AlphaBetaSearcher(
            lambda board: self.fail("heuristic must not score a terminal board")
        )

        result = searcher.search(self.game, state, 1)

        self.assertEqual(result.value, -69)
        self.assertIsNone(result.best_column)
        self.assertEqual(result.stats.terminal_leaves, 1)
        self.assertEqual(result.stats.evaluations, 0)


if __name__ == "__main__":
    unittest.main()
