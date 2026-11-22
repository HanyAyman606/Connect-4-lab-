import unittest

from core.board import Board
from core.rules import Rules, build_windows
from helpers import RED, YELLOW, board_from

EMPTY_ROWS = ["......."] * 6


def with_rows(**changes):
    rows = list(EMPTY_ROWS)
    for index, text in changes.items():
        rows[int(index[1:])] = text
    return board_from(rows)


class RulesTests(unittest.TestCase):
    def setUp(self):
        self.rules = Rules(6, 7, 4)

    def test_window_counts(self):
        self.assertEqual(len(build_windows(6, 7, 4)), 69)
        self.assertEqual(len(build_windows(5, 5, 4)), 28)
        self.assertEqual(len(self.rules.windows), 69)

    def test_windows_stay_inside_the_board(self):
        for window in self.rules.windows:
            self.assertEqual(len(window), 4)
            for row, col in window:
                self.assertTrue(0 <= row < 6 and 0 <= col < 7)

    def test_empty_board_has_no_fours(self):
        board = Board(6, 7)
        self.assertEqual(self.rules.count_fours(board, RED), 0)
        self.assertEqual(self.rules.count_fours(board, YELLOW), 0)

    def test_horizontal(self):
        board = with_rows(r5="XXXX...")
        self.assertEqual(self.rules.count_fours(board, RED), 1)
        self.assertEqual(self.rules.count_fours(board, YELLOW), 0)

    def test_vertical(self):
        rows = list(EMPTY_ROWS)
        for index in range(2, 6):
            rows[index] = "X......"
        self.assertEqual(self.rules.count_fours(board_from(rows), RED), 1)

    def test_diagonal_up_right(self):
        board = board_from([".......", ".......", "...X...", "..X....", ".X.....", "X......"])
        self.assertEqual(self.rules.count_fours(board, RED), 1)

    def test_diagonal_down_right(self):
        board = board_from([".......", ".......", "X......", ".X.....", "..X....", "...X..."])
        self.assertEqual(self.rules.count_fours(board, RED), 1)

    def test_overlapping_fours_all_count(self):
        self.assertEqual(self.rules.count_fours(with_rows(r5="XXXXX.."), RED), 2)
        self.assertEqual(self.rules.count_fours(with_rows(r5="XXXXXX."), RED), 3)
        self.assertEqual(self.rules.count_fours(with_rows(r5="XXXXXXX"), RED), 4)

    def test_three_in_a_row_is_not_a_four(self):
        self.assertEqual(self.rules.count_fours(with_rows(r5="XXX...."), RED), 0)

    def test_mixed_window_is_not_a_four(self):
        self.assertEqual(self.rules.count_fours(with_rows(r5="XXOX..."), RED), 0)

    def test_score_is_the_difference(self):
        board = with_rows(r4="OOOO...", r5="XXXXX..")
        self.assertEqual(self.rules.score(board, RED, YELLOW), 1)
        self.assertEqual(self.rules.score(board, YELLOW, RED), -1)

    def test_empty_disc_cannot_be_counted(self):
        from core.disc import EMPTY_DISC
        with self.assertRaises(ValueError):
            self.rules.count_fours(Board(6, 7), EMPTY_DISC)

    def test_validation(self):
        for args in ((0, 7), (6, 0), (3, 3, 4), (6, 7, 1)):
            with self.assertRaises(ValueError):
                Rules(*args)

    def test_other_connect_length(self):
        rules = Rules(6, 7, 3)
        self.assertEqual(rules.count_fours(with_rows(r5="XXX...."), RED), 1)


if __name__ == "__main__":
    unittest.main()
