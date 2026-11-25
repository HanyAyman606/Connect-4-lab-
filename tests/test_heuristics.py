import unittest

from heuristics.evaluation import (
    evaluate,
    evaluate_gravity_aware,
    evaluate_gravity_threat,
    evaluate_nonlinear_window,
    evaluate_scoring_opportunities,
    explain_evaluation,
    explain_gravity_aware,
    explain_gravity_threat,
    explain_scoring_opportunities,
)
from helpers import board_from


class HeuristicTests(unittest.TestCase):
    def test_all_three_evaluators_score_an_empty_board_as_zero(self):
        board = board_from(["......."] * 6)

        self.assertEqual(evaluate(board), 0)
        self.assertEqual(evaluate_gravity_aware(board), 0)
        self.assertEqual(evaluate_gravity_threat(board), 0)
        self.assertEqual(evaluate_scoring_opportunities(board), 0)

    def test_all_three_evaluators_use_computer_minus_human_perspective(self):
        computer_board = board_from(["......."] * 5 + ["OOO...."])
        human_board = board_from(["......."] * 5 + ["XXX...."])

        for evaluator in (evaluate, evaluate_gravity_aware, evaluate_gravity_threat,
                          evaluate_scoring_opportunities):
            self.assertGreater(evaluator(computer_board), 0)
            self.assertLess(evaluator(human_board), 0)
            self.assertAlmostEqual(evaluator(computer_board), -evaluator(human_board))

    def test_window_heuristic_counts_an_open_three(self):
        board = board_from(["......."] * 5 + ["OOO...."])

        details = explain_evaluation(board)

        self.assertGreater(details.computer_open_threes, 0)
        self.assertEqual(details.human_open_threes, 0)
        self.assertGreater(details.value, 0)

    def test_gravity_aware_heuristic_prefers_playable_three(self):
        playable = board_from(["......."] * 5 + ["OOO...."])
        unsupported = board_from([
            ".......",
            ".......",
            ".......",
            "OOO....",
            "XXX....",
            "XXX....",
        ])

        playable_details = explain_gravity_aware(playable)
        unsupported_details = explain_gravity_aware(unsupported)

        self.assertGreater(playable_details.computer_open_threes,
                           unsupported_details.computer_open_threes)

    def test_scoring_opportunity_heuristic_finds_a_legal_four_making_move(self):
        board = board_from(["......."] * 5 + ["OOO...."])

        details = explain_scoring_opportunities(board)

        self.assertEqual(details.computer_scoring_moves, 1)
        self.assertEqual(details.computer_best_four_gain, 1)
        self.assertEqual(details.computer_total_four_gain, 1)
        self.assertEqual(details.human_scoring_moves, 0)

    def test_scoring_opportunity_counts_overlapping_fours_from_one_move(self):
        board = board_from(["......."] * 5 + ["OOO.OOO"])

        details = explain_scoring_opportunities(board)

        self.assertEqual(details.computer_scoring_moves, 1)
        self.assertEqual(details.computer_best_four_gain, 4)
        self.assertEqual(details.computer_total_four_gain, 4)

    def test_gravity_threat_heuristic_combines_accessibility_and_scoring_options(self):
        board = board_from(["......."] * 5 + ["OOO...."])

        details = explain_gravity_threat(board)

        self.assertGreater(details.computer_accessible_threes, 0)
        self.assertEqual(details.computer_scoring_moves, 1)
        self.assertEqual(details.human_scoring_moves, 0)
        self.assertGreater(details.value, 0)

    def test_nonlinear_window_heuristic_is_zero_on_empty_board_and_symmetric(self):
        empty = board_from(["......."] * 6)
        computer_board = board_from(["......."] * 5 + ["OOO...."])
        human_board = board_from(["......."] * 5 + ["XXX...."])

        self.assertEqual(evaluate_nonlinear_window(empty), 0)
        self.assertGreater(evaluate_nonlinear_window(computer_board), 0)
        self.assertAlmostEqual(
            evaluate_nonlinear_window(computer_board),
            -evaluate_nonlinear_window(human_board),
        )


if __name__ == "__main__":
    unittest.main()
