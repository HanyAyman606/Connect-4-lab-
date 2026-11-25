"""Visual theme, asset loader, particle field, and custom QPainter renderers.

Implements the 'Dark Kingdom, Spirit Light' style (Hollow Knight corruption +
Ori cleansing light) using pure PySide6 QPainter primitives and cached artwork.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_assets_dir() -> Path:
    """Locate the project media folder (supports 'assets' or 'assests')."""
    for candidate in ("assets", "assests"):
        folder = PROJECT_ROOT / candidate
        if folder.is_dir():
            return folder
    return PROJECT_ROOT / "assets"


ASSETS_DIR = resolve_assets_dir()


class Palette:
    """Core color palette from Game_Design_V1.md sampled against scene artwork."""

    BG_VOID = QColor("#0b0d12")
    BG_DEEP = QColor("#101726")
    PANEL_FILL = QColor(11, 15, 24, 218)
    PANEL_BORDER = QColor(232, 228, 216, 65)

    TEXT_BONE = QColor("#f0ece1")
    TEXT_MUTED = QColor("#9ba9be")
    TEXT_DIM = QColor("#69778c")

    # Hero / Ori Spirit Light (Human = MIN)
    SPIRIT_CYAN = QColor("#5fd6c4")
    SPIRIT_ICE = QColor("#7be3ff")
    SPIRIT_CORE = QColor("#f2feff")
    SPIRIT_DEEP = QColor("#165873")

    # Devil Corruption / Molten Ember (Computer = MAX)
    DEVIL_EMBER = QColor("#c2412d")
    DEVIL_MAGMA = QColor("#ff7542")
    DEVIL_CRUST = QColor("#260d0b")
    DEVIL_GLOW = QColor("#e84a27")

    # Sister's Memory / Sacred Gold
    MEMORY_GOLD = QColor("#e8c26a")
    GOLD_BRIGHT = QColor("#fae09e")
    GOLD_DIM = QColor("#9e7f3b")


class AssetCache:
    """Caches original QPixmaps and scaled cover-fit crops by size."""

    _raw: dict[str, QPixmap] = {}
    _scaled: dict[tuple[str, int, int], QPixmap] = {}

    @classmethod
    def path(cls, filename: str) -> Path:
        return ASSETS_DIR / filename

    @classmethod
    def pixmap(cls, filename: str) -> QPixmap:
        if filename not in cls._raw:
            file_path = cls.path(filename)
            pix = QPixmap(str(file_path)) if file_path.exists() else QPixmap()
            cls._raw[filename] = pix
        return cls._raw[filename]

    @classmethod
    def cover(cls, filename: str, width: int, height: int) -> QPixmap:
        """Scale and center-crop an image to fill (width, height) cleanly."""
        if width <= 0 or height <= 0:
            return QPixmap()
        key = (filename, width, height)
        cached = cls._scaled.get(key)
        if cached is not None:
            return cached

        raw = cls.pixmap(filename)
        if raw.isNull():
            return raw

        # Keep cache bounded if user resizes window continuously
        if len(cls._scaled) > 24:
            cls._scaled.clear()

        expanded = raw.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x_off = max(0, (expanded.width() - width) // 2)
        y_off = max(0, (expanded.height() - height) // 2)
        cropped = expanded.copy(x_off, y_off, width, height)
        cls._scaled[key] = cropped
        return cropped


def make_display_font(point_size: int, bold: bool = False, italic: bool = False) -> QFont:
    """Return an atmospheric serif font suitable for dark-myth titles and quotes."""
    families = set(QFontDatabase.families())
    for preferred in ("Cinzel", "Palatino Linotype", "Book Antiqua", "Georgia", "Times New Roman"):
        if preferred in families:
            font = QFont(preferred, point_size)
            break
    else:
        font = QFont("Serif", point_size)
    font.setBold(bold)
    font.setItalic(italic)
    return font


def make_ui_font(point_size: int, bold: bool = False) -> QFont:
    """Return a crisp sans/UI font for stats, heuristic tables, and minimax trees."""
    families = set(QFontDatabase.families())
    for preferred in ("Segoe UI", "Inter", "Calibri", "Arial"):
        if preferred in families:
            font = QFont(preferred, point_size)
            break
    else:
        font = QFont("Sans-Serif", point_size)
    font.setBold(bold)
    return font


@dataclass(slots=True)
class _Mote:
    x: float
    y: float
    radius: float
    speed_y: float
    sway_amp: float
    sway_freq: float
    phase: float
    alpha: float
    kind: str  # "spirit" | "gold" | "ember"


class AmbientParticleField:
    """Lightweight drifting spirit motes and ember dust rendered at 60 FPS."""

    def __init__(self, count: int = 44, seed: int = 42) -> None:
        rng = random.Random(seed)
        self._motes: list[_Mote] = []
        for i in range(count):
            kind = "spirit" if i % 5 != 0 else ("gold" if i % 10 == 0 else "ember")
            self._motes.append(
                _Mote(
                    x=rng.random(),
                    y=rng.random(),
                    radius=rng.uniform(1.4, 3.8),
                    speed_y=rng.uniform(0.012, 0.036),
                    sway_amp=rng.uniform(0.006, 0.022),
                    sway_freq=rng.uniform(0.7, 1.9),
                    phase=rng.uniform(0.0, math.tau),
                    alpha=rng.uniform(0.28, 0.82),
                    kind=kind,
                )
            )

    def step(self, dt: float) -> None:
        for m in self._motes:
            m.y -= m.speed_y * dt
            m.phase += m.sway_freq * dt
            if m.y < -0.04:
                m.y = 1.04

    def paint(self, painter: QPainter, width: int, height: int, time_s: float) -> None:
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        for m in self._motes:
            px = (m.x + math.sin(m.phase) * m.sway_amp) * width
            py = m.y * height
            pulse = 0.65 + 0.35 * math.sin(time_s * 2.2 + m.phase)
            alpha = int(255 * m.alpha * pulse)

            if m.kind == "spirit":
                core = QColor(168, 245, 255, alpha)
                halo = QColor(72, 202, 228, int(alpha * 0.35))
            elif m.kind == "gold":
                core = QColor(250, 224, 158, alpha)
                halo = QColor(232, 194, 106, int(alpha * 0.32))
            else:
                core = QColor(255, 128, 82, int(alpha * 0.85))
                halo = QColor(194, 65, 45, int(alpha * 0.28))

            grad = QRadialGradient(QPointF(px, py), m.radius * 3.4)
            grad.setColorAt(0.0, core)
            grad.setColorAt(0.38, halo)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(grad)
            painter.drawEllipse(QPointF(px, py), m.radius * 3.4, m.radius * 3.4)
        painter.restore()


def draw_ornate_divider(
    painter: QPainter,
    center_x: float,
    y: float,
    half_width: float,
    color: QColor = Palette.TEXT_BONE,
    accent: QColor = Palette.MEMORY_GOLD,
) -> None:
    """Draw a Hollow-Knight / Ori inspired delicate line flourish with center sigil."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    line_grad = QLinearGradient(center_x - half_width, y, center_x + half_width, y)
    transparent = QColor(color.red(), color.green(), color.blue(), 0)
    mid_col = QColor(color.red(), color.green(), color.blue(), 175)
    line_grad.setColorAt(0.0, transparent)
    line_grad.setColorAt(0.22, mid_col)
    line_grad.setColorAt(0.78, mid_col)
    line_grad.setColorAt(1.0, transparent)

    painter.setPen(QPen(line_grad, 1.25))
    painter.drawLine(QPointF(center_x - half_width, y), QPointF(center_x - 16, y))
    painter.drawLine(QPointF(center_x + 16, y), QPointF(center_x + half_width, y))

    # Subtle side curl arcs
    curl_pen = QPen(QColor(color.red(), color.green(), color.blue(), 135), 1.1)
    painter.setPen(curl_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for sign in (-1.0, 1.0):
        path = QPainterPath(QPointF(center_x + sign * 16, y))
        path.cubicTo(
            QPointF(center_x + sign * 28, y - 8),
            QPointF(center_x + sign * 42, y - 6),
            QPointF(center_x + sign * 48, y),
        )
        painter.drawPath(path)

    # Central diamond + spirit ring
    sigil_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 215), 1.3)
    painter.setPen(sigil_pen)
    painter.drawEllipse(QPointF(center_x, y), 4.5, 4.5)
    painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 220))
    painter.drawEllipse(QPointF(center_x, y), 1.8, 1.8)
    painter.restore()


def _load_board_meta() -> Optional[dict[str, Any]]:
    meta_path = ASSETS_DIR / "extracted" / "board_meta.json"
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_BOARD_META: Optional[dict[str, Any]] = _load_board_meta()


def draw_spirit_disc(
    painter: QPainter,
    center: QPointF,
    radius: float,
    phase: float = 0.0,
    opacity: float = 1.0,
    highlight: bool = False,
) -> None:
    """Paint a luminous Ori spirit-light orb with real painted texture + glow."""
    painter.save()
    painter.setOpacity(opacity)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    pulse = 0.85 + 0.15 * math.sin(phase * 2.3)
    halo_r = radius * (1.52 if highlight else 1.34)
    halo = QRadialGradient(center, halo_r)
    halo.setColorAt(0.0, QColor(145, 246, 255, int(205 * pulse)))
    halo.setColorAt(0.56, QColor(52, 182, 238, int(135 * pulse)))
    halo.setColorAt(1.0, QColor(24, 118, 200, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(center, halo_r, halo_r)

    orb_pix = AssetCache.pixmap("extracted/spirit_orb.png")
    if not orb_pix.isNull():
        painter.save()
        painter.translate(center)
        painter.rotate((phase * 18.0) % 360.0)
        target = QRectF(-radius * 1.03, -radius * 1.03, radius * 2.06, radius * 2.06)
        painter.drawPixmap(target, orb_pix, QRectF(orb_pix.rect()))
        painter.restore()
    else:
        body = QRadialGradient(
            QPointF(center.x() - radius * 0.22, center.y() - radius * 0.22),
            radius * 1.15,
        )
        body.setColorAt(0.0, QColor("#ffffff"))
        body.setColorAt(0.35, QColor("#9ff4ff"))
        body.setColorAt(0.74, QColor("#309ce0"))
        body.setColorAt(1.0, QColor("#124878"))
        painter.setBrush(body)
        painter.setPen(QPen(QColor(195, 250, 255, 215), max(1.2, radius * 0.08)))
        painter.drawEllipse(center, radius, radius)

    if highlight:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(Palette.MEMORY_GOLD, max(2.0, radius * 0.13)))
        painter.drawEllipse(center, radius * 1.08, radius * 1.08)

    painter.restore()


def draw_devil_disc(
    painter: QPainter,
    center: QPointF,
    radius: float,
    phase: float = 0.0,
    opacity: float = 1.0,
    highlight: bool = False,
) -> None:
    """Paint a volcanic devil orb with painted magma fissures + pulsing ember aura."""
    painter.save()
    painter.setOpacity(opacity)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    pulse = 0.78 + 0.22 * math.sin(phase * 2.1)
    halo_r = radius * (1.44 if highlight else 1.25)
    halo = QRadialGradient(center, halo_r)
    halo.setColorAt(0.0, QColor(242, 82, 40, int(165 * pulse)))
    halo.setColorAt(0.62, QColor(168, 36, 20, int(85 * pulse)))
    halo.setColorAt(1.0, QColor(90, 15, 10, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(halo)
    painter.drawEllipse(center, halo_r, halo_r)

    orb_pix = AssetCache.pixmap("extracted/devil_orb.png")
    if not orb_pix.isNull():
        target = QRectF(
            center.x() - radius * 1.03,
            center.y() - radius * 1.03,
            radius * 2.06,
            radius * 2.06,
        )
        painter.drawPixmap(target, orb_pix, QRectF(orb_pix.rect()))
    else:
        body = QRadialGradient(
            QPointF(center.x() - radius * 0.25, center.y() - radius * 0.25),
            radius * 1.2,
        )
        body.setColorAt(0.0, QColor("#59211b"))
        body.setColorAt(0.50, QColor("#2b100d"))
        body.setColorAt(1.0, QColor("#4a1812"))
        painter.setBrush(body)
        painter.drawEllipse(center, radius, radius)

    if highlight:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(Palette.MEMORY_GOLD, max(2.0, radius * 0.13)))
        painter.drawEllipse(center, radius * 1.08, radius * 1.08)

    painter.restore()


def draw_ritual_board(
    painter: QPainter,
    board_rect: QRectF,
    grid_owners: tuple[tuple[int, ...], ...],
    phase: float = 0.0,
    hover_col: Optional[int] = None,
    hover_owner: int = 1,
    highlighted_cells: Optional[set[tuple[int, int]]] = None,
    falling_disc: Optional[tuple[int, float, int]] = None,
) -> tuple[float, float, float]:
    """Render the sculpted gnarled-wood Connect 4 ritual board and glowing orbs.

    Uses the extracted hand-painted frame (``assests/extracted/ritual_board_frame.png``)
    with true transparent holes so discs drop cleanly behind the carved wood
    pillars, falling back to procedural rendering if unavailable.
    """
    rows = len(grid_owners)
    cols = len(grid_owners[0]) if rows else 7
    highlighted = highlighted_cells or set()

    frame_pix = AssetCache.pixmap("extracted/ritual_board_frame.png")
    if not frame_pix.isNull() and _BOARD_META is not None and rows == 6 and cols == 7:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        meta_w = float(_BOARD_META["width"])
        meta_h = float(_BOARD_META["height"])
        scale = min(board_rect.width() / meta_w, board_rect.height() / meta_h)
        draw_w = meta_w * scale
        draw_h = meta_h * scale
        ox = board_rect.left() + (board_rect.width() - draw_w) * 0.5
        oy = board_rect.top() + (board_rect.height() - draw_h) * 0.5
        dest_rect = QRectF(ox, oy, draw_w, draw_h)

        # Ground contact shadow under carved root feet
        shadow_rect = QRectF(
            ox - draw_w * 0.03,
            oy + draw_h * 0.945,
            draw_w * 1.06,
            draw_h * 0.085,
        )
        shadow_grad = QRadialGradient(shadow_rect.center(), shadow_rect.width() * 0.50)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 155))
        shadow_grad.setColorAt(0.60, QColor(3, 5, 10, 80))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_grad)
        painter.drawEllipse(shadow_rect)

        centers = _BOARD_META["centers"]
        orb_r = float(_BOARD_META["orb_radius"]) * scale

        # Ghost disc above hovered column
        if hover_col is not None and 0 <= hover_col < cols:
            top_cx, top_cy = centers[0][hover_col]
            ghost_pt = QPointF(ox + top_cx * scale, oy + top_cy * scale - orb_r * 2.55)
            if hover_owner == 1:
                draw_spirit_disc(painter, ghost_pt, orb_r * 0.95, phase, opacity=0.76)
            else:
                draw_devil_disc(painter, ghost_pt, orb_r * 0.95, phase, opacity=0.76)

        # Settled orbs drawn behind the carved frame holes
        for r in range(rows):
            for c in range(cols):
                owner = grid_owners[r][c]
                if owner == 0:
                    continue
                cx, cy = centers[r][c]
                pt = QPointF(ox + cx * scale, oy + cy * scale)
                is_hi = (r, c) in highlighted
                if owner == 1:
                    draw_spirit_disc(painter, pt, orb_r, phase + r * 0.4 + c * 0.3, highlight=is_hi)
                elif owner == 2:
                    draw_devil_disc(painter, pt, orb_r, phase + r * 0.5 + c * 0.2, highlight=is_hi)

        # Falling animated orb (interpolated along column's hole centers)
        if falling_disc is not None:
            f_col, f_row_float, f_owner = falling_disc
            r_low = max(0, min(rows - 1, int(math.floor(f_row_float))))
            r_high = max(0, min(rows - 1, r_low + 1))
            frac = f_row_float - math.floor(f_row_float)
            if f_row_float < 0:
                c0x, c0y = centers[0][f_col]
                c1x, c1y = centers[1][f_col]
                step_y_px = c1y - c0y
                fx = c0x
                fy = c0y + f_row_float * step_y_px
            else:
                c0x, c0y = centers[r_low][f_col]
                c1x, c1y = centers[r_high][f_col]
                fx = c0x + frac * (c1x - c0x)
                fy = c0y + frac * (c1y - c0y)
            f_pt = QPointF(ox + fx * scale, oy + fy * scale)
            if f_owner == 1:
                draw_spirit_disc(painter, f_pt, orb_r, phase * 2.0)
            else:
                draw_devil_disc(painter, f_pt, orb_r, phase * 2.0)

        # Overlay the carved gnarled-wood frame on top of the orbs!
        painter.drawPixmap(dest_rect, frame_pix, QRectF(frame_pix.rect()))

        # Subtle highlight rings on completed 4-in-a-row windows ON TOP of the wood rim
        if highlighted:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            ring_alpha = int(165 + 75 * math.sin(phase * 3.0))
            painter.setPen(QPen(QColor(232, 194, 106, ring_alpha), max(2.0, orb_r * 0.12)))
            for (hr, hc) in highlighted:
                cx, cy = centers[hr][hc]
                pt = QPointF(ox + cx * scale, oy + cy * scale)
                painter.drawEllipse(pt, orb_r * 1.04, orb_r * 1.04)

        col0_x = ox + centers[0][0][0] * scale
        col6_x = ox + centers[0][6][0] * scale
        step_x = (col6_x - col0_x) / 6.0
        grid_left = col0_x - step_x * 0.5
        grid_top = oy + centers[0][0][1] * scale - step_x * 0.5
        painter.restore()
        return grid_left, grid_top, step_x

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Padding inside carved wooden border
    pad_x = board_rect.width() * 0.065
    pad_top = board_rect.height() * 0.095
    pad_bot = board_rect.height() * 0.085

    inner_w = board_rect.width() - 2 * pad_x
    inner_h = board_rect.height() - pad_top - pad_bot
    step = min(inner_w / cols, inner_h / rows)
    grid_w = step * cols
    grid_h = step * rows
    grid_left = board_rect.left() + (board_rect.width() - grid_w) * 0.5
    grid_top = board_rect.top() + pad_top + (inner_h - grid_h) * 0.5
    hole_r = step * 0.375

    # Ground shadow beneath the carved board feet
    shadow_rect = QRectF(
        board_rect.left() - board_rect.width() * 0.06,
        board_rect.bottom() - board_rect.height() * 0.045,
        board_rect.width() * 1.12,
        board_rect.height() * 0.11,
    )
    shadow_grad = QRadialGradient(shadow_rect.center(), shadow_rect.width() * 0.52)
    shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 195))
    shadow_grad.setColorAt(0.65, QColor(4, 6, 12, 115))
    shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(shadow_grad)
    painter.drawEllipse(shadow_rect)

    # Draw hover ghost disc above hovered column if active
    if hover_col is not None and 0 <= hover_col < cols:
        ghost_center = QPointF(
            grid_left + (hover_col + 0.5) * step,
            board_rect.top() - hole_r * 0.85,
        )
        if hover_owner == 1:
            draw_spirit_disc(painter, ghost_center, hole_r * 0.94, phase, opacity=0.72)
        else:
            draw_devil_disc(painter, ghost_center, hole_r * 0.94, phase, opacity=0.72)

    # Draw settled discs and any falling disc BEFORE frame rim bevels so they sit inside slots
    for r in range(rows):
        for c in range(cols):
            owner = grid_owners[r][c]
            if owner == 0:
                continue
            center = QPointF(grid_left + (c + 0.5) * step, grid_top + (r + 0.5) * step)
            is_hi = (r, c) in highlighted
            if owner == 1:
                draw_spirit_disc(painter, center, hole_r * 0.96, phase + r * 0.4 + c * 0.3, highlight=is_hi)
            elif owner == 2:
                draw_devil_disc(painter, center, hole_r * 0.96, phase + r * 0.5 + c * 0.2, highlight=is_hi)

    if falling_disc is not None:
        f_col, f_row_float, f_owner = falling_disc
        f_center = QPointF(
            grid_left + (f_col + 0.5) * step,
            grid_top + (f_row_float + 0.5) * step,
        )
        if f_owner == 1:
            draw_spirit_disc(painter, f_center, hole_r * 0.96, phase * 2.0)
        else:
            draw_devil_disc(painter, f_center, hole_r * 0.96, phase * 2.0)

    # Build sculpted gnarled-wood outer silhouette with crown & root feet
    left, top, right, bottom = (
        board_rect.left(),
        board_rect.top(),
        board_rect.right(),
        board_rect.bottom(),
    )
    mid_x = board_rect.center().x()
    crown_lift = board_rect.height() * 0.032
    foot_out = board_rect.width() * 0.028

    outer = QPainterPath()
    outer.moveTo(left - foot_out * 0.5, top - crown_lift * 0.55)
    # Top arched ritual crown
    outer.quadTo(left + board_rect.width() * 0.24, top + crown_lift * 0.25, mid_x - step * 0.45, top - crown_lift * 0.35)
    outer.quadTo(mid_x, top - crown_lift * 1.15, mid_x + step * 0.45, top - crown_lift * 0.35)
    outer.quadTo(right - board_rect.width() * 0.24, top + crown_lift * 0.25, right + foot_out * 0.5, top - crown_lift * 0.55)
    # Right gnarled pillar & root foot
    outer.quadTo(right - foot_out * 0.25, board_rect.center().y(), right + foot_out, bottom + crown_lift * 0.45)
    outer.lineTo(right - step * 0.38, bottom + crown_lift * 0.45)
    outer.quadTo(right - step * 0.52, bottom - crown_lift * 0.35, mid_x, bottom - crown_lift * 0.25)
    outer.quadTo(left + step * 0.52, bottom - crown_lift * 0.35, left + step * 0.38, bottom + crown_lift * 0.45)
    outer.lineTo(left - foot_out, bottom + crown_lift * 0.45)
    outer.quadTo(left + foot_out * 0.25, board_rect.center().y(), left - foot_out * 0.5, top - crown_lift * 0.55)
    outer.closeSubpath()

    # Subtract the 42 circular apertures so empty holes stay transparent!
    holes = QPainterPath()
    for r in range(rows):
        for c in range(cols):
            center = QPointF(grid_left + (c + 0.5) * step, grid_top + (r + 0.5) * step)
            holes.addEllipse(center, hole_r, hole_r)
    frame_path = outer.subtracted(holes)

    # Rich moonlit obsidian-wood gradient
    wood_grad = QLinearGradient(board_rect.topLeft(), board_rect.bottomRight())
    wood_grad.setColorAt(0.0, QColor("#2e3548"))
    wood_grad.setColorAt(0.32, QColor("#1f2433"))
    wood_grad.setColorAt(0.68, QColor("#181c28"))
    wood_grad.setColorAt(1.0, QColor("#252a3b"))

    painter.setBrush(wood_grad)
    painter.setPen(QPen(QColor(158, 178, 214, 115), 1.6))
    painter.drawPath(frame_path)

    # Vertical carved pillar grooves between columns
    groove_pen = QPen(QColor(10, 12, 18, 130), max(1.0, step * 0.035))
    highlight_pen = QPen(QColor(175, 198, 235, 42), 1.0)
    for c in range(cols + 1):
        gx = grid_left + c * step
        painter.setPen(groove_pen)
        painter.drawLine(QPointF(gx, grid_top + 4), QPointF(gx, grid_top + grid_h - 4))
        painter.setPen(highlight_pen)
        painter.drawLine(QPointF(gx + 1.4, grid_top + 6), QPointF(gx + 1.4, grid_top + grid_h - 6))

    # Recessed bevel ring around each circular slot
    rim_shadow = QPen(QColor(8, 10, 16, 205), max(1.6, step * 0.055))
    rim_moon = QPen(QColor(168, 194, 235, 88), max(1.0, step * 0.028))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for r in range(rows):
        for c in range(cols):
            center = QPointF(grid_left + (c + 0.5) * step, grid_top + (r + 0.5) * step)
            painter.setPen(rim_shadow)
            painter.drawEllipse(center, hole_r, hole_r)
            painter.setPen(rim_moon)
            painter.drawEllipse(QPointF(center.x(), center.y() + 0.7), hole_r * 1.03, hole_r * 1.03)

    # Top crown crest rune
    crest_center = QPointF(mid_x, top + pad_top * 0.34)
    painter.setPen(QPen(QColor(232, 194, 106, 165), 1.2))
    painter.setBrush(QColor(194, 65, 45, 155))
    diamond = QPainterPath()
    diamond.moveTo(crest_center.x(), crest_center.y() - 6)
    diamond.lineTo(crest_center.x() + 5, crest_center.y())
    diamond.lineTo(crest_center.x(), crest_center.y() + 6)
    diamond.lineTo(crest_center.x() - 5, crest_center.y())
    diamond.closeSubpath()
    painter.drawPath(diamond)

    painter.restore()
    return grid_left, grid_top, step
