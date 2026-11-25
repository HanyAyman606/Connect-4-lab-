"""Archive & Experimental Report Analysis screen ('experiments/*.csv').

Loads the real experimental CSV benchmarks produced by ``experiments/``:
  1. Depth K Scaling (k_analysis.csv: K=1..6 visited, expanded, ms, 7^K & 7^(K/2))
  2. Move Ordering Comparison (final_candidates.csv & final_candidates_k4.csv)
  3. Heuristic Tournament (Windows vs Gravity vs Opportunities across K=2,3,4)
  4. Weight Tuning: Hill Climbing vs Genetic Algorithm & Center Sweep
  5. Architecture, Data Structures & Lab Assumptions Guide (for TA discussion)
"""

from __future__ import annotations

import csv
import math
import time
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QFileDialog, QWidget

from ui.theme import (
    PROJECT_ROOT,
    AmbientParticleField,
    AssetCache,
    Palette,
    make_display_font,
    make_ui_font,
)

_EXPERIMENTS_DIR = PROJECT_ROOT / "experiments"
_ARCHIVE_BG = "wallpaperflare.com_wallpaper (3).jpg"


def _read_csv_rows(filename: str) -> list[dict[str, str]]:
    path = _EXPERIMENTS_DIR / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ArchiveScreen(QWidget):
    """Interactive multi-tab benchmark & architecture archive for the report & viva."""

    back_requested = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._tab_idx: int = 0
        self._tabs: tuple[str, ...] = (
            "1 · Depth K Scaling",
            "2 · Move Ordering",
            "3 · Heuristics Matchups",
            "4 · HC vs GA Tuning",
            "5 · Architecture & Viva",
        )
        self._hitboxes: dict[str, QRectF] = {}
        self._hovered: Optional[str] = None

        self._k_rows: list[dict[str, str]] = []
        self._cand_rows: list[dict[str, str]] = []
        self._tuning_rows: list[dict[str, str]] = []
        self._center_val_rows: list[dict[str, str]] = []
        self.reload_data()

        self._particles = AmbientParticleField(count=30, seed=404)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def reload_data(self) -> None:
        self._k_rows = _read_csv_rows("k_analysis.csv")
        self._cand_rows = _read_csv_rows("final_candidates.csv") + _read_csv_rows("final_candidates_k4.csv")
        self._tuning_rows = _read_csv_rows("heuristic_tuning.csv")
        self._center_val_rows = _read_csv_rows("center_weight_validation.csv")
        self.update()

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
        self.reload_data()
        self._last_tick = time.perf_counter()
        if not self._timer.isActive():
            self._timer.start()
        self.setFocus()

    def _on_tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self._last_tick))
        self._last_tick = now
        self._particles.step(dt)
        self.update()

    # --------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        self._hitboxes.clear()
        elapsed = time.perf_counter() - self._t0

        bg = AssetCache.cover(_ARCHIVE_BG, w, h)
        if not bg.isNull():
            painter.drawPixmap(0, 0, bg)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(6, 9, 16, 228))
        veil.setColorAt(1.0, QColor(5, 8, 14, 244))
        painter.fillRect(0, 0, w, h, veil)

        self._particles.paint(painter, w, h, elapsed)

        # Top Bar + Title + Tab Strip
        self._paint_top_header(painter, w)

        content_rect = QRectF(26, 108, w - 52, h - 130)
        painter.setBrush(QColor(10, 15, 26, 232))
        painter.setPen(QPen(QColor(232, 194, 106, 85), 1.3))
        painter.drawRoundedRect(content_rect, 14, 14)

        inner = content_rect.adjusted(20, 16, -20, -16)
        if self._tab_idx == 0:
            self._paint_tab_k_scaling(painter, inner)
        elif self._tab_idx == 1:
            self._paint_tab_ordering(painter, inner)
        elif self._tab_idx == 2:
            self._paint_tab_heuristics(painter, inner)
        elif self._tab_idx == 3:
            self._paint_tab_tuning(painter, inner)
        else:
            self._paint_tab_architecture(painter, inner)

        painter.end()

    def _paint_top_header(self, painter: QPainter, w: int) -> None:
        r_back = QRectF(26, 16, 134, 32)
        self._hitboxes["back"] = r_back
        self._draw_chip(painter, r_back, "«  Back", self._hovered == "back", False)

        r_png = QRectF(w - 332, 16, 158, 32)
        self._hitboxes["export_png"] = r_png
        self._draw_chip(painter, r_png, "Export Tab PNG", self._hovered == "export_png", False)

        r_fs = QRectF(w - 164, 16, 138, 32)
        self._hitboxes["fs"] = r_fs
        self._draw_chip(painter, r_fs, "Full Screen (F11)", self._hovered == "fs", False)

        painter.setFont(make_display_font(18, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(QRectF(170, 12, w - 510, 38), Qt.AlignmentFlag.AlignCenter, "ROYAL ARCHIVE · EXPERIMENTAL ANALYSIS")

        # 5 Tab Buttons
        gap = 8.0
        total_w = w - 52.0
        tw = (total_w - gap * (len(self._tabs) - 1)) / len(self._tabs)
        for i, title in enumerate(self._tabs):
            tr = QRectF(26 + i * (tw + gap), 60, tw, 36)
            hid = f"tab:{i}"
            self._hitboxes[hid] = tr
            self._draw_chip(painter, tr, title, self._hovered == hid, self._tab_idx == i)

    # ------------------------------------------------- Tab 0: K Complexity
    def _paint_tab_k_scaling(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(make_display_font(14, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), 24),
            Qt.AlignmentFlag.AlignLeft,
            "Alpha-Beta Search Cost vs Depth K (experiments/k_analysis.csv · 20 Shared Positions, Windows + Four-Gain Ordering)",
        )

        if not self._k_rows:
            return

        top_y = rect.top() + 32.0
        chart_h = rect.height() * 0.54
        half_w = (rect.width() - 18.0) * 0.5

        ks = [int(r["k"]) for r in self._k_rows]
        visited = [float(r["average_nodes_visited"]) for r in self._k_rows]
        expanded = [float(r["average_nodes_expanded"]) for r in self._k_rows]
        ms_vals = [float(r["average_search_ms"]) for r in self._k_rows]
        unpruned = [float(sum(7 ** d for d in range(k + 1))) for k in ks]
        ideal_ab = [float(sum(7 ** (d / 2.0) for d in range(k + 1))) for k in ks]

        # Left Chart: Log-10 Nodes vs K alongside O(b^K) and O(b^(K/2))
        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left(), top_y, half_w, chart_h),
            title="LOG₁₀ NODES vs K  (WITH b^K AND b^(K/2) COMPLEXITY BOUNDS)",
            x_labels=[f"K={k}" for k in ks],
            series=[
                ("7^K Unpruned Bound", [math.log10(max(1.0, v)) for v in unpruned], QColor("#c2412d"), True),
                ("Actual Visited (α-β)", [math.log10(max(1.0, v)) for v in visited], Palette.SPIRIT_CYAN, False),
                ("Actual Expanded", [math.log10(max(1.0, v)) for v in expanded], Palette.MEMORY_GOLD, False),
                ("Ideal 7^(K/2) Curve", [math.log10(max(1.0, v)) for v in ideal_ab], QColor("#80ed99"), True),
            ],
            y_unit="log₁₀",
        )

        # Right Chart: Average & Median Time (ms) vs K
        medians = [float(r["median_search_ms"]) for r in self._k_rows]
        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left() + half_w + 18.0, top_y, half_w, chart_h),
            title="WALL-CLOCK SEARCH TIME (ms) vs DEPTH K",
            x_labels=[f"K={k}" for k in ks],
            series=[
                ("Mean Time (ms)", ms_vals, Palette.MEMORY_GOLD, False),
                ("Median Time (ms)", medians, Palette.SPIRIT_CYAN, False),
            ],
            y_unit="ms",
        )

        # Bottom Data Table
        ty = top_y + chart_h + 14.0
        headers = ("Depth K", "7^K Unpruned", "Avg Visited", "Avg Expanded", "Avg Cutoffs", "Avg Pruned", "Pruning Saved", "Mean (ms)", "Median (ms)")
        rows_txt = []
        for idx, r in enumerate(self._k_rows):
            vis = visited[idx]
            unp = unpruned[idx]
            saved = 100.0 * (1.0 - vis / unp)
            rows_txt.append((
                f"K = {r['k']}",
                f"{int(unp):,}",
                f"{vis:,.1f}",
                f"{float(r['average_nodes_expanded']):,.1f}",
                f"{float(r['average_cutoffs']):,.1f}",
                f"{float(r['average_pruned_branches']):,.1f}",
                f"{saved:.1f}%",
                f"{float(r['average_search_ms']):.2f} ms",
                f"{float(r['median_search_ms']):.2f} ms",
            ))
        self._draw_table(painter, QRectF(rect.left(), ty, rect.width(), rect.bottom() - ty), headers, rows_txt)

    # ------------------------------------------------- Tab 1: Move Ordering
    def _paint_tab_ordering(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(make_display_font(14, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), 24),
            Qt.AlignmentFlag.AlignLeft,
            "Move Ordering Efficiency on Window Heuristic (experiments/final_candidates*.csv · Exact Same Minimax Value, Different Pruning)",
        )

        # Aggregate average nodes/search & ms/search per ordering at K=2, 3, 4 under 'orderings/windows'
        ord_names = ("center", "four_gain_center", "threat_center", "tactical")
        ks = (2, 3, 4)
        nodes_map: dict[tuple[int, str], list[float]] = {}
        ms_map: dict[tuple[int, str], list[float]] = {}

        for r in self._cand_rows:
            if r.get("experiment") != "orderings/windows":
                continue
            k = int(r["k"])
            for side, col_n, col_ms in (
                ("agent_a", "average_nodes_per_search_a", "average_search_ms_a"),
                ("agent_b", "average_nodes_per_search_b", "average_search_ms_b"),
            ):
                ag = r[side]
                nodes_map.setdefault((k, ag), []).append(float(r[col_n]))
                ms_map.setdefault((k, ag), []).append(float(r[col_ms]))

        top_y = rect.top() + 32.0
        chart_h = rect.height() * 0.52
        half_w = (rect.width() - 18.0) * 0.5

        colors = {
            "center": QColor("#9ba9be"),
            "four_gain_center": Palette.SPIRIT_CYAN,
            "threat_center": Palette.MEMORY_GOLD,
            "tactical": QColor("#80ed99"),
        }
        labels = {
            "center": "Center-First",
            "four_gain_center": "Four-Gain + Center",
            "threat_center": "Threat + Center",
            "tactical": "Full Tactical",
        }

        series_nodes = []
        series_ms = []
        for oname in ord_names:
            n_pts = [sum(nodes_map.get((k, oname), [0.0])) / max(1, len(nodes_map.get((k, oname), [1]))) for k in ks]
            m_pts = [sum(ms_map.get((k, oname), [0.0])) / max(1, len(ms_map.get((k, oname), [1]))) for k in ks]
            series_nodes.append((labels[oname], n_pts, colors[oname], False))
            series_ms.append((labels[oname], m_pts, colors[oname], False))

        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left(), top_y, half_w, chart_h),
            title="AVG VISITED NODES / SEARCH (LOWER = BETTER PRUNING)",
            x_labels=[f"K={k}" for k in ks],
            series=series_nodes,
            y_unit="nodes",
        )
        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left() + half_w + 18.0, top_y, half_w, chart_h),
            title="AVG WALL-CLOCK TIME / SEARCH (ms) — PRUNING vs OVERHEAD TRADE-OFF",
            x_labels=[f"K={k}" for k in ks],
            series=series_ms,
            y_unit="ms",
        )

        ty = top_y + chart_h + 14.0
        headers = ("Ordering Strategy", "K=2 Nodes", "K=2 ms", "K=3 Nodes", "K=3 ms", "K=4 Nodes", "K=4 ms", "Key Takeaway")
        notes = {
            "center": "Fastest key, baseline",
            "four_gain_center": "Best speed + pruning ★",
            "threat_center": "1-ply threat lookahead",
            "tactical": "Fewest nodes (178 at K=4)",
        }
        rows_txt = []
        for idx, oname in enumerate(ord_names):
            n_vals = series_nodes[idx][1]
            m_vals = series_ms[idx][1]
            rows_txt.append((
                labels[oname],
                f"{n_vals[0]:.1f}",
                f"{m_vals[0]:.2f} ms",
                f"{n_vals[1]:.1f}",
                f"{m_vals[1]:.2f} ms",
                f"{n_vals[2]:.1f}",
                f"{m_vals[2]:.2f} ms",
                notes[oname],
            ))
        self._draw_table(painter, QRectF(rect.left(), ty, rect.width(), rect.bottom() - ty), headers, rows_txt)

    # ------------------------------------------------- Tab 2: Heuristics
    def _paint_tab_heuristics(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(make_display_font(14, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), 24),
            Qt.AlignmentFlag.AlignLeft,
            "Three Devils Heuristic Head-to-Head Tournament (Balanced Role & Start Rotation, Shared Center Ordering)",
        )

        matchups = [
            r for r in self._cand_rows
            if r.get("experiment") == "heuristics/center"
            and r.get("agent_a") in ("windows", "gravity", "opportunities")
            and r.get("agent_b") in ("windows", "gravity", "opportunities")
        ]

        headers = (
            "Depth K",
            "Agent A",
            "Agent B",
            "Games",
            "A Wins – Draws – B Wins",
            "Avg Fours Margin (A)",
            "Nodes/Search (A / B)",
            "Time ms (A / B)",
        )
        pretty = {
            "windows": "Shriek (Windows)",
            "gravity": "Mora (Gravity)",
            "opportunities": "Howl (Opportunities)",
        }
        rows_txt = []
        for r in matchups:
            rows_txt.append((
                f"K = {r['k']}",
                pretty.get(r["agent_a"], r["agent_a"]),
                pretty.get(r["agent_b"], r["agent_b"]),
                r["games"],
                f"{r['wins_a']}W – {r['draws']}D – {r['wins_b']}L",
                f"{float(r['average_score_margin_a']):+.2f}",
                f"{float(r['average_nodes_per_search_a']):.1f} / {float(r['average_nodes_per_search_b']):.1f}",
                f"{float(r['average_search_ms_a']):.2f} / {float(r['average_search_ms_b']):.2f}",
            ))

        table_h = rect.height() - 128.0
        self._draw_table(painter, QRectF(rect.left(), rect.top() + 34, rect.width(), table_h), headers, rows_txt)

        # Summary insight banner at bottom
        ins_rect = QRectF(rect.left(), rect.bottom() - 82, rect.width(), 78)
        painter.setBrush(QColor(15, 24, 38, 225))
        painter.setPen(QPen(Palette.SPIRIT_CYAN, 1.1))
        painter.drawRoundedRect(ins_rect, 10, 10)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(QRectF(ins_rect.left() + 14, ins_rect.top() + 8, ins_rect.width() - 28, 18), Qt.AlignmentFlag.AlignLeft, "TOURNAMENT FINDINGS (WHY THE 3 DEVILS SCALE FROM EASY → HARD):")
        painter.setFont(make_ui_font(8))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(ins_rect.left() + 14, ins_rect.top() + 28, ins_rect.width() - 28, 44),
            Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap,
            "• At deeper search (K=4), Window Heuristic dominates Scoring-Opportunities 10W–2D–0L (+1.33 fours/game) and outscores Gravity-Aware (+0.67 margin) at lower ms/search.\n"
            "• Gravity-Aware (Mora) beats immediate-only Opportunities 4W–6D–2L (+0.50 margin) at K=4 by discounting floating windows that lack support stones.",
        )

    # ------------------------------------------------- Tab 3: HC vs GA Tuning
    def _paint_tab_tuning(self, painter: QPainter, rect: QRectF) -> None:
        painter.setFont(make_display_font(14, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(rect.left(), rect.top(), rect.width(), 24),
            Qt.AlignmentFlag.AlignLeft,
            "Local Search Heuristic Weight Tuning: Hill Climbing vs Genetic Algorithm & Center-Weight Validation",
        )

        val_rows = [r for r in self._tuning_rows if r.get("phase") == "validation"]
        top_y = rect.top() + 32.0
        half_w = (rect.width() - 18.0) * 0.5
        chart_h = rect.height() * 0.46

        hc_margins = [float(r["average_score_margin"]) for r in val_rows if r["method"] == "hill_climbing"]
        ga_margins = [float(r["average_score_margin"]) for r in val_rows if r["method"] == "genetic_algorithm"]

        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left(), top_y, half_w, chart_h),
            title="160-GAME VALIDATION MARGIN vs UNTUNED BASELINE (100, 10, 3, 2)",
            x_labels=["K=2", "K=3", "K=4"],
            series=[
                ("Genetic Algorithm (100, 10, 5, 6)", ga_margins, Palette.SPIRIT_CYAN, False),
                ("Hill Climbing (100, 10, 2, 4)", hc_margins, Palette.MEMORY_GOLD, False),
            ],
            y_unit="fours",
        )

        # Right chart: Center-weight validation at K=4
        k4_center = [r for r in self._center_val_rows if r.get("k") == "4"]
        c_labels = [f"w_c={r['center_control']}" for r in k4_center]
        c_margins = [float(r["average_score_margin"]) for r in k4_center]
        self._draw_multi_line_chart(
            painter,
            QRectF(rect.left() + half_w + 18.0, top_y, half_w, chart_h),
            title="CENTER WEIGHT VALIDATION AT K=4 (64 BALANCED GAMES EACH)",
            x_labels=c_labels,
            series=[("Avg Score Margin vs Baseline", c_margins, Palette.GOLD_BRIGHT, False)],
            y_unit="fours",
        )

        ty = top_y + chart_h + 14.0
        headers = ("Method / Stage", "Test K", "Weights (Fours, Open3, Open2, Center)", "Games", "W – D – L vs Baseline", "Avg Margin")
        rows_txt = []
        for r in val_rows:
            m_lbl = "Hill Climbing Winner" if r["method"] == "hill_climbing" else "Genetic Algorithm Winner"
            rows_txt.append((
                m_lbl,
                f"K = {r['k']}",
                f"(100, {r['open_threes']}, {r['open_twos']}, {r['center_control']})",
                r["games"],
                f"{r['wins']}W – {r['draws']}D – {r['losses']}L",
                f"{float(r['average_score_margin']):+.3f}",
            ))
        for r in k4_center:
            if r["center_control"] == "10":
                rows_txt.append((
                    "Final Locked (GA + Center Sweep)",
                    "K = 4",
                    "(100, 10.0, 5.0, 10.0)  ★ FINAL",
                    r["games"],
                    f"{r['wins']}W – {r['draws']}D – {r['losses']}L",
                    f"{float(r['average_score_margin']):+.3f}",
                ))
        self._draw_table(painter, QRectF(rect.left(), ty, rect.width(), rect.bottom() - ty), headers, rows_txt)

    # ------------------------------------------------- Tab 4: Architecture & Viva
    def _paint_tab_architecture(self, painter: QPainter, rect: QRectF) -> None:
        cards = (
            (
                "1 · PEAS & PROBLEM FORMULATION",
                Palette.SPIRIT_CYAN,
                "• Performance: Final connected-fours difference (Computer MAX − Human MIN) on a full 42-disc board.\n"
                "• Environment: 7×6 discrete grid; fully observable, deterministic, zero-sum, two-player adversarial.\n"
                "• Special Lab Rule: Game NEVER stops at the first four—all 69 four-cell windows count (5-in-a-row = 2 fours).",
            ),
            (
                "2 · CORE DATA STRUCTURES (IMMUTABLE & FAST)",
                Palette.MEMORY_GOLD,
                "• Flyweight Disc (core/disc.py): Cached immutable instances per (Owner, color) for O(1) identity checks.\n"
                "• Immutable Tuple-of-Tuples Board (core/board.py): drop() rebuilds only the landing row—zero undo bugs & hashable!\n"
                "• Cached 69 Windows (core/rules.py): @lru_cache precomputes all 24 horizontal, 21 vertical & 24 diagonal windows.",
            ),
            (
                "3 · MINIMAX α-β & SCALE INVARIANT",
                Palette.DEVIL_MAGMA,
                "• Terminal-Before-Cutoff Check: Full-board exact utility is checked BEFORE depth >= K so exact scores are never estimated.\n"
                "• Monotonic Normalization: eval = raw / (1000 + |raw|) strictly bounds heuristic guesses inside (−1, +1) so even a ±1 real terminal score outranks any heuristic guess!\n"
                "• Recorder Protocol: NullRecorder for pure timing benchmarks vs TreeRecorder for zero-coupling tree visualization.",
            ),
            (
                "4 · KEY ASSUMPTIONS & THREADING",
                QColor("#80ed99"),
                "• Level Counting: Root is depth 0; cutoff occurs after K plies (1 move = 1 level).\n"
                "• Console + GUI Traceability: Every AI turn prints the readable Minimax tree with LEAF eval values to stdout AND updates 'The Devil's Mind' panel.\n"
                "• Responsive Threading: Search runs inside AISearchWorker (QThread) so 60 FPS rendering never freezes.",
            ),
        )
        gap = 14.0
        cw = (rect.width() - gap) * 0.5
        ch = (rect.height() - gap) * 0.5
        for i, (title, col, body) in enumerate(cards):
            ri, ci = divmod(i, 2)
            cr = QRectF(rect.left() + ci * (cw + gap), rect.top() + ri * (ch + gap), cw, ch)
            painter.setBrush(QColor(14, 21, 36, 225))
            painter.setPen(QPen(col, 1.2))
            painter.drawRoundedRect(cr, 10, 10)

            painter.setFont(make_ui_font(10, bold=True))
            painter.setPen(col)
            painter.drawText(QRectF(cr.left() + 16, cr.top() + 12, cw - 32, 20), Qt.AlignmentFlag.AlignLeft, title)

            painter.setFont(make_ui_font(9))
            painter.setPen(Palette.TEXT_BONE)
            painter.drawText(
                QRectF(cr.left() + 16, cr.top() + 38, cw - 32, ch - 48),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                body,
            )

    # ------------------------------------------------------- chart/table helpers
    @staticmethod
    def _draw_multi_line_chart(
        painter: QPainter,
        rect: QRectF,
        title: str,
        x_labels: list[str],
        series: list[tuple[str, list[float], QColor, bool]],
        y_unit: str,
    ) -> None:
        painter.setBrush(QColor(14, 20, 34, 225))
        painter.setPen(QPen(QColor(232, 228, 216, 58), 1.0))
        painter.drawRoundedRect(rect, 9, 9)

        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(rect.left() + 12, rect.top() + 7, rect.width() - 24, 16), Qt.AlignmentFlag.AlignLeft, title)

        # Legend row
        lx = rect.left() + 12
        ly = rect.top() + 25
        painter.setFont(make_ui_font(7, bold=True))
        for name, _vals, col, dashed in series:
            pen = QPen(col, 2.0, Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            painter.drawLine(QPointF(lx, ly + 6), QPointF(lx + 16, ly + 6))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(lx + 20, ly, 150, 14), Qt.AlignmentFlag.AlignLeft, name)
            lx += painter.fontMetrics().horizontalAdvance(name) + 34

        plot = QRectF(rect.left() + 48, rect.top() + 46, rect.width() - 66, rect.height() - 72)
        if plot.height() < 20 or not x_labels:
            return

        all_vals = [v for _n, vals, _c, _d in series for v in vals]
        if not all_vals:
            return
        lo = min(0.0, min(all_vals))
        hi = max(all_vals) * 1.08
        span = max(1e-6, hi - lo)

        # Horizontal grid lines
        painter.setFont(make_ui_font(7))
        for gi in range(5):
            frac = gi / 4.0
            gy = plot.bottom() - frac * plot.height()
            gv = lo + frac * span
            painter.setPen(QPen(QColor(255, 255, 255, 22), 1.0))
            painter.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
            painter.setPen(Palette.TEXT_DIM)
            painter.drawText(QRectF(rect.left() + 4, gy - 7, 40, 14), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{gv:.1f}")

        # X labels
        n_x = len(x_labels)
        for i, xl in enumerate(x_labels):
            px = plot.left() + (plot.width() * i / max(1, n_x - 1)) if n_x > 1 else plot.center().x()
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(px - 28, plot.bottom() + 5, 56, 16), Qt.AlignmentFlag.AlignCenter, xl)

        # Series curves
        for _name, vals, col, dashed in series:
            if not vals:
                continue
            pts = [
                QPointF(
                    plot.left() + (plot.width() * i / max(1, len(vals) - 1)) if len(vals) > 1 else plot.center().x(),
                    plot.bottom() - ((v - lo) / span) * plot.height(),
                )
                for i, v in enumerate(vals)
            ]
            pen = QPen(col, 2.0, Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
            painter.setPen(pen)
            for i in range(len(pts) - 1):
                painter.drawLine(pts[i], pts[i + 1])
            painter.setBrush(col)
            painter.setPen(Qt.PenStyle.NoPen)
            for pt in pts:
                painter.drawEllipse(pt, 3.2, 3.2)

    @staticmethod
    def _draw_table(
        painter: QPainter,
        rect: QRectF,
        headers: tuple[str, ...],
        rows: list[tuple[str, ...]],
    ) -> None:
        if rect.height() < 32 or not headers:
            return
        col_w = rect.width() / len(headers)
        hdr_h = 24.0
        painter.fillRect(QRectF(rect.left(), rect.top(), rect.width(), hdr_h), QColor(20, 32, 52, 230))
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.MEMORY_GOLD)
        for ci, h_txt in enumerate(headers):
            painter.drawText(
                QRectF(rect.left() + ci * col_w + 6, rect.top(), col_w - 12, hdr_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                h_txt,
            )

        avail_h = rect.height() - hdr_h
        row_h = min(24.0, max(17.0, avail_h / max(1, len(rows))))
        max_rows = int(avail_h // row_h)
        painter.setFont(make_ui_font(8))
        for ri, row in enumerate(rows[:max_rows]):
            ry = rect.top() + hdr_h + ri * row_h
            if ri % 2 == 1:
                painter.fillRect(QRectF(rect.left(), ry, rect.width(), row_h), QColor(15, 22, 36, 165))
            for ci, cell in enumerate(row):
                painter.setPen(Palette.SPIRIT_CYAN if ci == 0 else Palette.TEXT_BONE)
                painter.drawText(
                    QRectF(rect.left() + ci * col_w + 6, ry, col_w - 12, row_h),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                    cell,
                )

    @staticmethod
    def _draw_chip(painter: QPainter, rect: QRectF, label: str, hovered: bool, active: bool) -> None:
        if active:
            bg = QColor(34, 78, 94, 235)
            border = Palette.SPIRIT_CYAN
            fg = Palette.GOLD_BRIGHT
        else:
            bg = QColor(22, 34, 54, 220) if hovered else QColor(12, 18, 30, 200)
            border = Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 68)
            fg = Palette.TEXT_BONE
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.25 if (active or hovered) else 1.0))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _export_png(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Archive Chart Screenshot",
            f"archive_tab_{self._tab_idx + 1}.png",
            "PNG Images (*.png)",
        )
        if file_path:
            self.grab().save(file_path)

    # ------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hov = next((k for k, r in self._hitboxes.items() if r.contains(pos)), None)
        if hov != self._hovered:
            self._hovered = hov
            self.update()
        self.setCursor(Qt.CursorShape.PointingHandCursor if hov else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        clicked = next((k for k, r in self._hitboxes.items() if r.contains(pos)), None)
        if clicked == "back":
            self.back_requested.emit()
        elif clicked == "export_png":
            self._export_png()
        elif clicked == "fs":
            self.toggle_fullscreen_requested.emit()
        elif clicked is not None and clicked.startswith("tab:"):
            self._tab_idx = int(clicked.split(":", 1)[1])
            self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.back_requested.emit()
        elif Qt.Key.Key_1 <= event.key() <= Qt.Key.Key_5:
            self._tab_idx = event.key() - Qt.Key.Key_1
            self.update()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)
