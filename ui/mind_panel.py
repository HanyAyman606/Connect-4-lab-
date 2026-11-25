"""'The Devil's Mind' Minimax Tree, Playback & Sheet-6 Trace Theater.

Provides five synchronized views powered by real ``SearchResult`` data:
  1. △/▽ Tree   — 2D graphical MAX/MIN triangle & leaf-box tree (Lecture 6 &
                  Sheet 6 style) + live node 7x6 board & heuristic formula bar.
  2. α-β Table  — Exact Alexandria University *Sheet 6* Visiting-Order Trace
                  Table (old α, new α, old β, new β, old v, new v / cutoff) +
                  Bottom-Up Minimax Computation Table (min/max over children).
  3. Board Eval — Full feature × weight breakdown, candidate open-3 targets,
                  and side-by-side comparison across all 3 Devils.
  4. Stats      — Pruning saved %, α/β cutoff split, b*, 10^35 log scale &
                  per-turn sparklines.
  5. Trace      — Console text mirror (tree + Sheet-6 table) with Copy/Export.

Includes a persistent AI Turn Switcher, Step-by-Step Alpha-Beta Playback
transport bar (Start, Step −, Play/Pause, Step +, Final, Speed, Scrubber), and
one-click Full-Width Theater expansion.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.board import Board
from core.game import Game, GameState
from core.owner import Owner
from tree_essentials import LeafKind, SearchResult, TreeNode
from ui.search_worker import (
    DerivedTreeMetrics,
    evaluate_board_detailed,
    find_candidate_cells,
    format_eval_score,
)
from ui.theme import (
    Palette,
    draw_devil_disc,
    draw_spirit_disc,
    make_display_font,
    make_ui_font,
)
from ui.tree_canvas import MinimaxTreeCanvas
from ui.tree_trace_engine import (
    TreeTraceBundle,
    build_tree_trace,
    format_path_label,
    reconstruct_board_at_path,
    render_detailed_console_report,
)

_MIND_QSS = """
QWidget {
    background: transparent;
    color: #f0ece1;
}
QTableWidget {
    background-color: rgba(8, 12, 20, 235);
    alternate-background-color: rgba(14, 20, 34, 210);
    border: 1px solid rgba(232, 228, 216, 52);
    border-radius: 7px;
    gridline-color: rgba(255, 255, 255, 18);
    color: #f0ece1;
    font-size: 11px;
    selection-background-color: rgba(232, 194, 106, 65);
    selection-color: #fae09e;
}
QHeaderView::section {
    background-color: rgba(20, 30, 48, 245);
    color: #5fd6c4;
    font-weight: bold;
    font-size: 10px;
    padding: 4px 5px;
    border: none;
    border-right: 1px solid rgba(255, 255, 255, 18);
    border-bottom: 1px solid rgba(95, 214, 196, 95);
}
QPlainTextEdit {
    background-color: rgba(8, 11, 18, 238);
    border: 1px solid rgba(232, 228, 216, 52);
    border-radius: 8px;
    color: #dce4f0;
    font-family: Consolas, 'Cascadia Mono', 'Courier New', monospace;
    font-size: 11px;
    padding: 6px;
}
QPushButton {
    background-color: rgba(16, 25, 40, 220);
    border: 1px solid rgba(232, 228, 216, 72);
    border-radius: 6px;
    color: #f0ece1;
    font-size: 10px;
    font-weight: bold;
    padding: 3px 8px;
}
QPushButton:hover {
    background-color: rgba(30, 50, 76, 238);
    border-color: #e8c26a;
    color: #fae09e;
}
QSlider::groove:horizontal {
    height: 6px;
    background: rgba(22, 32, 50, 220);
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #5fd6c4;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #fae09e;
    border: 1px solid #141008;
    width: 13px;
    margin: -4px 0;
    border-radius: 6px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: rgba(10, 14, 24, 160);
    width: 8px;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: rgba(95, 214, 196, 105);
    border-radius: 4px;
    min-height: 20px;
}
"""


@dataclass(slots=True)
class AITurnSnapshot:
    """Saved SearchResult, pre-move state, and precomputed Sheet-6 trace bundle."""

    turn_number: int
    chosen_col: int
    state_before: GameState
    result: SearchResult
    metrics: DerivedTreeMetrics
    bundle: TreeTraceBundle


class _NodeStateRibbon(QWidget):
    """Compact live strip under the 2D Tree showing the selected node's 7x6 board + eval formula."""

    open_eval_tab_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(114)
        self._board: Optional[Board] = None
        self._heuristic_key: str = "windows"
        self._title: str = "Node State"
        self._window_line: str = ""
        self._formula_line: str = ""

    def set_node_state(
        self,
        board: Optional[Board],
        heuristic_key: str,
        title: str,
        window_line: str,
        is_terminal_leaf: bool = False,
        terminal_score: Optional[float] = None,
    ) -> None:
        self._board = board
        self._heuristic_key = heuristic_key
        self._title = title
        self._window_line = window_line
        if board is not None:
            if is_terminal_leaf and terminal_score is not None:
                self._formula_line = (
                    f"TERMINAL FULL BOARD: exact utility = Devil Fours − Your Fours = {format_eval_score(terminal_score)}"
                )
            else:
                rep = evaluate_board_detailed(board, heuristic_key)
                terms = " + ".join(f"{r.weight_str}·({r.diff_val})" for r in rep.rows)
                self._formula_line = (
                    f"raw = {terms} = {rep.raw_score:+.1f}   ⇒   "
                    f"eval = {rep.raw_score:+.1f} / (1000 + |{rep.raw_score:.1f}|) = {rep.normalized_value:+.4f}"
                )
        else:
            self._formula_line = ""
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        rect = QRectF(0.5, 0.5, w - 1, h - 1)
        painter.setBrush(QColor(11, 17, 29, 238))
        painter.setPen(QPen(QColor(232, 194, 106, 85), 1.1))
        painter.drawRoundedRect(rect, 8, 8)

        if self._board is None:
            painter.setFont(make_ui_font(9))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Click any △ / ▽ / □ node in the tree (or press ▶ Play) to see its exact 7×6 board & heuristic math.")
            painter.end()
            return

        # Left: crisp mini 7x6 Connect 4 board of this exact tree node!
        b_w = 128.0
        b_rect = QRectF(6, 6, b_w, h - 12)
        painter.setBrush(QColor(7, 10, 18, 235))
        painter.setPen(QPen(QColor(95, 214, 196, 80), 1.0))
        painter.drawRoundedRect(b_rect, 6, 6)

        step = min((b_rect.width() - 8) / self._board.cols, (b_rect.height() - 8) / self._board.rows)
        gx = b_rect.left() + (b_rect.width() - step * self._board.cols) * 0.5
        gy = b_rect.top() + (b_rect.height() - step * self._board.rows) * 0.5
        rad = step * 0.38
        for r in range(self._board.rows):
            for c in range(self._board.cols):
                pt = QPointF(gx + (c + 0.5) * step, gy + (r + 0.5) * step)
                own = self._board.cell(r, c).owner
                if own is Owner.HUMAN:
                    draw_spirit_disc(painter, pt, rad)
                elif own is Owner.COMPUTER:
                    draw_devil_disc(painter, pt, rad)
                else:
                    painter.setBrush(QColor(15, 22, 36, 180))
                    painter.setPen(QPen(QColor(150, 170, 205, 42), 0.8))
                    painter.drawEllipse(pt, rad, rad)

        # Right: Node path, α/β/v trace values, and exact heuristic formula calculation!
        tx = b_rect.right() + 12.0
        tw = max(80.0, w - tx - 10.0)

        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(QRectF(tx, 8, tw, 18), Qt.AlignmentFlag.AlignLeft, self._title)

        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(tx, 29, tw, 18), Qt.AlignmentFlag.AlignLeft, self._window_line)

        painter.setFont(make_ui_font(8))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(tx, 50, tw, h - 56),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self._formula_line,
        )
        painter.end()


class _StatsCanvas(QWidget):
    """Custom QPainter view for Search Stats, complexity bars, and sparklines."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._snapshots: list[AITurnSnapshot] = []
        self._active_idx: int = -1

    def set_snapshots(self, snapshots: list[AITurnSnapshot], active_idx: int) -> None:
        self._snapshots = list(snapshots)
        self._active_idx = active_idx
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        if not self._snapshots or not (0 <= self._active_idx < len(self._snapshots)):
            painter.setFont(make_ui_font(10))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(16, 0, w - 32, h), Qt.AlignmentFlag.AlignCenter, "No AI search recorded yet.")
            painter.end()
            return

        snap = self._snapshots[self._active_idx]
        res = snap.result
        st = res.stats
        met = snap.metrics

        pad = 6.0
        tw = w - 2 * pad
        y = 4.0

        tiles = (
            ("VISITED / EXPANDED", f"{st.visited:,} / {st.expanded:,}", f"K={res.k}, max d={st.max_depth}", Palette.SPIRIT_CYAN),
            ("TIME TAKEN", f"{st.elapsed * 1000:.2f} ms", f"{st.elapsed:.4f} s total", Palette.MEMORY_GOLD),
            ("CUTOFFS (α / β)", f"{st.cutoffs:,} ({met.alpha_cutoffs}α / {met.beta_cutoffs}β)", f"{st.pruned_branches:,} branches skipped", Palette.DEVIL_MAGMA),
            ("EFF. BRANCHING b*", f"{met.effective_branching:.2f}  (vs b=7)", f"Ideal α-β ≈ {7 ** 0.5:.2f}", Palette.SPIRIT_CYAN),
            ("ORDERING QUALITY", f"{met.ordering_quality_pct:.1f}%", f"{met.first_child_cutoffs}/{st.cutoffs} 1st-move cutoffs", Palette.MEMORY_GOLD),
            ("SPACE O(b·m)", f"{max(1, st.max_depth) * 7} states", f"Display tree: {met.stored_nodes:,} nodes", Palette.TEXT_BONE),
        )
        gap = 6.0
        tile_w = (tw - 2 * gap) / 3.0
        tile_h = 52.0
        for i, (label, big, sub, col) in enumerate(tiles):
            r_i, c_i = divmod(i, 3)
            rx = pad + c_i * (tile_w + gap)
            ry = y + r_i * (tile_h + gap)
            t_rect = QRectF(rx, ry, tile_w, tile_h)
            painter.setBrush(QColor(13, 19, 32, 220))
            painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 85), 1.0))
            painter.drawRoundedRect(t_rect, 7, 7)

            painter.setFont(make_ui_font(7, bold=True))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(rx + 7, ry + 4, tile_w - 14, 13), Qt.AlignmentFlag.AlignLeft, label)

            painter.setFont(make_ui_font(10, bold=True))
            painter.setPen(col)
            painter.drawText(QRectF(rx + 7, ry + 18, tile_w - 14, 18), Qt.AlignmentFlag.AlignLeft, big)

            painter.setFont(make_ui_font(7))
            painter.setPen(Palette.TEXT_DIM)
            painter.drawText(QRectF(rx + 7, ry + 36, tile_w - 14, 13), Qt.AlignmentFlag.AlignLeft, sub)

        y += 2 * (tile_h + gap) + 4.0

        self._draw_bar(
            painter,
            QRectF(pad, y, tw, 38),
            f"ALPHA-BETA PRUNING SAVED: {met.pruned_saved_pct:.1f}%",
            f"{st.visited:,} visited vs {met.unpruned_bound:,} unpruned bound",
            min(1.0, st.visited / max(1, met.unpruned_bound)),
            Palette.SPIRIT_CYAN,
        )
        y += 44.0

        total_leaves = max(1, st.evaluations + st.terminal_leaves)
        self._draw_bar(
            painter,
            QRectF(pad, y, tw, 38),
            f"LEAF BREAKDOWN: {st.evaluations:,} EVAL  |  {st.terminal_leaves:,} TERMINAL",
            "Terminal full-board checked before K cutoff",
            st.evaluations / total_leaves,
            Palette.MEMORY_GOLD,
        )
        y += 44.0

        chart_h = max(60.0, h - y - 8.0)
        if chart_h >= 54.0:
            half_w = (tw - gap) * 0.5
            times_ms = [s.result.stats.elapsed * 1000.0 for s in self._snapshots]
            evals = [float(s.result.value) for s in self._snapshots]
            self._draw_sparkline(painter, QRectF(pad, y, half_w, chart_h), "TIME / AI MOVE (ms)", times_ms, Palette.MEMORY_GOLD, False)
            self._draw_sparkline(painter, QRectF(pad + half_w + gap, y, half_w, chart_h), "ROOT MINIMAX VALUE OVER FIGHT", evals, Palette.SPIRIT_CYAN, True)

        painter.end()

    @staticmethod
    def _draw_bar(painter: QPainter, rect: QRectF, title: str, right_lbl: str, ratio: float, color: QColor) -> None:
        painter.setBrush(QColor(13, 19, 32, 220))
        painter.setPen(QPen(QColor(232, 228, 216, 55), 1.0))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setFont(make_ui_font(7, bold=True))
        painter.setPen(color)
        painter.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() * 0.55, 14), Qt.AlignmentFlag.AlignLeft, title)
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(rect.left() + 8, rect.top() + 4, rect.width() - 16, 14), Qt.AlignmentFlag.AlignRight, right_lbl)
        bx, by, bw = rect.left() + 8, rect.top() + 21, rect.width() - 16
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(28, 38, 58, 200))
        painter.drawRoundedRect(QRectF(bx, by, bw, 9), 4, 4)
        painter.setBrush(color)
        painter.drawRoundedRect(QRectF(bx, by, max(4.0, bw * max(0.0, min(1.0, ratio))), 9), 4, 4)

    def _draw_sparkline(self, painter: QPainter, rect: QRectF, title: str, values: list[float], color: QColor, zero_line: bool) -> None:
        painter.setBrush(QColor(13, 19, 32, 220))
        painter.setPen(QPen(QColor(232, 228, 216, 55), 1.0))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setFont(make_ui_font(7, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(rect.left() + 7, rect.top() + 4, rect.width() - 14, 13), Qt.AlignmentFlag.AlignLeft, title)
        plot = QRectF(rect.left() + 8, rect.top() + 20, rect.width() - 16, rect.height() - 26)
        if not values or plot.height() < 12:
            return
        lo, hi = min(values), max(values)
        if zero_line:
            lo, hi = min(lo, -0.05), max(hi, 0.05)
        span = max(1e-6, hi - lo)
        if zero_line and lo <= 0.0 <= hi:
            zy = plot.bottom() - ((0.0 - lo) / span) * plot.height()
            painter.setPen(QPen(QColor(232, 228, 216, 55), 1.0, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), zy), QPointF(plot.right(), zy))
        pts = [
            QPointF(
                plot.left() + (plot.width() * i / max(1, len(values) - 1)) if len(values) > 1 else plot.center().x(),
                plot.bottom() - ((v - lo) / span) * plot.height(),
            )
            for i, v in enumerate(values)
        ]
        painter.setPen(QPen(color, 1.7))
        for i in range(len(pts) - 1):
            painter.drawLine(pts[i], pts[i + 1])
        for i, pt in enumerate(pts):
            sel = i == self._active_idx
            painter.setBrush(Palette.GOLD_BRIGHT if sel else color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(pt, 3.8 if sel else 2.4, 3.8 if sel else 2.4)


class _EvalCanvas(QWidget):
    """Full Board Eval breakdown canvas (mini board + gauge + feature table + 3-Devils comparison)."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._board: Optional[Board] = None
        self._heuristic_key: str = "windows"
        self._source_label: str = "Current Board"
        self._show_candidates: bool = True

    def set_data(self, board: Optional[Board], heuristic_key: str, source_label: str, show_candidates: bool) -> None:
        self._board = board
        self._heuristic_key = heuristic_key
        self._source_label = source_label
        self._show_candidates = show_candidates
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        if self._board is None:
            painter.end()
            return

        report = evaluate_board_detailed(self._board, self._heuristic_key)
        pad = 6.0
        tw = w - 2 * pad
        y = 4.0

        top_h = 122.0
        mini_w = 148.0
        self._paint_mini_board(painter, QRectF(pad, y, mini_w, top_h), self._board)
        self._paint_gauge(painter, QRectF(pad + mini_w + 8, y, tw - mini_w - 8, top_h), report.normalized_value, report.raw_score)
        y += top_h + 8.0

        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(pad, y, tw, 16), Qt.AlignmentFlag.AlignLeft, f"FEATURE × WEIGHT BREAKDOWN ({self._source_label.upper()})")
        y += 18.0

        hdr_h = 20.0
        painter.fillRect(QRectF(pad, y, tw, hdr_h), QColor(20, 30, 48, 220))
        painter.setFont(make_ui_font(7, bold=True))
        painter.setPen(Palette.MEMORY_GOLD)
        cols_x = (0.02, 0.36, 0.49, 0.61, 0.73, 0.85)
        for frac, text in zip(cols_x, ("FEATURE", "DEVIL", "YOU", "Δ", "W", "CONTRIB")):
            painter.drawText(QRectF(pad + tw * frac, y, tw * 0.22, hdr_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        y += hdr_h + 1.0

        row_h = 20.0
        painter.setFont(make_ui_font(8))
        for idx, r in enumerate(report.rows):
            if idx % 2 == 1:
                painter.fillRect(QRectF(pad, y, tw, row_h), QColor(14, 20, 34, 160))
            painter.setPen(Palette.TEXT_BONE)
            painter.drawText(QRectF(pad + tw * cols_x[0], y, tw * 0.33, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, r.label)
            painter.setPen(Palette.DEVIL_MAGMA)
            painter.drawText(QRectF(pad + tw * cols_x[1], y, tw * 0.12, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, r.comp_val)
            painter.setPen(Palette.SPIRIT_CYAN)
            painter.drawText(QRectF(pad + tw * cols_x[2], y, tw * 0.12, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, r.human_val)
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(pad + tw * cols_x[3], y, tw * 0.12, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, r.diff_val)
            painter.drawText(QRectF(pad + tw * cols_x[4], y, tw * 0.12, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, r.weight_str)
            c_col = Palette.DEVIL_MAGMA if r.contribution > 0 else (Palette.SPIRIT_CYAN if r.contribution < 0 else Palette.TEXT_MUTED)
            painter.setPen(c_col)
            painter.drawText(QRectF(pad + tw * cols_x[5], y, tw * 0.15, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{r.contribution:+.1f}")
            y += row_h

        tot_rect = QRectF(pad, y + 2, tw, 22)
        painter.fillRect(tot_rect, QColor(22, 34, 54, 215))
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(tot_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"Raw Weighted Sum = {report.raw_score:+.2f}")
        painter.drawText(tot_rect.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"Normalized Eval = {report.normalized_value:+.4f}")
        y += 30.0

        if h - y >= 62.0:
            painter.setFont(make_ui_font(8, bold=True))
            painter.setPen(Palette.SPIRIT_CYAN)
            painter.drawText(QRectF(pad, y, tw, 15), Qt.AlignmentFlag.AlignLeft, "SAME BOARD EVALUATED BY ALL 3 DEVILS:")
            y += 17.0
            cw = (tw - 12.0) / 3.0
            ch = min(52.0, h - y - 4.0)
            for idx, (hkey, dname, dcol) in enumerate((
                ("opportunities", "I · Howl (Easy)", QColor("#4cc9f0")),
                ("gravity", "II · Mora (Gravity)", QColor("#80ed99")),
                ("windows", "III · Shriek (GA-Tuned)", QColor("#e8c26a")),
            )):
                norm_v, raw_v = report.all_three_scores[hkey]
                cr = QRectF(pad + idx * (cw + 6.0), y, cw, ch)
                act = hkey == self._heuristic_key
                painter.setBrush(QColor(18, 28, 46, 230) if act else QColor(12, 17, 28, 200))
                painter.setPen(QPen(dcol if act else QColor(232, 228, 216, 55), 1.3 if act else 1.0))
                painter.drawRoundedRect(cr, 7, 7)
                painter.setFont(make_ui_font(7, bold=True))
                painter.setPen(dcol)
                painter.drawText(QRectF(cr.left() + 6, cr.top() + 3, cw - 12, 13), Qt.AlignmentFlag.AlignLeft, dname)
                painter.setFont(make_ui_font(9, bold=True))
                painter.setPen(Palette.TEXT_BONE)
                painter.drawText(QRectF(cr.left() + 6, cr.top() + 17, cw - 12, 16), Qt.AlignmentFlag.AlignLeft, f"{norm_v:+.4f}")
                painter.setFont(make_ui_font(7))
                painter.setPen(Palette.TEXT_MUTED)
                painter.drawText(QRectF(cr.left() + 6, cr.top() + 34, cw - 12, 13), Qt.AlignmentFlag.AlignLeft, f"raw {raw_v:+.1f}")

        painter.end()

    def _paint_mini_board(self, painter: QPainter, rect: QRectF, board: Board) -> None:
        painter.setBrush(QColor(13, 19, 32, 230))
        painter.setPen(QPen(QColor(232, 228, 216, 65), 1.0))
        painter.drawRoundedRect(rect, 8, 8)
        step = min((rect.width() - 12) / board.cols, (rect.height() - 12) / board.rows)
        gx = rect.left() + (rect.width() - step * board.cols) * 0.5
        gy = rect.top() + (rect.height() - step * board.rows) * 0.5
        r_disc = step * 0.38
        hum_cand, comp_cand = find_candidate_cells(board) if self._show_candidates else (set(), set())
        for r in range(board.rows):
            for c in range(board.cols):
                pt = QPointF(gx + (c + 0.5) * step, gy + (r + 0.5) * step)
                own = board.cell(r, c).owner
                if own is Owner.HUMAN:
                    draw_spirit_disc(painter, pt, r_disc)
                elif own is Owner.COMPUTER:
                    draw_devil_disc(painter, pt, r_disc)
                else:
                    painter.setBrush(QColor(7, 10, 18, 210))
                    if (r, c) in hum_cand:
                        painter.setPen(QPen(Palette.SPIRIT_CYAN, 1.3, Qt.PenStyle.DashLine))
                    elif (r, c) in comp_cand:
                        painter.setPen(QPen(Palette.DEVIL_MAGMA, 1.3, Qt.PenStyle.DashLine))
                    else:
                        painter.setPen(QPen(QColor(150, 170, 205, 45), 0.9))
                    painter.drawEllipse(pt, r_disc, r_disc)

    def _paint_gauge(self, painter: QPainter, rect: QRectF, norm_val: float, raw_val: float) -> None:
        painter.setBrush(QColor(13, 19, 32, 230))
        painter.setPen(QPen(QColor(232, 228, 216, 65), 1.0))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setFont(make_ui_font(7, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(rect.left() + 10, rect.top() + 6, rect.width() - 20, 14), Qt.AlignmentFlag.AlignLeft, f"BOARD VALUE · {self._source_label.upper()}")
        fav_col = Palette.DEVIL_MAGMA if norm_val > 0.0005 else (Palette.SPIRIT_CYAN if norm_val < -0.0005 else Palette.MEMORY_GOLD)
        painter.setFont(make_display_font(16, bold=True))
        painter.setPen(fav_col)
        painter.drawText(QRectF(rect.left() + 10, rect.top() + 22, rect.width() - 20, 26), Qt.AlignmentFlag.AlignLeft, f"{norm_val:+.4f}   (raw {raw_val:+.1f})")
        bx, by, bw = rect.left() + 10, rect.top() + 72, rect.width() - 20
        mid = bx + bw * 0.5
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(24, 34, 52, 220))
        painter.drawRoundedRect(QRectF(bx, by, bw, 12), 6, 6)
        clamped = max(-1.0, min(1.0, norm_val))
        fw = abs(clamped) * (bw * 0.5)
        painter.setBrush(Palette.DEVIL_MAGMA if clamped >= 0 else Palette.SPIRIT_CYAN)
        painter.drawRoundedRect(QRectF(mid if clamped >= 0 else mid - fw, by, max(2.0, fw), 12), 4, 4)
        painter.setPen(QPen(Palette.TEXT_BONE, 1.4))
        painter.drawLine(QPointF(mid, by - 3), QPointF(mid, by + 15))
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(bx, by + 15, bw * 0.5, 14), Qt.AlignmentFlag.AlignLeft, "← −1.0 You (MIN)")
        painter.setPen(Palette.DEVIL_MAGMA)
        painter.drawText(QRectF(mid, by + 15, bw * 0.5, 14), Qt.AlignmentFlag.AlignRight, "Devil (MAX) +1.0 →")


class MindPanel(QWidget):
    """Minimax △/▽ Tree Diagram, Playback & Sheet-6 Trace Theater panel."""

    pv_preview_requested = Signal(tuple)
    theater_toggle_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_MIND_QSS)

        self._game: Optional[Game] = None
        self._heuristic_key: str = "windows"
        self._current_board: Optional[Board] = None
        self._selected_node_board: Optional[Board] = None
        self._selected_node_label: str = "Selected Tree Node"
        self._eval_uses_node: bool = True
        self._show_candidates: bool = True
        self._is_theater: bool = False

        self._snapshots: list[AITurnSnapshot] = []
        self._active_snap_idx: int = -1
        self._step_idx: int = 0
        self._speed_mult: float = 1.0

        self._play_timer = QTimer(self)
        self._play_timer.setInterval(550)
        self._play_timer.timeout.connect(self._on_playback_tick)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(6)

        # 1. Top Row: Title + AI Turn Selector Strip + Full-Width Theater Toggle
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(6)
        title_lbl = QLabel("MINIMAX TREE & α-β TRACE")
        title_lbl.setFont(make_display_font(11, bold=True))
        title_lbl.setStyleSheet("color: #e8c26a; letter-spacing: 1.5px;")
        hdr_row.addWidget(title_lbl)

        self._btn_prev_turn = QPushButton("◀ Turn")
        self._btn_prev_turn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev_turn.clicked.connect(lambda: self._select_snapshot(self._active_snap_idx - 1))
        self._lbl_turn_badge = QLabel("Turn —")
        self._lbl_turn_badge.setStyleSheet(
            "background: rgba(20, 36, 54, 225); border: 1px solid rgba(95,214,196,95); "
            "border-radius: 6px; padding: 2px 8px; color: #5fd6c4; font-weight: bold; font-size: 10px;"
        )
        self._btn_next_turn = QPushButton("Turn ▶")
        self._btn_next_turn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next_turn.clicked.connect(lambda: self._select_snapshot(self._active_snap_idx + 1))

        hdr_row.addStretch(1)
        hdr_row.addWidget(self._btn_prev_turn)
        hdr_row.addWidget(self._lbl_turn_badge)
        hdr_row.addWidget(self._btn_next_turn)

        self._btn_theater = QPushButton("⤢ Full Tree Theater (T)")
        self._btn_theater.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_theater.setStyleSheet(
            "background: rgba(42, 34, 18, 235); border: 1px solid #e8c26a; color: #fae09e;"
        )
        self._btn_theater.clicked.connect(self.theater_toggle_requested.emit)
        hdr_row.addWidget(self._btn_theater)
        root_layout.addLayout(hdr_row)

        # 2. Five View Tabs
        tab_row = QHBoxLayout()
        tab_row.setSpacing(4)
        self._tab_buttons: list[QPushButton] = []
        tab_titles = (
            "1 · △/▽ Tree Diagram",
            "2 · Sheet-6 α-β Table",
            "3 · State && Eval",
            "4 · Stats",
            "5 · Console Trace",
        )
        for idx, name in enumerate(tab_titles):
            btn = QPushButton(name)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, i=idx: self.set_active_tab(i))
            tab_row.addWidget(btn)
            self._tab_buttons.append(btn)
        root_layout.addLayout(tab_row)

        # 3. Persistent Step-by-Step Alpha-Beta Playback Bar (synchronized with Tree & Sheet-6 Table!)
        pb_box = QWidget()
        pb_box.setStyleSheet(
            "QWidget#pbBox { background: rgba(12, 18, 30, 230); border: 1px solid rgba(95,214,196,70); border-radius: 7px; }"
        )
        pb_box.setObjectName("pbBox")
        pb_lay = QVBoxLayout(pb_box)
        pb_lay.setContentsMargins(8, 5, 8, 5)
        pb_lay.setSpacing(4)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(5)
        btn_first = QPushButton("⏮ Start")
        btn_first.clicked.connect(lambda: self._jump_to_step(0))
        btn_prev = QPushButton("⏪ −1")
        btn_prev.clicked.connect(lambda: self._jump_to_step(self._step_idx - 1))
        self._btn_play = QPushButton("▶ Play Steps")
        self._btn_play.setStyleSheet("border-color: #5fd6c4; color: #5fd6c4;")
        self._btn_play.clicked.connect(self._toggle_playback)
        btn_next = QPushButton("+1 ⏩")
        btn_next.clicked.connect(lambda: self._jump_to_step(self._step_idx + 1))
        btn_last = QPushButton("Final ⏭")
        btn_last.clicked.connect(self._jump_to_final_step)
        self._btn_speed = QPushButton("1×")
        self._btn_speed.clicked.connect(self._cycle_speed)

        for b in (btn_first, btn_prev, self._btn_play, btn_next, btn_last, self._btn_speed):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            ctrl_row.addWidget(b)

        self._step_slider = QSlider(Qt.Orientation.Horizontal)
        self._step_slider.setMinimum(0)
        self._step_slider.setMaximum(0)
        self._step_slider.valueChanged.connect(self._on_slider_changed)
        ctrl_row.addWidget(self._step_slider, 1)

        self._lbl_step_counter = QLabel("Step 0 / 0")
        self._lbl_step_counter.setStyleSheet("color: #fae09e; font-weight: bold; font-size: 10px;")
        ctrl_row.addWidget(self._lbl_step_counter)
        pb_lay.addLayout(ctrl_row)

        self._lbl_step_explain = QLabel("Play a turn to step through every Enter, Leaf Eval, Back-Up, and α-β Cutoff.")
        self._lbl_step_explain.setWordWrap(True)
        self._lbl_step_explain.setStyleSheet("color: #dce4f0; font-size: 10px;")
        pb_lay.addWidget(self._lbl_step_explain)
        root_layout.addWidget(pb_box)
        self._pb_box = pb_box

        # 4. Main Stacked Content
        self._stack = QStackedWidget(self)
        root_layout.addWidget(self._stack, 1)

        # --- Page 0: 2D Graphical △ MAX / ▽ MIN Tree + Node State Ribbon ---
        tree_page = QWidget()
        tp_lay = QVBoxLayout(tree_page)
        tp_lay.setContentsMargins(0, 0, 0, 0)
        tp_lay.setSpacing(5)

        canvas_tools = QHBoxLayout()
        canvas_tools.setSpacing(5)
        b_fit = QPushButton("Fit View")
        b_fit.clicked.connect(lambda: self._tree_canvas.fit_to_view())
        b_zin = QPushButton("Zoom +")
        b_zin.clicked.connect(lambda: self._tree_canvas.zoom_by(1.2))
        b_zout = QPushButton("Zoom −")
        b_zout.clicked.connect(lambda: self._tree_canvas.zoom_by(1.0 / 1.2))
        b_pv = QPushButton("★ PV Path")
        b_pv.clicked.connect(self._on_pv_clicked)
        b_more = QPushButton("Expand +1 Level")
        b_more.clicked.connect(lambda: self._tree_canvas.expand_one_more_level())
        self._btn_win_lbl = QPushButton("[α,β] Windows: ON")
        self._btn_win_lbl.clicked.connect(self._on_toggle_windows)
        for b in (b_fit, b_zin, b_zout, b_pv, b_more, self._btn_win_lbl):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            canvas_tools.addWidget(b)
        canvas_tools.addStretch(1)
        tp_lay.addLayout(canvas_tools)

        self._tree_canvas = MinimaxTreeCanvas()
        self._tree_canvas.node_selected.connect(self._on_canvas_node_selected)
        tp_lay.addWidget(self._tree_canvas, 1)

        self._node_ribbon = _NodeStateRibbon()
        tp_lay.addWidget(self._node_ribbon)
        self._stack.addWidget(tree_page)

        # --- Page 1: Sheet-6 Alpha-Beta Trace Table + Minimax Computation Table ---
        table_page = QSplitter(Qt.Orientation.Vertical)

        top_tbl_wrap = QWidget()
        tt_lay = QVBoxLayout(top_tbl_wrap)
        tt_lay.setContentsMargins(0, 0, 0, 0)
        tt_lay.setSpacing(3)
        lbl_s6 = QLabel("SHEET-6 ALPHA-BETA TRACE TABLE (Visiting Order — Click Any Row to Inspect Board & Jump in Tree)")
        lbl_s6.setStyleSheet("color: #5fd6c4; font-weight: bold; font-size: 10px;")
        tt_lay.addWidget(lbl_s6)

        self._trace_table = QTableWidget(0, 10)
        self._trace_table.setAlternatingRowColors(True)
        self._trace_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._trace_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._trace_table.verticalHeader().setVisible(False)
        self._trace_table.setHorizontalHeaderLabels([
            "#", "Node", "Type", "old α", "new α", "old β", "new β", "old v", "new v", "Decision / Cutoff"
        ])
        th = self._trace_table.horizontalHeader()
        for ci in range(9):
            th.setSectionResizeMode(ci, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        self._trace_table.cellClicked.connect(self._on_trace_row_clicked)
        tt_lay.addWidget(self._trace_table, 1)
        table_page.addWidget(top_tbl_wrap)

        bot_tbl_wrap = QWidget()
        bt_lay = QVBoxLayout(bot_tbl_wrap)
        bt_lay.setContentsMargins(0, 4, 0, 0)
        bt_lay.setSpacing(3)
        lbl_comp = QLabel("MINIMAX BACK-UP COMPUTATION TABLE (Bottom-Up max / min per Internal Node — Sheet 6 Q1a / Q3f)")
        lbl_comp.setStyleSheet("color: #e8c26a; font-weight: bold; font-size: 10px;")
        bt_lay.addWidget(lbl_comp)

        self._comp_table = QTableWidget(0, 5)
        self._comp_table.setAlternatingRowColors(True)
        self._comp_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._comp_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._comp_table.verticalHeader().setVisible(False)
        self._comp_table.setHorizontalHeaderLabels([
            "Node", "Role (d)", "Computation over Children", "Chosen Move", "Backed-Up Value"
        ])
        chdr = self._comp_table.horizontalHeader()
        chdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        chdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        chdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        chdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        chdr.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._comp_table.cellClicked.connect(self._on_comp_row_clicked)
        bt_lay.addWidget(self._comp_table, 1)
        table_page.addWidget(bot_tbl_wrap)
        table_page.setSizes([320, 170])
        self._stack.addWidget(table_page)

        # --- Page 2: State & Eval ---
        eval_page = QWidget()
        e_lay = QVBoxLayout(eval_page)
        e_lay.setContentsMargins(0, 0, 0, 0)
        e_lay.setSpacing(5)
        e_tools = QHBoxLayout()
        self._btn_eval_node = QPushButton("Inspected Tree Node")
        self._btn_eval_node.clicked.connect(lambda: self._set_eval_source(True))
        self._btn_eval_live = QPushButton("Current Live Match Board")
        self._btn_eval_live.clicked.connect(lambda: self._set_eval_source(False))
        self._btn_cand = QPushButton("Open-3 Targets: ON")
        self._btn_cand.clicked.connect(self._toggle_candidates)
        for b in (self._btn_eval_node, self._btn_eval_live, self._btn_cand):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            e_tools.addWidget(b)
        e_lay.addLayout(e_tools)
        self._eval_canvas = _EvalCanvas()
        e_lay.addWidget(self._eval_canvas, 1)
        self._stack.addWidget(eval_page)

        # --- Page 3: Stats ---
        self._stats_canvas = _StatsCanvas()
        self._stack.addWidget(self._stats_canvas)

        # --- Page 4: Console Trace ---
        trace_page = QWidget()
        tr_lay = QVBoxLayout(trace_page)
        tr_lay.setContentsMargins(0, 0, 0, 0)
        tr_lay.setSpacing(5)
        tr_tools = QHBoxLayout()
        btn_copy = QPushButton("Copy Console Report")
        btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_copy.clicked.connect(self._copy_trace)
        btn_exp = QPushButton("Export Full Report (.txt)")
        btn_exp.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_exp.clicked.connect(self._export_trace)
        tr_tools.addWidget(btn_copy)
        tr_tools.addWidget(btn_exp)
        tr_tools.addStretch(1)
        tr_lay.addLayout(tr_tools)
        self._trace_edit = QPlainTextEdit()
        self._trace_edit.setReadOnly(True)
        tr_lay.addWidget(self._trace_edit, 1)
        self._stack.addWidget(trace_page)

        self.set_active_tab(0)

    def set_theater_mode_label(self, active: bool) -> None:
        self._is_theater = active
        self._btn_theater.setText(
            "⤡ Split Board + Tree (T)" if active else "⤢ Full Tree Theater (T)"
        )
        self._tree_canvas.fit_to_view()

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QColor(11, 16, 28, 238))
        bg.setColorAt(1.0, QColor(7, 10, 19, 245))
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(232, 194, 106, 88), 1.25))
        painter.drawRoundedRect(rect, 12, 12)
        painter.end()

    # ------------------------------------------------------------------ match
    def reset_for_match(self, game: Game, heuristic_key: str, initial_board: Board) -> None:
        self._stop_playback()
        self._game = game
        self._heuristic_key = heuristic_key
        self._current_board = initial_board
        self._selected_node_board = initial_board
        self._selected_node_label = "Initial Board"
        self._snapshots.clear()
        self._active_snap_idx = -1
        self._step_idx = 0

        self._lbl_turn_badge.setText("No AI Turn Yet")
        self._step_slider.blockSignals(True)
        self._step_slider.setMaximum(0)
        self._step_slider.setValue(0)
        self._step_slider.blockSignals(False)
        self._lbl_step_counter.setText("Step 0 / 0")
        self._lbl_step_explain.setText("Drop your orb—as soon as the Devil searches, its △/▽ tree, playback & Sheet-6 trace appear here.")

        self._tree_canvas.set_tree(None, None)
        self._node_ribbon.set_node_state(initial_board, heuristic_key, "Initial Empty Board", "Waiting for search...", False)
        self._trace_table.setRowCount(0)
        self._comp_table.setRowCount(0)
        self._trace_edit.clear()
        self._stats_canvas.set_snapshots([], -1)
        self._refresh_eval_canvas()

    def update_live_board(self, board: Board) -> None:
        self._current_board = board
        if not self._eval_uses_node:
            self._refresh_eval_canvas()

    def record_ai_turn(
        self,
        turn_number: int,
        chosen_col: int,
        state_before: GameState,
        result: SearchResult,
        metrics: DerivedTreeMetrics,
    ) -> None:
        bundle = build_tree_trace(result.root)
        snap = AITurnSnapshot(turn_number, chosen_col, state_before, result, metrics, bundle)
        self._snapshots.append(snap)
        self._select_snapshot(len(self._snapshots) - 1)

    def set_active_tab(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        self._pb_box.setVisible(index in (0, 1))
        for i, btn in enumerate(self._tab_buttons):
            if i == index:
                btn.setStyleSheet("background-color: rgba(34, 78, 92, 238); border: 1px solid #5fd6c4; color: #fae09e;")
            else:
                btn.setStyleSheet("")

    # --------------------------------------------------------- turn & playback
    def _select_snapshot(self, index: int) -> None:
        if not (0 <= index < len(self._snapshots)):
            return
        self._stop_playback()
        self._active_snap_idx = index
        snap = self._snapshots[index]
        bundle = snap.bundle

        self._lbl_turn_badge.setText(
            f"Turn {snap.turn_number} ({index + 1}/{len(self._snapshots)}) · K={snap.result.k} · {snap.result.stats.visited:,} nodes"
        )
        self._btn_prev_turn.setEnabled(index > 0)
        self._btn_next_turn.setEnabled(index + 1 < len(self._snapshots))

        self._stats_canvas.set_snapshots(self._snapshots, index)
        self._tree_canvas.set_tree(snap.result.root, bundle)
        self._populate_sheet6_tables(bundle, snap.result.root)

        self._trace_edit.setPlainText(
            render_detailed_console_report(snap.result, self._heuristic_key, max_tree_lines=300, max_table_rows=120)
        )

        max_step = max(0, len(bundle.steps) - 1)
        self._step_slider.blockSignals(True)
        self._step_slider.setMaximum(max_step)
        self._step_slider.setValue(max_step)
        self._step_slider.blockSignals(False)
        self._apply_step(max_step, auto_focus_canvas=False)

    def _populate_sheet6_tables(self, bundle: TreeTraceBundle, root: Optional[TreeNode]) -> None:
        pv_ids = {id(n) for n in root.principal_variation()} if root is not None else set()

        # Table 1: Visiting-order Sheet-6 Alpha-Beta trace
        rows = bundle.trace_rows
        self._trace_table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            cells = (
                str(row.visit_id),
                row.node_label,
                row.node_type,
                row.old_alpha,
                row.new_alpha,
                row.old_beta,
                row.new_beta,
                row.old_value,
                row.new_value,
                row.note,
            )
            is_pv = row.node_id in pv_ids
            has_cut = "cutoff" in row.note
            fg = (
                Palette.DEVIL_MAGMA
                if has_cut
                else (
                    Palette.GOLD_BRIGHT
                    if is_pv
                    else (Palette.SPIRIT_CYAN if row.node_type in ("LEAF", "TERM") else Palette.TEXT_BONE)
                )
            )
            for c_idx, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                it.setForeground(QBrush(fg if c_idx in (1, 2, 8, 9) else Palette.TEXT_BONE))
                if c_idx in (0, 3, 4, 5, 6, 7, 8):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._trace_table.setItem(r_idx, c_idx, it)

        # Table 2: Bottom-up Minimax computation summary
        crows = bundle.computation_rows
        self._comp_table.setRowCount(len(crows))
        for r_idx, crow in enumerate(crows):
            cells_c = (
                crow.node_label,
                f"{crow.role_str} (d={crow.depth})",
                crow.computation,
                crow.chosen_move,
                crow.backed_up_value,
            )
            col = Palette.DEVIL_MAGMA if crow.role_str == "MAX" else Palette.SPIRIT_CYAN
            for c_idx, txt in enumerate(cells_c):
                it = QTableWidgetItem(txt)
                it.setForeground(QBrush(col if c_idx in (0, 1) else Palette.TEXT_BONE))
                self._comp_table.setItem(r_idx, c_idx, it)

    def _toggle_playback(self) -> None:
        if self._play_timer.isActive():
            self._stop_playback()
            return
        if self._active_snap_idx < 0:
            return
        bundle = self._snapshots[self._active_snap_idx].bundle
        if not bundle.steps:
            return
        if self._step_idx >= len(bundle.steps) - 1:
            self._jump_to_step(0)
        self._btn_play.setText("⏸ Pause")
        self._play_timer.start()

    def _stop_playback(self) -> None:
        if self._play_timer.isActive():
            self._play_timer.stop()
        self._btn_play.setText("▶ Play Steps")

    def _cycle_speed(self) -> None:
        speeds = (0.5, 1.0, 2.0, 4.0)
        nxt = speeds[(speeds.index(self._speed_mult) + 1) % len(speeds)] if self._speed_mult in speeds else 1.0
        self._speed_mult = nxt
        self._btn_speed.setText(f"{nxt:g}×")
        self._play_timer.setInterval(max(80, int(550 / nxt)))

    def _on_playback_tick(self) -> None:
        if self._active_snap_idx < 0:
            self._stop_playback()
            return
        bundle = self._snapshots[self._active_snap_idx].bundle
        if self._step_idx + 1 < len(bundle.steps):
            self._jump_to_step(self._step_idx + 1)
        else:
            self._stop_playback()

    def _jump_to_final_step(self) -> None:
        self._stop_playback()
        if self._active_snap_idx >= 0:
            bundle = self._snapshots[self._active_snap_idx].bundle
            self._jump_to_step(max(0, len(bundle.steps) - 1))

    def _jump_to_step(self, idx: int) -> None:
        if self._active_snap_idx < 0:
            return
        bundle = self._snapshots[self._active_snap_idx].bundle
        if not bundle.steps:
            return
        idx = max(0, min(len(bundle.steps) - 1, idx))
        self._step_slider.blockSignals(True)
        self._step_slider.setValue(idx)
        self._step_slider.blockSignals(False)
        self._apply_step(idx, auto_focus_canvas=True)

    def _on_slider_changed(self, value: int) -> None:
        self._apply_step(value, auto_focus_canvas=True)

    def _apply_step(self, idx: int, auto_focus_canvas: bool) -> None:
        if self._active_snap_idx < 0 or self._game is None:
            return
        snap = self._snapshots[self._active_snap_idx]
        bundle = snap.bundle
        if not bundle.steps:
            return

        self._step_idx = max(0, min(len(bundle.steps) - 1, idx))
        step = bundle.steps[self._step_idx]

        self._lbl_step_counter.setText(f"Step {step.step_index} / {len(bundle.steps)}")
        self._lbl_step_explain.setText(
            f"[α = {step.cur_alpha} , β = {step.cur_beta} , v = {step.cur_v}]   {step.headline} — {step.detail}"
        )

        self._tree_canvas.set_step_index(self._step_idx, auto_focus=auto_focus_canvas)

        # Highlight matching row in Sheet-6 Trace Table
        row_idx = step.trace_visit_id - 1
        if 0 <= row_idx < self._trace_table.rowCount():
            self._trace_table.selectRow(row_idx)
            item = self._trace_table.item(row_idx, 0)
            if item is not None:
                self._trace_table.scrollToItem(item)

        # Reconstruct exact 7x6 board at this step's active node & update ribbon + Eval tab!
        node = bundle.node_by_id.get(step.active_node_id)
        if node is not None:
            self._inspect_node(node, step.active_path, live_window=f"α = {step.cur_alpha}   |   β = {step.cur_beta}   |   v = {step.cur_v}")

    # ---------------------------------------------------- node click handlers
    def _inspect_node(self, node: TreeNode, path: tuple[int, ...], live_window: Optional[str] = None) -> None:
        if self._active_snap_idx < 0 or self._game is None:
            return
        snap = self._snapshots[self._active_snap_idx]
        board = reconstruct_board_at_path(self._game, snap.state_before, path, node)
        lbl = format_path_label(path)
        role_tag = (
            "□ TERMINAL"
            if (node.is_leaf and node.leaf_kind is LeafKind.TERMINAL)
            else ("□ LEAF" if node.is_leaf else ("△ MAX" if node.is_max else "▽ MIN"))
        )
        title = f"Node {lbl} ({role_tag}, d={node.depth}) · Turn {snap.turn_number}"
        win_txt = live_window or (
            f"Entry [α={format_eval_score(node.alpha)}, β={format_eval_score(node.beta)}]  →  "
            f"Value {node.bound.symbol} {format_eval_score(node.value)}"
        )

        self._node_ribbon.set_node_state(
            board=board,
            heuristic_key=self._heuristic_key,
            title=title,
            window_line=win_txt,
            is_terminal_leaf=(node.is_leaf and node.leaf_kind is LeafKind.TERMINAL),
            terminal_score=node.value,
        )
        self._selected_node_board = board
        self._selected_node_label = f"{lbl} ({role_tag}, d={node.depth})"
        self._eval_uses_node = True
        self._refresh_eval_canvas()

    def _on_canvas_node_selected(self, node: TreeNode, path: tuple[int, ...]) -> None:
        self._stop_playback()
        if self._active_snap_idx >= 0:
            vid = self._snapshots[self._active_snap_idx].bundle.visit_id_by_node.get(id(node))
            if vid is not None and 0 <= vid - 1 < self._trace_table.rowCount():
                self._trace_table.selectRow(vid - 1)
                it = self._trace_table.item(vid - 1, 0)
                if it is not None:
                    self._trace_table.scrollToItem(it)
        self._inspect_node(node, path)

    def _on_trace_row_clicked(self, row_idx: int, _col: int) -> None:
        if self._active_snap_idx < 0:
            return
        self._stop_playback()
        bundle = self._snapshots[self._active_snap_idx].bundle
        if 0 <= row_idx < len(bundle.trace_rows):
            trow = bundle.trace_rows[row_idx]
            self._tree_canvas.select_node_by_id(trow.node_id)
            win = (
                f"Sheet-6 Row #{trow.visit_id}: old α={trow.old_alpha}→{trow.new_alpha}, "
                f"old β={trow.old_beta}→{trow.new_beta}, v: {trow.old_value}→{trow.new_value} ({trow.note})"
            )
            self._inspect_node(trow.node, trow.path, live_window=win)

    def _on_comp_row_clicked(self, row_idx: int, _col: int) -> None:
        if self._active_snap_idx < 0:
            return
        self._stop_playback()
        bundle = self._snapshots[self._active_snap_idx].bundle
        if 0 <= row_idx < len(bundle.computation_rows):
            crow = bundle.computation_rows[row_idx]
            self._tree_canvas.select_node_by_id(crow.node_id)
            self._inspect_node(crow.node, crow.path, live_window=f"{crow.computation}  ⇒  {crow.backed_up_value}")

    def _on_pv_clicked(self) -> None:
        self._tree_canvas.expand_pv_only()
        if self._active_snap_idx >= 0:
            res = self._snapshots[self._active_snap_idx].result
            pv = res.principal_columns
            if len(pv) > 1:
                self.pv_preview_requested.emit(pv[1:])

    def _on_toggle_windows(self) -> None:
        shown = self._tree_canvas.toggle_window_labels()
        self._btn_win_lbl.setText("[α,β] Windows: ON" if shown else "[α,β] Windows: OFF")

    # ------------------------------------------------------------ eval & trace
    def _set_eval_source(self, use_node: bool) -> None:
        self._eval_uses_node = use_node
        self._refresh_eval_canvas()

    def _toggle_candidates(self) -> None:
        self._show_candidates = not self._show_candidates
        self._btn_cand.setText("Open-3 Targets: ON" if self._show_candidates else "Open-3 Targets: OFF")
        self._refresh_eval_canvas()

    def _refresh_eval_canvas(self) -> None:
        if self._eval_uses_node and self._selected_node_board is not None:
            board = self._selected_node_board
            label = self._selected_node_label
            self._btn_eval_node.setStyleSheet("border: 1px solid #5fd6c4; color: #fae09e;")
            self._btn_eval_live.setStyleSheet("")
        else:
            board = self._current_board
            label = "Current Live Board"
            self._btn_eval_live.setStyleSheet("border: 1px solid #5fd6c4; color: #fae09e;")
            self._btn_eval_node.setStyleSheet("")
        self._eval_canvas.set_data(board, self._heuristic_key, label, self._show_candidates)

    def _copy_trace(self) -> None:
        txt = self._trace_edit.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)

    def _export_trace(self) -> None:
        if self._active_snap_idx < 0:
            return
        snap = self._snapshots[self._active_snap_idx]
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Full Minimax Tree & Sheet-6 Trace",
            f"minimax_sheet6_turn_{snap.turn_number}_K{snap.result.k}.txt",
            "Text Files (*.txt)",
        )
        if file_path:
            report = render_detailed_console_report(
                snap.result,
                self._heuristic_key,
                max_tree_lines=50000,
                max_table_rows=50000,
            )
            Path(file_path).write_text(report, encoding="utf-8")
