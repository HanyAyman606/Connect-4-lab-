"""Main Menu screen ('Connect 4: vs The Devils').

Renders the moonlit Three-Devils ritual stage, the ornate title crest, an
animated carved 7x6 ritual board centerpiece with a glowing diagonal
connected-four, drifting spirit motes, and Hollow-Knight / Ori chevron menu
navigation.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable, Optional

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

from ui.theme import (
    AmbientParticleField,
    AssetCache,
    Palette,
    draw_ornate_divider,
    draw_ritual_board,
    make_display_font,
    make_ui_font,
)

# Iconic showcase board from the concept art: diagonal (5,0)-(4,1)-(3,2)-(2,3) is a Spirit 4!
_SHOWCASE_GRID: tuple[tuple[int, ...], ...] = (
    (0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 0, 0, 0, 0),
    (0, 0, 0, 1, 0, 0, 0),
    (0, 0, 1, 2, 1, 2, 0),
    (0, 1, 1, 2, 2, 2, 0),
    (1, 2, 2, 1, 2, 1, 2),
)
_SHOWCASE_FOUR: set[tuple[int, int]] = {(5, 0), (4, 1), (3, 2), (2, 3)}

_STAGE_BG = "Gemini_Generated_Image_7uat4u7uat4u7uat.jpg"


@dataclass(slots=True)
class _MenuEntry:
    key: str
    label: str
    subtitle: str
    rect: QRectF


class MainMenuScreen(QWidget):
    """Interactive main menu with 60 FPS ambient particles and ritual board."""

    start_journey_requested = Signal()
    open_map_requested = Signal()
    open_archive_requested = Signal()
    toggle_fullscreen_requested = Signal()
    quit_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._particles = AmbientParticleField(count=46, seed=108)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0
        self._cleansed_count = 0

        self._entries: list[_MenuEntry] = [
            _MenuEntry("start", "Start Game", "Follow the hero's oath & face the Three Devils", QRectF()),
            _MenuEntry("map", "Realm of the Devils", "Jump directly to the 3-region map", QRectF()),
            _MenuEntry("archive", "Archive & Analysis", "Complexity curves, K benchmarks & heuristics", QRectF()),
            _MenuEntry("quit", "Quit Game", "Leave the ritual table", QRectF()),
        ]
        self._selected_index: int = 0

        self._fullscreen_pill_rect = QRectF()
        self._hovered_fullscreen: bool = False

        self._toast_text: str = ""
        self._toast_until: float = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    # ------------------------------------------------------------------ state
    def set_cleansed_count(self, count: int) -> None:
        self._cleansed_count = max(0, min(3, count))
        self.update()

    def show_toast(self, message: str, duration_sec: float = 3.2) -> None:
        self._toast_text = message
        self._toast_until = time.perf_counter() + duration_sec
        self.update()

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
        self._last_tick = time.perf_counter()
        if not self._timer.isActive():
            self._timer.start()
        self.setFocus()

    # -------------------------------------------------------------- animation
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
        now = time.perf_counter()
        elapsed = now - self._t0

        # 1. Moonlit 3-Devils ritual stage background
        bg = AssetCache.cover(_STAGE_BG, w, h)
        if not bg.isNull():
            painter.drawPixmap(0, 0, bg)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        # 2. Floating spirit motes & ember sparks
        self._particles.paint(painter, w, h, elapsed)

        # 3. Framing vignettes
        self._paint_vignettes(painter, w, h)

        # 4. Ornate header ('CONNECT 4' / 'VS THE DEVILS')
        self._paint_header(painter, w, h, elapsed)

        # 5. Centerpiece carved ritual Connect 4 board resting on the wooden table
        board_h = h * 0.485
        board_w = board_h * 1.18
        board_rect = QRectF((w - board_w) * 0.5, h * 0.268, board_w, board_h)
        highlight_four = _SHOWCASE_FOUR if (math.sin(elapsed * 1.7) > -0.25) else set()
        draw_ritual_board(
            painter,
            board_rect,
            _SHOWCASE_GRID,
            phase=elapsed,
            highlighted_cells=highlight_four,
        )

        # 6. Interactive Hollow-Knight / Ori chevron menu list
        self._paint_menu_items(painter, w, h, elapsed)

        # 7. Top status pills & bottom corner lore quotes
        self._paint_hud_and_quotes(painter, w, h)

        # 8. Optional toast notification
        if self._toast_text and now < self._toast_until:
            self._paint_toast(painter, w, h, self._toast_until - now)

        painter.end()

    def _paint_vignettes(self, painter: QPainter, w: int, h: int) -> None:
        top_grad = QLinearGradient(0, 0, 0, h * 0.26)
        top_grad.setColorAt(0.0, QColor(7, 10, 18, 195))
        top_grad.setColorAt(0.68, QColor(9, 13, 24, 95))
        top_grad.setColorAt(1.0, QColor(9, 13, 24, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.26), top_grad)

        bot_grad = QLinearGradient(0, h * 0.68, 0, h)
        bot_grad.setColorAt(0.0, QColor(6, 8, 14, 0))
        bot_grad.setColorAt(0.38, QColor(6, 8, 14, 155))
        bot_grad.setColorAt(1.0, QColor(5, 7, 12, 232))
        painter.fillRect(QRectF(0, h * 0.68, w, h * 0.32), bot_grad)

        edge = QRadialGradient(QPointF(w * 0.5, h * 0.48), max(w, h) * 0.72)
        edge.setColorAt(0.0, QColor(0, 0, 0, 0))
        edge.setColorAt(0.76, QColor(4, 6, 11, 45))
        edge.setColorAt(1.0, QColor(3, 5, 9, 175))
        painter.fillRect(0, 0, w, h, edge)

    def _paint_header(self, painter: QPainter, w: int, h: int, elapsed: float) -> None:
        cx = w * 0.5
        flourish_half = min(w * 0.24, 290.0)

        draw_ornate_divider(painter, cx, h * 0.045, flourish_half * 0.78)

        title_px = max(28, int(h * 0.056))
        title_font = make_display_font(title_px, bold=True)
        title_font.setLetterSpacing(title_font.SpacingType.AbsoluteSpacing, 5.5)
        painter.setFont(title_font)

        title_rect = QRectF(0, h * 0.052, w, h * 0.105)
        glow_alpha = int(72 + 24 * math.sin(elapsed * 1.6))

        for dx, dy in ((-2.0, 0.0), (2.0, 0.0), (0.0, -2.0), (0.0, 2.0)):
            painter.setPen(QColor(115, 218, 245, glow_alpha))
            painter.drawText(title_rect.translated(dx, dy), Qt.AlignmentFlag.AlignCenter, "CONNECT 4")
        painter.setPen(QColor(0, 0, 0, 210))
        painter.drawText(title_rect.translated(0, 3.0), Qt.AlignmentFlag.AlignCenter, "CONNECT 4")

        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "CONNECT 4")

        draw_ornate_divider(painter, cx, h * 0.162, flourish_half)

        sub_px = max(12, int(h * 0.020))
        sub_font = make_display_font(sub_px, bold=True)
        sub_font.setLetterSpacing(sub_font.SpacingType.AbsoluteSpacing, 4.2)
        painter.setFont(sub_font)
        sub_rect = QRectF(0, h * 0.172, w, h * 0.045)
        painter.setPen(QColor(0, 0, 0, 190))
        painter.drawText(sub_rect.translated(0, 2.0), Qt.AlignmentFlag.AlignCenter, "VS THE DEVILS")
        painter.setPen(Palette.MEMORY_GOLD)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "VS THE DEVILS")

    def _paint_menu_items(self, painter: QPainter, w: int, h: int, elapsed: float) -> None:
        cx = w * 0.5
        start_y = h * 0.764
        row_h = max(29.0, h * 0.044)
        item_w = min(420.0, w * 0.38)

        item_font_px = max(13, int(h * 0.022))
        font_normal = make_display_font(item_font_px, bold=False)
        font_active = make_display_font(item_font_px + 1, bold=True)

        chevron_shift = 4.0 * math.sin(elapsed * 3.4)

        for idx, entry in enumerate(self._entries):
            y = start_y + idx * row_h
            rect = QRectF(cx - item_w * 0.5, y, item_w, row_h * 0.88)
            entry.rect = rect
            selected = idx == self._selected_index

            if selected:
                sel_grad = QLinearGradient(rect.left(), rect.center().y(), rect.right(), rect.center().y())
                sel_grad.setColorAt(0.0, QColor(95, 214, 196, 0))
                sel_grad.setColorAt(0.25, QColor(95, 214, 196, 34))
                sel_grad.setColorAt(0.50, QColor(232, 194, 106, 48))
                sel_grad.setColorAt(0.75, QColor(95, 214, 196, 34))
                sel_grad.setColorAt(1.0, QColor(95, 214, 196, 0))
                painter.fillRect(rect, sel_grad)

                line_grad = QLinearGradient(cx - 115, rect.bottom(), cx + 115, rect.bottom())
                line_grad.setColorAt(0.0, QColor(95, 214, 196, 0))
                line_grad.setColorAt(0.5, QColor(95, 214, 196, 175))
                line_grad.setColorAt(1.0, QColor(95, 214, 196, 0))
                painter.setPen(QPen(line_grad, 1.2))
                painter.drawLine(QPointF(cx - 115, rect.bottom() - 2), QPointF(cx + 115, rect.bottom() - 2))

                painter.setFont(font_active)
                metrics = painter.fontMetrics()
                text_half = metrics.horizontalAdvance(entry.label) * 0.5

                chev_font = make_ui_font(item_font_px, bold=True)
                painter.setFont(chev_font)
                painter.setPen(Palette.SPIRIT_CYAN)
                painter.drawText(
                    QRectF(cx - text_half - 38 - chevron_shift, rect.top(), 28, rect.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    "«",
                )
                painter.drawText(
                    QRectF(cx + text_half + 10 + chevron_shift, rect.top(), 28, rect.height()),
                    Qt.AlignmentFlag.AlignCenter,
                    "»",
                )

                painter.setFont(font_active)
                painter.setPen(QColor(0, 0, 0, 215))
                painter.drawText(rect.translated(0, 2), Qt.AlignmentFlag.AlignCenter, entry.label)
                painter.setPen(Palette.GOLD_BRIGHT)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, entry.label)
            else:
                painter.setFont(font_normal)
                painter.setPen(QColor(0, 0, 0, 190))
                painter.drawText(rect.translated(0, 1.5), Qt.AlignmentFlag.AlignCenter, entry.label)
                painter.setPen(QColor(232, 228, 216, 198))
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, entry.label)

        active = self._entries[self._selected_index]
        hint_font = make_ui_font(max(9, int(h * 0.0135)))
        painter.setFont(hint_font)
        hint_rect = QRectF(cx - 260, start_y + len(self._entries) * row_h + 2, 520, 22)
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(hint_rect, Qt.AlignmentFlag.AlignCenter, active.subtitle)

    def _paint_hud_and_quotes(self, painter: QPainter, w: int, h: int) -> None:
        pill_font = make_ui_font(10, bold=True)
        painter.setFont(pill_font)
        seal_rect = QRectF(22, 18, 192, 30)
        painter.setBrush(QColor(11, 15, 24, 178))
        painter.setPen(QPen(QColor(95, 214, 196, 95), 1.0))
        painter.drawRoundedRect(seal_rect, 15, 15)
        painter.setPen(Palette.SPIRIT_CYAN if self._cleansed_count > 0 else Palette.TEXT_MUTED)
        painter.drawText(
            seal_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"Souls Reclaimed: {self._cleansed_count} / 3",
        )

        fs_w = 138.0
        self._fullscreen_pill_rect = QRectF(w - 22.0 - fs_w, 18, fs_w, 30)
        bg = QColor(22, 34, 52, 215) if self._hovered_fullscreen else QColor(11, 15, 24, 178)
        border = Palette.MEMORY_GOLD if self._hovered_fullscreen else QColor(232, 228, 216, 72)
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.15))
        painter.drawRoundedRect(self._fullscreen_pill_rect, 15, 15)
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(self._fullscreen_pill_rect, Qt.AlignmentFlag.AlignCenter, "Full Screen (F11)")

        quote_px = max(10, int(h * 0.0155))
        quote_font = make_display_font(quote_px, italic=True)
        painter.setFont(quote_font)
        quote_color = QColor(232, 198, 128, 215)

        left_quote = "“The game is never done until the last disc\nfalls.”"
        right_quote = "“Every four is a door. Mind which one you\nleave open.”"

        left_rect = QRectF(28, h - 62, 340, 48)
        right_rect = QRectF(w - 368, h - 62, 340, 48)

        painter.setPen(QColor(0, 0, 0, 210))
        painter.drawText(left_rect.translated(0, 1.5), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, left_quote)
        painter.drawText(right_rect.translated(0, 1.5), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, right_quote)

        painter.setPen(quote_color)
        painter.drawText(left_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, left_quote)
        painter.drawText(right_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, right_quote)

    def _paint_toast(self, painter: QPainter, w: int, h: int, remaining: float) -> None:
        fade = min(1.0, remaining / 0.45)
        alpha = int(235 * fade)
        toast_w = min(560.0, w * 0.62)
        rect = QRectF((w - toast_w) * 0.5, h - 98, toast_w, 34)
        painter.save()
        painter.setBrush(QColor(12, 18, 30, alpha))
        painter.setPen(QPen(QColor(95, 214, 196, int(185 * fade)), 1.2))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(QColor(240, 236, 225, alpha))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._toast_text)
        painter.restore()

    # ------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hover_any = False

        for idx, entry in enumerate(self._entries):
            if entry.rect.contains(pos):
                if self._selected_index != idx:
                    self._selected_index = idx
                    self.update()
                hover_any = True
                break

        fs_hover = self._fullscreen_pill_rect.contains(pos)
        if fs_hover != self._hovered_fullscreen:
            self._hovered_fullscreen = fs_hover
            self.update()
        if fs_hover:
            hover_any = True

        self.setCursor(
            Qt.CursorShape.PointingHandCursor if hover_any else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()

        if self._fullscreen_pill_rect.contains(pos):
            self.toggle_fullscreen_requested.emit()
            return

        for idx, entry in enumerate(self._entries):
            if entry.rect.contains(pos):
                self._selected_index = idx
                self._trigger_entry(entry.key)
                return

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
            self._selected_index = (self._selected_index - 1) % len(self._entries)
            self.update()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
            self._selected_index = (self._selected_index + 1) % len(self._entries)
            self.update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._trigger_entry(self._entries[self._selected_index].key)
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        elif key == Qt.Key.Key_Escape:
            self.quit_requested.emit()
        else:
            super().keyPressEvent(event)

    def _trigger_entry(self, key: str) -> None:
        actions: dict[str, Callable[[], None]] = {
            "start": self.start_journey_requested.emit,
            "map": self.open_map_requested.emit,
            "archive": self.open_archive_requested.emit,
            "quit": self.quit_requested.emit,
        }
        action = actions.get(key)
        if action is not None:
            action()
