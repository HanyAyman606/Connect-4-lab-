"""Devil Pre-Fight Setup & Heuristic Inspector screen.

Opened when the player clicks any Devil on the Realm Map. Displays:
1. Full Devil portrait, difficulty level, and lore challenge.
2. Complete heuristic architecture: strategic summary, exact normalization
   formula, and feature-weight contribution table.
3. Mandatory pre-game depth parameter K selector with live node/complexity
   telemetry powered by ``tree_essentials.search_limits.assess_k``.
4. First-player choice, move-ordering selector, and console trace options.
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
)
from PySide6.QtWidgets import QWidget

from options.first_player import FIRST_COMPUTER, FIRST_HUMAN, FIRST_RANDOM
from setup.session_settings import SessionSettings
from tree_essentials.search_limits import KLevel, assess_k
from ui.devils import DEVIL_BY_ID, DEVILS, DevilProfile
from ui.theme import (
    AmbientParticleField,
    AssetCache,
    Palette,
    make_display_font,
    make_ui_font,
)

_FIRST_CHOICES: tuple[tuple[str, str], ...] = (
    (FIRST_HUMAN, "You First (Spirit · MIN)"),
    (FIRST_COMPUTER, "Devil First (AI · MAX)"),
    (FIRST_RANDOM, "Random Coin Flip"),
)

_ORDERING_CHOICES: tuple[tuple[str, str], ...] = (
    ("four_gain_center", "Four-Gain + Center (Default)"),
    ("center", "Center-First (3,2,4,1,5,0,6)"),
    ("threat_center", "Threat-Block + Center"),
    ("tactical", "Full Tactical"),
    ("left_to_right", "Left-to-Right (0..6)"),
)

_PRINT_DEPTH_CHOICES: tuple[tuple[Optional[int], str], ...] = (
    (2, "Depth 2"),
    (3, "Depth 3"),
    (4, "Depth 4"),
    (None, "Full Tree"),
)


class PreFightScreen(QWidget):
    """Detailed heuristic dossier and pre-battle parameter setup for one Devil."""

    start_battle_requested = Signal(object, object)  # (DevilProfile, SessionSettings)
    back_to_map = Signal()
    toggle_fullscreen_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._devil: DevilProfile = DEVILS[0]
        self._k: int = self._devil.default_k
        self._first_player: str = FIRST_HUMAN
        self._ordering_key: str = "four_gain_center"
        self._console_trace: bool = True
        self._console_max_depth: Optional[int] = None
        self._cleansed_ids: set[str] = set()

        self._particles = AmbientParticleField(count=34, seed=99)
        self._t0 = time.perf_counter()
        self._last_tick = self._t0

        # Interactive hitboxes populated during paint
        self._hitboxes: dict[str, QRectF] = {}
        self._hovered_id: Optional[str] = None
        self._toast_text: str = ""
        self._toast_until: float = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------ state
    def load_devil(self, devil_id: str, cleansed_ids: Optional[set[str]] = None) -> None:
        devil = DEVIL_BY_ID.get(devil_id, DEVILS[0])
        self._devil = devil
        self._k = devil.default_k
        if cleansed_ids is not None:
            self._cleansed_ids = set(cleansed_ids)
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

    def _reset_defaults(self) -> None:
        self._k = self._devil.default_k
        self._first_player = FIRST_HUMAN
        self._ordering_key = "four_gain_center"
        self._console_trace = True
        self._console_max_depth = None
        self.update()

    def build_session_settings(self) -> SessionSettings:
        return SessionSettings(
            k=self._k,
            first_player=self._first_player,
            heuristic_key=self._devil.heuristic_key,
            ordering_key=self._ordering_key,
            pruning_enabled=True,
            devil_name=self._devil.name,
            console_trace=self._console_trace,
            console_max_depth=self._console_max_depth,
        )

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
        self._hitboxes.clear()

        # 1. Devil scene background + dark sanctuary veil
        bg = AssetCache.cover(self._devil.scene_image, w, h)
        if not bg.isNull():
            painter.drawPixmap(0, 0, bg)
        else:
            painter.fillRect(0, 0, w, h, Palette.BG_VOID)

        veil = QLinearGradient(0, 0, w, h)
        veil.setColorAt(0.0, QColor(6, 9, 16, 192))
        veil.setColorAt(0.5, QColor(9, 13, 23, 182))
        veil.setColorAt(1.0, QColor(7, 10, 18, 218))
        painter.fillRect(0, 0, w, h, veil)

        self._particles.paint(painter, w, h, elapsed)

        # 2. Top bar: Back to Map | Quick Devil Switcher Tabs | Fullscreen
        self._paint_top_bar(painter, w)

        # 3. Main two-column dossier area
        margin_x = max(24.0, w * 0.032)
        top_y = 66.0
        bot_margin = 22.0
        content_h = h - top_y - bot_margin
        gap = 20.0
        left_w = min(430.0, (w - 2 * margin_x - gap) * 0.35)
        right_w = w - 2 * margin_x - gap - left_w

        left_rect = QRectF(margin_x, top_y, left_w, content_h)
        right_rect = QRectF(margin_x + left_w + gap, top_y, right_w, content_h)

        self._paint_left_boss_panel(painter, left_rect, elapsed)
        self._paint_right_setup_panel(painter, right_rect)

        if self._toast_text and now < self._toast_until:
            self._paint_toast(painter, w, h, self._toast_until - now)

        painter.end()

    def _paint_top_bar(self, painter: QPainter, w: int) -> None:
        back_r = QRectF(24, 16, 152, 34)
        self._hitboxes["back"] = back_r
        self._draw_chip(painter, back_r, "«  Realm Map", self._hovered_id == "back", False)

        fs_r = QRectF(w - 162, 16, 138, 34)
        self._hitboxes["fs"] = fs_r
        self._draw_chip(painter, fs_r, "Full Screen (F11)", self._hovered_id == "fs", False)

        # Center Devil switcher tabs so user/TA can compare all 3 Devils effortlessly
        tab_w = 172.0
        tab_gap = 10.0
        total_tabs = len(DEVILS) * tab_w + (len(DEVILS) - 1) * tab_gap
        tx = (w - total_tabs) * 0.5
        for d in DEVILS:
            r = QRectF(tx, 16, tab_w, 34)
            hid = f"devil:{d.devil_id}"
            self._hitboxes[hid] = r
            active = d.devil_id == self._devil.devil_id
            self._draw_chip(
                painter,
                r,
                f"{d.numeral} · {d.name} (K={d.default_k})",
                self._hovered_id == hid,
                active,
                accent=QColor(d.accent_hex),
            )
            tx += tab_w + tab_gap

    def _paint_left_boss_panel(self, painter: QPainter, rect: QRectF, elapsed: float) -> None:
        devil = self._devil
        accent = QColor(devil.accent_hex)
        cleansed = devil.devil_id in self._cleansed_ids

        painter.save()
        painter.setBrush(QColor(11, 15, 26, 232))
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 135), 1.4))
        painter.drawRoundedRect(rect, 14, 14)

        # Panoramic art window
        art_h = rect.height() * 0.43
        art_rect = QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, art_h)
        clip = QPainterPath()
        clip.addRoundedRect(art_rect, 12, 12)
        painter.save()
        painter.setClipPath(clip)

        scene = AssetCache.cover(devil.scene_image, max(1, int(art_rect.width())), max(1, int(art_rect.height())))
        if not scene.isNull():
            painter.drawPixmap(art_rect.topLeft(), scene)

        fade = QLinearGradient(0, art_rect.top() + art_h * 0.52, 0, art_rect.bottom())
        fade.setColorAt(0.0, QColor(11, 15, 26, 0))
        fade.setColorAt(1.0, QColor(11, 15, 26, 236))
        painter.fillRect(art_rect, fade)
        painter.restore()

        pad = 20.0
        tx = rect.left() + pad
        tw = rect.width() - 2 * pad
        y = art_rect.bottom() + 10.0

        # Region + Status
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(accent)
        status = "CLEANSED SANCTUARY" if cleansed else f"REGION {devil.numeral} · {devil.region_name.upper()}"
        painter.drawText(QRectF(tx, y, tw, 18), Qt.AlignmentFlag.AlignLeft, status)
        y += 20.0

        # Name + Title
        painter.setFont(make_display_font(22, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, y, tw, 32), Qt.AlignmentFlag.AlignLeft, devil.name)
        y += 30.0

        painter.setFont(make_ui_font(10))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, y, tw, 20), Qt.AlignmentFlag.AlignLeft, devil.title)
        y += 26.0

        # Level badge
        lvl_rect = QRectF(tx, y, tw, 28)
        painter.setBrush(QColor(22, 30, 48, 220))
        painter.setPen(QPen(Palette.MEMORY_GOLD, 1.1))
        painter.drawRoundedRect(lvl_rect, 8, 8)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.MEMORY_GOLD)
        painter.drawText(lvl_rect, Qt.AlignmentFlag.AlignCenter, devil.difficulty_label)
        y += 38.0

        # Taunt quote box
        quote_h = 74.0
        q_rect = QRectF(tx, y, tw, quote_h)
        painter.setBrush(QColor(16, 20, 34, 195))
        painter.setPen(QPen(QColor(232, 228, 216, 52), 1.0))
        painter.drawRoundedRect(q_rect, 8, 8)
        painter.setFont(make_display_font(10, italic=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(
            q_rect.adjusted(12, 8, -12, -8),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
            f"“{devil.intro_taunt}”",
        )
        y += quote_h + 14.0

        # Assignment Rules Contract summary at bottom of left panel
        rules_h = max(78.0, rect.bottom() - 16.0 - y)
        r_rect = QRectF(tx, y, tw, rules_h)
        painter.setBrush(QColor(12, 22, 34, 185))
        painter.setPen(QPen(QColor(95, 214, 196, 75), 1.0))
        painter.drawRoundedRect(r_rect, 8, 8)

        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(tx + 12, y + 7, tw - 24, 16), Qt.AlignmentFlag.AlignLeft, "RITUAL RULES (FULL-BOARD CONNECT 4)")

        painter.setFont(make_ui_font(8))
        painter.setPen(Palette.TEXT_MUTED)
        rules_text = (
            "• 7×6 Grid: Play continues until all 42 orbs fill the board.\n"
            "• Scoring: All 69 windows of 4 count (overlaps score extra).\n"
            "• Minimax + Alpha-Beta: Devil = MAX, You = MIN; cutoff at K."
        )
        painter.drawText(
            QRectF(tx + 12, y + 25, tw - 24, rules_h - 30),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            rules_text,
        )
        painter.restore()

    def _paint_right_setup_panel(self, painter: QPainter, rect: QRectF) -> None:
        devil = self._devil
        accent = QColor(devil.accent_hex)

        painter.save()
        painter.setBrush(QColor(11, 15, 26, 232))
        painter.setPen(QPen(QColor(232, 228, 216, 75), 1.25))
        painter.drawRoundedRect(rect, 14, 14)

        pad = 22.0
        tx = rect.left() + pad
        tw = rect.width() - 2 * pad
        y = rect.top() + 16.0

        # ---------------- SECTION 1: HEURISTIC ARCHITECTURE ----------------
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(accent)
        painter.drawText(QRectF(tx, y, tw, 16), Qt.AlignmentFlag.AlignLeft, "1 · HEURISTIC EVALUATION ARCHITECTURE")
        y += 18.0

        painter.setFont(make_display_font(15, bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(QRectF(tx, y, tw, 24), Qt.AlignmentFlag.AlignLeft, devil.heuristic_title)
        y += 24.0

        painter.setFont(make_ui_font(9))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(
            QRectF(tx, y, tw, 36),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            devil.heuristic_summary,
        )
        y += 38.0

        # Formula box
        form_rect = QRectF(tx, y, tw, 28)
        painter.setBrush(QColor(17, 25, 42, 230))
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 110), 1.0))
        painter.drawRoundedRect(form_rect, 6, 6)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT)
        painter.drawText(form_rect.adjusted(10, 0, -10, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, devil.heuristic_formula)
        y += 34.0

        # Feature weights table
        row_h = 23.0
        header_rect = QRectF(tx, y, tw, 21)
        painter.fillRect(header_rect, QColor(22, 32, 52, 200))
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(tx + 8, y, tw * 0.28, 21), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "FEATURE (COMP − HUMAN)")
        painter.drawText(QRectF(tx + tw * 0.29, y, tw * 0.16, 21), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "WEIGHT")
        painter.drawText(QRectF(tx + tw * 0.46, y, tw * 0.52, 21), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "ROLE IN EVALUATION")
        y += 22.0

        painter.setFont(make_ui_font(8))
        for idx, feat in enumerate(devil.features):
            r_rect = QRectF(tx, y, tw, row_h)
            if idx % 2 == 1:
                painter.fillRect(r_rect, QColor(16, 22, 36, 150))
            painter.setPen(Palette.TEXT_BONE)
            painter.drawText(QRectF(tx + 8, y, tw * 0.28, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, feat.name)
            painter.setPen(Palette.MEMORY_GOLD)
            painter.drawText(QRectF(tx + tw * 0.29, y, tw * 0.16, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, feat.weight)
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(QRectF(tx + tw * 0.46, y, tw * 0.53, row_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, feat.description)
            y += row_h

        y += 12.0

        # ---------------- SECTION 2: SEARCH DEPTH K PARAMETER ----------------
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(
            QRectF(tx, y, tw, 18),
            Qt.AlignmentFlag.AlignLeft,
            "2 · SEARCH DEPTH CUTOFF K (ENTERED BEFORE MATCH BEGINS)",
        )
        y += 22.0

        # [-]  [1][2][3][4][5][6][7]  [+]   Current K badge
        btn_x = tx
        minus_r = QRectF(btn_x, y, 34, 30)
        self._hitboxes["k_minus"] = minus_r
        self._draw_chip(painter, minus_r, "−", self._hovered_id == "k_minus", False)
        btn_x += 40.0

        for k_val in range(1, 8):
            kr = QRectF(btn_x, y, 36, 30)
            hid = f"k_set:{k_val}"
            self._hitboxes[hid] = kr
            self._draw_chip(painter, kr, str(k_val), self._hovered_id == hid, self._k == k_val, accent=Palette.SPIRIT_CYAN)
            btn_x += 41.0

        plus_r = QRectF(btn_x, y, 34, 30)
        self._hitboxes["k_plus"] = plus_r
        self._draw_chip(painter, plus_r, "+", self._hovered_id == "k_plus", False)
        btn_x += 44.0

        # Live K readout badge
        k_badge = QRectF(btn_x, y, max(110.0, tx + tw - btn_x), 30)
        assessment = assess_k(self._k, columns=7, moves_left=42)
        lvl_col = (
            Palette.SPIRIT_CYAN
            if assessment.level is KLevel.NORMAL
            else (Palette.MEMORY_GOLD if assessment.level is KLevel.SLOW else Palette.DEVIL_MAGMA)
        )
        painter.setBrush(QColor(16, 26, 40, 215))
        painter.setPen(QPen(lvl_col, 1.2))
        painter.drawRoundedRect(k_badge, 8, 8)
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(lvl_col)
        ideal_ab = int(round(7 ** (self._k / 2.0)))
        painter.drawText(
            k_badge,
            Qt.AlignmentFlag.AlignCenter,
            f"Active K = {self._k}  ·  7^K Bound ≤ {assessment.estimated_nodes:,}  ·  Ideal α-β ≈ {ideal_ab:,}",
        )
        y += 36.0

        painter.setFont(make_ui_font(8))
        painter.setPen(lvl_col if assessment.is_warning else Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, y, tw, 16), Qt.AlignmentFlag.AlignLeft, assessment.message)
        y += 22.0

        # ---------------- SECTION 3: TURN ORDER, ORDERING & CONSOLE ----------------
        painter.setFont(make_ui_font(9, bold=True))
        painter.setPen(Palette.SPIRIT_CYAN)
        painter.drawText(QRectF(tx, y, tw, 18), Qt.AlignmentFlag.AlignLeft, "3 · FIRST PLAYER, MOVE ORDERING & CONSOLE TREE TRACE")
        y += 21.0

        # Who starts row
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, y, 88, 26), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "First Move:")
        fx = tx + 92.0
        f_w = (tw - 92.0 - 16.0) / 3.0
        for key, label in _FIRST_CHOICES:
            fr = QRectF(fx, y, f_w, 26)
            hid = f"first:{key}"
            self._hitboxes[hid] = fr
            self._draw_chip(painter, fr, label, self._hovered_id == hid, self._first_player == key)
            fx += f_w + 8.0
        y += 32.0

        # Move ordering row
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, y, 88, 26), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Ordering:")
        ox = tx + 92.0
        o_w = (tw - 92.0 - 32.0) / 5.0
        short_labels = ("4-Gain+Ctr", "Center-1st", "Threat+Ctr", "Tactical", "Left→Right")
        for (key, _full), short in zip(_ORDERING_CHOICES, short_labels):
            or_rect = QRectF(ox, y, o_w, 26)
            hid = f"ord:{key}"
            self._hitboxes[hid] = or_rect
            self._draw_chip(painter, or_rect, short, self._hovered_id == hid, self._ordering_key == key)
            ox += o_w + 8.0
        y += 32.0

        # Console trace row
        painter.setFont(make_ui_font(8, bold=True))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(QRectF(tx, y, 88, 26), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Console Tree:")
        cx_cur = tx + 92.0
        tr_rect = QRectF(cx_cur, y, 136, 26)
        self._hitboxes["toggle_trace"] = tr_rect
        self._draw_chip(
            painter,
            tr_rect,
            "Trace: ON (Req.)" if self._console_trace else "Trace: OFF",
            self._hovered_id == "toggle_trace",
            self._console_trace,
        )
        cx_cur += 146.0

        rem_w = (tx + tw - cx_cur - 24.0) / 4.0
        for depth_val, d_label in _PRINT_DEPTH_CHOICES:
            dr = QRectF(cx_cur, y, rem_w, 26)
            hid = f"pdepth:{depth_val}"
            self._hitboxes[hid] = dr
            self._draw_chip(
                painter,
                dr,
                d_label,
                self._hovered_id == hid,
                self._console_max_depth == depth_val,
            )
            cx_cur += rem_w + 8.0

        # ---------------- BOTTOM LAUNCH BAR ----------------
        bar_y = rect.bottom() - 50.0
        reset_r = QRectF(tx, bar_y, 168, 36)
        self._hitboxes["reset"] = reset_r
        self._draw_chip(painter, reset_r, "Reset Devil Defaults", self._hovered_id == "reset", False)

        fight_w = min(360.0, tw - 186.0)
        fight_r = QRectF(tx + tw - fight_w, bar_y, fight_w, 38)
        self._hitboxes["fight"] = fight_r
        f_hov = self._hovered_id == "fight"
        f_grad = QLinearGradient(fight_r.topLeft(), fight_r.bottomRight())
        if f_hov:
            f_grad.setColorAt(0.0, QColor("#2a6f82"))
            f_grad.setColorAt(1.0, QColor("#1e4e68"))
        else:
            f_grad.setColorAt(0.0, QColor("#1c5264"))
            f_grad.setColorAt(1.0, QColor("#14394d"))
        painter.setBrush(f_grad)
        painter.setPen(QPen(Palette.GOLD_BRIGHT if f_hov else Palette.SPIRIT_CYAN, 1.6))
        painter.drawRoundedRect(fight_r, 10, 10)
        painter.setFont(make_display_font(12, bold=True))
        painter.setPen(Palette.GOLD_BRIGHT if f_hov else Palette.TEXT_BONE)
        painter.drawText(
            fight_r,
            Qt.AlignmentFlag.AlignCenter,
            f"«  Enter Battlefield vs {devil.name} (K = {self._k})  »",
        )

        painter.restore()

    @staticmethod
    def _draw_chip(
        painter: QPainter,
        rect: QRectF,
        label: str,
        hovered: bool,
        active: bool,
        accent: QColor = Palette.SPIRIT_CYAN,
    ) -> None:
        if active:
            bg = QColor(accent.red(), accent.green(), accent.blue(), 52)
            border = accent
            fg = Palette.GOLD_BRIGHT if hovered else Palette.TEXT_BONE
        else:
            bg = QColor(26, 36, 56, 215) if hovered else QColor(15, 20, 34, 195)
            border = Palette.MEMORY_GOLD if hovered else QColor(232, 228, 216, 68)
            fg = Palette.TEXT_BONE

        painter.setBrush(bg)
        painter.setPen(QPen(border, 1.25 if (active or hovered) else 1.0))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setFont(make_ui_font(8, bold=active or hovered))
        painter.setPen(fg)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _paint_toast(self, painter: QPainter, w: int, h: int, remaining: float) -> None:
        fade = min(1.0, remaining / 0.45)
        alpha = int(238 * fade)
        tw = min(600.0, w * 0.65)
        rect = QRectF((w - tw) * 0.5, h - 76, tw, 36)
        painter.save()
        painter.setBrush(QColor(12, 18, 30, alpha))
        painter.setPen(QPen(QColor(95, 214, 196, int(195 * fade)), 1.3))
        painter.drawRoundedRect(rect, 10, 10)
        painter.setFont(make_ui_font(10, bold=True))
        painter.setPen(QColor(240, 236, 225, alpha))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._toast_text)
        painter.restore()

    # ------------------------------------------------------------ interaction
    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        hov: Optional[str] = None
        for hid, r in self._hitboxes.items():
            if r.contains(pos):
                hov = hid
                break
        if hov != self._hovered_id:
            self._hovered_id = hov
            self.update()
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if hov is not None else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        clicked: Optional[str] = None
        for hid, r in self._hitboxes.items():
            if r.contains(pos):
                clicked = hid
                break
        if clicked is None:
            return

        if clicked == "back":
            self.back_to_map.emit()
        elif clicked == "fs":
            self.toggle_fullscreen_requested.emit()
        elif clicked.startswith("devil:"):
            self.load_devil(clicked.split(":", 1)[1])
        elif clicked == "k_minus":
            self._k = max(1, self._k - 1)
            self.update()
        elif clicked == "k_plus":
            self._k = min(12, self._k + 1)
            self.update()
        elif clicked.startswith("k_set:"):
            self._k = int(clicked.split(":", 1)[1])
            self.update()
        elif clicked.startswith("first:"):
            self._first_player = clicked.split(":", 1)[1]
            self.update()
        elif clicked.startswith("ord:"):
            self._ordering_key = clicked.split(":", 1)[1]
            self.update()
        elif clicked == "toggle_trace":
            self._console_trace = not self._console_trace
            self.update()
        elif clicked.startswith("pdepth:"):
            val = clicked.split(":", 1)[1]
            self._console_max_depth = None if val == "None" else int(val)
            self.update()
        elif clicked == "reset":
            self._reset_defaults()
        elif clicked == "fight":
            self.start_battle_requested.emit(self._devil, self.build_session_settings())

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.back_to_map.emit()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.start_battle_requested.emit(self._devil, self.build_session_settings())
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Down):
            self._k = max(1, self._k - 1)
            self.update()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_Up):
            self._k = min(12, self._k + 1)
            self.update()
        elif key == Qt.Key.Key_F11:
            self.toggle_fullscreen_requested.emit()
        else:
            super().keyPressEvent(event)
