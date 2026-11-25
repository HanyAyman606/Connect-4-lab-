"""Gravity-aware heuristic evaluator."""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.board import Board
from core.owner import Owner
from core.rules import build_windows

from heuristics.heuristic_common import _normalize
from heuristics.window_heuristic import Heuristic, HeuristicWeights


@dataclass(frozen=True, slots=True)
class GravityHeuristicBreakdown:
    """Counts and accessibility-weighted candidate windows."""

    computer_fours: int
    human_fours: int
    computer_open_threes: float
    human_open_threes: float
    computer_open_twos: float
    human_open_twos: float
    computer_center_discs: int
    human_center_discs: int
    raw_score: float
    value: float


class GravityAwareHeuristic(Heuristic):
    """Discount candidate windows whose empty cells need support moves.

    An empty target cell is immediately playable when every cell below it is
    occupied. Empty cells below a target are support moves that must happen
    first. Candidate windows are discounted by ``support_discount`` for each
    distinct support cell required.
    """

    def __init__(self, weights: HeuristicWeights = HeuristicWeights(),
                 connect_length: int = 4, support_discount: float = 0.5) -> None:
        super().__init__(weights, connect_length)
        if not math.isfinite(support_discount) or not 0 < support_discount <= 1:
            raise ValueError("support_discount must be in (0, 1]")
        self.support_discount = support_discount

    def breakdown(self, board: Board) -> GravityHeuristicBreakdown:
        comp_fours = human_fours = 0
        comp_threes = human_threes = 0.0
        comp_twos = human_twos = 0.0
        grid = board.grid

        for window in build_windows(board.rows, board.cols, self.connect_length):
            comp_count = sum(grid[row][col].owner is Owner.COMPUTER
                             for row, col in window)
            human_count = sum(grid[row][col].owner is Owner.HUMAN
                              for row, col in window)
            empty_count = self.connect_length - comp_count - human_count
            if comp_count and human_count:
                continue

            if comp_count == self.connect_length:
                comp_fours += 1
            elif comp_count == 3 and empty_count == 1:
                support = self._support_moves(board, window)
                comp_threes += self.support_discount ** support
            elif comp_count == 2 and empty_count == 2:
                support = self._support_moves(board, window)
                comp_twos += self.support_discount ** support

            if human_count == self.connect_length:
                human_fours += 1
            elif human_count == 3 and empty_count == 1:
                support = self._support_moves(board, window)
                human_threes += self.support_discount ** support
            elif human_count == 2 and empty_count == 2:
                support = self._support_moves(board, window)
                human_twos += self.support_discount ** support

        comp_center, human_center = self._center_counts(board)
        weights = self.weights
        raw_score = (
            weights.fours * (comp_fours - human_fours)
            + weights.open_threes * (comp_threes - human_threes)
            + weights.open_twos * (comp_twos - human_twos)
            + weights.center_control * (comp_center - human_center)
        )
        value = _normalize(raw_score, weights.normalization_scale)
        return GravityHeuristicBreakdown(
            computer_fours=comp_fours,
            human_fours=human_fours,
            computer_open_threes=comp_threes,
            human_open_threes=human_threes,
            computer_open_twos=comp_twos,
            human_open_twos=human_twos,
            computer_center_discs=comp_center,
            human_center_discs=human_center,
            raw_score=raw_score,
            value=value,
        )

    @staticmethod
    def _support_moves(board: Board, window: tuple) -> int:
        """Count distinct empty cells below window targets in their columns."""
        targets = {
            (row, col) for row, col in window
            if board.cell(row, col).owner is Owner.EMPTY
        }
        supports = set()
        for row, col in targets:
            for lower_row in range(row + 1, board.rows):
                position = (lower_row, col)
                if (position not in targets
                        and board.cell(*position).owner is Owner.EMPTY):
                    supports.add(position)
        return len(supports)
