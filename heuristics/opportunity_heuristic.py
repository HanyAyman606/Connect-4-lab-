"""Evaluator that values legal moves which immediately create scoring fours."""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.board import Board
from core.owner import Owner
from core.rules import build_windows
from heuristics.heuristic_common import _count_owner_fours, _index_windows, _normalize
from heuristics.window_heuristic import Heuristic


@dataclass(frozen=True, slots=True)
class OpportunityHeuristicWeights:
    """Weights for current score and legal four-making options."""

    fours: float = 100.0
    scoring_moves: float = 20.0
    best_four_gain: float = 15.0
    total_four_gain: float = 5.0
    center_control: float = 2.0
    normalization_scale: float = 1000.0

    def __post_init__(self) -> None:
        values = (self.fours, self.scoring_moves, self.best_four_gain,
                  self.total_four_gain, self.center_control)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("feature weights must be finite and non-negative")
        if not math.isfinite(self.normalization_scale) or self.normalization_scale <= 0:
            raise ValueError("normalization_scale must be finite and positive")


@dataclass(frozen=True, slots=True)
class OpportunityHeuristicBreakdown:
    """Current fours and one-move scoring opportunities for both players."""

    computer_fours: int
    human_fours: int
    computer_scoring_moves: int
    human_scoring_moves: int
    computer_best_four_gain: int
    human_best_four_gain: int
    computer_total_four_gain: int
    human_total_four_gain: int
    computer_center_discs: int
    human_center_discs: int
    raw_score: float
    value: float


class ScoringOpportunityHeuristic:
    """Score completed fours and legal drops that immediately create fours.

    For each playable column, inspect only windows containing the landing
    cell. The evaluator rewards the number of scoring columns, the largest
    gain available in one column, and the total gain across legal columns.
    """

    def __init__(self, weights: OpportunityHeuristicWeights = OpportunityHeuristicWeights(),
                 connect_length: int = 4) -> None:
        if connect_length != 4:
            raise ValueError("this heuristic currently supports connect_length=4")
        self.weights = weights
        self.connect_length = connect_length
        self._windows_cache: dict[tuple[int, int], tuple] = {}
        self._window_index_cache: dict[tuple[int, int], dict] = {}

    def __call__(self, board: Board) -> float:
        return self.breakdown(board).value

    def breakdown(self, board: Board) -> OpportunityHeuristicBreakdown:
        cache_key = (board.rows, board.cols)
        windows = self._windows_cache.get(cache_key)
        if windows is None:
            windows = build_windows(board.rows, board.cols, self.connect_length)
            self._windows_cache[cache_key] = windows
        window_index = self._window_index_cache.get(cache_key)
        if window_index is None:
            window_index = _index_windows(windows)
            self._window_index_cache[cache_key] = window_index

        comp_fours = _count_owner_fours(board, Owner.COMPUTER, windows)
        human_fours = _count_owner_fours(board, Owner.HUMAN, windows)
        comp_moves, comp_best, comp_total = self._scoring_opportunities(
            board, Owner.COMPUTER, window_index,
        )
        human_moves, human_best, human_total = self._scoring_opportunities(
            board, Owner.HUMAN, window_index,
        )
        comp_center, human_center = Heuristic._center_counts(board)
        weights = self.weights
        raw_score = (
            weights.fours * (comp_fours - human_fours)
            + weights.scoring_moves * (comp_moves - human_moves)
            + weights.best_four_gain * (comp_best - human_best)
            + weights.total_four_gain * (comp_total - human_total)
            + weights.center_control * (comp_center - human_center)
        )
        return OpportunityHeuristicBreakdown(
            computer_fours=comp_fours,
            human_fours=human_fours,
            computer_scoring_moves=comp_moves,
            human_scoring_moves=human_moves,
            computer_best_four_gain=comp_best,
            human_best_four_gain=human_best,
            computer_total_four_gain=comp_total,
            human_total_four_gain=human_total,
            computer_center_discs=comp_center,
            human_center_discs=human_center,
            raw_score=raw_score,
            value=_normalize(raw_score, weights.normalization_scale),
        )

    @staticmethod
    def _scoring_opportunities(board: Board, owner: Owner,
                               window_index: dict) -> tuple[int, int, int]:
        gains = []
        for column in board.valid_moves():
            landing = (board.lowest_empty_row(column), column)
            gain = sum(
                all(board.cell(row, col).owner is owner
                    for row, col in window if (row, col) != landing)
                for window in window_index.get(landing, ())
            )
            if gain > 0:
                gains.append(gain)
        return len(gains), max(gains, default=0), sum(gains)
