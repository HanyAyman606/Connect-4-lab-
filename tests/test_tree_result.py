import dataclasses
import unittest

from tree_essentials import SearchResult, SearchStats, TreeRecorder, format_columns, format_number
from helpers_tree import FIGURE_6_2, PRUNING_EXAMPLE, run


class FormattingTests(unittest.TestCase):
    def test_format_number(self):
        cases = [(None, "N/A"), (0, "0"), (0.0, "0"), (4, "+4"), (-3, "-3"), (3.0, "+3"),
                 (-2.0, "-2"), (2.5, "+2.50"), (-0.5, "-0.50"), (float("inf"), "+∞"),
                 (float("-inf"), "-∞"), (float("nan"), "nan")]
        for value, expected in cases:
            self.assertEqual(format_number(value), expected, value)

    def test_format_columns(self):
        self.assertEqual(format_columns((1, 2, 5)), "1, 2, 5")
        self.assertEqual(format_columns(()), "")


class StatsTests(unittest.TestCase):
    def test_lecture_counts(self):
        first = run(FIGURE_6_2).stats
        self.assertEqual((first.visited, first.expanded, first.evaluations), (11, 4, 7))
        self.assertEqual((first.cutoffs, first.pruned_branches), (1, 2))
        second = run(PRUNING_EXAMPLE).stats
        self.assertEqual((second.visited, second.expanded, second.evaluations), (17, 9, 8))
        self.assertEqual((second.cutoffs, second.pruned_branches), (3, 4))
        for stats in (first, second):
            self.assertTrue(stats.is_consistent())
            self.assertEqual(stats.leaves, stats.evaluations)

    def test_leaves_and_consistency(self):
        stats = SearchStats(visited=10, expanded=4, evaluations=3, terminal_leaves=2, cache_hits=1)
        self.assertEqual(stats.leaves, 6)
        self.assertTrue(stats.is_consistent())
        stats.visited += 1
        self.assertFalse(stats.is_consistent())

    def test_timer(self):
        stats = SearchStats()
        with self.assertRaises(RuntimeError):
            stats.stop_timer()
        stats.start_timer()
        first = stats.stop_timer()
        self.assertGreaterEqual(first, 0.0)
        stats.start_timer()
        self.assertGreaterEqual(stats.stop_timer(), first)
        with self.assertRaises(RuntimeError):
            stats.stop_timer()

    def test_merge_and_reset(self):
        total = SearchStats(visited=5, expanded=2, evaluations=3, max_depth=4, elapsed=1.0)
        other = SearchStats(visited=7, expanded=3, evaluations=4, cutoffs=2, pruned_branches=5,
                            max_depth=6, elapsed=0.5)
        total.merge(other)
        self.assertEqual((total.visited, total.expanded, total.evaluations), (12, 5, 7))
        self.assertEqual((total.cutoffs, total.pruned_branches, total.max_depth), (2, 5, 6))
        self.assertAlmostEqual(total.elapsed, 1.5)
        total.reset()
        self.assertEqual(total.as_dict(), SearchStats().as_dict())

    def test_as_dict_and_summary(self):
        stats = SearchStats(visited=3, expanded=1, evaluations=2, elapsed=0.25)
        data = stats.as_dict()
        self.assertEqual(set(data), {"visited", "expanded", "evaluations", "terminal_leaves",
                                     "cache_hits", "cutoffs", "pruned_branches", "max_depth",
                                     "elapsed_sec"})
        self.assertEqual(data["elapsed_sec"], 0.25)
        self.assertIn("visited=3", stats.summary())

    def test_identity_equality(self):
        self.assertNotEqual(SearchStats(), SearchStats())
        self.assertEqual(len({SearchStats(), SearchStats()}), 2)


class SearchResultTests(unittest.TestCase):
    def test_properties(self):
        result = run(PRUNING_EXAMPLE, k=3)
        self.assertEqual((result.best_column, result.value, result.k), (2, 5, 3))
        self.assertEqual((result.nodes_visited, result.nodes_expanded), (17, 9))
        self.assertTrue(result.has_tree)
        self.assertEqual(result.time_sec, result.stats.elapsed)
        self.assertEqual(result.principal_columns, (2, 0, 0))
        self.assertFalse(result.tree_truncated)

    def test_without_a_tree(self):
        silent = SearchResult(best_column=4, value=1, k=2, algorithm="minimax",
                              stats=SearchStats())
        self.assertFalse(silent.has_tree)
        self.assertEqual(silent.principal_columns, (4,))
        nothing = SearchResult(best_column=None, value=0, k=2, algorithm="minimax",
                               stats=SearchStats())
        self.assertEqual(nothing.principal_columns, ())

    def test_truncated_flag(self):
        result = run(FIGURE_6_2, recorder=TreeRecorder(max_depth=1))
        self.assertTrue(result.tree_truncated)

    def test_row_and_summary(self):
        result = run(FIGURE_6_2, k=2)
        row = result.to_row()
        self.assertEqual((row["algorithm"], row["k"], row["best_column"], row["value"]),
                         ("alpha-beta", 2, 0, 3))
        self.assertEqual((row["visited"], row["expanded"], row["cutoffs"]), (11, 4, 1))
        text = result.summary()
        self.assertIn("alpha-beta K=2", text)
        self.assertIn("value=+3", text)

    def test_result_is_immutable_with_identity_equality(self):
        result = run(FIGURE_6_2)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.value = 0
        self.assertNotEqual(run(FIGURE_6_2), run(FIGURE_6_2))
        self.assertEqual(len({result}), 1)


if __name__ == "__main__":
    unittest.main()
