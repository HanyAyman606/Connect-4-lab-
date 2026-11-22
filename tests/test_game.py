import unittest

from core.board import Board
from core.game import Game, GameState
from core.owner import Owner
from core.player import Player
from core.rules import Rules
from helpers import RED, YELLOW, ScriptedPlayer, board_from


def make_game(first=Owner.HUMAN):
    return Game(ScriptedPlayer(RED, "Me"), ScriptedPlayer(YELLOW, "PC"), Rules(6, 7, 4), first)


class PlayerTests(unittest.TestCase):
    def test_player_is_abstract(self):
        with self.assertRaises(TypeError):
            Player(RED, "Me")

    def test_player_attributes(self):
        player = ScriptedPlayer(RED, "  Me ")
        self.assertEqual((player.name, player.owner, player.color), ("Me", Owner.HUMAN, "red"))
        self.assertIs(player.disc, RED)

    def test_player_validation(self):
        from core.disc import EMPTY_DISC
        with self.assertRaises(ValueError):
            ScriptedPlayer(EMPTY_DISC, "Me")
        with self.assertRaises(ValueError):
            ScriptedPlayer(RED, "  ")


class GameTests(unittest.TestCase):
    def test_initial_state(self):
        game = make_game()
        state = game.initial_state()
        self.assertEqual(game.to_move(state), Owner.HUMAN)
        self.assertEqual(game.actions(state), (0, 1, 2, 3, 4, 5, 6))
        self.assertFalse(game.is_terminal(state))
        self.assertEqual(make_game(Owner.COMPUTER).initial_state().turn, Owner.COMPUTER)

    def test_result_drops_the_right_disc_and_switches_turn(self):
        game = make_game()
        state = game.initial_state()
        after = game.result(state, 3)
        self.assertIs(after.board.cell(5, 3), RED)
        self.assertEqual(after.turn, Owner.COMPUTER)
        self.assertIs(game.result(after, 3).board.cell(4, 3), YELLOW)
        self.assertEqual(state.board, Board(6, 7))
        self.assertEqual(state.turn, Owner.HUMAN)

    def test_filling_the_board_ends_the_game_in_a_draw(self):
        game = make_game()
        state = game.initial_state()
        moves = 0
        while not game.is_terminal(state):
            state = game.result(state, game.actions(state)[0])
            moves += 1
        self.assertEqual(moves, 42)
        self.assertEqual(game.actions(state), ())
        self.assertEqual(game.fours(state, Owner.HUMAN), game.fours(state, Owner.COMPUTER))
        self.assertEqual(game.utility(state), 0)
        self.assertEqual(game.winner(state), Owner.EMPTY)

    def test_winner_and_utility_perspective(self):
        game = make_game()
        state = GameState(board_from(["XXXXXXX"] * 6), Owner.HUMAN)
        self.assertTrue(game.is_terminal(state))
        self.assertEqual(game.winner(state), Owner.HUMAN)
        self.assertEqual(game.utility(state), -69)
        self.assertEqual(game.utility(state, Owner.HUMAN), 69)
        state = GameState(board_from(["OOOOOOO"] * 6), Owner.HUMAN)
        self.assertEqual(game.winner(state), Owner.COMPUTER)

    def test_winner_needs_a_finished_game(self):
        game = make_game()
        with self.assertRaises(ValueError):
            game.winner(game.initial_state())

    def test_lookup_helpers(self):
        game = make_game()
        self.assertIs(game.disc_of(Owner.HUMAN), RED)
        self.assertIs(game.player_of(Owner.COMPUTER), game.computer)
        self.assertEqual(game.opponent(Owner.HUMAN), Owner.COMPUTER)
        self.assertEqual(game.opponent(Owner.COMPUTER), Owner.HUMAN)

    def test_validation(self):
        rules = Rules(6, 7, 4)
        with self.assertRaises(ValueError):
            Game(ScriptedPlayer(YELLOW, "Me"), ScriptedPlayer(YELLOW, "PC"), rules)
        with self.assertRaises(ValueError):
            Game(ScriptedPlayer(RED, "Me"), ScriptedPlayer(RED, "PC"), rules)
        with self.assertRaises(ValueError):
            Game(ScriptedPlayer(RED, "Me"), ScriptedPlayer(YELLOW, "PC"), rules, Owner.EMPTY)

    def test_state_is_hashable_and_comparable(self):
        game = make_game()
        first = game.result(game.initial_state(), 1)
        second = game.result(game.initial_state(), 1)
        self.assertEqual(first, second)
        self.assertEqual(len({first, second}), 1)


if __name__ == "__main__":
    unittest.main()
