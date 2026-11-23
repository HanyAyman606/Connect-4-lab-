import unittest

from tree_essentials import (
    Bound, LeafKind, NULL_RECORDER, NullRecorder, Role, SearchRecorder,
    TreeRecorder, create_recorder,
)
from helpers_tree import FIGURE_6_2, PRUNING_EXAMPLE, run


class NullRecorderTests(unittest.TestCase):
    def test_does_nothing(self):
        recorder = NullRecorder()
        node = recorder.enter(None, Role.MAX, 0, 1.0, 2.0)
        self.assertIsNone(node)
        recorder.leaf(node, LeafKind.EVAL, 3)
        recorder.exit(node, 3, 0, (1,))
        self.assertIsNone(recorder.root)
        self.assertFalse(recorder.truncated)
        self.assertEqual(recorder.recorded_nodes, 0)

    def test_shared_instance_and_factory(self):
        self.assertIsInstance(NULL_RECORDER, SearchRecorder)
        self.assertIs(create_recorder(False), NULL_RECORDER)
        recorder = create_recorder(True, max_depth=2, max_nodes=10)
        self.assertIsInstance(recorder, TreeRecorder)
        self.assertIsNot(recorder, create_recorder(True))

    def test_search_gives_the_same_answer_with_either_recorder(self):
        for tree in (FIGURE_6_2, PRUNING_EXAMPLE):
            recorded = run(tree)
            silent = run(tree, recorder=NULL_RECORDER)
            self.assertEqual(recorded.value, silent.value)
            self.assertEqual(recorded.best_column, silent.best_column)
            self.assertEqual(recorded.stats.as_dict()["visited"], silent.stats.visited)
            self.assertIsNotNone(recorded.root)
            self.assertIsNone(silent.root)


class TreeRecorderTests(unittest.TestCase):
    def test_records_the_whole_tree(self):
        recorder = TreeRecorder()
        result = run(FIGURE_6_2, recorder=recorder)
        self.assertEqual(recorder.recorded_nodes, 11)
        self.assertEqual(result.root.count_nodes(), 11)
        self.assertTrue(recorder.is_balanced)
        self.assertFalse(recorder.truncated)
        self.assertIs(recorder.root, result.root)

    def test_records_roles_depths_and_windows(self):
        root = run(PRUNING_EXAMPLE).root
        for node, path in root.iter_with_path():
            self.assertEqual(node.depth, len(path))
            self.assertIs(node.role, Role.MAX if node.depth % 2 == 0 else Role.MIN)
            self.assertTrue(node.finished)
        self.assertEqual((root.alpha, root.beta), (float("-inf"), float("inf")))
        self.assertEqual((root.children[1].alpha, root.children[1].beta), (4, float("inf")))

    def test_lecture_values_and_bounds(self):
        root = run(PRUNING_EXAMPLE).root
        a, b, c = root.children
        self.assertEqual((root.value, root.best_column), (5, 2))
        self.assertEqual((a.value, a.bound), (4, Bound.EXACT))
        self.assertEqual((a.children[0].value, a.children[0].bound), (4, Bound.EXACT))
        self.assertEqual((a.children[1].value, a.children[1].bound), (6, Bound.LOWER))
        self.assertEqual((b.value, b.bound, b.pruned_columns), (2, Bound.UPPER, (1, 2)))
        self.assertEqual((b.children[0].value, b.children[0].bound), (2, Bound.EXACT))
        self.assertEqual((c.value, c.bound), (5, Bound.EXACT))
        self.assertEqual((c.children[1].value, c.children[1].bound), (7, Bound.LOWER))

    def test_figure_6_2_values_and_bounds(self):
        root = run(FIGURE_6_2).root
        b, c, d = root.children
        self.assertEqual((root.value, root.best_column), (3, 0))
        self.assertEqual((b.value, b.bound), (3, Bound.EXACT))
        self.assertEqual((c.value, c.bound, c.pruned_columns), (2, Bound.UPPER, (1, 2)))
        self.assertEqual((d.value, d.bound, d.pruned_columns), (2, Bound.EXACT, ()))

    def test_out_of_order_calls_are_rejected(self):
        recorder = TreeRecorder()
        outer = recorder.enter(None, Role.MAX, 0)
        inner = recorder.enter(0, Role.MIN, 1)
        with self.assertRaises(RuntimeError):
            recorder.exit(outer, 1, 0)
        recorder.leaf(inner, LeafKind.EVAL, 1)
        recorder.exit(outer, 1, 0)

    def test_second_tree_needs_reset(self):
        recorder = TreeRecorder()
        node = recorder.enter(None, Role.MAX, 0)
        recorder.leaf(node, LeafKind.EVAL, 1)
        with self.assertRaises(RuntimeError):
            recorder.enter(None, Role.MAX, 0)
        recorder.reset()
        self.assertIsNone(recorder.root)
        self.assertEqual(recorder.recorded_nodes, 0)
        recorder.enter(None, Role.MAX, 0)
        self.assertEqual(recorder.recorded_nodes, 1)

    def test_unbalanced_recording_is_detectable(self):
        recorder = TreeRecorder()
        recorder.enter(None, Role.MAX, 0)
        self.assertFalse(recorder.is_balanced)

    def test_invalid_limits(self):
        with self.assertRaises(ValueError):
            TreeRecorder(max_depth=-1)
        with self.assertRaises(ValueError):
            TreeRecorder(max_nodes=0)


class RecordingLimitTests(unittest.TestCase):
    def test_depth_limit(self):
        recorder = TreeRecorder(max_depth=1)
        result = run(FIGURE_6_2, recorder=recorder)
        self.assertEqual(recorder.recorded_nodes, 4)
        self.assertTrue(recorder.truncated and result.tree_truncated)
        for child in result.root.children:
            self.assertTrue(child.truncated)
            self.assertEqual(child.children, [])
        self.assertFalse(result.root.truncated)
        self.assertEqual(result.value, 3)
        self.assertEqual(result.stats.visited, 11)

    def test_depth_limit_zero_keeps_only_the_root(self):
        recorder = TreeRecorder(max_depth=0)
        result = run(PRUNING_EXAMPLE, recorder=recorder)
        self.assertEqual(result.root.count_nodes(), 1)
        self.assertTrue(result.root.truncated)
        self.assertEqual(result.root.value, 5)

    def test_node_limit(self):
        recorder = TreeRecorder(max_nodes=5)
        result = run(PRUNING_EXAMPLE, recorder=recorder)
        self.assertEqual(recorder.recorded_nodes, 5)
        self.assertEqual(result.root.count_nodes(), 5)
        self.assertTrue(recorder.truncated)
        self.assertTrue(all(node.finished for node in result.root.iter_nodes()))
        self.assertEqual(result.value, 5)

    def test_limits_above_the_tree_size_change_nothing(self):
        recorder = TreeRecorder(max_depth=10, max_nodes=1000)
        result = run(FIGURE_6_2, recorder=recorder)
        self.assertFalse(recorder.truncated)
        self.assertEqual(result.root.count_nodes(), 11)


if __name__ == "__main__":
    unittest.main()
