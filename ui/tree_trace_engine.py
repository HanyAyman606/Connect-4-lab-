"""Sheet-6 Alpha-Beta Trace Table & Lecture-6 Step-by-Step Playback Engine.

Transforms any recorded ``TreeNode`` root into:
1. ``Sheet6TraceRow`` rows matching Alexandria University's *Sheet 6 Model Answer*
   trace convention (Node, Type, old α, new α, old β, new β, old v, new v / cutoff).
2. ``MinimaxComputationRow`` rows matching *Sheet 6 Question 1a / 3f*
   (Node, Type, min/max(...) over children, Chosen Column, Backed-Up Value).
3. ``PlaybackStep`` chronological DFS events matching *Lecture 6 Slides 16–21*
   (ENTER node, EVALUATE leaf, BACK-UP arrow to parent updating v/α/β, and
   CUTOFF !! pruning remaining columns), using O(K) state per step.
4. Console text formatters with 4-decimal heuristic precision + raw scores so
   early-game evaluations never round to ``+0.00``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.board import Board
from core.game import Game, GameState
from tree_essentials import LeafKind, Role, SearchResult, TreeNode
from ui.search_worker import evaluate_board_detailed, format_eval_score

MAX_PLAYBACK_STEPS = 3000


def format_path_label(path: tuple[int, ...]) -> str:
    """Return 'R' for root or 1-based column path such as 'C4' or 'C4→C3'."""
    if not path:
        return "R"
    return "→".join(f"C{c + 1}" for c in path)


@dataclass(frozen=True, slots=True)
class Sheet6TraceRow:
    """One row of the Sheet-6 Alpha-Beta trace table, in exact visiting order."""

    visit_id: int
    node_id: int
    node: TreeNode
    path: tuple[int, ...]
    node_label: str
    node_type: str  # "MAX", "MIN", "LEAF", "TERM"
    depth: int
    old_alpha: str
    new_alpha: str
    old_beta: str
    new_beta: str
    old_value: str
    new_value: str
    note: str


@dataclass(frozen=True, slots=True)
class MinimaxComputationRow:
    """One row of the Sheet-6 bottom-up Minimax computation summary table."""

    visit_id: int
    node_id: int
    node: TreeNode
    path: tuple[int, ...]
    node_label: str
    role_str: str
    depth: int
    computation: str
    chosen_move: str
    backed_up_value: str


@dataclass(frozen=True, slots=True)
class PlaybackStep:
    """One atomic step of the Alpha-Beta DFS playback (Lecture 6 Slides 16–21)."""

    step_index: int  # 1-based
    kind: str  # "ENTER" | "LEAF" | "BACKUP" | "CUTOFF" | "DONE"
    active_node_id: int
    active_path: tuple[int, ...]
    backup_child_id: Optional[int]
    max_visit_seen: int
    trace_visit_id: int  # 1-based row in Sheet6TraceRow
    cur_alpha: str
    cur_beta: str
    cur_v: str
    # Open stack overrides: node_id -> (live_badge_str, live_alpha_str, live_beta_str)
    open_overrides: dict[int, tuple[str, str, str]]
    headline: str
    detail: str


@dataclass(slots=True)
class TreeTraceBundle:
    """Complete trace, computation tables, node metadata, and playback timeline."""

    trace_rows: list[Sheet6TraceRow]
    computation_rows: list[MinimaxComputationRow]
    steps: list[PlaybackStep]
    visit_id_by_node: dict[int, int]
    finish_step_by_node: dict[int, int]
    cutoff_step_by_node: dict[int, int]
    path_by_node: dict[int, tuple[int, ...]]
    final_badge_by_node: dict[int, str]
    node_by_id: dict[int, TreeNode]
    steps_truncated: bool = False

    def is_node_revealed(self, node: TreeNode, step_idx: int) -> bool:
        if not self.steps or step_idx >= len(self.steps):
            return True
        vid = self.visit_id_by_node.get(id(node), 0)
        return vid <= self.steps[step_idx].max_visit_seen

    def is_cutoff_revealed(self, node: TreeNode, step_idx: int) -> bool:
        if not node.has_cutoff:
            return False
        if not self.steps or step_idx >= len(self.steps):
            return True
        c_step = self.cutoff_step_by_node.get(id(node))
        if c_step is None:
            return True
        return self.steps[step_idx].step_index >= c_step

    def badge_for_node(self, node: TreeNode, step_idx: int) -> str:
        nid = id(node)
        if not self.steps or step_idx >= len(self.steps):
            return self.final_badge_by_node.get(nid, "")
        step = self.steps[step_idx]
        if nid in step.open_overrides:
            return step.open_overrides[nid][0]
        fin = self.finish_step_by_node.get(nid)
        if fin is not None and step.step_index >= fin:
            return self.final_badge_by_node.get(nid, "")
        return ""


def build_tree_trace(root: Optional[TreeNode]) -> TreeTraceBundle:
    """Simulate the exact DFS walk over ``root`` to build Sheet-6 tables & steps."""
    if root is None:
        return TreeTraceBundle([], [], [], {}, {}, {}, {}, {}, {}, False)

    trace_rows: list[Sheet6TraceRow] = []
    computation_rows: list[MinimaxComputationRow] = []
    steps: list[PlaybackStep] = []

    visit_id_by_node: dict[int, int] = {}
    finish_step_by_node: dict[int, int] = {}
    cutoff_step_by_node: dict[int, int] = {}
    path_by_node: dict[int, tuple[int, ...]] = {}
    final_badge_by_node: dict[int, str] = {}
    node_by_id: dict[int, TreeNode] = {}

    visit_counter = 0
    steps_truncated = False

    # Active ancestor stack during DFS simulation:
    # node_id -> [role, live_v, live_alpha, live_beta]
    open_stack: dict[int, list] = {}

    def snapshot_overrides() -> dict[int, tuple[str, str, str]]:
        out: dict[int, tuple[str, str, str]] = {}
        for onid, (orole, ov, oalpha, obeta) in open_stack.items():
            if ov == float("-inf") or ov == float("inf"):
                b_txt = "v = −∞" if orole is Role.MAX else "v = +∞"
            else:
                sym = "≥" if orole is Role.MAX else "≤"
                b_txt = f"{sym} {format_eval_score(ov)}"
            out[onid] = (b_txt, format_eval_score(oalpha), format_eval_score(obeta))
        return out

    def push_step(
        kind: str,
        active_node: TreeNode,
        active_path: tuple[int, ...],
        backup_child: Optional[TreeNode],
        cur_a: Optional[float],
        cur_b: Optional[float],
        cur_v: Optional[float],
        v_is_dash: bool,
        headline: str,
        detail: str,
    ) -> int:
        nonlocal steps_truncated
        if len(steps) >= MAX_PLAYBACK_STEPS:
            steps_truncated = True
            return len(steps)
        s_num = len(steps) + 1
        vid = visit_id_by_node[id(active_node)]
        steps.append(
            PlaybackStep(
                step_index=s_num,
                kind=kind,
                active_node_id=id(active_node),
                active_path=active_path,
                backup_child_id=id(backup_child) if backup_child is not None else None,
                max_visit_seen=visit_counter,
                trace_visit_id=vid,
                cur_alpha=format_eval_score(cur_a),
                cur_beta=format_eval_score(cur_b),
                cur_v="—" if v_is_dash else format_eval_score(cur_v),
                open_overrides=snapshot_overrides(),
                headline=headline,
                detail=detail,
            )
        )
        return s_num

    def dfs(node: TreeNode, path: tuple[int, ...]) -> None:
        nonlocal visit_counter
        visit_counter += 1
        my_visit = visit_counter
        nid = id(node)
        visit_id_by_node[nid] = my_visit
        path_by_node[nid] = path
        node_by_id[nid] = node

        lbl = format_path_label(path)
        old_a = node.alpha
        old_b = node.beta

        if node.is_leaf:
            leaf_type = "TERM" if node.leaf_kind is LeafKind.TERMINAL else "LEAF"
            final_badge = f"= {format_eval_score(node.value)}"
            final_badge_by_node[nid] = final_badge
            note_txt = (
                "exact full-board utility"
                if node.leaf_kind is LeafKind.TERMINAL
                else "cutoff depth K heuristic eval"
            )
            trace_rows.append(
                Sheet6TraceRow(
                    visit_id=my_visit,
                    node_id=nid,
                    node=node,
                    path=path,
                    node_label=lbl,
                    node_type=leaf_type,
                    depth=node.depth,
                    old_alpha=format_eval_score(old_a),
                    new_alpha=format_eval_score(old_a),
                    old_beta=format_eval_score(old_b),
                    new_beta=format_eval_score(old_b),
                    old_value="—",
                    new_value=format_eval_score(node.value),
                    note=note_txt,
                )
            )
            s_idx = push_step(
                kind="LEAF",
                active_node=node,
                active_path=path,
                backup_child=None,
                cur_a=old_a,
                cur_b=old_b,
                cur_v=node.value,
                v_is_dash=False,
                headline=f"Evaluate {leaf_type} {lbl} (d={node.depth}) → {format_eval_score(node.value)}",
                detail=(
                    f"Reached {'full board (TERMINAL)' if leaf_type == 'TERM' else f'depth K={node.depth} (LEAF)'}: "
                    f"returns {format_eval_score(node.value)} with entry window [α={format_eval_score(old_a)}, β={format_eval_score(old_b)}]."
                ),
            )
            finish_step_by_node[nid] = s_idx
            return

        # Internal MAX or MIN node
        init_v = float("-inf") if node.role is Role.MAX else float("inf")
        cur_a = old_a if old_a is not None else float("-inf")
        cur_b = old_b if old_b is not None else float("inf")
        cur_v = init_v

        # Reserve slot in trace_rows in pre-order visiting position!
        row_slot = len(trace_rows)
        trace_rows.append(None)  # type: ignore[arg-type]

        open_stack[nid] = [node.role, cur_v, cur_a, cur_b]
        push_step(
            kind="ENTER",
            active_node=node,
            active_path=path,
            backup_child=None,
            cur_a=cur_a,
            cur_b=cur_b,
            cur_v=cur_v,
            v_is_dash=False,
            headline=f"Enter {node.role.value} Node {lbl} (d={node.depth})",
            detail=(
                f"Receive window α = {format_eval_score(old_a)}, β = {format_eval_score(old_b)}; "
                f"initialize v = {format_eval_score(init_v)}."
            ),
        )

        for child in node.children:
            c_path = path + ((child.column,) if child.column is not None else ())
            dfs(child, c_path)
            c_val = child.value if child.value is not None else 0.0
            prev_v = cur_v

            if node.role is Role.MAX:
                if c_val > cur_v:
                    cur_v = c_val
                cur_a = max(cur_a, cur_v)
                open_stack[nid][1] = cur_v
                open_stack[nid][2] = cur_a
                op_desc = (
                    f"MAX updates v = max({format_eval_score(prev_v)}, {format_eval_score(c_val)}) = {format_eval_score(cur_v)}; "
                    f"α = max(α, v) = {format_eval_score(cur_a)}, β = {format_eval_score(cur_b)}."
                )
            else:
                if c_val < cur_v:
                    cur_v = c_val
                cur_b = min(cur_b, cur_v)
                open_stack[nid][1] = cur_v
                open_stack[nid][3] = cur_b
                op_desc = (
                    f"MIN updates v = min({format_eval_score(prev_v)}, {format_eval_score(c_val)}) = {format_eval_score(cur_v)}; "
                    f"β = min(β, v) = {format_eval_score(cur_b)}, α = {format_eval_score(cur_a)}."
                )

            push_step(
                kind="BACKUP",
                active_node=node,
                active_path=path,
                backup_child=child,
                cur_a=cur_a,
                cur_b=cur_b,
                cur_v=cur_v,
                v_is_dash=False,
                headline=f"Back-up {format_path_label(c_path)} ({format_eval_score(c_val)}) → {lbl} ({node.role.value})",
                detail=op_desc,
            )

        if node.has_cutoff:
            pruned_lbls = ", ".join(f"C{c + 1}" for c in node.pruned_columns)
            if node.role is Role.MAX:
                cut_cond = f"v ({format_eval_score(cur_v)}) ≥ β ({format_eval_score(cur_b)})"
                cut_kind = "BETA CUTOFF !!"
                short_cut = "cutoff: v ≥ β"
            else:
                cut_cond = f"v ({format_eval_score(cur_v)}) ≤ α ({format_eval_score(cur_a)})"
                cut_kind = "ALPHA CUTOFF !!"
                short_cut = "cutoff: v ≤ α"
            c_step = push_step(
                kind="CUTOFF",
                active_node=node,
                active_path=path,
                backup_child=None,
                cur_a=cur_a,
                cur_b=cur_b,
                cur_v=cur_v,
                v_is_dash=False,
                headline=f"✂ {cut_kind} at {lbl} — Pruned [{pruned_lbls}]",
                detail=f"Condition {cut_cond} holds! Remaining branch(es) [{pruned_lbls}] cannot affect ancestor choice and are never explored.",
            )
            cutoff_step_by_node[nid] = c_step
            note_str = f"{short_cut} → prune [{pruned_lbls}]"
        else:
            best_c_str = f"Col {(node.best_column or 0) + 1}" if node.best_column is not None else "—"
            note_str = f"best → {best_c_str}"

        del open_stack[nid]
        final_val = node.value if node.value is not None else cur_v
        final_badge = f"{node.bound.symbol} {format_eval_score(final_val)}"
        final_badge_by_node[nid] = final_badge
        finish_step_by_node[nid] = len(steps)

        # Fill Sheet-6 trace row in exact pre-order slot
        new_a_val = cur_a if old_a is not None else None
        new_b_val = cur_b if old_b is not None else None
        trace_rows[row_slot] = Sheet6TraceRow(
            visit_id=my_visit,
            node_id=nid,
            node=node,
            path=path,
            node_label=lbl,
            node_type=node.role.value,
            depth=node.depth,
            old_alpha=format_eval_score(old_a),
            new_alpha=format_eval_score(new_a_val),
            old_beta=format_eval_score(old_b),
            new_beta=format_eval_score(new_b_val),
            old_value=format_eval_score(init_v),
            new_value=format_eval_score(final_val),
            note=note_str,
        )

        # Append bottom-up Minimax computation row (Sheet 6 Q1a / Q3f style!)
        op_fn = "max" if node.role is Role.MAX else "min"
        terms = [
            f"C{(ch.column or 0) + 1}:{ch.bound.symbol}{format_eval_score(ch.value)}"
            for ch in node.children
        ]
        if node.pruned_columns:
            terms.append("pruned:" + ",".join(f"C{c + 1}" for c in node.pruned_columns))
        comp_expr = f"{op_fn}({', '.join(terms)})"
        chosen_txt = f"Col {(node.best_column or 0) + 1} (c={node.best_column})" if node.best_column is not None else "—"
        computation_rows.append(
            MinimaxComputationRow(
                visit_id=my_visit,
                node_id=nid,
                node=node,
                path=path,
                node_label=lbl,
                role_str=node.role.value,
                depth=node.depth,
                computation=comp_expr,
                chosen_move=chosen_txt,
                backed_up_value=final_badge,
            )
        )

    dfs(root, ())

    if root.best_column is not None:
        push_step(
            kind="DONE",
            active_node=root,
            active_path=(),
            backup_child=root.best_child(),
            cur_a=max(root.alpha or float("-inf"), root.value or 0.0) if root.is_max else root.alpha,
            cur_b=root.beta if root.is_max else min(root.beta or float("inf"), root.value or 0.0),
            cur_v=root.value,
            v_is_dash=False,
            headline=f"Search Complete — Root chooses Col {root.best_column + 1} (value = {format_eval_score(root.value)})",
            detail=(
                f"Final backed-up minimax value at ROOT is {format_eval_score(root.value)}. "
                f"AI plays Column {root.best_column + 1} (0-based index {root.best_column})."
            ),
        )

    return TreeTraceBundle(
        trace_rows=trace_rows,
        computation_rows=computation_rows,
        steps=steps,
        visit_id_by_node=visit_id_by_node,
        finish_step_by_node=finish_step_by_node,
        cutoff_step_by_node=cutoff_step_by_node,
        path_by_node=path_by_node,
        final_badge_by_node=final_badge_by_node,
        node_by_id=node_by_id,
        steps_truncated=steps_truncated,
    )


def reconstruct_board_at_path(
    game: Game,
    state_before: GameState,
    path: tuple[int, ...],
    node: Optional[TreeNode] = None,
) -> Board:
    """Return the exact Connect 4 ``Board`` at ``path`` below ``state_before``."""
    if node is not None and isinstance(node.board, Board):
        return node.board
    cur = state_before
    for col in path:
        cur = game.result(cur, col)
    return cur.board


def render_detailed_console_report(
    result: SearchResult,
    heuristic_key: str,
    max_tree_lines: int = 180,
    max_table_rows: int = 60,
) -> str:
    """Render both a 4-decimal Minimax tree (with raw & normalized leaf evals)
    AND the Sheet-6 Alpha-Beta Visiting-Order Trace Table as readable text."""
    lines: list[str] = []
    st = result.stats
    lines.append(
        f"Search Summary: algorithm={result.algorithm} | K={result.k} | "
        f"best_col={result.best_column} (Col {(result.best_column or 0) + 1}) | "
        f"root_value={format_eval_score(result.value)}"
    )
    lines.append(
        f"  visited={st.visited} | expanded={st.expanded} | eval_leaves={st.evaluations} | "
        f"terminal_leaves={st.terminal_leaves} | cutoffs={st.cutoffs} | "
        f"pruned_branches={st.pruned_branches} | time={st.elapsed * 1000:.2f} ms"
    )
    lines.append("")

    if result.root is None:
        lines.append("(tree recording was disabled)")
        return "\n".join(lines)

    # 1. Readable Minimax Tree with 4-decimal + raw heuristic values on leaves
    lines.append("1) MINIMAX ALPHA-BETA TREE (△ = MAX, ▽ = MIN, * = best move, x = pruned):")
    stack: list[tuple[object, str, bool, bool, bool]] = [(result.root, "", True, True, False)]
    tree_line_count = 0
    while stack:
        item, prefix, is_last, is_root, is_best = stack.pop()
        conn = "" if is_root else ("└── " if is_last else "├── ")
        tree_line_count += 1
        if tree_line_count > max_tree_lines:
            lines.append(f"... ({st.visited} total visited nodes; use GUI or Export for full tree)")
            break
        if isinstance(item, str):
            lines.append(prefix + conn + item)
            continue

        assert isinstance(item, TreeNode)
        tri = "△ MAX" if item.is_max else "▽ MIN"
        star = "* " if is_best else ""
        where = "ROOT" if item.is_root else f"Col {(item.column or 0) + 1} (c={item.column})"
        if item.is_leaf:
            if item.leaf_kind is LeafKind.TERMINAL:
                desc = f"{star}{where} -> [TERMINAL exact utility = {format_eval_score(item.value)}]"
            else:
                raw_part = ""
                if isinstance(item.board, Board):
                    rep = evaluate_board_detailed(item.board, heuristic_key)
                    raw_part = f", raw={rep.raw_score:+.1f}"
                desc = f"{star}{where} -> [LEAF heuristic eval = {format_eval_score(item.value)}{raw_part}]"
        else:
            win = (
                f" (α={format_eval_score(item.alpha)}, β={format_eval_score(item.beta)})"
                if item.alpha is not None
                else ""
            )
            desc = f"{star}{where} [{tri} d={item.depth}] value{item.bound.symbol}{format_eval_score(item.value)}{win}"
        lines.append(prefix + conn + desc)

        child_prefix = prefix if is_root else prefix + ("    " if is_last else "│   ")
        entries: list[tuple[object, bool]] = [
            (ch, item.best_column is not None and ch.column == item.best_column)
            for ch in item.children
        ]
        if item.pruned_columns:
            p_cols = ", ".join(f"Col {c + 1}(c={c})" for c in item.pruned_columns)
            reason = "β-cutoff: v ≥ β" if item.is_max else "α-cutoff: v ≤ α"
            entries.append((f"x PRUNED [{p_cols}] ({reason})", False))
        for idx in range(len(entries) - 1, -1, -1):
            ent, ent_best = entries[idx]
            stack.append((ent, child_prefix, idx == len(entries) - 1, False, ent_best))

    # 2. Sheet-6 Alpha-Beta Trace Table
    bundle = build_tree_trace(result.root)
    lines.append("")
    lines.append("2) SHEET-6 ALPHA-BETA TRACE TABLE (Visiting Order):")
    hdr = (
        f"{'#':>4} | {'Node':<14} | {'Type':<4} | {'old α':>9} | {'new α':>9} | "
        f"{'old β':>9} | {'new β':>9} | {'old v':>9} | {'new v':>9} | Note"
    )
    lines.append(hdr)
    lines.append("-" * len(hdr))
    for row in bundle.trace_rows[:max_table_rows]:
        lines.append(
            f"{row.visit_id:>4} | {row.node_label:<14.14} | {row.node_type:<4} | "
            f"{row.old_alpha:>9} | {row.new_alpha:>9} | {row.old_beta:>9} | "
            f"{row.new_beta:>9} | {row.old_value:>9} | {row.new_value:>9} | {row.note}"
        )
    if len(bundle.trace_rows) > max_table_rows:
        lines.append(f"... ({len(bundle.trace_rows) - max_table_rows} more visited rows in GUI Sheet-6 Trace Table)")

    return "\n".join(lines)
