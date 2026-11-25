"""Realm Map Hub screen ('Realm of the Three Devils').

Displays the three blighted sanctuaries across Nibel connected by a spirit
leyline. Players may choose ANY Devil in ANY order. Clicking a Devil opens its
full heuristic dossier and pre-fight setup screen.
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
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from ui.devils import DEVILS, DevilProfile
from ui.theme import (
    AmbientParticleField,
    AssetCache,
    Palette,
    draw_ornate_divider,
    make_display_font,
    make_ui_font,
)

_CORRUPTED_REALM_BG = "wallpaperflare.com_wallpaper (3).jpg"
_CLEANSED_REALM_BG = "wallpaperflare.com_wallpaper (4).jpg"


class RealmMapScreen(QWidget):
    """Interactive 3-region hub where any Devil can be inspected and challenged."""

    devil_selected = Signal(str)  # emits devil_id ('howl' | 'mora' | 'shriek')
    back_to_menu = Signal()
    replay_story_requested = Signal()
    open_archive_requested = Signal()
    open_ending_requested = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._cleansed_ids: set[str] = set()
        self._focused_index: int = 0
        self._hovered_card: Optional[int] = None
        self._hovered_btn: Optional[str] = None

        self._card_rects: list[QRectF] = [QRectF(), QRectF(), QRectF()]
        self._menu_btn_rect = QRectF()
        self._story_btn_rect = QRectF()
        self._ending_btn_rect = QRectF()
        self._archive_btn_rect = QRectF()
        self._fs_btn_rect = QRectF()
        self._challenge_btn_rect = QRectF()

        self._particles = AmbientParticleField(count=42, seed=314)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------ state
    def set_cleansed_ids(self, cleansed: set[str]) -> None:
        self._cleansed_ids = set(cleansed)
        self.update()

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

    # --------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        w, h = self.width(), self.height()
        elapsed = time.perf_counter() - self._t0

        # 1. Corrupted storm-willow background blending into golden cleansed Spirit Tree
        self._paint_realm_backdrop(painter, w, h)

        # 2. Spirit particles
        self._particles.paint(painter, w, h, elapsed)

        # 3. Top navigation bar & realm title
        self._paint_top_bar(painter, w, h)

        # 4. Compute card positions along a slight rising arc & draw connecting spirit leyline
        self._layout_cards(w, h)
        self._paint_leyline(painter, elapsed)

        # 5. Draw the 3 clickable Devil Sanctuary cards
        for idx, devil in enumerate(DEVILS):
            self._paint_devil_card(painter, idx, devil, elapsed)

        # 6. Bottom focused Devil whisper & quick-challenge bar
        self._paint_bottom_strip(painter, w, h)

        painter.end()

    def _paint_realm_backdrop(self, painter: QPainter, w: int, h: int) -> None:
        corrupted = AssetCache.cover(_CORRUPTED_REALM_BG, w, h)
        cleansed = AssetCache.cover(_CLEANSED_REALM_BG, w, h)
        ratio = len(self._cleansed_ids) / 3.0

        if not corrupted.isNull():
            painter.drawPixmap(0, 0, corrupted)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        if ratio > 0.0 and not cleansed.isNull():
            painter.save()
            painter.setOpacity(min(1.0, ratio * 0.92))
            painter.drawPixmap(0, 0, cleansed)
            painter.restore()

        # Dark atmospheric overlay so map nodes & typography stay crisp
        veil = QLinearGradient(0, 0, 0, h)
        veil.setColorAt(0.0, QColor(7, 10, 18, 205))
        veil.setColorAt(0.25, QColor(9, 13, 24, 135))
        veil.setColorAt(0.76, QColor(8, 12, 22, 165))
        veil.setColorAt(1.0, QColor(5, 7, 13, 238))
        painter.fillRect(0, 0, w, h, veil)

    def _paint_top_bar(self, painter: QPainter, w: int, h: int) -> None:
        # Left utility pills
        self._menu_btn_rect = QRectF(22, 18, 132, 32)
        self._draw_pill(painter, self._menu_btn_rect, "«  Main Menu", self._hovered_btn == "menu")

        self._story_btn_rect = QRectF(164, 18, 124, 32)
        self._draw_pill(painter, self._story_btn_rect, "Replay Story", self._hovered_btn == "story")

        if len(self._cleansed_ids) >= 3:
            self._ending_btn_rect = QRectF(298, 18, 142, 32)
            self._draw_pill(painter, self._ending_btn_rect, "Sister's Finale »", self._hovered_btn == "ending")
        else:
            self._ending_btn_rect = QRectF()

        # Right utility pills
        self._fs_btn_rect = QRectF(w - 160, 18, 138, 32)
        self._draw_pill(painter, self._fs_btn_rect, "Full Screen (F11)", self._hovered_btn == "fs")

        self._archive_btn_rect = QRectF(w - 308, 18, 138, 32)
        self._draw_pill(painter, self._archive_btn_rect, "Archive & Charts", self._hovered_btn == "archive")

        # Realm header
        cx = w * 0.5
        title_font = make_display_font(max(20, int(h * 0.034)), bold=True)
        title_font.setLetterSpacing(title_font.SpacingType.AbsoluteSpacing, 3.8)
        painter.setFont(title_font)
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(0, h * 0.055, w, 42), Qt.AlignmentFlag.AlignCenter, "REALM OF THE THREE DEVILS")

        draw_ornate_divider(painter, cx, h * 0.116, min(260.0, w * 0.22))

        cleansed_n = len(self._cleansed_ids)
        sub_text = (
            f"Souls Reclaimed: {cleansed_n} / 3   ·   "
            "Select any Devil in any order to inspect its Heuristic & enter battle"
        )
        painter.setFont(make_ui_font(10, bold=False))
        painter.setPen(Palette.SPIRIT_CYAN if cleansed_n == 3 else Palette.MEMORY_GOLD)
        painter.drawText(QRectF(0, h * 0.126, w, 24), Qt.AlignmentFlag.AlignCenter, sub_text)

    def _layout_cards(self, w: int, h: int) -> None:
        margin_x = max(36.0, w * 0.052)
        usable_w = w - 2 * margin_x
        gap = max(22.0, usable_w * 0.032)
        card_w = min(380.0, (usable_w - 2 * gap) / 3.0)
        total_w = 3 * card_w + 2 * gap
        start_x = (w - total_w) * 0.5

        card_h = min(465.0, h * 0.605)
        base_y = h * 0.182
        # Slight mythic elevation stagger: Marsh (lower) -> Mouldwood (mid) -> Silent Spire (peak)
        y_offsets = (18.0, 6.0, -8.0)

        for i in range(3):
            x = start_x + i * (card_w + gap)
            self._card_rects[i] = QRectF(x, base_y + y_offsets[i], card_w, card_h)

    def _paint_leyline(self, painter: QPainter, elapsed: float) -> None:
        if len(self._card_rects) < 3:
            return
        c0 = self._card_rects[0].center()
        c1 = self._card_rects[1].center()
        c2 = self._card_rects[2].center()

        path = QPainterPath(c0)
        path.quadTo(QPointF((c0.x() + c1.x()) * 0.5, c0.y() + 48), c1)
        path.quadTo(QPointF((c1.x() + c2.x()) * 0.5, c2.y() - 42), c2)

        pulse = 0.6 + 0.4 * math.sin(elapsed * 2.0)
        glow_pen = QPen(QColor(95, 214, 196, int(65 * pulse)), 6.0)
        core_pen = QPen(QColor(232, 194, 106, 125), 1.6, Qt.PenStyle.DashLine)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(glow_pen)
        painter.drawPath(path)
        painter.setPen(core_pen)
        painter.drawPath(path)
        painter.restore()

    def _paint_devil_card(
        self,
        painter: QPainter,
        idx: int,
        devil: DevilProfile,
        elapsed: float,
    ) -> None:
        rect = self._card_rects[idx]
        hovered = self._hovered_card == idx
        focused = self._focused_index == idx
        cleansed = devil.devil_id in self._cleansed_ids
        accent = Palette.SPIRIT_CYAN if cleansed else QColor(devil.accent_hex)

        # Lift card slightly on hover
        draw_rect = rect.translated(0, -6.0 if hovered else 0.0)

        painter.save()

        # Outer aura when hovered or focused
        if hovered or focused:
            aura_col = QColor(accent.red(), accent.green(), accent.blue(), 58 if hovered else 32)
            painter.setPen(QPen(aura_col, 5.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(draw_rect.adjusted(-2, -2, 2, 2), 16, 16)

        # Card dark-slate body
        card_bg = QLinearGradient(draw_rect.topLeft(), draw_rect.bottomLeft())
        card_bg.setColorAt(0.0, QColor(16, 22, 36, 238))
        card_bg.setColorAt(1.0, QColor(9, 13, 22, 246))
        painter.setBrush(card_bg)
        border_col = (
            accent
            if (hovered or focused)
            else QColor(accent.red(), accent.green(), accent.blue(), 110)
        )
        painter.setPen(QPen(border_col, 1.8 if (hovered or focused) else 1.15))
        painter.drawRoundedRect(draw_rect, 14, 14)

        # Top scene art window clipped to rounded top corners
        art_h = draw_rect.height() * 0.44
        art_rect = QRectF(draw_rect.left() + 2, draw_rect.top() + 2, draw_rect.width() - 4, art_h)
        clip_path = QPainterPath()
        clip_path.addRoundedRect(art_rect, 12, 12)
        painter.save()
        painter.setClipPath(clip_path)

        scene_pix = AssetCache.cover(
            _CLEANSED_REALM_BG if cleansed else devil.scene_image,
            max(1, int(art_rect.width())),
            max(1, int(art_rect.height())),
        )
        if not scene_pix.isNull():
            painter.drawPixmap(art_rect.topLeft(), scene_pix)

        # Subtle bottom gradient fade on scene art
        art_fade = QLinearGradient(0, art_rect.top() + art_h * 0.50, 0, art_rect.bottom())
        art_fade.setColorAt(0.0, QColor(12, 16, 28, 0))
        art_fade.setColorAt(1.0, QColor(12, 16, 28, 232))
        painter.fillRect(art_rect, art_fade)

        painter.restore()  # end art clip

        # Top-left Numeral Seal + Top-right Status Seal over banner
        num_rect = QRectF(draw_rect.left() + 14, draw_rect.top() + 12, 34, 26)
        painter.setBrush(QColor(10, 14, 24, 215))
        painter.setPen(QPen(accent, 1.2))
        painter.drawRoundedRect(num_rect, 8, 8)
        painter.setFont(make_display_font(11, bold=True))
        painter.setPen(accent)
        painter.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, devil.numeral)

        status_label = "CLEANSED" if cleansed else "CORRUPTED"
        status_col = Palette.SPIRIT_CYAN if cleansed else Palette.DEVIL_MAGMA
        st_rect = QRectF(draw_rect.right() - 108, draw_rect.top() + 12, 94, 24)
        painter.setBrush(QColor(10, 14, 24, 215))
        painter.setPen(QPen(status_col, 1.0))
        painter.drawRoundedRect(st_rect, 12, 12)
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(status_col)
        painter.drawText(st_rect, Qt.AlignmentFlag.AlignCenter, status_label)

        # Card body typography
        pad = 16.0
        tx = draw_rect.left() + pad
        tw = draw_rect.width() - 2 * pad
        cur_y = art_rect.bottom() + 8.0

        # Region label
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(accent)
        painter.drawText(QRectF(tx, cur_y, tw, 18), Qt.AlignmentFlag.AlignLeft, devil.region_name.upper())
        cur_y += 18.0

        # Devil Name & Title
        painter.setFont(make_display_font(17, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, cur_y, tw, 26), Qt.AlignmentFlag.AlignLeft, devil.name)
        cur_y += 24.0

        painter.setFont(make_ui_font(9))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, cur_y, tw, 18), Qt.AlignmentFlag.AlignLeft, devil.title)
        cur_y += 22.0

        # Difficulty & Default K pills
        badge_rect = QRectF(tx, cur_y, tw, 24)
        painter.setBrush(QColor(20, 28, 44, 210))
        painter.setPen(QPen(QColor(232, 194, 106, 85), 1.0))
        painter.drawRoundedRect(badge_rect, 6, 6)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.MEMORY_GOLD)
        painter.drawText(
            badge_rect.adjusted(8, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            devil.difficulty_label,
        )
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(
            badge_rect.adjusted(8, 0, -8, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            f"Default K={devil.default_k}",
        )
        cur_y += 30.0

        # Heuristic Name & concise explanation
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, cur_y, tw, 18), Qt.AlignmentFlag.AlignLeft, f"Heuristic: {devil.heuristic_title}")
        cur_y += 18.0

        painter.setFont(make_ui_font(9))
        painter.setPen(Palette.TEXT_MUTED)
        desc_h = max(36.0, draw_rect.bottom() - 48.0 - cur_y)
        painter.drawText(
            QRectF(tx, cur_y, tw, desc_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            devil.heuristic_summary,
        )

        # Card footer action button
        btn_rect = QRectF(tx, draw_rect.bottom() - 42, tw, 30)
        btn_fill = QColor(32, 74, 90, 230) if hovered else QColor(18, 30, 48, 210)
        painter.setBrush(btn_fill)
        painter.setPen(QPen(accent if hovered else QColor(accent.red(), accent.green(), accent.blue(), 120), 1.2))
        painter.drawRoundedRect(btn_rect, 8, 8)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT if hovered else Palette.TEXT_BONE)
        painter.drawText(
            btn_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"«  Inspect Heuristic & Challenge {devil.name}  »",
        )

        painter.restore()

    def _paint_bottom_strip(self, painter: QPainter, w: int, h: int) -> None:
        devil = DEVILS[self._focused_index]
        strip_w = min(1120.0, w * 0.90)
        strip_rect = QRectF((w - strip_w) * 0.5, h - 68, strip_w, 48)

        painter.setBrush(QColor(10, 14, 24, 215))
        painter.setPen(QPen(QColor(232, 194, 106, 80), 1.1))
        painter.drawRoundedRect(strip_rect, 12, 12)

        painter.setFont(make_display_font(11, italic=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        quote_rect = QRectF(strip_rect.left() + 20, strip_rect.top(), strip_w - 260, 48)
        painter.drawText(
            quote_rect,
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            f"{devil.name}: “{devil.intro_taunt}”",
        )

        self._challenge_btn_rect = QRectF(strip_rect.right() - 224, strip_rect.top() + 8, 208, 32)
        hov = self._hovered_btn == "challenge"
        painter.setBrush(QColor(34, 82, 98, 235) if hov else QColor(22, 56, 72, 215))
        painter.setPen(QPen(Palette.GOLD_BRIGHT if hov else Palette.SPIRIT_CYAN, 1.3))
        painter.drawRoundedRect(self._challenge_btn_rect, 16, 16)
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT if hov else Palette.TEXT_BONE)
        painter.drawText(
            self._challenge_btn_rect,
            Qt.AlignmentFlag.AlignCenter,
            f"Open {devil.name}'s Dossier  »",
        )

    @staticmethod
    def _draw_pill(painter: QPainter, rect: QRectF, text: str, hovered: bool) -> None:
        painter.setBrush(QColor(24, 36, 56, 220) if hovered else QColor(11, 15, 24, 190))
        painter.setPen(QPen(Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 75), 1.15))
        painter.drawRoundedRect(rect, 16, 16)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    # ------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hov_card: Optional[int] = None
        for idx, r in enumerate(self._card_rects):
            if r.contains(pos):
                hov_card = idx
                self._focused_index = idx
                break

        hov_btn: Optional[str] = None
        if self._menu_btn_rect.contains(pos):
            hov_btn = "menu"
        elif self._story_btn_rect.contains(pos):
            hov_btn = "story"
        elif not self._ending_btn_rect.isEmpty() and self._ending_btn_rect.contains(pos):
            hov_btn = "ending"
        elif self._archive_btn_rect.contains(pos):
            hov_btn = "archive"
        elif self._fs_btn_rect.contains(pos):
            hov_btn = "fs"
        elif self._challenge_btn_rect.contains(pos):
            hov_btn = "challenge"

        if hov_card != self._hovered_card or hov_btn != self._hovered_btn:
            self._hovered_card = hov_card
            self._hovered_btn = hov_btn
            self.update()

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if (hov_card is not None or hov_btn is not None)
            else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()

        for idx, r in enumerate(self._card_rects):
            if r.contains(pos):
                self._focused_index = idx
                self.devil_selected.emit(DEVILS[idx].devil_id)
                return

        if self._challenge_btn_rect.contains(pos):
            self.devil_selected.emit(DEVILS[self._focused_index].devil_id)
        elif self._menu_btn_rect.contains(pos):
            self.back_to_menu.emit()
        elif self._story_btn_rect.contains(pos):
            self.replay_story_requested.emit()
        elif not self._ending_btn_rect.isEmpty() and self._ending_btn_rect.contains(pos):
            self.open_ending_requested.emit()
        elif self._archive_btn_rect.contains(pos):
            self.open_archive_requested.emit()
        elif self._fs_btn_rect.contains(pos):
            self.toggle_fullscreen_requested.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            self._focused_index = (self._focused_index - 1) % len(DEVILS)
            self.update()
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            self._focused_index = (self._focused_index + 1) % len(DEVILS)
            self.update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.devil_selected.emit(DEVILS[self._focused_index].devil_id)
        elif key == Qt.Key.Key_Escape:
            self.back_to_menu.emit()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)
