import unittest

from algorithms.ordering import (
    center_first,
    four_gain_center_first,
    tactical_center_first,
    threat_center_first,
)
from core.game import Game, GameState
from core.owner import Owner
from core.rules import Rules
from helpers import RED, YELLOW, ScriptedPlayer, board_from


class OrderingTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(
            ScriptedPlayer(RED, "Human"),
            ScriptedPlayer(YELLOW, "Computer"),
            Rules(6, 7, 4),
            Owner.COMPUTER,
        )

    def test_center_ordering_starts_in_the_middle(self):
        state = self.game.initial_state()

        ordered = center_first(self.game, state, self.game.actions(state))

        self.assertEqual(ordered, (3, 2, 4, 1, 5, 0, 6))

    def test_four_gain_ordering_puts_a_scoring_move_before_the_center(self):
        board = board_from(["......."] * 5 + ["O.OO..."])
        state = GameState(board, Owner.COMPUTER)
        legal = self.game.actions(state)

        center_order = center_first(self.game, state, legal)
        tactical_order = four_gain_center_first(self.game, state, legal)

        self.assertEqual(center_order[0], 3)
        self.assertEqual(tactical_order[0], 1)

    def test_all_orderings_return_each_legal_move_once(self):
        state = self.game.initial_state()
        legal = self.game.actions(state)

        for orderer in (center_first, four_gain_center_first,
                        threat_center_first, tactical_center_first):
            ordered = orderer(self.game, state, legal)
            self.assertEqual(set(ordered), set(legal))
            self.assertEqual(len(ordered), len(legal))


if __name__ == "__main__":
    unittest.main()
