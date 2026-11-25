"""Brief Hero Story sequence screen (4 illustrated chapters before the Map).

Presents the dark-myth premise concisely across four chapters with smooth
crossfades, subtle Ken-Burns motion on the artwork, drifting spirit motes,
and instant keyboard/mouse navigation (Next, Back, Skip Story).
"""

from __future__ import annotations

import math
import time
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

from ui.devils import STORY_SLIDES
from ui.theme import (
    AmbientParticleField,
    AssetCache,
    Palette,
    draw_ornate_divider,
    make_display_font,
    make_ui_font,
)


class StoryScreen(QWidget):
    """Four-panel narrative introduction leading from Main Menu to Realm Map."""

    finished_story = Signal()
    back_to_menu = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._slides = STORY_SLIDES
        self._index = 0
        self._prev_index = 0
        self._transition_start = time.perf_counter()
        self._slide_started = self._transition_start

        self._particles = AmbientParticleField(count=38, seed=77)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0

        self._back_rect = QRectF()
        self._next_rect = QRectF()
        self._skip_rect = QRectF()
        self._dot_rects: list[QRectF] = []
        self._hovered: Optional[str] = None

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    def reset_to_start(self) -> None:
        self._index = 0
        self._prev_index = 0
        now = time.perf_counter()
        self._transition_start = now - 1.0
        self._slide_started = now
        self.resume_effects()

    def pause_effects(self) -> None:
        self._timer.stop()

    def resume_effects(self) -> None:
        self._last_tick = time.perf_counter()
        if not self._timer.isActive():
            self._timer.start()
        self.setFocus()

    def _go_to(self, new_index: int) -> None:
        new_index = max(0, min(len(self._slides) - 1, new_index))
        if new_index == self._index:
            return
        self._prev_index = self._index
        self._index = new_index
        now = time.perf_counter()
        self._transition_start = now
        self._slide_started = now
        self.update()

    def _advance(self) -> None:
        if self._index + 1 < len(self._slides):
            self._go_to(self._index + 1)
        else:
            self.finished_story.emit()

    def _go_back(self) -> None:
        if self._index > 0:
            self._go_to(self._index - 1)
        else:
            self.back_to_menu.emit()

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

        # Smooth crossfade + subtle slow zoom on chapter illustration
        fade_t = min(1.0, (now - self._transition_start) / 0.42)
        slide_age = now - self._slide_started
        zoom = 1.0 + min(0.045, slide_age * 0.0045)

        if fade_t < 1.0 and self._prev_index != self._index:
            self._draw_slide_image(painter, self._slides[self._prev_index]["image"], w, h, 1.02, 1.0)
            self._draw_slide_image(painter, self._slides[self._index]["image"], w, h, zoom, fade_t)
        else:
            self._draw_slide_image(painter, self._slides[self._index]["image"], w, h, zoom, 1.0)

        # Ambient motes
        self._particles.paint(painter, w, h, elapsed)

        # Atmospheric top & bottom dark gradients
        top_veil = QLinearGradient(0, 0, 0, h * 0.18)
        top_veil.setColorAt(0.0, QColor(6, 8, 14, 195))
        top_veil.setColorAt(1.0, QColor(6, 8, 14, 0))
        painter.fillRect(QRectF(0, 0, w, h * 0.18), top_veil)

        bot_veil = QLinearGradient(0, h * 0.48, 0, h)
        bot_veil.setColorAt(0.0, QColor(6, 8, 14, 0))
        bot_veil.setColorAt(0.42, QColor(6, 8, 14, 200))
        bot_veil.setColorAt(1.0, QColor(5, 7, 12, 246))
        painter.fillRect(QRectF(0, h * 0.48, w, h * 0.52), bot_veil)

        edge = QRadialGradient(QPointF(w * 0.5, h * 0.42), max(w, h) * 0.72)
        edge.setColorAt(0.0, QColor(0, 0, 0, 0))
        edge.setColorAt(1.0, QColor(3, 5, 10, 175))
        painter.fillRect(0, 0, w, h, edge)

        # Top-right Skip Story pill
        self._skip_rect = QRectF(w - 168, 20, 144, 32)
        self._draw_button(
            painter,
            self._skip_rect,
            "Skip Story  »",
            hovered=(self._hovered == "skip"),
            primary=False,
        )

        # Bottom ornate story scroll card
        card_w = min(900.0, w * 0.80)
        card_h = max(215.0, h * 0.295)
        card_rect = QRectF((w - card_w) * 0.5, h - card_h - 28, card_w, card_h)

        painter.setBrush(QColor(10, 14, 24, 218))
        painter.setPen(QPen(QColor(232, 194, 106, 95), 1.3))
        painter.drawRoundedRect(card_rect, 14, 14)

        slide = self._slides[self._index]
        cx = card_rect.center().x()

        # Chapter tag
        chap_font = make_ui_font(10, bold=True)
        chap_font.setLetterSpacing(chap_font.SpacingType.AbsoluteSpacing, 2.2)
        painter.setFont(chap_font)
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(
            QRectF(card_rect.left(), card_rect.top() + 14, card_w, 20),
            Qt.AlignmentFlag.AlignCenter,
            slide["chapter"],
        )

        # Chapter title
        title_font = make_display_font(max(18, int(h * 0.028)), bold=True)
        painter.setFont(title_font)
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(
            QRectF(card_rect.left() + 30, card_rect.top() + 36, card_w - 60, 38),
            Qt.AlignmentFlag.AlignCenter,
            slide["title"],
        )

        draw_ornate_divider(painter, cx, card_rect.top() + 79, min(220.0, card_w * 0.30))

        # Body prose
        body_font = make_display_font(max(12, int(h * 0.0175)))
        painter.setFont(body_font)
        painter.setPen(Palette.TEXT_BONE)
        body_rect = QRectF(
            card_rect.left() + 48,
            card_rect.top() + 90,
            card_w - 96,
            card_h - 148,
        )
        painter.drawText(
            body_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            slide["body"],
        )

        # Bottom controls inside story card: Back | Dots | Next / Enter Realm
        ctrl_y = card_rect.bottom() - 48
        self._back_rect = QRectF(card_rect.left() + 26, ctrl_y, 148, 34)
        back_label = "«  Main Menu" if self._index == 0 else "«  Previous"
        self._draw_button(
            painter,
            self._back_rect,
            back_label,
            hovered=(self._hovered == "back"),
            primary=False,
        )

        is_last = self._index == len(self._slides) - 1
        next_w = 196.0 if is_last else 148.0
        self._next_rect = QRectF(card_rect.right() - 26 - next_w, ctrl_y, next_w, 34)
        next_label = "Enter the Realm  »" if is_last else "Continue  »"
        self._draw_button(
            painter,
            self._next_rect,
            next_label,
            hovered=(self._hovered == "next"),
            primary=True,
        )

        # Progress diamonds
        self._dot_rects.clear()
        dot_spacing = 26.0
        dots_start_x = cx - (len(self._slides) - 1) * dot_spacing * 0.5
        for i in range(len(self._slides)):
            dx = dots_start_x + i * dot_spacing
            dy = ctrl_y + 17.0
            d_rect = QRectF(dx - 9, dy - 9, 18, 18)
            self._dot_rects.append(d_rect)
            active = i == self._index
            passed = i < self._index
            radius = 5.2 if active else 3.6
            color = (
                Palette.MEMORY_GOLD
                if active
                else (Palette.SPIRIT_CYAN if passed else QColor(155, 169, 190, 90))
            )
            painter.setPen(QPen(color, 1.3))
            painter.setBrush(color if (active or passed) else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(dx, dy), radius, radius)

        painter.end()

    @staticmethod
    def _draw_slide_image(
        painter: QPainter,
        filename: str,
        w: int,
        h: int,
        zoom: float,
        opacity: float,
    ) -> None:
        pix = AssetCache.cover(filename, w, h)
        if pix.isNull():
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)
            return
        painter.save()
        painter.setOpacity(opacity)
        zw, zh = w * zoom, h * zoom
        target = QRectF((w - zw) * 0.5, (h - zh) * 0.5, zw, zh)
        painter.drawPixmap(target, pix, QRectF(pix.rect()))
        painter.restore()

    @staticmethod
    def _draw_button(
        painter: QPainter,
        rect: QRectF,
        label: str,
        hovered: bool,
        primary: bool,
    ) -> None:
        if primary:
            bg = QColor(34, 78, 92, 235) if hovered else QColor(20, 52, 66, 215)
            border = Palette.GOLD_BRIGHT if hovered else Palette.SPIRIT_CYAN
            fg = Palette.GOLD_BRIGHT if hovered else Palette.TEXT_BONE
        else:
            bg = QColor(24, 34, 52, 220) if hovered else QColor(13, 18, 30, 190)
            border = Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 80)
            fg = Palette.TEXT_BONE

        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.25))
        painter.drawRoundedRect(rect, 17, 17)
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    # ------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hov: Optional[str] = None
        if self._next_rect.contains(pos):
            hov = "next"
        elif self._back_rect.contains(pos):
            hov = "back"
        elif self._skip_rect.contains(pos):
            hov = "skip"
        else:
            for idx, r in enumerate(self._dot_rects):
                if r.contains(pos):
                    hov = f"dot:{idx}"
                    break

        if hov != self._hovered:
            self._hovered = hov
            self.update()
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if hov is not None else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._next_rect.contains(pos):
            self._advance()
        elif self._back_rect.contains(pos):
            self._go_back()
        elif self._skip_rect.contains(pos):
            self.finished_story.emit()
        else:
            for idx, r in enumerate(self._dot_rects):
                if r.contains(pos):
                    self._go_to(idx)
                    return

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Right, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._advance()
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Backspace):
            self._go_back()
        elif key == Qt.Key.Key_Escape:
            self.finished_story.emit()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)
