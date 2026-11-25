"""Background QThread search worker and SearchResult analytics helpers.

Runs AlphaBetaSearcher off the GUI thread so animations and UI interaction stay
at 60 FPS even at deeper K, and derives rich tree inspection metrics directly
from ``SearchResult`` and ``heuristics.evaluation`` without modifying core
algorithm modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from PySide6.QtCore import QThread, Signal

from algorithms.alpha_beta import AlphaBetaSearcher
from core.board import Board
from core.game import Game, GameState
from core.owner import Owner
from core.rules import build_windows
from heuristics.evaluation import (
    DEFAULT_HEURISTIC,
    GRAVITY_AWARE_HEURISTIC,
    HEURISTIC_MODELS,
    SCORING_OPPORTUNITY_HEURISTIC,
    explain_evaluation,
    explain_gravity_aware,
    explain_scoring_opportunities,
)
from setup.player_factory import ORDERING_MODELS
from setup.session_settings import SessionSettings
from tree_essentials import LeafKind, Role, SearchResult, TreeNode


def format_eval_score(value: Optional[float]) -> str:
    """Format exact integer terminal scores as +d and normalized floats to 4 decimals."""
    if value is None:
        return "N/A"
    if value == float("inf"):
        return "+∞"
    if value == float("-inf"):
        return "−∞"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        iv = int(value)
        return "0" if iv == 0 else f"{iv:+d}"
    return f"{value:+.4f}"


@dataclass(frozen=True, slots=True)
class RootMoveSummary:
    """Summary of one column at the root for the under-board ordering strip."""

    column: int
    order_rank: Optional[int]  # 1-based exploration order, None if illegal/pruned
    value: Optional[float]
    bound_symbol: str
    is_best: bool
    is_pruned: bool
    is_legal: bool


@dataclass(frozen=True, slots=True)
class DerivedTreeMetrics:
    """Detailed α-β and ordering statistics extracted from a recorded tree."""

    alpha_cutoffs: int
    beta_cutoffs: int
    first_child_cutoffs: int
    ordering_quality_pct: float
    stored_nodes: int
    effective_branching: float
    unpruned_bound: int
    pruned_saved_pct: float
    root_moves: tuple[RootMoveSummary, ...]


def compute_tree_metrics(
    result: SearchResult,
    legal_columns: tuple[int, ...],
    cols: int = 7,
) -> DerivedTreeMetrics:
    """Extract cutoff splits, ordering quality, and root column values from SearchResult."""
    alpha_cutoffs = 0
    beta_cutoffs = 0
    first_child_cutoffs = 0
    stored_nodes = 0

    if result.root is not None:
        for node in result.root.iter_nodes():
            stored_nodes += 1
            if node.has_cutoff:
                # At MAX, value >= beta causes a beta-cutoff; at MIN, value <= alpha causes an alpha-cutoff
                if node.role is Role.MAX:
                    beta_cutoffs += 1
                else:
                    alpha_cutoffs += 1
                if len(node.children) == 1:
                    first_child_cutoffs += 1

    total_cutoffs = result.stats.cutoffs
    ordering_quality = (
        100.0 * first_child_cutoffs / total_cutoffs if total_cutoffs > 0 else 0.0
    )

    k = max(1, result.k)
    visited = max(1, result.stats.visited)
    eff_b = visited ** (1.0 / k)

    unpruned = sum(cols ** d for d in range(k + 1))
    saved_pct = max(0.0, 100.0 * (1.0 - visited / max(1, unpruned)))

    # Build 7-column root summary strip
    legal_set = set(legal_columns)
    child_by_col: dict[int, tuple[int, TreeNode]] = {}
    pruned_set: set[int] = set()
    if result.root is not None:
        for idx, child in enumerate(result.root.children, start=1):
            if child.column is not None:
                child_by_col[child.column] = (idx, child)
        pruned_set = set(result.root.pruned_columns)

    summaries: list[RootMoveSummary] = []
    for c in range(cols):
        if c not in legal_set:
            summaries.append(
                RootMoveSummary(c, None, None, "", False, False, False)
            )
        elif c in child_by_col:
            rank, ch = child_by_col[c]
            summaries.append(
                RootMoveSummary(
                    column=c,
                    order_rank=rank,
                    value=ch.value,
                    bound_symbol=ch.bound.symbol,
                    is_best=(c == result.best_column),
                    is_pruned=False,
                    is_legal=True,
                )
            )
        elif c in pruned_set:
            summaries.append(
                RootMoveSummary(c, None, None, "", False, True, True)
            )
        else:
            summaries.append(
                RootMoveSummary(
                    column=c,
                    order_rank=None,
                    value=result.value if c == result.best_column else None,
                    bound_symbol="=",
                    is_best=(c == result.best_column),
                    is_pruned=False,
                    is_legal=True,
                )
            )

    return DerivedTreeMetrics(
        alpha_cutoffs=alpha_cutoffs,
        beta_cutoffs=beta_cutoffs,
        first_child_cutoffs=first_child_cutoffs,
        ordering_quality_pct=ordering_quality,
        stored_nodes=stored_nodes,
        effective_branching=eff_b,
        unpruned_bound=unpruned,
        pruned_saved_pct=saved_pct,
        root_moves=tuple(summaries),
    )


@dataclass(frozen=True, slots=True)
class FeatureRow:
    """Unified row representation for displaying any of the 3 heuristic breakdowns."""

    label: str
    comp_val: str
    human_val: str
    diff_val: str
    weight_str: str
    contribution: float


@dataclass(frozen=True, slots=True)
class UnifiedEvalReport:
    """Unified board evaluation report across active heuristic + all 3 Devils."""

    heuristic_key: str
    raw_score: float
    normalized_value: float
    rows: tuple[FeatureRow, ...]
    all_three_scores: dict[str, tuple[float, float]]  # key -> (normalized, raw)


def evaluate_board_detailed(board: Board, heuristic_key: str) -> UnifiedEvalReport:
    """Compute full feature table for ``heuristic_key`` plus side-by-side scores of all 3 Devils."""
    b_win = explain_evaluation(board)
    b_grav = explain_gravity_aware(board)
    b_opp = explain_scoring_opportunities(board)

    all_three = {
        "opportunities": (b_opp.value, b_opp.raw_score),
        "gravity": (b_grav.value, b_grav.raw_score),
        "windows": (b_win.value, b_win.raw_score),
    }

    rows: list[FeatureRow] = []
    if heuristic_key == "opportunities":
        wo = SCORING_OPPORTUNITY_HEURISTIC.weights
        specs = [
            ("Completed Fours", b_opp.computer_fours, b_opp.human_fours, wo.fours, False),
            ("Scoring Columns", b_opp.computer_scoring_moves, b_opp.human_scoring_moves, wo.scoring_moves, False),
            ("Best Single Gain", b_opp.computer_best_four_gain, b_opp.human_best_four_gain, wo.best_four_gain, False),
            ("Total Move Gain", b_opp.computer_total_four_gain, b_opp.human_total_four_gain, wo.total_four_gain, False),
            ("Center Control", b_opp.computer_center_discs, b_opp.human_center_discs, wo.center_control, False),
        ]
        raw = b_opp.raw_score
        val = b_opp.value
    elif heuristic_key == "gravity":
        wg = GRAVITY_AWARE_HEURISTIC.weights
        specs = [
            ("Completed Fours", b_grav.computer_fours, b_grav.human_fours, wg.fours, False),
            ("Gravity Open 3s", b_grav.computer_open_threes, b_grav.human_open_threes, wg.open_threes, True),
            ("Gravity Open 2s", b_grav.computer_open_twos, b_grav.human_open_twos, wg.open_twos, True),
            ("Center Control", b_grav.computer_center_discs, b_grav.human_center_discs, wg.center_control, False),
        ]
        raw = b_grav.raw_score
        val = b_grav.value
    else:
        ww = DEFAULT_HEURISTIC.weights
        specs = [
            ("Completed Fours", b_win.computer_fours, b_win.human_fours, ww.fours, False),
            ("Open Threes", b_win.computer_open_threes, b_win.human_open_threes, ww.open_threes, False),
            ("Open Twos", b_win.computer_open_twos, b_win.human_open_twos, ww.open_twos, False),
            ("Center Control", b_win.computer_center_discs, b_win.human_center_discs, ww.center_control, False),
        ]
        raw = b_win.raw_score
        val = b_win.value

    for name, c_v, h_v, w_num, is_float in specs:
        diff = c_v - h_v
        contrib = w_num * diff
        if is_float:
            rows.append(
                FeatureRow(
                    name,
                    f"{c_v:.2f}",
                    f"{h_v:.2f}",
                    f"{diff:+.2f}",
                    f"{w_num:.1f}",
                    contrib,
                )
            )
        else:
            rows.append(
                FeatureRow(
                    name,
                    str(int(c_v)),
                    str(int(h_v)),
                    f"{int(diff):+d}",
                    f"{w_num:.1f}",
                    contrib,
                )
            )

    return UnifiedEvalReport(
        heuristic_key=heuristic_key,
        raw_score=raw,
        normalized_value=val,
        rows=tuple(rows),
        all_three_scores=all_three,
    )


def find_completed_four_windows(
    board: Board,
    connect_length: int = 4,
) -> tuple[list[tuple[tuple[int, int], ...]], list[tuple[tuple[int, int], ...]]]:
    """Return lists of completed 4-cell windows for (human_windows, computer_windows)."""
    human_wins: list[tuple[tuple[int, int], ...]] = []
    comp_wins: list[tuple[tuple[int, int], ...]] = []
    grid = board.grid
    for win in build_windows(board.rows, board.cols, connect_length):
        first_owner = grid[win[0][0]][win[0][1]].owner
        if first_owner is Owner.EMPTY:
            continue
        if all(grid[r][c].owner is first_owner for r, c in win):
            if first_owner is Owner.HUMAN:
                human_wins.append(win)
            elif first_owner is Owner.COMPUTER:
                comp_wins.append(win)
    return human_wins, comp_wins


def find_candidate_cells(
    board: Board,
    connect_length: int = 4,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Find empty cells completing an open-3 window for (human_targets, computer_targets)."""
    human_targets: set[tuple[int, int]] = set()
    comp_targets: set[tuple[int, int]] = set()
    grid = board.grid
    for win in build_windows(board.rows, board.cols, connect_length):
        comp_n = sum(grid[r][c].owner is Owner.COMPUTER for r, c in win)
        hum_n = sum(grid[r][c].owner is Owner.HUMAN for r, c in win)
        if comp_n == 3 and hum_n == 0:
            for r, c in win:
                if grid[r][c].owner is Owner.EMPTY:
                    comp_targets.add((r, c))
        elif hum_n == 3 and comp_n == 0:
            for r, c in win:
                if grid[r][c].owner is Owner.EMPTY:
                    human_targets.add((r, c))
    return human_targets, comp_targets


class AISearchWorker(QThread):
    """Worker thread executing AlphaBetaSearcher without blocking the Qt UI loop."""

    search_completed = Signal(int, object)  # (best_column, SearchResult)
    search_failed = Signal(str)

    def __init__(
        self,
        game: Game,
        state: GameState,
        settings: SessionSettings,
        max_record_nodes: int = 35000,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self._game = game
        self._state = state
        self._settings = settings
        self._max_record_nodes = max_record_nodes

    def run(self) -> None:
        try:
            evaluator = HEURISTIC_MODELS[self._settings.heuristic_key]
            orderer = ORDERING_MODELS[self._settings.ordering_key]
            searcher = AlphaBetaSearcher(evaluator=evaluator, move_orderer=orderer)
            result = searcher.search(
                self._game,
                self._state,
                self._settings.k,
                record=True,
                max_record_nodes=self._max_record_nodes,
            )
            if result.best_column is None:
                self.search_failed.emit("Alpha-beta returned no legal move.")
                return
            self.search_completed.emit(result.best_column, result)
        except Exception as exc:  # pragma: no cover - safety net for worker thread
            self.search_failed.emit(str(exc))
