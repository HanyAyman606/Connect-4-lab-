"""Interactive 2D Graphical Minimax Alpha-Beta Tree Canvas.

Draws the textbook / Alexandria University *Lecture 6* & *Sheet 6* diagram:
  • △ Upward triangles for MAX nodes
  • ▽ Downward triangles for MIN nodes
  • □ Rectangular boxes for evaluated LEAF (depth K) & TERMINAL (full board) states
  • Dashed lines + red-circled nodes for pruned (unvisited) branches
  • Lecture-6 value/bound badges (= v, ≥ v, ≤ v) & [α, β] windows on nodes
  • Step-by-step playback overlays: red active DFS path, curved blue back-up
    arrows, and '!! CUTOFF' callouts
  • Mouse drag panning, wheel zoom, Fit-to-View, and click/double-click to
    inspect any node's board or expand/collapse subtrees.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Union

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from tree_essentials import LeafKind, Role, TreeNode
from ui.search_worker import format_eval_score
from ui.theme import Palette, make_ui_font
from ui.tree_trace_engine import PlaybackStep, TreeTraceBundle

_SLOT_W = 104.0
_LEVEL_H = 118.0


@dataclass(slots=True)
class _PrunedStub:
    """Visual placeholder for one or more pruned columns under a cutoff node."""

    parent_id: int
    depth: int
    label: str
    tooltip: str


@dataclass(slots=True)
class _LayoutItem:
    item: Union[TreeNode, _PrunedStub]
    x: float = 0.0
    y: float = 0.0
    children: list["_LayoutItem"] = field(default_factory=list)
    hit_rect: QRectF = field(default_factory=QRectF)

    @property
    def is_pruned_stub(self) -> bool:
        return isinstance(self.item, _PrunedStub)


class MinimaxTreeCanvas(QWidget):
    """Pan/zoom 2D vector canvas rendering △ MAX / ▽ MIN / □ Leaf trees."""

    node_selected = Signal(object, tuple)  # (TreeNode, path_tuple)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(230)

        self._root: Optional[TreeNode] = None
        self._bundle: Optional[TreeTraceBundle] = None
        self._step_idx: int = 0  # index into bundle.steps (defaults to final step)
        self._show_windows: bool = True

        self._expanded_ids: set[int] = set()
        self._selected_node_id: Optional[int] = None
        self._hovered_node_id: Optional[int] = None

        self._layout_root: Optional[_LayoutItem] = None
        self._layout_by_node_id: dict[int, _LayoutItem] = {}
        self._all_items: list[_LayoutItem] = []
        self._bounds = QRectF(0, 0, 400, 300)

        # Camera transform: screen_pt = (world_pt + pan) * zoom + center_offset
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 20.0
        self._dragging: bool = False
        self._drag_start = QPointF()
        self._drag_moved: bool = False

    # ------------------------------------------------------------------ setup
    def set_tree(self, root: Optional[TreeNode], bundle: Optional[TreeTraceBundle]) -> None:
        self._root = root
        self._bundle = bundle
        self._expanded_ids.clear()
        self._selected_node_id = id(root) if root is not None else None

        if root is not None and bundle is not None:
            total = len(bundle.trace_rows)
            if total <= 55:
                # Small enough to show every single node at once!
                for n in root.iter_nodes():
                    if not n.is_leaf:
                        self._expanded_ids.add(id(n))
            else:
                # Expand root, depth-1 nodes, the full Principal Variation, and first cutoff
                self._expanded_ids.add(id(root))
                for ch in root.children:
                    self._expanded_ids.add(id(ch))
                for pv_n in root.principal_variation():
                    self._expanded_ids.add(id(pv_n))
                for n in root.iter_nodes():
                    if n.has_cutoff and n.depth <= 2:
                        self._expanded_ids.add(id(n))
                        break
            self._step_idx = max(0, len(bundle.steps) - 1)
        else:
            self._step_idx = 0

        self._rebuild_layout()
        self.fit_to_view()

    def set_step_index(self, step_idx: int, auto_focus: bool = True) -> None:
        if self._bundle is None or not self._bundle.steps:
            return
        self._step_idx = max(0, min(len(self._bundle.steps) - 1, step_idx))
        step = self._bundle.steps[self._step_idx]

        # Ensure ancestors of active node are expanded so user sees the step live!
        if self._root is not None:
            cur = self._root
            self._expanded_ids.add(id(cur))
            need_relayout = False
            for col in step.active_path[:-1]:
                nxt = cur.child_for(col)
                if nxt is None:
                    break
                if id(nxt) not in self._expanded_ids:
                    self._expanded_ids.add(id(nxt))
                    need_relayout = True
                cur = nxt
            if step.kind == "CUTOFF" and step.active_node_id not in self._expanded_ids:
                self._expanded_ids.add(step.active_node_id)
                need_relayout = True
            if need_relayout:
                self._rebuild_layout()

        self._selected_node_id = step.active_node_id
        if auto_focus and step.active_node_id in self._layout_by_node_id:
            self._ensure_item_visible(self._layout_by_node_id[step.active_node_id])
        self.update()

    def select_node_by_id(self, node_id: int) -> None:
        if self._bundle is None or self._root is None:
            return
        path = self._bundle.path_by_node.get(node_id)
        if path is not None:
            cur = self._root
            changed = False
            for col in path[:-1]:
                if id(cur) not in self._expanded_ids:
                    self._expanded_ids.add(id(cur))
                    changed = True
                nxt = cur.child_for(col)
                if nxt is None:
                    break
                cur = nxt
            if id(cur) not in self._expanded_ids and not cur.is_leaf and path:
                self._expanded_ids.add(id(cur))
                changed = True
            if changed:
                self._rebuild_layout()

        self._selected_node_id = node_id
        if node_id in self._layout_by_node_id:
            self._ensure_item_visible(self._layout_by_node_id[node_id])
        self.update()

    def expand_pv_only(self) -> None:
        if self._root is None:
            return
        self._expanded_ids = {id(self._root)}
        for n in self._root.principal_variation():
            self._expanded_ids.add(id(n))
        self._rebuild_layout()
        self.fit_to_view()

    def expand_one_more_level(self) -> None:
        if self._root is None:
            return
        to_add: set[int] = set()
        for n in self._root.iter_nodes():
            if id(n) in self._expanded_ids:
                for ch in n.children:
                    if not ch.is_leaf:
                        to_add.add(id(ch))
        if len(self._expanded_ids) + len(to_add) <= 280:
            self._expanded_ids |= to_add
        else:
            for nid in list(to_add)[:160]:
                self._expanded_ids.add(nid)
        self._rebuild_layout()
        self.fit_to_view()

    def toggle_window_labels(self) -> bool:
        self._show_windows = not self._show_windows
        self.update()
        return self._show_windows

    def zoom_by(self, factor: float) -> None:
        self._zoom = max(0.22, min(2.6, self._zoom * factor))
        self.update()

    def fit_to_view(self) -> None:
        if self._layout_root is None:
            self._zoom = 1.0
            self._pan_x = 0.0
            self._pan_y = 0.0
            self.update()
            return
        vw = max(200.0, self.width() - 96.0)
        vh = max(140.0, self.height() - 56.0)
        bw = max(120.0, self._bounds.width())
        bh = max(100.0, self._bounds.height())
        self._zoom = max(0.26, min(1.35, min(vw / bw, vh / bh)))
        self._pan_x = -self._bounds.center().x()
        self._pan_y = -self._bounds.center().y()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._layout_root is not None and not self._dragging:
            self.fit_to_view()

    # --------------------------------------------------------- layout builder
    def _rebuild_layout(self) -> None:
        self._layout_by_node_id.clear()
        self._all_items.clear()
        if self._root is None:
            self._layout_root = None
            return

        next_leaf_x = 0.0

        def build(node: TreeNode) -> _LayoutItem:
            nonlocal next_leaf_x
            li = _LayoutItem(item=node)
            self._layout_by_node_id[id(node)] = li
            self._all_items.append(li)

            li.y = node.depth * _LEVEL_H
            expanded = id(node) in self._expanded_ids and not node.is_leaf

            if expanded and (node.children or node.pruned_columns):
                for ch in node.children:
                    li.children.append(build(ch))

                if node.pruned_columns:
                    # Show up to 2 individual circled pruned nodes (Sheet 6 style), or compact group
                    ctype = "v ≥ β" if node.role is Role.MAX else "v ≤ α"
                    if len(node.pruned_columns) <= 2:
                        for pc in node.pruned_columns:
                            stub = _PrunedStub(
                                parent_id=id(node),
                                depth=node.depth + 1,
                                label=f"C{pc + 1}",
                                tooltip=f"Column {pc + 1} pruned ({ctype}) — never explored!",
                            )
                            s_item = _LayoutItem(item=stub, x=next_leaf_x, y=(node.depth + 1) * _LEVEL_H)
                            next_leaf_x += _SLOT_W * 0.86
                            li.children.append(s_item)
                            self._all_items.append(s_item)
                    else:
                        cols_lbl = ",".join(f"C{c + 1}" for c in node.pruned_columns)
                        short = f"C{node.pruned_columns[0]+1}..({len(node.pruned_columns)})" if len(cols_lbl) > 9 else cols_lbl
                        stub = _PrunedStub(
                            parent_id=id(node),
                            depth=node.depth + 1,
                            label=short,
                            tooltip=f"Pruned columns [{cols_lbl}] ({ctype}) — never explored!",
                        )
                        s_item = _LayoutItem(item=stub, x=next_leaf_x, y=(node.depth + 1) * _LEVEL_H)
                        next_leaf_x += _SLOT_W * 0.95
                        li.children.append(s_item)
                        self._all_items.append(s_item)

                li.x = 0.5 * (li.children[0].x + li.children[-1].x)
            else:
                li.x = next_leaf_x
                next_leaf_x += _SLOT_W

            return li

        self._layout_root = build(self._root)
        xs = [it.x for it in self._all_items]
        ys = [it.y for it in self._all_items]
        self._bounds = QRectF(
            min(xs) - 70.0,
            min(ys) - 48.0,
            (max(xs) - min(xs)) + 150.0,
            (max(ys) - min(ys)) + 105.0,
        )

    # ------------------------------------------------------- coordinate xform
    def _world_to_screen(self, wx: float, wy: float) -> QPointF:
        cx = self.width() * 0.5 + 28.0
        cy = self.height() * 0.5
        return QPointF((wx + self._pan_x) * self._zoom + cx, (wy + self._pan_y) * self._zoom + cy)

    def _ensure_item_visible(self, li: _LayoutItem) -> None:
        sp = self._world_to_screen(li.x, li.y)
        margin_x = 90.0
        margin_y = 55.0
        if not (margin_x <= sp.x() <= self.width() - margin_x and margin_y <= sp.y() <= self.height() - margin_y):
            self._pan_x = -li.x
            self._pan_y = -li.y

    # --------------------------------------------------------------- painting
    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        # Subtle blueprint / dark parchment grid background
        painter.fillRect(0, 0, w, h, QColor(8, 12, 20, 245))
        painter.setPen(QPen(QColor(95, 214, 196, 55), 1.0))
        painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 8, 8)

        if self._layout_root is None or self._root is None or self._bundle is None:
            painter.setFont(make_ui_font(10))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(
                QRectF(20, 0, w - 40, h),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Waiting for an AI search turn to draw the △ MAX / ▽ MIN Minimax Tree...",
            )
            painter.end()
            return

        bundle = self._bundle
        cur_step: Optional[PlaybackStep] = (
            bundle.steps[self._step_idx] if bundle.steps and 0 <= self._step_idx < len(bundle.steps) else None
        )
        pv_ids = {id(n) for n in self._root.principal_variation()}

        # Build set of active path node IDs for glowing red Lecture-6 search path
        active_path_ids: set[int] = set()
        if cur_step is not None:
            cur_n = self._root
            active_path_ids.add(id(cur_n))
            for col in cur_step.active_path:
                nxt = cur_n.child_for(col)
                if nxt is None:
                    break
                active_path_ids.add(id(nxt))
                cur_n = nxt

        # 1. Draw horizontal depth guides & left-margin MAX / MIN / Leaves labels (Sheet 6 Page 2 style!)
        max_d = max(
            (it.item.depth if isinstance(it.item, _PrunedStub) else it.item.depth)
            for it in self._all_items
        )
        root_is_max = self._root.is_max
        painter.setFont(make_ui_font(8, bold=True))
        for d in range(max_d + 1):
            sy = self._world_to_screen(0.0, d * _LEVEL_H).y()
            if -20.0 <= sy <= h + 20.0:
                painter.setPen(QPen(QColor(255, 255, 255, 16), 1.0, Qt.PenStyle.DotLine))
                painter.drawLine(QPointF(68, sy), QPointF(w - 8, sy))

                is_max_lvl = (d % 2 == 0) if root_is_max else (d % 2 == 1)
                if d == self._root.height() and d > 0:
                    lvl_txt = f"d={d} Leaves"
                    lvl_col = Palette.MEMORY_GOLD
                elif is_max_lvl:
                    lvl_txt = f"d={d} △ MAX"
                    lvl_col = Palette.DEVIL_MAGMA
                else:
                    lvl_txt = f"d={d} ▽ MIN"
                    lvl_col = Palette.SPIRIT_CYAN
                painter.fillRect(QRectF(4, sy - 10, 76, 20), QColor(10, 15, 26, 225))
                painter.setPen(lvl_col)
                painter.drawText(QRectF(6, sy - 10, 72, 20), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, lvl_txt)

        # 2. Draw all parent -> child edges (including dashed pruned edges & bold PV / red active edges)
        self._paint_edges(painter, self._layout_root, bundle, cur_step, pv_ids, active_path_ids)

        # 3. Draw curved blue Back-Up Arrow on BACKUP step (Lecture 6 Slides 16–21!)
        if cur_step is not None and cur_step.backup_child_id is not None:
            p_li = self._layout_by_node_id.get(cur_step.active_node_id)
            c_li = self._layout_by_node_id.get(cur_step.backup_child_id)
            if p_li is not None and c_li is not None:
                self._paint_backup_arrow(painter, c_li, p_li)

        # 4. Draw all visible nodes (△ MAX, ▽ MIN, □ Leaf, and Red-Circled Pruned nodes!)
        for li in self._all_items:
            self._paint_item(painter, li, bundle, cur_step, pv_ids)

        # 5. Legend strip in bottom-left corner of canvas
        leg_rect = QRectF(8, h - 24, min(w - 16, 560), 19)
        painter.fillRect(leg_rect, QColor(9, 13, 22, 210))
        painter.setFont(make_ui_font(7))
        painter.setPen(Palette.TEXT_MUTED)
        painter.drawText(
            leg_rect.adjusted(6, 0, -6, 0),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "△ MAX   ▽ MIN   □ Leaf Eval   ○ Dashed Red = Pruned   ★ Gold = Best Move (PV)   Drag = Pan, Wheel = Zoom, Dbl-Click △/▽ = Expand",
        )

        painter.end()

    def _paint_edges(
        self,
        painter: QPainter,
        parent_li: _LayoutItem,
        bundle: TreeTraceBundle,
        cur_step: Optional[PlaybackStep],
        pv_ids: set[int],
        active_path_ids: set[int],
    ) -> None:
        assert isinstance(parent_li.item, TreeNode)
        p_node = parent_li.item
        if not bundle.is_node_revealed(p_node, self._step_idx):
            return

        p_scr = self._world_to_screen(parent_li.x, parent_li.y)
        r_scaled = 20.0 * self._zoom

        for ch_li in parent_li.children:
            c_scr = self._world_to_screen(ch_li.x, ch_li.y)
            p_anchor = QPointF(p_scr.x(), p_scr.y() + r_scaled * 0.85)
            c_anchor = QPointF(c_scr.x(), c_scr.y() - r_scaled * 0.90)

            if ch_li.is_pruned_stub:
                if not bundle.is_cutoff_revealed(p_node, self._step_idx):
                    continue
                pen = QPen(QColor(235, 86, 72, 195), max(1.3, 1.7 * self._zoom), Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawLine(p_anchor, c_anchor)
                continue

            assert isinstance(ch_li.item, TreeNode)
            c_node = ch_li.item
            revealed = bundle.is_node_revealed(c_node, self._step_idx)
            if not revealed:
                # Faint unvisited ghost line during playback (like Lecture 6 Slide 13!)
                painter.setPen(QPen(QColor(150, 165, 190, 40), 1.0, Qt.PenStyle.DotLine))
                painter.drawLine(p_anchor, c_anchor)
                continue

            is_active_edge = id(p_node) in active_path_ids and id(c_node) in active_path_ids and cur_step is not None and cur_step.kind != "DONE"
            is_best_edge = (p_node.best_column is not None and c_node.column == p_node.best_column and id(p_node) in pv_ids)

            if is_active_edge:
                painter.setPen(QPen(QColor(255, 82, 68, 245), max(2.4, 3.0 * self._zoom)))
            elif is_best_edge:
                painter.setPen(QPen(Palette.GOLD_BRIGHT, max(2.0, 2.5 * self._zoom)))
            else:
                painter.setPen(QPen(QColor(168, 186, 215, 145), max(1.1, 1.4 * self._zoom)))

            painter.drawLine(p_anchor, c_anchor)

            # Column edge label on midpoint (e.g. C4)
            if self._zoom >= 0.48 and c_node.column is not None:
                mid = QPointF((p_anchor.x() + c_anchor.x()) * 0.5, (p_anchor.y() + c_anchor.y()) * 0.5)
                lbl_r = QRectF(mid.x() - 13, mid.y() - 8, 26, 15)
                painter.fillRect(lbl_r, QColor(9, 13, 22, 205))
                painter.setFont(make_ui_font(max(6, int(7.5 * min(1.15, self._zoom))), bold=is_best_edge))
                painter.setPen(Palette.GOLD_BRIGHT if is_best_edge else Palette.TEXT_MUTED)
                painter.drawText(lbl_r, Qt.AlignmentFlag.AlignCenter, f"C{c_node.column + 1}")

            self._paint_edges(painter, ch_li, bundle, cur_step, pv_ids, active_path_ids)

    def _paint_backup_arrow(self, painter: QPainter, child_li: _LayoutItem, parent_li: _LayoutItem) -> None:
        c_pt = self._world_to_screen(child_li.x, child_li.y)
        p_pt = self._world_to_screen(parent_li.x, parent_li.y)
        start = QPointF(c_pt.x() + 18 * self._zoom, c_pt.y() - 12 * self._zoom)
        end = QPointF(p_pt.x() + 20 * self._zoom, p_pt.y() + 10 * self._zoom)
        ctrl = QPointF(max(start.x(), end.x()) + 26 * self._zoom, (start.y() + end.y()) * 0.5)

        path = QPainterPath(start)
        path.quadTo(ctrl, end)
        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#5fd6c4"), max(2.0, 2.4 * self._zoom)))
        painter.drawPath(path)

        # Arrowhead at parent
        ang = math.atan2(end.y() - ctrl.y(), end.x() - ctrl.x())
        ah = 7.5 * max(0.75, self._zoom)
        p1 = QPointF(end.x() - ah * math.cos(ang - 0.45), end.y() - ah * math.sin(ang - 0.45))
        p2 = QPointF(end.x() - ah * math.cos(ang + 0.45), end.y() - ah * math.sin(ang + 0.45))
        painter.setBrush(QColor("#5fd6c4"))
        painter.drawPolygon(QPolygonF([end, p1, p2]))
        painter.restore()

    def _paint_item(
        self,
        painter: QPainter,
        li: _LayoutItem,
        bundle: TreeTraceBundle,
        cur_step: Optional[PlaybackStep],
        pv_ids: set[int],
    ) -> None:
        scr = self._world_to_screen(li.x, li.y)
        z = self._zoom

        # --- Case 1: Pruned Ghost Node (Sheet 6 Page 2 Red-Circled Unvisited Node!) ---
        if isinstance(li.item, _PrunedStub):
            p_node = bundle.node_by_id.get(li.item.parent_id)
            if p_node is None or not bundle.is_cutoff_revealed(p_node, self._step_idx):
                li.hit_rect = QRectF()
                return
            rad = max(12.0, 19.0 * z)
            li.hit_rect = QRectF(scr.x() - rad, scr.y() - rad, rad * 2, rad * 2)

            # Inner unvisited pale box + bold crimson circle (just like Sheet 6 Page 2!)
            box_r = QRectF(scr.x() - rad * 0.62, scr.y() - rad * 0.52, rad * 1.24, rad * 1.04)
            painter.setBrush(QColor(35, 24, 30, 190))
            painter.setPen(QPen(QColor(180, 140, 145, 130), 1.0, Qt.PenStyle.DashLine))
            painter.drawRoundedRect(box_r, 3, 3)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor("#ff4d4d"), max(1.8, 2.2 * z)))
            painter.drawEllipse(scr, rad, rad)

            painter.setFont(make_ui_font(max(6, int(7.5 * min(1.2, z))), bold=True))
            painter.setPen(QColor("#ff9e9e"))
            painter.drawText(li.hit_rect, Qt.AlignmentFlag.AlignCenter, li.item.label)
            if z >= 0.55:
                painter.setFont(make_ui_font(max(6, int(6.8 * min(1.15, z)))))
                painter.setPen(QColor("#ff6b6b"))
                painter.drawText(
                    QRectF(scr.x() - 36, scr.y() + rad + 1, 72, 13),
                    Qt.AlignmentFlag.AlignCenter,
                    "pruned",
                )
            return

        # --- Case 2: Real Visited TreeNode ---
        node = li.item
        nid = id(node)
        revealed = bundle.is_node_revealed(node, self._step_idx)
        if not revealed:
            r_small = max(7.0, 12.0 * z)
            li.hit_rect = QRectF()
            painter.setBrush(QColor(22, 30, 46, 110))
            painter.setPen(QPen(QColor(140, 155, 180, 60), 1.0))
            painter.drawEllipse(scr, r_small, r_small)
            return

        is_active = cur_step is not None and cur_step.active_node_id == nid and cur_step.kind != "DONE"
        is_sel = self._selected_node_id == nid
        is_hov = self._hovered_node_id == nid
        is_pv = nid in pv_ids

        # --- 2a: Leaf / Terminal Rectangular Box (□) ---
        if node.is_leaf:
            bw = max(36.0, 62.0 * z)
            bh = max(20.0, 30.0 * z)
            box = QRectF(scr.x() - bw * 0.5, scr.y() - bh * 0.5, bw, bh)
            li.hit_rect = box.adjusted(-4, -4, 4, 4)

            is_term = node.leaf_kind is LeafKind.TERMINAL
            if is_active:
                painter.setPen(QPen(QColor(255, 90, 70, 175), 5.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(box.adjusted(-2, -2, 2, 2), 6, 6)

            fill = QColor(38, 32, 16, 240) if is_term else QColor(14, 28, 42, 240)
            rim = (
                QColor("#ff5945")
                if is_active
                else (
                    Palette.GOLD_BRIGHT
                    if (is_sel or is_pv or is_term)
                    else (Palette.SPIRIT_CYAN if is_hov else QColor(95, 214, 196, 155))
                )
            )
            painter.setBrush(fill)
            painter.setPen(QPen(rim, 2.0 if (is_sel or is_active or is_pv) else 1.2))
            painter.drawRoundedRect(box, 5, 5)

            painter.setFont(make_ui_font(max(6, int(8.0 * min(1.2, z))), bold=True))
            painter.setPen(Palette.GOLD_BRIGHT if is_term else Palette.TEXT_BONE)
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter, format_eval_score(node.value))

            if z >= 0.55:
                tag = "TERM" if is_term else f"#{bundle.visit_id_by_node.get(nid, '')} eval"
                painter.setFont(make_ui_font(max(6, int(6.8 * min(1.15, z)))))
                painter.setPen(Palette.MEMORY_GOLD if is_term else Palette.SPIRIT_CYAN)
                painter.drawText(
                    QRectF(scr.x() - 36, box.bottom() + 1, 72, 13),
                    Qt.AlignmentFlag.AlignCenter,
                    tag,
                )
            return

        # --- 2b: Internal MAX (△ Upward Triangle) or MIN (▽ Downward Triangle) ---
        rad = max(14.0, 23.0 * z)
        li.hit_rect = QRectF(scr.x() - rad * 1.15, scr.y() - rad * 1.15, rad * 2.3, rad * 2.3)

        if node.is_max:
            # Upward pointing triangle △
            tri = QPolygonF([
                QPointF(scr.x(), scr.y() - rad * 1.05),
                QPointF(scr.x() - rad * 1.02, scr.y() + rad * 0.82),
                QPointF(scr.x() + rad * 1.02, scr.y() + rad * 0.82),
            ])
            fill = QColor(64, 28, 42, 242)
            base_rim = Palette.DEVIL_MAGMA
            text_y_shift = rad * 0.18
        else:
            # Downward pointing triangle ▽
            tri = QPolygonF([
                QPointF(scr.x() - rad * 1.02, scr.y() - rad * 0.82),
                QPointF(scr.x() + rad * 1.02, scr.y() - rad * 0.82),
                QPointF(scr.x(), scr.y() + rad * 1.05),
            ])
            fill = QColor(18, 44, 64, 242)
            base_rim = Palette.SPIRIT_CYAN
            text_y_shift = -rad * 0.16

        if is_active:
            painter.setPen(QPen(QColor(255, 86, 68, 175), 5.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(tri)

        rim = (
            QColor("#ff5945")
            if is_active
            else (Palette.GOLD_BRIGHT if (is_sel or is_pv or is_hov) else base_rim)
        )
        painter.setBrush(fill)
        painter.setPen(QPen(rim, 2.2 if (is_sel or is_pv or is_active) else 1.5))
        painter.drawPolygon(tri)

        # Short label inside triangle ('R' or 'C4')
        in_lbl = "R" if node.is_root else f"C{(node.column or 0) + 1}"
        painter.setFont(make_ui_font(max(6, int(7.8 * min(1.2, z))), bold=True))
        painter.setPen(Palette.TEXT_BONE)
        painter.drawText(
            QRectF(scr.x() - rad, scr.y() - rad * 0.55 + text_y_shift, rad * 2, rad * 1.1),
            Qt.AlignmentFlag.AlignCenter,
            in_lbl,
        )

        # Lecture-6 Yellow Value / Bound Badge next to the triangle (= v, ≥ v, ≤ v)
        badge_txt = bundle.badge_for_node(node, self._step_idx)
        if badge_txt and z >= 0.42:
            bw_tag = max(46.0, 62.0 * min(1.1, z))
            bh_tag = max(14.0, 17.0 * min(1.1, z))
            tag_rect = QRectF(scr.x() + rad * 0.95, scr.y() - bh_tag * 0.55, bw_tag, bh_tag)
            painter.setBrush(QColor(246, 214, 118, 232))
            painter.setPen(QPen(QColor(60, 42, 10, 220), 1.0))
            painter.drawRoundedRect(tag_rect, 4, 4)
            painter.setFont(make_ui_font(max(6, int(7.2 * min(1.15, z))), bold=True))
            painter.setPen(QColor("#141008"))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, badge_txt)

        # Entry [α, β] window pill above triangle when enabled
        if self._show_windows and node.alpha is not None and z >= 0.58:
            if cur_step is not None and nid in cur_step.open_overrides:
                _, a_s, b_s = cur_step.open_overrides[nid]
            else:
                a_s, b_s = format_eval_score(node.alpha), format_eval_score(node.beta)
            w_str = f"[{a_s}, {b_s}]"
            w_rect = QRectF(scr.x() - 56, scr.y() - rad - 16, 112, 14)
            painter.fillRect(w_rect, QColor(8, 12, 20, 195))
            painter.setFont(make_ui_font(max(6, int(6.8 * min(1.1, z)))))
            painter.setPen(Palette.TEXT_MUTED)
            painter.drawText(w_rect, Qt.AlignmentFlag.AlignCenter, w_str)

        # Collapsed subtree indicator pill (+N)
        if nid not in self._expanded_ids and node.children:
            c_rect = QRectF(scr.x() - 22, scr.y() + rad + 2, 44, 14)
            painter.setBrush(QColor(22, 36, 56, 230))
            painter.setPen(QPen(Palette.SPIRIT_CYAN, 1.0))
            painter.drawRoundedRect(c_rect, 6, 6)
            painter.setFont(make_ui_font(6, bold=True))
            painter.setPen(Palette.SPIRIT_CYAN)
            painter.drawText(c_rect, Qt.AlignmentFlag.AlignCenter, f"+{len(node.children)} ▾")

        # '!! CUTOFF' callout during a CUTOFF step at this node
        if cur_step is not None and cur_step.kind == "CUTOFF" and cur_step.active_node_id == nid:
            cut_r = QRectF(scr.x() - 62, scr.y() - rad - 34, 124, 18)
            painter.setBrush(QColor(194, 42, 34, 240))
            painter.setPen(QPen(Palette.GOLD_BRIGHT, 1.2))
            painter.drawRoundedRect(cut_r, 5, 5)
            painter.setFont(make_ui_font(7, bold=True))
            painter.setPen(Palette.TEXT_BONE)
            painter.drawText(cut_r, Qt.AlignmentFlag.AlignCenter, "✂ CUTOFF !!")

    # ------------------------------------------------------------ interaction
    def _hit_test(self, pos: QPointF) -> Optional[_LayoutItem]:
        for li in reversed(self._all_items):
            if not li.hit_rect.isEmpty() and li.hit_rect.contains(pos):
                return li
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.position()
            self._drag_moved = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        if self._dragging:
            delta = pos - self._drag_start
            if delta.manhattanLength() > 4.0:
                self._drag_moved = True
            self._pan_x += delta.x() / self._zoom
            self._pan_y += delta.y() / self._zoom
            self._drag_start = pos
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.update()
            return

        hit = self._hit_test(pos)
        hov_id = id(hit.item) if (hit is not None and isinstance(hit.item, TreeNode)) else None
        if hov_id != self._hovered_node_id:
            self._hovered_node_id = hov_id
            self.update()
        if hit is not None and isinstance(hit.item, _PrunedStub):
            self.setToolTip(hit.item.tooltip)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif hov_id is not None:
            self.setToolTip("")
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setToolTip("")
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            was_click = not self._drag_moved
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if was_click and self._bundle is not None:
                hit = self._hit_test(event.position())
                if hit is not None and isinstance(hit.item, TreeNode):
                    nid = id(hit.item)
                    # Clicking a collapsed node's bottom '+N' area or selecting it
                    self._selected_node_id = nid
                    path = self._bundle.path_by_node.get(nid, ())
                    self.node_selected.emit(hit.item, path)
                    self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            return
        hit = self._hit_test(event.position())
        if hit is not None and isinstance(hit.item, TreeNode) and not hit.item.is_leaf:
            nid = id(hit.item)
            if nid in self._expanded_ids and not hit.item.is_root:
                self._expanded_ids.remove(nid)
            else:
                self._expanded_ids.add(nid)
            self._rebuild_layout()
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        dy = event.angleDelta().y()
        if dy > 0:
            self.zoom_by(1.15)
        elif dy < 0:
            self.zoom_by(1.0 / 1.15)
