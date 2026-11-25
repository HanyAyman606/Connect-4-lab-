"""Match Result (Cleansing / Defeat / Draw) and 3/3 Final Ending screens.

Implements:
- ResultScreen: Expanding spirit-light cleansing wave animation on victory,
  Devil taunt on defeat, final connected-fours scoreboard, and complete
  Fight Telemetry Summary ('The Devil's Memory').
- EndingScreen: Golden Spirit Tree finale unlocked when all 3 Devils are
  cleansed, freeing your sister's spirit.
"""

from __future__ import annotations

import math
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
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from core.owner import Owner
from setup.game_session import GameSession
from ui.devils import DEVILS, DevilProfile
from ui.theme import (
    AmbientParticleField,
    AssetCache,
    Palette,
    draw_devil_disc,
    draw_ornate_divider,
    draw_spirit_disc,
    make_display_font,
    make_ui_font,
)

_CLEANSED_BG = "wallpaperflare.com_wallpaper (4).jpg"


@dataclass(frozen=True, slots=True)
class FightSummaryData:
    """Aggregated statistics across an entire 42-disc battle."""

    devil: DevilProfile
    k: int
    ordering_key: str
    first_owner: Owner
    human_fours: int
    computer_fours: int
    ai_turns: int
    total_visited: int
    total_expanded: int
    total_cutoffs: int
    total_pruned: int
    eval_leaves: int
    terminal_leaves: int
    total_time_sec: float

    @property
    def human_won(self) -> bool:
        return self.human_fours > self.computer_fours

    @property
    def is_draw(self) -> bool:
        return self.human_fours == self.computer_fours


def build_fight_summary(devil: DevilProfile, session: GameSession) -> FightSummaryData:
    """Aggregate every AI SearchResult recorded in ``session.history``."""
    ai_turns = 0
    visited = expanded = cutoffs = pruned = eval_l = term_l = 0
    total_sec = 0.0

    for rec in session.history:
        if rec.search_result is not None:
            ai_turns += 1
            st = rec.search_result.stats
            visited += st.visited
            expanded += st.expanded
            cutoffs += st.cutoffs
            pruned += st.pruned_branches
            eval_l += st.evaluations
            term_l += st.terminal_leaves
            total_sec += st.elapsed

    return FightSummaryData(
        devil=devil,
        k=session.settings.k,
        ordering_key=session.settings.ordering_key,
        first_owner=session.game.first,
        human_fours=session.human_fours,
        computer_fours=session.computer_fours,
        ai_turns=ai_turns,
        total_visited=visited,
        total_expanded=expanded,
        total_cutoffs=cutoffs,
        total_pruned=pruned,
        eval_leaves=eval_l,
        terminal_leaves=term_l,
        total_time_sec=total_sec,
    )


class ResultScreen(QWidget):
    """Post-battle screen with cleansing light-wave animation & fight summary."""

    inspect_board_requested = Signal()
    rematch_requested = Signal()
    continue_to_map_requested = Signal()
    witness_ending_requested = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._summary: Optional[FightSummaryData] = None
        self._all_three_cleansed: bool = False
        self._opened_at: float = time.perf_counter()
        self._last_tick: float = self._opened_at

        self._particles = AmbientParticleField(count=52, seed=777)
        self._hitboxes: dict[str, QRectF] = {}
        self._hovered: Optional[str] = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def show_summary(self, summary: FightSummaryData, all_three_cleansed: bool) -> None:
        self._summary = summary
        self._all_three_cleansed = all_three_cleansed
        self._opened_at = time.perf_counter()
        self.resume_effects()

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
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

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        self._hitboxes.clear()
        if self._summary is None:
            painter.end()
            return

        s = self._summary
        age = time.perf_counter() - self._opened_at

        # 1. Background: on Victory, cleanse Devil's dark arena into Golden Spirit Tree!
        corrupted = AssetCache.cover(s.devil.scene_image, w, h)
        if not corrupted.isNull():
            painter.drawPixmap(0, 0, corrupted)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        if s.human_won:
            cleanse_t = min(1.0, age / 2.0)
            cleansed_pix = AssetCache.cover(_CLEANSED_BG, w, h)
            if not cleansed_pix.isNull():
                painter.save()
                painter.setOpacity(cleanse_t * 0.88)
                painter.drawPixmap(0, 0, cleansed_pix)
                painter.restore()

            # Expanding spirit-light wave ring during first 2.2 seconds
            if age < 2.4:
                wave_r = (age / 2.4) * max(w, h) * 0.85
                wave_alpha = int(190 * (1.0 - age / 2.4))
                ring = QRadialGradient(QPointF(w * 0.5, h * 0.45), max(10.0, wave_r))
                ring.setColorAt(0.0, QColor(95, 214, 196, 0))
                ring.setColorAt(0.82, QColor(155, 245, 255, wave_alpha))
                ring.setColorAt(0.95, QColor(250, 224, 158, wave_alpha))
                ring.setColorAt(1.0, QColor(250, 224, 158, 0))
                painter.fillRect(0, 0, w, h, ring)

        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(6, 9, 16, 188))
        veil.setColorAt(0.5, QColor(8, 12, 22, 198))
        veil.setColorAt(1.0, QColor(5, 8, 14, 238))
        painter.fillRect(0, 0, w, h, veil)

        self._particles.paint(painter, w, h, age)

        # 2. Central Verdict & Fight Summary Card
        card_w = min(920.0, w * 0.84)
        card_h = min(610.0, h * 0.82)
        card = QRectF((w - card_w) * 0.5, (h - card_h) * 0.5, card_w, card_h)

        accent = (
            Palette.SPIRIT_CYAN
            if s.human_won
            else (Palette.MEMORY_GOLD if s.is_draw else Palette.DEVIL_MAGMA)
        )
        painter.setBrush(QColor(10, 15, 26, 232))
        painter.setPen(QPen(accent, 1.6))
        painter.drawRoundedRect(card, 16, 16)

        cx = card.center().x()
        y = card.top() + 22.0

        tag = (
            f"SANCTUARY {s.devil.numeral} CLEANSED · {s.devil.region_name.upper()}"
            if s.human_won
            else (
                f"EQUILIBRIUM AT 42 STONES · {s.devil.region_name.upper()}"
                if s.is_draw
                else f"CORRUPTION ENDURES · {s.devil.region_name.upper()}"
            )
        )
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(accent)
        painter.drawText(QRectF(card.left(), y, card_w, 20), Qt.AlignmentFlag.AlignCenter, tag)
        y += 24.0

        headline = (
            f"{s.devil.name} Defeated — Light Restored"
            if s.human_won
            else ("Neither Spirit Yields (Draw)" if s.is_draw else f"{s.devil.name} Claims the Board")
        )
        painter.setFont(make_display_font(max(22, int(h * 0.032)), bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(card.left() + 24, y, card_w - 48, 42), Qt.AlignmentFlag.AlignCenter, headline)
        y += 46.0

        draw_ornate_divider(painter, cx, y, min(250.0, card_w * 0.30), accent=accent)
        y += 14.0

        quote = (
            s.devil.defeat_line
            if s.human_won
            else ("Forty-two stones stand equal under the moon." if s.is_draw else s.devil.victory_taunt)
        )
        painter.setFont(make_display_font(11, italic=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(
            QRectF(card.left() + 48, y, card_w - 96, 36),
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            f"“{quote}”",
        )
        y += 44.0

        # 3. Big Final Connected-Fours Scoreboard
        sb_w = min(560.0, card_w - 80.0)
        sb_rect = QRectF(cx - sb_w * 0.5, y, sb_w, 74.0)
        painter.setBrush(QColor(15, 22, 38, 225))
        painter.setPen(QPen(QColor(232, 194, 106, 90), 1.1))
        painter.drawRoundedRect(sb_rect, 12, 12)

        draw_spirit_disc(painter, QPointF(sb_rect.left() + 36, sb_rect.center().y()), 17.0, phase=age, highlight=s.human_won)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(sb_rect.left() + 64, sb_rect.top() + 14, 140, 18), Qt.AlignmentFlag.AlignLeft, "YOU (SPIRIT · MIN)")
        painter.setFont(make_display_font(24, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(sb_rect.left() + 64, sb_rect.top() + 32, 120, 34), Qt.AlignmentFlag.AlignLeft, f"{s.human_fours} Fours")

        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        util = s.computer_fours - s.human_fours
        painter.drawText(sb_rect, Qt.AlignmentFlag.AlignCenter, f"42 / 42 FULL BOARD\nUtility (MAX−MIN) = {util:+d}")

        draw_devil_disc(painter, QPointF(sb_rect.right() - 36, sb_rect.center().y()), 17.0, phase=age, highlight=(not s.human_won and not s.is_draw))
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.DEVIL_MAGMA)
        painter.drawText(QRectF(sb_rect.right() - 204, sb_rect.top() + 14, 140, 18), Qt.AlignmentFlag.AlignRight, f"{s.devil.name.upper()} (MAX)")
        painter.setFont(make_display_font(24, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(sb_rect.right() - 204, sb_rect.top() + 32, 140, 34), Qt.AlignmentFlag.AlignRight, f"{s.computer_fours} Fours")
        y += 92.0

        # 4. Fight Telemetry Grid ('The Devil's Memory' — 2 rows x 4 columns)
        pad_x = 34.0
        grid_w = card_w - 2 * pad_x
        gap = 10.0
        tw = (grid_w - 3 * gap) / 4.0
        th = 58.0
        avg_ms = (1000.0 * s.total_time_sec / s.ai_turns) if s.ai_turns else 0.0
        first_lbl = "You (MIN)" if s.first_owner is Owner.HUMAN else f"{s.devil.name} (MAX)"

        stats_items = (
            ("DEPTH & HEURISTIC", f"K = {s.k}", s.devil.heuristic_title),
            ("FIRST PLAYER & ORDER", first_lbl, f"Order: {s.ordering_key}"),
            ("TOTAL NODES VISITED", f"{s.total_visited:,}", f" across {s.ai_turns} AI searches"),
            ("TOTAL NODES EXPANDED", f"{s.total_expanded:,}", "Internal branching states"),
            ("α-β CUTOFFS", f"{s.total_cutoffs:,}", f"{s.total_pruned:,} branches skipped"),
            ("EVAL vs TERMINAL LEAVES", f"{s.eval_leaves:,} / {s.terminal_leaves:,}", "Heuristic vs exact leaves"),
            ("TOTAL AI SEARCH TIME", f"{s.total_time_sec:.3f} s", "Cumulative wall-clock"),
            ("AVG TIME / AI MOVE", f"{avg_ms:.2f} ms", "Real-time responsiveness"),
        )
        for idx, (lbl, val, sub) in enumerate(stats_items):
            ri, ci = divmod(idx, 4)
            rx = card.left() + pad_x + ci * (tw + gap)
            ry = y + ri * (th + gap)
            tr = QRectF(rx, ry, tw, th)
            painter.setBrush(QColor(14, 20, 34, 215))
            painter.setPen(QPen(QColor(232, 228, 216, 52), 1.0))
            painter.drawRoundedRect(tr, 8, 8)

            painter.setFont(make_ui_font(7, bold=True))
            painter.setPen(Palette.SPIRIT_CYAN)
            painter.drawText(QRectF(rx + 8, ry + 5, tw - 16, 13), Qt.AlignmentFlag.AlignLeft, lbl)

            painter.setFont(make_ui_font(11, bold=True))
            painter.setPen(Palette.TEXT_BONE)
            painter.drawText(QRectF(rx + 8, ry + 20, tw - 16, 18), Qt.AlignmentFlag.AlignLeft, val)

            painter.setFont(make_ui_font(7))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(rx + 8, ry + 40, tw - 16, 13), Qt.AlignmentFlag.AlignLeft, sub)

        # 5. Bottom Action Buttons
        btn_y = card.bottom() - 54.0
        r_inspect = QRectF(card.left() + pad_x, btn_y, 210, 36)
        self._hitboxes["inspect"] = r_inspect
        self._draw_btn(painter, r_inspect, "«  Inspect Final Board & Tree", self._hovered == "inspect", False)

        r_rematch = QRectF(card.left() + pad_x + 222, btn_y, 170, 36)
        self._hitboxes["rematch"] = r_rematch
        self._draw_btn(painter, r_rematch, f"Rematch {s.devil.name}", self._hovered == "rematch", False)

        if self._all_three_cleansed and s.human_won:
            r_next = QRectF(card.right() - pad_x - 270, btn_y, 270, 36)
            self._hitboxes["ending"] = r_next
            self._draw_btn(painter, r_next, "«  Witness Sister's Finale  »", self._hovered == "ending", True)
        else:
            r_next = QRectF(card.right() - pad_x - 230, btn_y, 230, 36)
            self._hitboxes["map"] = r_next
            self._draw_btn(painter, r_next, "Return to Realm Map  »", self._hovered == "map", True)

        painter.end()

    @staticmethod
    def _draw_btn(painter: QPainter, rect: QRectF, text: str, hovered: bool, primary: bool) -> None:
        if primary:
            bg = QColor(34, 82, 98, 238) if hovered else QColor(20, 54, 70, 220)
            border = Palette.GOLD_BRIGHT if hovered else Palette.SPIRIT_CYAN
            fg = Palette.GOLD_BRIGHT if hovered else Palette.TEXT_BONE
        else:
            bg = QColor(24, 36, 56, 225) if hovered else QColor(14, 20, 34, 205)
            border = Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 75)
            fg = Palette.TEXT_BONE
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.3))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

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
        if clicked == "inspect":
            self.inspect_board_requested.emit()
        elif clicked == "rematch":
            self.rematch_requested.emit()
        elif clicked == "ending":
            self.witness_ending_requested.emit()
        elif clicked == "map":
            self.continue_to_map_requested.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if "ending" in self._hitboxes:
                self.witness_ending_requested.emit()
            else:
                self.continue_to_map_requested.emit()
        elif event.key() == Qt.Key.Key_Escape:
            self.continue_to_map_requested.emit()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)


class EndingScreen(QWidget):
    """Golden Spirit Tree ending screen unlocked once all 3 Devils are cleansed."""

    return_to_map = Signal()
    return_to_menu = Signal()
    open_archive = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._opened_at = time.perf_counter()
        self._last_tick = self._opened_at
        self._particles = AmbientParticleField(count=64, seed=999)
        self._hitboxes: dict[str, QRectF] = {}
        self._hovered: Optional[str] = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def reset_finale(self) -> None:
        self._opened_at = time.perf_counter()
        self.resume_effects()

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
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

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        self._hitboxes.clear()
        age = time.perf_counter() - self._opened_at
        zoom = 1.0 + min(0.05, age * 0.004)

        pix = AssetCache.cover(_CLEANSED_BG, w, h)
        if not pix.isNull():
            zw, zh = w * zoom, h * zoom
            painter.drawPixmap(QRectF((w - zw) * 0.5, (h - zh) * 0.5, zw, zh), pix, QRectF(pix.rect()))
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        # Warm golden-indigo vignette
        bot_veil = QLinearGradient(0, h * 0.35, 0, h)
        bot_veil.setColorAt(0.0, QColor(8, 10, 20, 0))
        bot_veil.setColorAt(0.55, QColor(10, 12, 24, 185))
        bot_veil.setColorAt(1.0, QColor(7, 9, 18, 242))
        painter.fillRect(QRectF(0, h * 0.35, w, h * 0.65), bot_veil)

        self._particles.paint(painter, w, h, age)

        # Finale Scroll Card
        card_w = min(860.0, w * 0.78)
        card_h = 276.0
        card = QRectF((w - card_w) * 0.5, h - card_h - 34, card_w, card_h)
        painter.setBrush(QColor(11, 15, 26, 222))
        painter.setPen(QPen(Palette.GOLD_BRIGHT, 1.5))
        painter.drawRoundedRect(card, 16, 16)

        cx = card.center().x()
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(
            QRectF(card.left(), card.top() + 16, card_w, 20),
            Qt.AlignmentFlag.AlignCenter,
            "3 / 3 SANCTUARIES CLEANSED · HOWL, MORA & SHRIEK DEFEATED",
        )

        painter.setFont(make_display_font(24, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(
            QRectF(card.left() + 24, card.top() + 40, card_w - 48, 38),
            Qt.AlignmentFlag.AlignCenter,
            "Her Golden Light Rises Free",
        )

        draw_ornate_divider(painter, cx, card.top() + 86, 220.0)

        epilogue = (
            "Across the Whispering Marsh, the Mouldwood Depths, and the Silent Spire, "
            "the dark mist dissolves into warm golden light. From the heart of the "
            "restored Spirit Tree, your sister's wisp returns—every oath kept to the "
            "forty-second stone."
        )
        painter.setFont(make_display_font(12))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(card.left() + 52, card.top() + 98, card_w - 104, 96),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            epilogue,
        )

        by = card.bottom() - 52.0
        b_map = QRectF(card.left() + 34, by, 186, 36)
        b_arc = QRectF(cx - 115, by, 230, 36)
        b_menu = QRectF(card.right() - 34 - 186, by, 186, 36)
        self._hitboxes["map"] = b_map
        self._hitboxes["archive"] = b_arc
        self._hitboxes["menu"] = b_menu

        ResultScreen._draw_btn(painter, b_map, "«  Realm Map", self._hovered == "map", False)
        ResultScreen._draw_btn(painter, b_arc, "Archive & Report Charts", self._hovered == "archive", False)
        ResultScreen._draw_btn(painter, b_menu, "Main Menu  »", self._hovered == "menu", True)

        painter.end()

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
        if clicked == "map":
            self.return_to_map.emit()
        elif clicked == "archive":
            self.open_archive.emit()
        elif clicked == "menu":
            self.return_to_menu.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.return_to_menu.emit()
        elif event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)
