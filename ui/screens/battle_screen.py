"""Connect 4 Battlefield screen ('Connect 4: vs The Devils').

Combines:
- Left panel: Devil reactive portrait, live Soul Tally (connected-fours),
  42-stone full-board progress bar, and board overlay toggles.
- Center stage: Interactive 7x6 carved gnarled-wood ritual board with hover
  ghost orb, gravity-bounce drop animation, screen shake on new fours,
  overlapping 4-window beam highlights, and the 7-column Root Ordering &
  Minimax Value strip underneath.
- Right panel: Collapsible 'The Devil's Mind' inspector (Tree, Stats, Eval,
  and Console Trace tabs).
- Background QThread AI search so the window never freezes.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from core.board import Board
from core.owner import Owner
from setup.game_builder import build_session
from setup.game_session import GameSession
from setup.session_settings import SessionSettings
from tree_essentials import SearchResult
from ui.devils import DEVILS, DevilProfile
from ui.mind_panel import MindPanel
from ui.search_worker import (
    AISearchWorker,
    DerivedTreeMetrics,
    RootMoveSummary,
    compute_tree_metrics,
    find_candidate_cells,
    find_completed_four_windows,
    format_eval_score,
)
from ui.theme import (
     ASSETS_DIR,
    AmbientParticleField,
    AssetCache,
    Palette,
    _BOARD_META,
    draw_devil_disc,
    draw_ritual_board,
    draw_spirit_disc,
    make_display_font,
    make_ui_font,
)


@dataclass(slots=True)
class _DropAnim:
    column: int
    target_row: int
    owner: Owner
    started_at: float
    duration: float
    pending_ai_result: Optional[SearchResult] = None
    pending_metrics: Optional[DerivedTreeMetrics] = None


def _ease_out_bounce(t: float) -> float:
    """Classic smooth gravity fall with gentle wooden landing bounce in [0, 1]."""
    if t < 1.0 / 2.75:
        return 7.5625 * t * t
    if t < 2.0 / 2.75:
        t -= 1.5 / 2.75
        return 7.5625 * t * t + 0.75
    if t < 2.5 / 2.75:
        t -= 2.25 / 2.75
        return 7.5625 * t * t + 0.9375
    t -= 2.625 / 2.75
    return 7.5625 * t * t + 0.984375


class _BattleArenaCanvas(QWidget):
    """Left Devil Soul-Tally panel + Center 7x6 Board + Root Column Ordering Strip."""

    human_column_clicked = Signal(int)
    rematch_requested = Signal()
    finish_to_map_requested = Signal(bool)  # True if human won

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)

        self._devil: DevilProfile = DEVILS[0]
        self._session: Optional[GameSession] = None
        self._ai_thinking: bool = False
        self._drop_anim: Optional[_DropAnim] = None
        self._root_moves: tuple[RootMoveSummary, ...] = ()
        self._last_move_cell: Optional[tuple[int, int]] = None
        self._pv_preview_cols: tuple[int, ...] = ()
        self._pv_preview_until: float = 0.0

        self._hover_col: Optional[int] = None
        self._hovered_btn: Optional[str] = None
        self._show_four_lines: bool = True
        self._show_candidate_overlay: bool = False

        # Devil mood & screen shake state
        self._devil_line: str = ""
        self._mood: str = "neutral"  # "neutral" | "flinch" | "laugh"
        self._mood_until: float = 0.0
        self._shake_until: float = 0.0

        # Fight-wide cumulative counters for the end-of-fight summary
        self._total_ai_nodes: int = 0
        self._total_ai_cutoffs: int = 0
        self._total_ai_time: float = 0.0
        self._ai_turns_played: int = 0

        # Hitboxes populated during paint
        self._col_strip_rects: list[QRectF] = []
        self._board_grid_geom: tuple[float, float, float, float, float] = (0, 0, 0, 0, 0)
        self._toggle_fours_rect = QRectF()
        self._toggle_cand_rect = QRectF()
        self._rematch_rect = QRectF()
        self._return_map_rect = QRectF()

        self._t0 = time.perf_counter()

    # ------------------------------------------------------------------ state
    def bind_match(self, devil: DevilProfile, session: GameSession) -> None:
        self._devil = devil
        self._session = session
        self._ai_thinking = False
        self._drop_anim = None
        self._root_moves = tuple(
            RootMoveSummary(c, None, None, "", False, False, True)
            for c in range(session.game.rules.cols)
        )
        self._last_move_cell = None
        self._pv_preview_cols = ()
        self._devil_line = devil.intro_taunt
        self._mood = "neutral"
        self._shake_until = 0.0
        self._total_ai_nodes = 0
        self._total_ai_cutoffs = 0
        self._total_ai_time = 0.0
        self._ai_turns_played = 0
        self.update()

    def set_ai_thinking(self, thinking: bool) -> None:
        self._ai_thinking = thinking
        if thinking:
            self._devil_line = "The Devil considers the branches ahead..."
        self.update()

    def set_drop_anim(self, anim: Optional[_DropAnim]) -> None:
        self._drop_anim = anim
        self.update()

    def record_move_outcome(
        self,
        row: int,
        col: int,
        gained_human_fours: int,
        gained_comp_fours: int,
        root_moves: Optional[tuple[RootMoveSummary, ...]] = None,
        ai_result: Optional[SearchResult] = None,
    ) -> None:
        self._last_move_cell = (row, col)
        if root_moves is not None:
            self._root_moves = root_moves
        if ai_result is not None:
            self._total_ai_nodes += ai_result.stats.visited
            self._total_ai_cutoffs += ai_result.stats.cutoffs
            self._total_ai_time += ai_result.stats.elapsed
            self._ai_turns_played += 1

        now = time.perf_counter()
        if gained_human_fours > 0:
            self._devil_line = self._devil.flinch_line
            self._mood = "flinch"
            self._mood_until = now + 2.4
            self._shake_until = now + 0.28
        elif gained_comp_fours > 0:
            self._devil_line = self._devil.score_taunt
            self._mood = "laugh"
            self._mood_until = now + 2.4
            self._shake_until = now + 0.28
        elif self._session is not None and self._session.is_over:
            diff = self._session.computer_fours - self._session.human_fours
            if diff < 0:
                self._devil_line = self._devil.defeat_line
                self._mood = "flinch"
            elif diff > 0:
                self._devil_line = self._devil.victory_taunt
                self._mood = "laugh"
            else:
                self._devil_line = "Forty-two stones, and neither spirit yields."
                self._mood = "neutral"
        self.update()

    def trigger_pv_preview(self, pv_cols: tuple[int, ...]) -> None:
        self._pv_preview_cols = pv_cols
        self._pv_preview_until = time.perf_counter() + 3.2
        self.update()

    # --------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        if self._session is None:
            painter.end()
            return

        w, h = self.width(), self.height()
        now = time.perf_counter()
        elapsed = now - self._t0

        left_w = min(268.0, max(226.0, w * 0.29))
        left_rect = QRectF(0, 0, left_w, h)
        center_rect = QRectF(left_w + 12.0, 0, max(200.0, w - left_w - 12.0), h)

        self._paint_left_tally(painter, left_rect, now)
        self._paint_center_stage(painter, center_rect, now, elapsed)

        painter.end()

    def _paint_left_tally(self, painter: QPainter, rect: QRectF, now: float) -> None:
        assert self._session is not None
        devil = self._devil
        accent = QColor(devil.accent_hex)

        painter.save()
        painter.setBrush(QColor(10, 14, 24, 228))
        border_col = accent
        if now < self._mood_until:
            border_col = Palette.SPIRIT_CYAN if self._mood == "flinch" else Palette.DEVIL_MAGMA
        painter.setPen(QPen(QColor(border_col.red(), border_col.green(), border_col.blue(), 135), 1.3))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 12, 12)

        pad = 12.0
        tx = rect.left() + pad
        tw = rect.width() - 2 * pad
        y = rect.top() + 10.0

        # 1. Devil Portrait Window
        art_h = min(148.0, rect.height() * 0.25)
        art_rect = QRectF(tx, y, tw, art_h)
        clip = QPainterPath()
        clip.addRoundedRect(art_rect, 9, 9)
        painter.save()
        painter.setClipPath(clip)
        pix = AssetCache.cover(devil.scene_image, max(1, int(tw)), max(1, int(art_h)))
        if not pix.isNull():
            painter.drawPixmap(art_rect.topLeft(), pix)
        if now < self._mood_until:
            flash = QColor(95, 214, 196, 48) if self._mood == "flinch" else QColor(232, 74, 39, 55)
            painter.fillRect(art_rect, flash)
        fade = QLinearGradient(0, art_rect.bottom() - 48, 0, art_rect.bottom())
        fade.setColorAt(0.0, QColor(10, 14, 24, 0))
        fade.setColorAt(1.0, QColor(10, 14, 24, 230))
        painter.fillRect(art_rect, fade)
        painter.restore()

        painter.setPen(QPen(accent, 1.1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(art_rect, 9, 9)

        painter.setFont(make_display_font(13, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx + 8, art_rect.bottom() - 26, tw - 16, 22), Qt.AlignmentFlag.AlignLeft, f"{devil.name} · K={self._session.settings.k}")
        y += art_h + 8.0

        # 2. Reactive Devil Dialogue Box
        q_rect = QRectF(tx, y, tw, 52.0)
        painter.setBrush(QColor(15, 21, 35, 210))
        painter.setPen(QPen(QColor(232, 228, 216, 48), 1.0))
        painter.drawRoundedRect(q_rect, 7, 7)
        painter.setFont(make_display_font(9, italic=True))
        painter.setPen(Palette.GOLD_BRIGHT if not self._ai_thinking else Palette.SPIRIT_CYAN)
        painter.drawText(
            q_rect.adjusted(8, 5, -8, -5),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            f"“{self._devil_line}”",
        )
        y += 60.0

        # 3. SOUL TALLY (Connected-Fours Scoreboard)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.MEMORY_GOLD)
        painter.drawText(QRectF(tx, y, tw, 15), Qt.AlignmentFlag.AlignLeft, "SOUL TALLY (CONNECTED-FOURS)")
        y += 18.0

        h_fours = self._session.human_fours
        c_fours = self._session.computer_fours

        # You row
        you_r = QRectF(tx, y, tw, 40.0)
        painter.setBrush(QColor(14, 30, 44, 215))
        painter.setPen(QPen(QColor(95, 214, 196, 110), 1.1))
        painter.drawRoundedRect(you_r, 8, 8)
        draw_spirit_disc(painter, QPointF(tx + 20, y + 20), 11.0, phase=now)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(tx + 38, y + 4, tw - 90, 16), Qt.AlignmentFlag.AlignLeft, "You (Spirit)")
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx + 38, y + 20, tw - 90, 14), Qt.AlignmentFlag.AlignLeft, "MIN Player")
        painter.setFont(make_display_font(18, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, y, tw - 12, 40), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(h_fours))
        y += 46.0

        # Devil row
        dev_r = QRectF(tx, y, tw, 40.0)
        painter.setBrush(QColor(34, 16, 18, 215))
        painter.setPen(QPen(QColor(214, 79, 48, 115), 1.1))
        painter.drawRoundedRect(dev_r, 8, 8)
        draw_devil_disc(painter, QPointF(tx + 20, y + 20), 11.0, phase=now)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.DEVIL_MAGMA)
        painter.drawText(QRectF(tx + 38, y + 4, tw - 90, 16), Qt.AlignmentFlag.AlignLeft, f"{devil.name}")
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx + 38, y + 20, tw - 90, 14), Qt.AlignmentFlag.AlignLeft, "MAX Agent")
        painter.setFont(make_display_font(18, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, y, tw - 12, 40), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, str(c_fours))
        y += 46.0

        # Current leader indicator
        diff = h_fours - c_fours
        if diff > 0:
            lead_txt, lead_col = f"Spirit Leads by +{diff} Four(s)", Palette.SPIRIT_CYAN
        elif diff < 0:
            lead_txt, lead_col = f"{devil.name} Leads by +{-diff} Four(s)", Palette.DEVIL_MAGMA
        else:
            lead_txt, lead_col = "Tied in Connected-Fours", Palette.MEMORY_GOLD
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(lead_col)
        painter.drawText(QRectF(tx, y, tw, 18), Qt.AlignmentFlag.AlignCenter, lead_txt)
        y += 24.0

        # 4. Turn Counter n / 42 (Full-board ending condition)
        turn_n = self._session.turn_count
        max_t = self._session.max_turns
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, y, tw, 16), Qt.AlignmentFlag.AlignLeft, f"STONES PLACED: {turn_n} / {max_t}")
        y += 18.0

        pbar = QRectF(tx, y, tw, 10.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(24, 34, 52, 220))
        painter.drawRoundedRect(pbar, 5, 5)
        if turn_n > 0:
            painter.setBrush(Palette.MEMORY_GOLD)
            painter.drawRoundedRect(QRectF(tx, y, max(6.0, tw * (turn_n / max_t)), 10.0), 5, 5)
        y += 14.0
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.TEXT_DIM)
        painter.drawText(QRectF(tx, y, tw, 14), Qt.AlignmentFlag.AlignLeft, "Play continues until all 42 slots are full.")
        y += 22.0

        # 5. Board Visual Overlay Toggles
        if rect.bottom() - y >= 62.0:
            self._toggle_fours_rect = QRectF(tx, rect.bottom() - 68.0, tw, 26.0)
            self._draw_small_toggle(
                painter,
                self._toggle_fours_rect,
                "4-in-a-Row Beams: ON" if self._show_four_lines else "4-in-a-Row Beams: OFF",
                self._show_four_lines,
                self._hovered_btn == "fours",
            )
            self._toggle_cand_rect = QRectF(tx, rect.bottom() - 36.0, tw, 26.0)
            self._draw_small_toggle(
                painter,
                self._toggle_cand_rect,
                "Open-3 Candidates: ON" if self._show_candidate_overlay else "Open-3 Candidates: OFF",
                self._show_candidate_overlay,
                self._hovered_btn == "cand",
            )

        painter.restore()

    @staticmethod
    def _draw_small_toggle(
        painter: QPainter,
        rect: QRectF,
        text: str,
        active: bool,
        hovered: bool,
    ) -> None:
        painter.setBrush(QColor(24, 44, 62, 220) if active else QColor(15, 21, 34, 200))
        border = Palette.GOLD_BRIGHT if hovered else (Palette.SPIRIT_CYAN if active else QColor(232, 228, 216, 60))
        painter.setPen(QPen(border, 1.1))
        painter.drawRoundedRect(rect, 7, 7)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_BONE if active else Palette.TEXT_MUTED)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_center_stage(
        self,
        painter: QPainter,
        rect: QRectF,
        now: float,
        elapsed: float,
    ) -> None:
        assert self._session is not None
        board = self._session.state.board

        # 1. Top Turn Banner (or Full-Board Verdict Banner when game is over)
        banner_h = 54.0 if self._session.is_over else 36.0
        banner_rect = QRectF(rect.left(), rect.top(), rect.width(), banner_h)
        self._paint_turn_or_verdict_banner(painter, banner_rect, now)

        # 2. Compute Board & Bottom Root Column Strip geometry
        strip_h = 64.0
        avail_h = rect.height() - banner_h - strip_h - 18.0
        avail_w = rect.width() - 8.0

        board_h = min(avail_h, avail_w / 1.14)
        board_w = board_h * 1.14
        bx = rect.left() + (rect.width() - board_w) * 0.5
        by = banner_rect.bottom() + 8.0 + max(0.0, (avail_h - board_h) * 0.45)

        # Short subtle screen shake when a new connected-four was just scored
        if now < self._shake_until:
            rng = random.Random(int(now * 1000))
            bx += rng.uniform(-4.5, 4.5)
            by += rng.uniform(-3.5, 3.5)

        board_rect = QRectF(bx, by, board_w, board_h)

        # Convert Board to integer owners grid for draw_ritual_board
        grid_ints = tuple(
            tuple(int(board.cell(r, c).owner) for c in range(board.cols))
            for r in range(board.rows)
        )

        # Prepare falling animated disc if active
        falling_tuple: Optional[tuple[int, float, int]] = None
        if self._drop_anim is not None:
            t_norm = min(1.0, (now - self._drop_anim.started_at) / max(0.05, self._drop_anim.duration))
            eased = _ease_out_bounce(t_norm)
            cur_row = -1.1 + eased * (self._drop_anim.target_row + 1.1)
            falling_tuple = (self._drop_anim.column, cur_row, int(self._drop_anim.owner))

        can_human_act = (
            not self._session.is_over
            and not self._ai_thinking
            and self._drop_anim is None
            and self._session.to_move is Owner.HUMAN
        )
        eff_hover = (
            self._hover_col
            if (can_human_act and self._hover_col is not None and board.is_valid_move(self._hover_col))
            else None
        )

        highlighted_set: set[tuple[int, int]] = set()
        if self._last_move_cell is not None and self._drop_anim is None:
            highlighted_set.add(self._last_move_cell)

        grid_left, grid_top, step_x = draw_ritual_board(
            painter,
            board_rect,
            grid_ints,
            phase=elapsed,
            hover_col=eff_hover,
            hover_owner=1,
            highlighted_cells=highlighted_set,
            falling_disc=falling_tuple,
        )
        self._board_grid_geom = (grid_left, grid_top, step_x, board_rect.top(), board_rect.bottom())

        # Overlays on the settled board: overlapping 4-window beams, candidate points, or PV ghosts
        self._paint_board_overlays(painter, board_rect, board, now)

        # 3. Root Column Ordering & Minimax Value Strip directly under the 7 columns
        strip_y = board_rect.bottom() + 6.0
        self._paint_column_strip(painter, grid_left, step_x, strip_y, strip_h, can_human_act)

    def _paint_turn_or_verdict_banner(self, painter: QPainter, rect: QRectF, now: float) -> None:
        assert self._session is not None
        self._rematch_rect = QRectF()
        self._return_map_rect = QRectF()

        if self._session.is_over and self._drop_anim is None:
            h_f = self._session.human_fours
            c_f = self._session.computer_fours
            human_won = h_f > c_f
            is_draw = h_f == c_f

            accent = (
                Palette.SPIRIT_CYAN
                if human_won
                else (Palette.MEMORY_GOLD if is_draw else Palette.DEVIL_MAGMA)
            )
            painter.setBrush(QColor(11, 18, 30, 238))
            painter.setPen(QPen(accent, 1.5))
            painter.drawRoundedRect(rect, 10, 10)

            verdict = (
                f"VICTORY! SANCTUARY CLEANSED ({h_f} – {c_f})"
                if human_won
                else (
                    f"DRAW AT 42 STONES ({h_f} – {c_f})"
                    if is_draw
                    else f"DEFEAT — {self._devil.name.upper()} PREVAILS ({c_f} – {h_f})"
                )
            )
            painter.setFont(make_display_font(12, bold=True))
            painter.setPen(accent)
            painter.drawText(
                QRectF(rect.left() + 14, rect.top() + 5, rect.width() - 320, 22),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                verdict,
            )

            avg_ms = (
                1000.0 * self._total_ai_time / self._ai_turns_played
                if self._ai_turns_played > 0
                else 0.0
            )
            painter.setFont(make_ui_font(8))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(
                QRectF(rect.left() + 14, rect.top() + 28, rect.width() - 320, 20),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                f"42/42 Full Board · Total AI Visited: {self._total_ai_nodes:,} · Cutoffs: {self._total_ai_cutoffs:,} · Avg: {avg_ms:.1f} ms/turn",
            )

            self._rematch_rect = QRectF(rect.right() - 294, rect.top() + 11, 104, 32)
            self._draw_small_toggle(painter, self._rematch_rect, "Rematch", False, self._hovered_btn == "rematch")

            ret_lbl = "Cleansing & Summary »" if human_won else "Fight Summary »"
            self._return_map_rect = QRectF(rect.right() - 182, rect.top() + 11, 168, 32)
            self._draw_small_toggle(painter, self._return_map_rect, ret_lbl, True, self._hovered_btn == "ret_map")
            return

        # Active match status banner
        painter.setBrush(QColor(10, 15, 26, 210))
        if self._ai_thinking:
            dots = "." * (1 + int((now * 3.0) % 3))
            txt = f"{self._devil.name} is searching Minimax α-β tree (K = {self._session.settings.k}){dots}"
            col = Palette.DEVIL_MAGMA
        elif self._drop_anim is not None:
            txt = "Orb descending..."
            col = Palette.MEMORY_GOLD
        elif self._session.to_move is Owner.HUMAN:
            txt = "YOUR TURN (MIN) — Click any column (or press 1–7) to drop a Spirit Orb"
            col = Palette.SPIRIT_CYAN
        else:
            txt = f"{self._devil.name}'s Turn (MAX)"
            col = Palette.DEVIL_MAGMA

        painter.setPen(QPen(QColor(col.red(), col.green(), col.blue(), 110), 1.1))
        painter.drawRoundedRect(rect, 9, 9)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(col)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, txt)

    def _paint_board_overlays(
        self,
        painter: QPainter,
        board_rect: QRectF,
        board: Board,
        now: float,
    ) -> None:
        if _BOARD_META is None:
            return
        meta_w = float(_BOARD_META["width"])
        meta_h = float(_BOARD_META["height"])
        scale = min(board_rect.width() / meta_w, board_rect.height() / meta_h)
        ox = board_rect.left() + (board_rect.width() - meta_w * scale) * 0.5
        oy = board_rect.top() + (board_rect.height() - meta_h * scale) * 0.5
        centers = _BOARD_META["centers"]
        orb_r = float(_BOARD_META["orb_radius"]) * scale

        def cell_pt(r: int, c: int) -> QPointF:
            cx, cy = centers[r][c]
            return QPointF(ox + cx * scale, oy + cy * scale)

        painter.save()

        # 1. Highlight every completed 4-cell window (shows overlapping fours!)
        if self._show_four_lines:
            hum_wins, comp_wins = find_completed_four_windows(board)
            for win in hum_wins:
                p0, p3 = cell_pt(*win[0]), cell_pt(*win[-1])
                painter.setPen(QPen(QColor(95, 214, 196, 105), max(4.5, orb_r * 0.28), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p3)
                painter.setPen(QPen(QColor(235, 255, 255, 225), max(1.8, orb_r * 0.10), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p3)
            for win in comp_wins:
                p0, p3 = cell_pt(*win[0]), cell_pt(*win[-1])
                painter.setPen(QPen(QColor(232, 74, 39, 110), max(4.5, orb_r * 0.28), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p3)
                painter.setPen(QPen(QColor(255, 210, 140, 220), max(1.8, orb_r * 0.10), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                painter.drawLine(p0, p3)

        # 2. Optional candidate Open-3 target cells overlay
        if self._show_candidate_overlay:
            h_cand, c_cand = find_candidate_cells(board)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for r, c in h_cand | c_cand:
                pt = cell_pt(r, c)
                both = (r, c) in h_cand and (r, c) in c_cand
                col = Palette.MEMORY_GOLD if both else (Palette.SPIRIT_CYAN if (r, c) in h_cand else Palette.DEVIL_MAGMA)
                painter.setPen(QPen(col, 2.0, Qt.PenStyle.DashLine))
                painter.drawEllipse(pt, orb_r * 0.68, orb_r * 0.68)

        # 3. Temporary Principal Variation ghost line preview when requested from Tree tab
        if self._pv_preview_cols and now < self._pv_preview_until and self._session is not None:
            sim_board = board
            turn_owner = self._session.to_move
            human_disc = self._session.game.disc_of(Owner.HUMAN)
            comp_disc = self._session.game.disc_of(Owner.COMPUTER)
            for step_i, col in enumerate(self._pv_preview_cols[:6], start=1):
                if not sim_board.is_valid_move(col):
                    break
                r_land = sim_board.lowest_empty_row(col)
                pt = cell_pt(r_land, col)
                if turn_owner is Owner.HUMAN:
                    draw_spirit_disc(painter, pt, orb_r * 0.82, opacity=0.45)
                else:
                    draw_devil_disc(painter, pt, orb_r * 0.82, opacity=0.45)
                painter.setFont(make_ui_font(8, bold=True))
                painter.setPen(Palette.GOLD_BRIGHT)
                painter.drawText(QRectF(pt.x() - 12, pt.y() - 10, 24, 20), Qt.AlignmentFlag.AlignCenter, f"#{step_i}")
                sim_board = sim_board.drop(col, human_disc if turn_owner is Owner.HUMAN else comp_disc)
                turn_owner = Owner.COMPUTER if turn_owner is Owner.HUMAN else Owner.HUMAN

        painter.restore()

    def _paint_column_strip(
        self,
        painter: QPainter,
        grid_left: float,
        step_x: float,
        strip_y: float,
        strip_h: float,
        can_human_act: bool,
    ) -> None:
        self._col_strip_rects.clear()
        if step_x <= 5.0:
            return

        painter.save()
        for c in range(7):
            slot_w = step_x - 5.0
            sx = grid_left + c * step_x + 2.5
            sr = QRectF(sx, strip_y, slot_w, strip_h)
            self._col_strip_rects.append(sr)

            summary = self._root_moves[c] if c < len(self._root_moves) else None
            hov = can_human_act and self._hover_col == c

            if summary is not None and summary.is_best:
                bg = QColor(42, 34, 20, 232)
                border = Palette.GOLD_BRIGHT
            elif hov:
                bg = QColor(20, 46, 62, 228)
                border = Palette.SPIRIT_CYAN
            elif summary is not None and summary.is_pruned:
                bg = QColor(24, 15, 20, 185)
                border = QColor(194, 65, 45, 90)
            else:
                bg = QColor(11, 16, 28, 210)
                border = QColor(232, 228, 216, 58)

            painter.setBrush(bg)
            painter.setPen(QPen(border, 1.35 if (hov or (summary and summary.is_best)) else 1.0))
            painter.drawRoundedRect(sr, 7, 7)

            # Row 1: Column number (1-based + 0-based tree index)
            painter.setFont(make_ui_font(8 if slot_w >= 66 else 7, bold=True))
            painter.setPen(Palette.GOLD_BRIGHT if (summary and summary.is_best) else Palette.TEXT_BONE)
            col_hdr = f"Col {c + 1} [c={c}]" if slot_w >= 72 else f"C{c + 1} [c={c}]"
            painter.drawText(
                QRectF(sx, strip_y + 3, slot_w, 16),
                Qt.AlignmentFlag.AlignCenter,
                col_hdr,
            )

            # Row 2: Move ordering exploration rank
            painter.setFont(make_ui_font(7, bold=True))
            if summary is None or not summary.is_legal:
                ord_txt, ord_col = "FULL", Palette.TEXT_DIM
            elif summary.is_pruned:
                ord_txt, ord_col = "✂ Pruned", Palette.DEVIL_MAGMA
            elif summary.order_rank is not None:
                ord_txt, ord_col = f"Order #{summary.order_rank}", Palette.SPIRIT_CYAN
            else:
                ord_txt, ord_col = "Ready", Palette.TEXT_MUTED
            painter.setPen(ord_col)
            painter.drawText(QRectF(sx, strip_y + 21, slot_w, 15), Qt.AlignmentFlag.AlignCenter, ord_txt)

            # Row 3: Root minimax value
            painter.setFont(make_ui_font(8, bold=True))
            if summary is not None and summary.value is not None:
                v_txt = f"{summary.bound_symbol}{format_eval_score(summary.value)}"
                v_col = Palette.GOLD_BRIGHT if summary.is_best else Palette.TEXT_BONE
            elif summary is not None and summary.is_pruned:
                v_txt, v_col = "skipped", Palette.TEXT_DIM
            else:
                v_txt, v_col = "—", Palette.TEXT_DIM
            painter.setPen(v_col)
            painter.drawText(QRectF(sx, strip_y + 39, slot_w, 18), Qt.AlignmentFlag.AlignCenter, v_txt)

        painter.restore()

    # ------------------------------------------------------------ interaction
    def _column_at(self, pos: QPointF) -> Optional[int]:
        for c, sr in enumerate(self._col_strip_rects):
            if sr.contains(pos):
                return c
        grid_left, _grid_top, step_x, b_top, b_bot = self._board_grid_geom
        if step_x > 5.0 and (b_top - 36.0) <= pos.y() <= b_bot:
            col = int((pos.x() - grid_left) // step_x)
            if 0 <= col < 7:
                return col
        return None

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        col = self._column_at(pos)

        hov_btn: Optional[str] = None
        if self._toggle_fours_rect.contains(pos):
            hov_btn = "fours"
        elif self._toggle_cand_rect.contains(pos):
            hov_btn = "cand"
        elif not self._rematch_rect.isEmpty() and self._rematch_rect.contains(pos):
            hov_btn = "rematch"
        elif not self._return_map_rect.isEmpty() and self._return_map_rect.contains(pos):
            hov_btn = "ret_map"

        if col != self._hover_col or hov_btn != self._hovered_btn:
            self._hover_col = col
            self._hovered_btn = hov_btn
            self.update()

        can_drop = (
            col is not None
            and self._session is not None
            and not self._session.is_over
            and not self._ai_thinking
            and self._drop_anim is None
            and self._session.to_move is Owner.HUMAN
            and self._session.state.board.is_valid_move(col)
        )
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if (can_drop or hov_btn is not None)
            else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._session is None:
            return
        pos = event.position()

        if self._toggle_fours_rect.contains(pos):
            self._show_four_lines = not self._show_four_lines
            self.update()
            return
        if self._toggle_cand_rect.contains(pos):
            self._show_candidate_overlay = not self._show_candidate_overlay
            self.update()
            return
        if not self._rematch_rect.isEmpty() and self._rematch_rect.contains(pos):
            self.rematch_requested.emit()
            return
        if not self._return_map_rect.isEmpty() and self._return_map_rect.contains(pos):
            human_won = self._session.human_fours > self._session.computer_fours
            self.finish_to_map_requested.emit(human_won)
            return

        col = self._column_at(pos)
        if col is not None:
            self.human_column_clicked.emit(col)


class BattleScreen(QWidget):
    """Full Connect 4 Battlefield screen hosting ArenaCanvas + MindPanel + Worker."""

    exit_to_map = Signal(bool, str)  # (human_won, devil_id)
    open_result_summary = Signal(object, object)  # (DevilProfile, GameSession)
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._devil: DevilProfile = DEVILS[0]
        self._settings: SessionSettings = SessionSettings()
        self._session: Optional[GameSession] = None
        self._worker: Optional[AISearchWorker] = None
        self._ai_state_before = None

        self._particles = AmbientParticleField(count=32, seed=512)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0
        self._log_line: str = "Ritual initialized."
        self._mind_visible: bool = True
        self._theater_mode: bool = False

        # Top header button rects
        self._back_rect = QRectF()
        self._restart_rect = QRectF()
        self._toggle_mind_rect = QRectF()
        self._fs_rect = QRectF()
        self._hovered_hdr: Optional[str] = None
        self.setMouseTracking(True)

        # Layout: reserve 52px top header and 30px bottom log bar
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 54, 14, 34)
        outer.setSpacing(10)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)

        self._arena = _BattleArenaCanvas(self)
        self._arena.human_column_clicked.connect(self._on_human_column)
        self._arena.rematch_requested.connect(self.restart_match)
        self._arena.finish_to_map_requested.connect(self._on_finish_to_map)

        self._mind = MindPanel(self)
        self._mind.setMinimumWidth(610)
        self._mind.pv_preview_requested.connect(self._arena.trigger_pv_preview)
        self._mind.theater_toggle_requested.connect(self.toggle_theater_mode)

        body.addWidget(self._arena, 5)
        body.addWidget(self._mind, 6)
        outer.addLayout(body, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    @property
    def mind_panel(self) -> MindPanel:
        return self._mind

    @property
    def session(self) -> Optional[GameSession]:
        return self._session

    # ------------------------------------------------------------ match lifecycle
    def start_match(self, devil: DevilProfile, settings: SessionSettings) -> None:
        self._stop_worker()
        self._devil = devil
        self._settings = settings
        self._session = build_session(settings)

        self._arena.bind_match(devil, self._session)
        self._mind.reset_for_match(
            self._session.game,
            settings.heuristic_key,
            self._session.state.board,
        )

        first_str = "You (MIN)" if self._session.to_move is Owner.HUMAN else f"{devil.name} (MAX)"
        self._log_line = (
            f"Ritual begun vs {devil.name} · K={settings.k} · "
            f"Heuristic={settings.heuristic_key} · First move: {first_str}"
        )
        self.resume_effects()

        if self._session.to_move is Owner.COMPUTER:
            self._launch_ai_turn()

    def restart_match(self) -> None:
        self.start_match(self._devil, self._settings)

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
        self._last_tick = time.perf_counter()
        if not self._timer.isActive():
            self._timer.start()
        self.setFocus()

    def _stop_worker(self) -> None:
        if self._worker is not None:
            if self._worker.isRunning():
                self._worker.wait(1500)
            self._worker.deleteLater()
            self._worker = None

    # --------------------------------------------------------- gameplay & AI
    def _on_human_column(self, column: int) -> None:
        if self._session is None or self._session.is_over:
            return
        if self._worker is not None or self._arena._drop_anim is not None:
            return
        if self._session.to_move is not Owner.HUMAN:
            return
        if not self._session.state.board.is_valid_move(column):
            return

        target_row = self._session.state.board.lowest_empty_row(column)
        anim = _DropAnim(
            column=column,
            target_row=target_row,
            owner=Owner.HUMAN,
            started_at=time.perf_counter(),
            duration=0.25,
        )
        self._arena.set_drop_anim(anim)

    def _launch_ai_turn(self) -> None:
        if self._session is None or self._session.is_over:
            return
        self._ai_state_before = self._session.state
        self._arena.set_ai_thinking(True)
        self._log_line = f"{self._devil.name} is running Minimax with Alpha-Beta pruning (K={self._settings.k})..."

        self._worker = AISearchWorker(
            game=self._session.game,
            state=self._session.state,
            settings=self._settings,
            parent=self,
        )
        self._worker.search_completed.connect(self._on_ai_search_done)
        self._worker.search_failed.connect(self._on_ai_search_failed)
        self._worker.start()

    def _on_ai_search_done(self, best_col: int, result: SearchResult) -> None:
        self._worker = None
        if self._session is None or self._ai_state_before is None:
            return
        self._arena.set_ai_thinking(False)
        legal_before = self._ai_state_before.board.valid_moves()
        metrics = compute_tree_metrics(result, legal_before, self._session.game.rules.cols)

        target_row = self._session.state.board.lowest_empty_row(best_col)
        anim = _DropAnim(
            column=best_col,
            target_row=target_row,
            owner=Owner.COMPUTER,
            started_at=time.perf_counter(),
            duration=0.27,
            pending_ai_result=result,
            pending_metrics=metrics,
        )
        self._arena.set_drop_anim(anim)

    def _on_ai_search_failed(self, err: str) -> None:
        self._worker = None
        self._arena.set_ai_thinking(False)
        self._log_line = f"Search error: {err}"
        self.update()

    def _finalize_drop(self, anim: _DropAnim) -> None:
        if self._session is None:
            return
        prev_h = self._session.human_fours
        prev_c = self._session.computer_fours

        if anim.owner is Owner.HUMAN:
            rec = self._session.apply_human_move(anim.column)
            gained_h = rec.human_fours - prev_h
            self._arena.record_move_outcome(rec.row, rec.column, gained_h, 0)
            self._mind.update_live_board(self._session.state.board)
            self._log_line = (
                f"Turn {rec.turn_number}/42 · You dropped in Col {rec.column + 1} "
                f"(Fours — You: {rec.human_fours}, {self._devil.name}: {rec.computer_fours})"
            )
            if not self._session.is_over:
                self._launch_ai_turn()
        else:
            assert anim.pending_ai_result is not None and anim.pending_metrics is not None
            state_before = self._ai_state_before or self._session.state
            rec = self._session.apply_ai_result(anim.column, anim.pending_ai_result)
            gained_c = rec.computer_fours - prev_c
            self._arena.record_move_outcome(
                rec.row,
                rec.column,
                0,
                gained_c,
                root_moves=anim.pending_metrics.root_moves,
                ai_result=anim.pending_ai_result,
            )
            self._mind.update_live_board(self._session.state.board)
            self._mind.record_ai_turn(
                turn_number=rec.turn_number,
                chosen_col=rec.column,
                state_before=state_before,
                result=anim.pending_ai_result,
                metrics=anim.pending_metrics,
            )
            st = anim.pending_ai_result.stats
            self._log_line = (
                f"Turn {rec.turn_number}/42 · {self._devil.name} visited {st.visited:,} nodes "
                f"({st.cutoffs:,} cutoffs, {st.pruned_branches:,} pruned) in {st.elapsed * 1000:.1f} ms "
                f"→ Col {rec.column + 1} [val={format_eval_score(anim.pending_ai_result.value)}]"
            )

        if self._session.is_over:
            diff = self._session.human_fours - self._session.computer_fours
            outcome = "YOU WIN!" if diff > 0 else ("DRAW!" if diff == 0 else f"{self._devil.name.upper()} WINS!")
            self._log_line = (
                f"Board Full (42/42) · {outcome} Final Connected-Fours — "
                f"You: {self._session.human_fours} | {self._devil.name}: {self._session.computer_fours}"
            )

    def _on_tick(self) -> None:
        now = time.perf_counter()
        dt = min(0.05, max(0.001, now - self._last_tick))
        self._last_tick = now
        self._particles.step(dt)

        anim = self._arena._drop_anim
        if anim is not None and (now - anim.started_at) >= anim.duration:
            self._arena.set_drop_anim(None)
            self._finalize_drop(anim)

        self._arena.update()
        self.update()

    # --------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        elapsed = time.perf_counter() - self._t0

        # Background boss arena + dark atmospheric veil
        bg = AssetCache.cover(self._devil.scene_image, w, h)
        if not bg.isNull():
            painter.drawPixmap(0, 0, bg)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(6, 9, 16, 224))
        veil.setColorAt(0.5, QColor(8, 12, 22, 208))
        veil.setColorAt(1.0, QColor(5, 8, 14, 238))
        painter.fillRect(0, 0, w, h, veil)

        self._particles.paint(painter, w, h, elapsed)

        # Top Header Bar
        self._paint_header_bar(painter, w)

        # Bottom Log Strip
        log_rect = QRectF(14, h - 28, w - 28, 22)
        painter.setBrush(QColor(9, 13, 22, 220))
        painter.setPen(QPen(QColor(232, 228, 216, 48), 1.0))
        painter.drawRoundedRect(log_rect, 6, 6)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(
            log_rect.adjusted(10, 0, -10, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._log_line,
        )

        painter.end()

    def _paint_header_bar(self, painter: QPainter, w: int) -> None:
        self._back_rect = QRectF(14, 12, 134, 30)
        self._draw_hdr_btn(painter, self._back_rect, "«  Retreat to Map", self._hovered_hdr == "back")

        self._restart_rect = QRectF(156, 12, 108, 30)
        self._draw_hdr_btn(painter, self._restart_rect, "Restart Fight", self._hovered_hdr == "restart")

        self._fs_rect = QRectF(w - 148, 12, 134, 30)
        self._draw_hdr_btn(painter, self._fs_rect, "Full Screen (F11)", self._hovered_hdr == "fs")

        self._toggle_mind_rect = QRectF(w - 302, 12, 146, 30)
        mind_lbl = "Hide Devil's Mind" if self._mind_visible else "Show Devil's Mind"
        self._draw_hdr_btn(painter, self._toggle_mind_rect, mind_lbl, self._hovered_hdr == "mind")

        # Center match info strip
        mid_rect = QRectF(274, 12, max(160.0, w - 586.0), 30)
        painter.setBrush(QColor(11, 16, 28, 210))
        painter.setPen(QPen(QColor(232, 194, 106, 80), 1.0))
        painter.drawRoundedRect(mid_rect, 15, 15)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        hdr_text = (
            f"YOU (MIN)  vs  {self._devil.name.upper()} (MAX)   ·   "
            f"{self._devil.heuristic_title}   ·   K = {self._settings.k}   ·   "
            f"Ordering: {self._settings.ordering_key}"
        )
        painter.drawText(mid_rect, Qt.AlignmentFlag.AlignCenter, hdr_text)

    @staticmethod
    def _draw_hdr_btn(painter: QPainter, rect: QRectF, label: str, hovered: bool) -> None:
        painter.setBrush(QColor(24, 38, 58, 225) if hovered else QColor(12, 17, 28, 200))
        painter.setPen(QPen(Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 70), 1.1))
        painter.drawRoundedRect(rect, 15, 15)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    # ------------------------------------------------------------ interaction
    def _toggle_mind_panel(self) -> None:
        if self._theater_mode:
            self.toggle_theater_mode()
            return
        self._mind_visible = not self._mind_visible
        self._mind.setVisible(self._mind_visible)
        self.update()

    def toggle_theater_mode(self) -> None:
        self._theater_mode = not self._theater_mode
        if self._theater_mode:
            self._mind_visible = True
            self._mind.setVisible(True)
            self._arena.setVisible(False)
        else:
            self._arena.setVisible(True)
        self._mind.set_theater_mode_label(self._theater_mode)
        self.update()

    def _on_finish_to_map(self, human_won: bool) -> None:
        self._stop_worker()
        if self._session is not None and self._session.is_over:
            self.open_result_summary.emit(self._devil, self._session)
        else:
            self.exit_to_map.emit(human_won, self._devil.devil_id)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hov: Optional[str] = None
        if self._back_rect.contains(pos):
            hov = "back"
        elif self._restart_rect.contains(pos):
            hov = "restart"
        elif self._toggle_mind_rect.contains(pos):
            hov = "mind"
        elif self._fs_rect.contains(pos):
            hov = "fs"
        if hov != self._hovered_hdr:
            self._hovered_hdr = hov
            self.update()
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if hov is not None else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._back_rect.contains(pos):
            if self._session is not None and self._session.is_over:
                self._on_finish_to_map(self._session.human_fours > self._session.computer_fours)
            else:
                self._stop_worker()
                self.exit_to_map.emit(False, self._devil.devil_id)
        elif self._restart_rect.contains(pos):
            self.restart_match()
        elif self._toggle_mind_rect.contains(pos):
            self._toggle_mind_panel()
        elif self._fs_rect.contains(pos):
            self.toggle_fullscreen_requested.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_7:
            self._on_human_column(key - Qt.Key.Key_1)
        elif key == Qt.Key.Key_Tab:
            self._toggle_mind_panel()
        elif key == Qt.Key.Key_T:
            self.toggle_theater_mode()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        elif key == Qt.Key.Key_Escape:
            self._on_finish_to_map(False)
        else:
            super().keyPressEvent(event)
