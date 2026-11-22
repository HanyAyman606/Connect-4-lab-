import unittest

from core.board import Board, InvalidMoveError
from core.disc import EMPTY_DISC
from helpers import RED, YELLOW, board_from


class BoardTests(unittest.TestCase):
    def test_new_board_is_empty(self):
        board = Board(6, 7)
        self.assertEqual((board.rows, board.cols), (6, 7))
        self.assertTrue(all(cell is EMPTY_DISC for row in board.grid for cell in row))
        self.assertEqual(board.valid_moves(), (0, 1, 2, 3, 4, 5, 6))
        self.assertFalse(board.is_full())

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            Board(0, 7)
        with self.assertRaises(ValueError):
            Board(6, -1)

    def test_drop_lands_on_bottom_and_stacks(self):
        board = Board(6, 7).drop(3, RED)
        self.assertIs(board.cell(5, 3), RED)
        board = board.drop(3, YELLOW)
        self.assertIs(board.cell(4, 3), YELLOW)
        self.assertEqual(board.lowest_empty_row(3), 3)

    def test_drop_does_not_change_the_original(self):
        board = Board(6, 7)
        board.drop(0, RED)
        self.assertIs(board.cell(5, 0), EMPTY_DISC)

    def test_full_column_is_not_a_valid_move(self):
        board = Board(6, 7)
        for _ in range(6):
            board = board.drop(2, RED)
        self.assertNotIn(2, board.valid_moves())
        self.assertFalse(board.is_valid_move(2))
        with self.assertRaises(InvalidMoveError):
            board.drop(2, RED)

    def test_outside_column_and_empty_disc_are_rejected(self):
        board = Board(6, 7)
        with self.assertRaises(InvalidMoveError):
            board.drop(7, RED)
        with self.assertRaises(InvalidMoveError):
            board.drop(-1, RED)
        with self.assertRaises(InvalidMoveError):
            board.drop(0, EMPTY_DISC)
        self.assertFalse(board.is_valid_move(7))

    def test_board_becomes_full(self):
        board = Board(2, 2)
        for col in (0, 0, 1, 1):
            board = board.drop(col, RED)
        self.assertTrue(board.is_full())
        self.assertEqual(board.valid_moves(), ())

    def test_equality_and_hash(self):
        first = Board(6, 7).drop(1, RED).drop(2, YELLOW)
        second = Board(6, 7).drop(1, RED).drop(2, YELLOW)
        self.assertEqual(first, second)
        self.assertEqual(hash(first), hash(second))
        self.assertNotEqual(first, Board(6, 7).drop(1, RED))
        self.assertEqual(len({first, second}), 1)

    def test_text_form(self):
        board = Board(2, 3).drop(0, RED).drop(0, YELLOW)
        self.assertEqual(str(board), "O . .\nX . .")
        self.assertEqual(str(board_from(["X.O", "XXO"])), "X . O\nX X O")


if __name__ == "__main__":
    unittest.main()
