import io
import os
import tempfile
import unittest

from core.board import Board
from tree_essentials import (
    Bound, LeafKind, PrintOptions, Role, SearchResult, SearchStats, TreeNode,
    TreePrinter, TreeRecorder,
)
from helpers import RED, YELLOW
from helpers_tree import FIGURE_6_2, PRUNING_EXAMPLE, run

FIGURE_6_2_TEXT = "\n".join([
    "ROOT [MAX] value=+3 (a=-∞, b=+∞)",
    "|-- * col 0 [MIN] value=+3 (a=-∞, b=+∞)",
    "|   |-- * col 0 LEAF eval=+3",
    "|   |-- col 1 LEAF eval=+12",
    "|   \\-- col 2 LEAF eval=+8",
    "|-- col 1 [MIN] value<=+2 (a=+3, b=+∞)",
    "|   |-- * col 0 LEAF eval=+2",
    "|   \\-- x pruned columns: 1, 2",
    "\\-- col 2 [MIN] value=+2 (a=+3, b=+∞)",
    "    |-- col 0 LEAF eval=+14",
    "    |-- col 1 LEAF eval=+5",
    "    \\-- * col 2 LEAF eval=+2",
])


def lines(tree, **options):
    root = run(tree).root
    return list(TreePrinter(PrintOptions(**options)).lines(root))


class LineFormatTests(unittest.TestCase):
    def test_figure_6_2_matches_the_lecture(self):
        self.assertEqual("\n".join(lines(FIGURE_6_2)), FIGURE_6_2_TEXT)

    def test_pruning_example_matches_the_lecture_labels(self):
        text = "\n".join(lines(PRUNING_EXAMPLE))
        for expected in ("ROOT [MAX] value=+5", "col 0 [MIN] value=+4", "value>=+6 (a=-∞, b=+4)",
                         "col 1 [MIN] value<=+2 (a=+4, b=+∞)", "col 0 [MAX] value=+2 (a=+4, b=+∞)",
                         "* col 2 [MIN] value=+5", "value>=+7 (a=+4, b=+5)"):
            self.assertIn(expected, text)
        self.assertEqual(text.count("x pruned columns"), 3)

    def test_one_line_per_node_plus_notes(self):
        root = run(PRUNING_EXAMPLE).root
        output = lines(PRUNING_EXAMPLE)
        self.assertEqual(len(output), root.count_nodes() + 3)

    def test_best_marker_only_on_chosen_children(self):
        root = run(PRUNING_EXAMPLE).root
        stars = [line for line in lines(PRUNING_EXAMPLE) if "* col" in line]
        expected = sum(1 for node in root.iter_nodes() if node.best_child() is not None)
        self.assertEqual(len(stars), expected)

    def test_describe_is_reusable(self):
        root = run(FIGURE_6_2).root
        printer = TreePrinter()
        self.assertEqual(printer.describe(root), "ROOT [MAX] value=+3 (a=-∞, b=+∞)")
        self.assertEqual(printer.describe(root.children[0], is_best=True),
                         "* col 0 [MIN] value=+3 (a=-∞, b=+∞)")

    def test_unfinished_node_shows_a_question_mark(self):
        node = TreeNode(None, Role.MAX, 0, -float("inf"), float("inf"))
        self.assertEqual(TreePrinter().describe(node), "ROOT [MAX] value=N/A (a=-∞, b=+∞)")


class OptionTests(unittest.TestCase):
    def test_print_depth_limit(self):
        output = lines(FIGURE_6_2, max_depth=1)
        self.assertEqual(len(output), 1 + 3 * 2)
        self.assertIn("... 3 subtree(s) hidden by the print depth limit", "\n".join(output))
        self.assertNotIn("LEAF", "\n".join(output))
        only_root = lines(FIGURE_6_2, max_depth=0)
        self.assertEqual(len(only_root), 2)

    def test_hide_window(self):
        text = "\n".join(lines(FIGURE_6_2, show_window=False))
        self.assertNotIn("(a=", text)
        self.assertIn("value<=+2", text)

    def test_hide_pruned(self):
        text = "\n".join(lines(FIGURE_6_2, show_pruned=False))
        self.assertNotIn("x pruned", text)

    def test_no_best_marker(self):
        self.assertNotIn("*", "\n".join(lines(FIGURE_6_2, mark_best=False)))

    def test_unicode_connectors(self):
        text = "\n".join(lines(FIGURE_6_2, ascii_only=False))
        self.assertIn("\u251c\u2500\u2500 ", text)
        self.assertIn("\u2514\u2500\u2500 ", text)
        self.assertIn("\u2502", text)
        self.assertNotIn("|--", text)

    def test_default_connectors_are_pure_ascii(self):
        TreePrinter().render(run(PRUNING_EXAMPLE).root).replace("\u221e", "").encode("ascii")

    def test_invalid_options(self):
        with self.assertRaises(ValueError):
            PrintOptions(max_depth=-1)


class LeafKindTests(unittest.TestCase):
    def build(self):
        recorder = TreeRecorder()
        root = recorder.enter(None, Role.MAX, 0, -float("inf"), float("inf"))
        board = Board(2, 3).drop(0, RED).drop(1, YELLOW)
        first = recorder.enter(0, Role.MIN, 1, -float("inf"), float("inf"))
        recorder.leaf(first, LeafKind.EVAL, 13, board)
        second = recorder.enter(1, Role.MIN, 1, 13, float("inf"))
        recorder.leaf(second, LeafKind.TERMINAL, 2, board)
        third = recorder.enter(2, Role.MIN, 1, 13, float("inf"))
        recorder.leaf(third, LeafKind.CACHED, 7, None, Bound.UPPER)
        recorder.exit(root, 13, 0)
        return recorder.root

    def test_leaf_labels(self):
        text = "\n".join(TreePrinter().lines(self.build()))
        self.assertIn("col 0 LEAF eval=+13", text)
        self.assertIn("col 1 TERMINAL score=+2", text)
        self.assertIn("col 2 CACHED value<=+7", text)

    def test_boards_under_leaves(self):
        output = list(TreePrinter(PrintOptions(show_boards=True)).lines(self.build()))
        self.assertIn("|     . . .", output)
        self.assertIn("|     X O .", output)
        plain = list(TreePrinter().lines(self.build()))
        self.assertEqual(len(plain), 4)
        self.assertEqual(len(output), 4 + 2 * 2)
        self.assertEqual(output[1], "|-- * col 0 LEAF eval=+13")

    def test_minimax_without_a_window_has_no_window_text(self):
        node = TreeNode(None, Role.MAX, 0)
        child = TreeNode(0, Role.MIN, 1)
        child.mark_leaf(LeafKind.EVAL, 4)
        node.add_child(child)
        node.finish(4, 0)
        text = "\n".join(TreePrinter().lines(node))
        self.assertEqual(text, "ROOT [MAX] value=+4\n\\-- * col 0 LEAF eval=+4")


class TruncationTests(unittest.TestCase):
    def test_recording_limit_note(self):
        result = run(FIGURE_6_2, recorder=TreeRecorder(max_depth=1))
        text = TreePrinter().render(result.root)
        self.assertEqual(text.count("... deeper levels were not recorded"), 3)


class ResultOutputTests(unittest.TestCase):
    def test_header_and_tree(self):
        result = run(PRUNING_EXAMPLE, k=3)
        text = TreePrinter().render(result)
        for expected in ("Search result", "algorithm : alpha-beta", "K         : 3",
                         "best col  : 2", "value     : +5", "visited   : 17", "expanded: 9",
                         "evaluations: 8", "cutoffs   : 3", "pruned branches: 4", "legend:"):
            self.assertIn(expected, text)
        self.assertTrue(text.endswith(TreePrinter().render(result.root)))

    def test_missing_tree(self):
        result = SearchResult(2, 5, 3, "alpha-beta", SearchStats())
        self.assertIn("(the tree was not recorded)", TreePrinter().render(result))

    def test_truncation_note(self):
        result = run(FIGURE_6_2, recorder=TreeRecorder(max_depth=1))
        self.assertIn("recording was limited", TreePrinter().render(result))


class ShowAndExportTests(unittest.TestCase):
    def test_show_writes_to_a_stream(self):
        stream = io.StringIO()
        root = run(FIGURE_6_2).root
        TreePrinter().show(root, stream)
        self.assertEqual(stream.getvalue(), FIGURE_6_2_TEXT + "\n")

    def test_show_defaults_to_the_console(self):
        import contextlib
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            TreePrinter().show(run(FIGURE_6_2).root)
        self.assertEqual(stream.getvalue(), FIGURE_6_2_TEXT + "\n")

    def test_show_stops_after_max_lines(self):
        stream = io.StringIO()
        TreePrinter().show(run(PRUNING_EXAMPLE).root, stream, max_lines=4)
        output = stream.getvalue().splitlines()
        self.assertEqual(len(output), 5)
        self.assertIn("output stopped after 4 lines", output[-1])

    def test_export_writes_a_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "logs", "turn1.txt")
            returned = TreePrinter().export(run(FIGURE_6_2).root, path)
            self.assertEqual(str(returned), path)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), FIGURE_6_2_TEXT + "\n")

    def test_export_result_with_title_and_append(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "game.txt")
            printer = TreePrinter()
            printer.export(run(FIGURE_6_2), path, title="Turn 1")
            printer.export(run(PRUNING_EXAMPLE), path, append=True, title="Turn 2")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertTrue(text.startswith("Turn 1\n======\nSearch result"))
            self.assertEqual(text.count("Search result"), 2)
            self.assertIn("\n\nTurn 2\n======\n", text)
            printer.export(run(FIGURE_6_2), path, title="Fresh")
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read().count("Search result"), 1)

    def test_export_unicode_tree(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "tree.txt")
            TreePrinter(PrintOptions(ascii_only=False)).export(run(FIGURE_6_2).root, path)
            with open(path, encoding="utf-8") as handle:
                self.assertIn("\u2514\u2500\u2500", handle.read())

    def test_render_of_a_node_and_a_result_agree_on_the_tree(self):
        result = run(FIGURE_6_2)
        self.assertTrue(TreePrinter().render(result).endswith(FIGURE_6_2_TEXT))


if __name__ == "__main__":
    unittest.main()
