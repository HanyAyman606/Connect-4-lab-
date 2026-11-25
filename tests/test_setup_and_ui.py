"""Unit tests for options, setup session wiring, and UI analytics helpers."""

from __future__ import annotations

import unittest

from algorithms.alpha_beta import AlphaBetaSearcher
from core.owner import Owner
from heuristics.evaluation import (
    HEURISTIC_MODELS,
    explain_evaluation,
    explain_gravity_aware,
    explain_scoring_opportunities,
)
from options import DEFAULT_COLS, DEFAULT_ROWS, FIRST_COMPUTER, FIRST_HUMAN
from setup import SessionSettings, build_session, validate_settings
from ui.devils import DEVIL_BY_ID, DEVILS
from ui.screens.result_screen import build_fight_summary
from ui.search_worker import (
    compute_tree_metrics,
    evaluate_board_detailed,
    find_completed_four_windows,
)
from ui.tree_trace_engine import build_tree_trace
from tests.helpers_tree import run as run_fixed_tree


class SetupAndUIAnalyticsTests(unittest.TestCase):
    def test_settings_validation_accepts_defaults_and_rejects_bad_values(self) -> None:
        settings = SessionSettings()
        self.assertIs(validate_settings(settings), settings)
        with self.assertRaises(ValueError):
            validate_settings(SessionSettings(rows=5, cols=7))
        with self.assertRaises(ValueError):
            validate_settings(SessionSettings(heuristic_key="unknown"))
        with self.assertRaises(ValueError):
            validate_settings(SessionSettings(human_color="spirit_light", computer_color="spirit_light"))

    def test_game_session_tracks_moves_and_ai_results(self) -> None:
        settings = SessionSettings(k=2, first_player=FIRST_HUMAN, console_trace=False)
        session = build_session(settings)
        self.assertEqual(session.max_turns, DEFAULT_ROWS * DEFAULT_COLS)
        self.assertIs(session.to_move, Owner.HUMAN)

        rec_h = session.apply_human_move(3)
        self.assertEqual(rec_h.turn_number, 1)
        self.assertEqual(rec_h.row, 5)
        self.assertIs(session.to_move, Owner.COMPUTER)

        searcher = AlphaBetaSearcher(HEURISTIC_MODELS[settings.heuristic_key])
        res = searcher.search(session.game, session.state, settings.k, record=True)
        self.assertIsNotNone(res.best_column)
        rec_ai = session.apply_ai_result(res.best_column, res)
        self.assertEqual(rec_ai.turn_number, 2)
        self.assertIs(session.to_move, Owner.HUMAN)

        summary = build_fight_summary(DEVIL_BY_ID["shriek"], session)
        self.assertEqual(summary.ai_turns, 1)
        self.assertEqual(summary.total_visited, res.stats.visited)

    def test_detailed_board_eval_matches_all_three_heuristics_exactly(self) -> None:
        session = build_session(SessionSettings(first_player=FIRST_COMPUTER, console_trace=False))
        board = session.state.board
        h_disc = session.game.disc_of(Owner.HUMAN)
        c_disc = session.game.disc_of(Owner.COMPUTER)
        board = board.drop(3, c_disc).drop(2, h_disc).drop(3, c_disc).drop(4, c_disc)

        b_win = explain_evaluation(board)
        b_grav = explain_gravity_aware(board)
        b_opp = explain_scoring_opportunities(board)

        for key, expected_raw, expected_val in (
            ("windows", b_win.raw_score, b_win.value),
            ("gravity", b_grav.raw_score, b_grav.value),
            ("opportunities", b_opp.raw_score, b_opp.value),
        ):
            rep = evaluate_board_detailed(board, key)
            self.assertAlmostEqual(rep.raw_score, expected_raw, places=6)
            self.assertAlmostEqual(rep.normalized_value, expected_val, places=6)
            row_sum = sum(r.contribution for r in rep.rows)
            self.assertAlmostEqual(row_sum, expected_raw, places=5)

    def test_completed_fours_and_tree_metrics(self) -> None:
        session = build_session(SessionSettings(k=2, console_trace=False))
        board = session.state.board
        h_disc = session.game.disc_of(Owner.HUMAN)
        for col in (0, 1, 2, 3, 4):  # 5 in a row -> 2 overlapping fours!
            board = board.drop(col, h_disc)
        hum_wins, comp_wins = find_completed_four_windows(board)
        self.assertEqual(len(hum_wins), 2)
        self.assertEqual(len(comp_wins), 0)

        searcher = AlphaBetaSearcher(HEURISTIC_MODELS["windows"])
        res = searcher.search(session.game, session.state, 2, record=True)
        met = compute_tree_metrics(res, session.state.board.valid_moves(), 7)
        self.assertEqual(len(met.root_moves), 7)
        self.assertEqual(met.alpha_cutoffs + met.beta_cutoffs, res.stats.cutoffs)
        self.assertEqual(len(DEVILS), 3)

    def test_sheet6_question_1b_trace_matches_model_answer_exactly(self) -> None:
        # Sheet 6 Question 1b tree: MAX at A; MIN at B(3,12,8), C(2,4,6), D(14,5,2)
        res = run_fixed_tree(((3, 12, 8), (2, 4, 6), (14, 5, 2)))
        bundle = build_tree_trace(res.root)
        # 11 visited nodes: A, B, b1, b2, b3, C, c1 (c2,c3 pruned!), D, d1, d2, d3
        self.assertEqual(len(bundle.trace_rows), 11)
        row_a = bundle.trace_rows[0]
        self.assertEqual((row_a.old_alpha, row_a.new_alpha, row_a.old_beta, row_a.new_beta, row_a.new_value), ("−∞", "+3", "+∞", "+∞", "+3"))
        row_c = bundle.trace_rows[5]
        self.assertEqual((row_c.node_type, row_c.old_alpha, row_c.new_beta, row_c.new_value), ("MIN", "+3", "+2", "+2"))
        self.assertIn("cutoff: v ≤ α", row_c.note)
        self.assertGreaterEqual(len(bundle.steps), 15)


if __name__ == "__main__":
    unittest.main()
