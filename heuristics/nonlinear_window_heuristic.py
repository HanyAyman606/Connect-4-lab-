"""Nonlinear, gravity-aware evaluator based on potential four-cell windows."""

from __future__ import annotations

import math
from dataclasses import dataclass

from core.board import Board
from core.owner import Owner
from core.rules import build_windows
from heuristics.heuristic_common import _normalize
from heuristics.window_heuristic import Heuristic


@dataclass(frozen=True, slots=True)
class NonlinearWindowBreakdown:
    """Weighted potential and completed scoring windows for each player."""

    computer_fours: int
    human_fours: int
    computer_window_potential: float
    human_window_potential: float
    computer_center_discs: int
    human_center_discs: int
    raw_score: float
    value: float


class NonlinearWindowHeuristic:
    """Value uncontested windows with exponentially increasing potential.

    Each window's value grows as ``growth ** number_of_discs``. Empty cells
    that need support drops reduce that value by ``support_discount`` per
    distinct support cell. This is a standalone evaluator: it scores window
    occupancy and gravity accessibility, without counting legal scoring moves.
    """

    def __init__(self, growth: float = 2.2, support_discount: float = 0.65,
                 center_control: float = 2.0, normalization_scale: float = 300.0,
                 connect_length: int = 4) -> None:
        if connect_length != 4:
            raise ValueError("this heuristic currently supports connect_length=4")
        if not math.isfinite(growth) or growth <= 1:
            raise ValueError("growth must be finite and greater than 1")
        if not math.isfinite(support_discount) or not 0 < support_discount <= 1:
            raise ValueError("support_discount must be in (0, 1]")
        if not math.isfinite(center_control) or center_control < 0:
            raise ValueError("center_control must be finite and non-negative")
        if not math.isfinite(normalization_scale) or normalization_scale <= 0:
            raise ValueError("normalization_scale must be finite and positive")
        self.growth = growth
        self.support_discount = support_discount
        self.center_control = center_control
        self.normalization_scale = normalization_scale
        self.connect_length = connect_length

    def __call__(self, board: Board) -> float:
        return self.breakdown(board).value

    def breakdown(self, board: Board) -> NonlinearWindowBreakdown:
        computer_fours = human_fours = 0
        computer_potential = human_potential = 0.0

        for window in build_windows(board.rows, board.cols, self.connect_length):
            computer_cells = [(row, col) for row, col in window
                              if board.cell(row, col).owner is Owner.COMPUTER]
            human_cells = [(row, col) for row, col in window
                           if board.cell(row, col).owner is Owner.HUMAN]
            if computer_cells and human_cells:
                continue
            own_cells = computer_cells or human_cells
            if not own_cells:
                continue

            support_count = self._support_moves(board, window)
            potential = (self.growth ** len(own_cells)
                         * self.support_discount ** support_count)
            if computer_cells:
                computer_potential += potential
                if len(computer_cells) == self.connect_length:
                    computer_fours += 1
            else:
                human_potential += potential
                if len(human_cells) == self.connect_length:
                    human_fours += 1

        computer_center, human_center = Heuristic._center_counts(board)
        raw_score = (
            computer_potential - human_potential
            + self.center_control * (computer_center - human_center)
        )
        return NonlinearWindowBreakdown(
            computer_fours=computer_fours,
            human_fours=human_fours,
            computer_window_potential=computer_potential,
            human_window_potential=human_potential,
            computer_center_discs=computer_center,
            human_center_discs=human_center,
            raw_score=raw_score,
            value=_normalize(raw_score, self.normalization_scale),
        )

    @staticmethod
    def _support_moves(board: Board, window: tuple[tuple[int, int], ...]) -> int:
        targets = {
            (row, col) for row, col in window
            if board.cell(row, col).owner is Owner.EMPTY
        }
        supports = set()
        for row, col in targets:
            for lower_row in range(row + 1, board.rows):
                position = (lower_row, col)
                if position not in targets and board.cell(*position).owner is Owner.EMPTY:
                    supports.add(position)
        return len(supports)
