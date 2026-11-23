import json
import unittest

from tree_essentials import Bound, LeafKind, Role, TreeNode
from helpers_tree import FIGURE_6_2, PRUNING_EXAMPLE, run

INF = float("inf")


def window_node(alpha=3, beta=10, children=()):
    node = TreeNode(None, Role.MAX, 0, alpha, beta)
    for index, bound in enumerate(children):
        child = TreeNode(index, Role.MIN, 1, alpha, beta)
        child.mark_leaf(LeafKind.CACHED, 1, bound=bound)
        node.add_child(child)
    return node


class NodeBasicsTests(unittest.TestCase):
    def test_validation(self):
        with self.assertRaises(TypeError):
            TreeNode(None, "MAX", 0)
        with self.assertRaises(ValueError):
            TreeNode(None, Role.MAX, -1)
        with self.assertRaises(ValueError):
            TreeNode(None, Role.MAX, 0, alpha=1.0)

    def test_new_node_state(self):
        node = TreeNode(None, Role.MAX, 0, -INF, INF)
        self.assertTrue(node.is_root and node.is_max and not node.is_min)
        self.assertFalse(node.is_leaf or node.finished or node.has_cutoff or node.truncated)
        self.assertIsNone(node.value)
        self.assertEqual(node.children, [])

    def test_children_rules(self):
        parent = TreeNode(None, Role.MAX, 0)
        with self.assertRaises(ValueError):
            parent.add_child(TreeNode(0, Role.MIN, 2))
        parent.add_child(TreeNode(0, Role.MIN, 1))
        parent.finish(1, 0)
        with self.assertRaises(RuntimeError):
            parent.add_child(TreeNode(1, Role.MIN, 1))

    def test_leaf_rules(self):
        leaf = TreeNode(0, Role.MIN, 1)
        leaf.mark_leaf(LeafKind.EVAL, 7)
        self.assertTrue(leaf.is_leaf and leaf.finished)
        self.assertEqual((leaf.value, leaf.bound, leaf.leaf_kind), (7, Bound.EXACT, LeafKind.EVAL))
        with self.assertRaises(RuntimeError):
            leaf.mark_leaf(LeafKind.EVAL, 8)
        with self.assertRaises(RuntimeError):
            leaf.finish(8, None)
        with self.assertRaises(RuntimeError):
            leaf.add_child(TreeNode(0, Role.MAX, 2))
        with self.assertRaises(TypeError):
            TreeNode(0, Role.MIN, 1).mark_leaf("eval", 1)

    def test_leaf_cannot_have_children_added_first(self):
        node = TreeNode(None, Role.MAX, 0)
        node.add_child(TreeNode(0, Role.MIN, 1))
        with self.assertRaises(RuntimeError):
            node.mark_leaf(LeafKind.EVAL, 1)

    def test_finish_once(self):
        node = TreeNode(None, Role.MAX, 0)
        node.finish(1, None)
        with self.assertRaises(RuntimeError):
            node.finish(2, None)

    def test_identity_hash_and_equality(self):
        first, second = TreeNode(None, Role.MAX, 0), TreeNode(None, Role.MAX, 0)
        self.assertNotEqual(first, second)
        self.assertEqual(len({first, second}), 2)
        self.assertEqual({first: "widget"}[first], "widget")
        first.finish(1, None)
        self.assertIn(first, {first})

    def test_repr(self):
        self.assertIn("root", repr(TreeNode(None, Role.MAX, 0)))
        self.assertIn("col=2", repr(TreeNode(2, Role.MIN, 1)))


class BoundClassificationTests(unittest.TestCase):
    def test_no_window_is_exact(self):
        node = TreeNode(None, Role.MAX, 0)
        node.finish(5, None, (1,))
        self.assertEqual(node.bound, Bound.EXACT)

    def test_window_rule_when_something_was_pruned(self):
        for value, expected in ((2, Bound.UPPER), (3, Bound.UPPER), (5, Bound.EXACT),
                                (10, Bound.LOWER), (12, Bound.LOWER)):
            node = window_node()
            node.finish(value, 0, (1,))
            self.assertEqual(node.bound, expected, value)

    def test_childless_node_uses_the_window_rule(self):
        node = window_node()
        node.finish(2, None)
        self.assertEqual(node.bound, Bound.UPPER)

    def test_fully_explored_exact_children_make_the_node_exact(self):
        node = window_node(children=(Bound.EXACT, Bound.EXACT))
        node.finish(2, 0)
        self.assertEqual(node.bound, Bound.EXACT)

    def test_a_bound_child_prevents_the_shortcut(self):
        node = window_node(children=(Bound.EXACT, Bound.UPPER))
        node.finish(2, 0)
        self.assertEqual(node.bound, Bound.UPPER)

    def test_truncated_recording_prevents_the_shortcut(self):
        node = window_node(children=(Bound.EXACT,))
        node.truncated = True
        node.finish(2, 0)
        self.assertEqual(node.bound, Bound.UPPER)

    def test_pruned_columns_prevent_the_shortcut(self):
        node = window_node(children=(Bound.EXACT,))
        node.finish(2, 0, (1,))
        self.assertEqual(node.bound, Bound.UPPER)
        self.assertTrue(node.has_cutoff)


class TraversalTests(unittest.TestCase):
    def setUp(self):
        self.root = run(FIGURE_6_2).root

    def test_preorder(self):
        columns = [node.column for node in self.root.iter_nodes()]
        self.assertEqual(columns, [None, 0, 0, 1, 2, 1, 0, 2, 0, 1, 2])

    def test_paths(self):
        paths = [path for _, path in self.root.iter_with_path()]
        self.assertEqual(paths[0], ())
        self.assertEqual(paths[1:5], [(0,), (0, 0), (0, 1), (0, 2)])
        self.assertEqual(paths[-1], (2, 2))

    def test_sizes(self):
        self.assertEqual(self.root.count_nodes(), 11)
        self.assertEqual(self.root.height(), 2)
        self.assertEqual(self.root.level_sizes(), (1, 3, 7))
        self.assertEqual(self.root.children[0].level_sizes(), (1, 3))

    def test_lookups(self):
        self.assertIs(self.root.child_for(1), self.root.children[1])
        self.assertIsNone(self.root.child_for(5))
        self.assertIs(self.root.best_child(), self.root.children[0])
        self.assertIs(self.root.find((2, 1)), self.root.children[2].children[1])
        self.assertIsNone(self.root.find((1, 2)))
        self.assertIs(self.root.find(()), self.root)

    def test_principal_variation(self):
        line = self.root.principal_variation()
        self.assertEqual([node.column for node in line], [None, 0, 0])
        self.assertEqual(self.root.principal_columns(), (0, 0))
        leaf = line[-1]
        self.assertEqual(leaf.principal_columns(), ())
        self.assertIsNone(leaf.best_child())

    def test_pruned_moves_are_not_nodes(self):
        pruned = self.root.children[1]
        self.assertEqual(pruned.pruned_columns, (1, 2))
        self.assertEqual(len(pruned.children), 1)
        self.assertIsNone(pruned.child_for(1))

    def test_traversal_of_a_deep_chain_does_not_recurse(self):
        root = TreeNode(None, Role.MAX, 0)
        node = root
        for depth in range(1, 5000):
            child = TreeNode(0, node.role.opposite, depth)
            node.add_child(child)
            node = child
        self.assertEqual(root.count_nodes(), 5000)
        self.assertEqual(root.height(), 4999)
        self.assertEqual(len(root.to_dict()["children"]), 1)


class ExportTests(unittest.TestCase):
    def test_to_dict_is_json_safe(self):
        root = run(PRUNING_EXAMPLE).root
        text = json.dumps(root.to_dict())
        data = json.loads(text)
        self.assertEqual(data["alpha"], "-inf")
        self.assertEqual(data["beta"], "+inf")
        self.assertEqual(data["role"], "MAX")
        self.assertEqual(data["value"], 5)
        self.assertEqual(len(data["children"]), 3)
        self.assertEqual(data["children"][0]["children"][1]["bound"], "lower")
        self.assertEqual(data["children"][1]["pruned_columns"], [1, 2])
        self.assertEqual(data["children"][0]["children"][0]["children"][0]["leaf_kind"], "eval")

    def test_to_dict_keeps_child_order_and_boards(self):
        from core.board import Board
        from helpers import RED
        node = TreeNode(None, Role.MAX, 0)
        for column in (3, 1, 2):
            child = TreeNode(column, Role.MIN, 1)
            child.mark_leaf(LeafKind.EVAL, column, Board(2, 2).drop(0, RED))
            node.add_child(child)
        node.finish(3, 3)
        data = node.to_dict()
        self.assertEqual([child["column"] for child in data["children"]], [3, 1, 2])
        self.assertEqual(data["children"][0]["board"], [". .", "X ."])


class EnumTests(unittest.TestCase):
    def test_role_opposite(self):
        self.assertIs(Role.MAX.opposite, Role.MIN)
        self.assertIs(Role.MIN.opposite, Role.MAX)

    def test_bound_symbols(self):
        self.assertEqual((Bound.EXACT.symbol, Bound.LOWER.symbol, Bound.UPPER.symbol),
                         ("=", ">=", "<="))


if __name__ == "__main__":
    unittest.main()
