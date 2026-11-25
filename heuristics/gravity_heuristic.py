from __future__ import annotations

import math
from dataclasses import dataclass

from core.board import Board
from core.owner import Owner
from core.rules import build_windows

from heuristics.heuristic_common import _normalize
from heuristics.window_heuristic import Heuristic, HeuristicWeights


#store the details behind one evaluation.It does not calculate the score itself.
@dataclass(frozen=True, slots=True)
class GravityHeuristicBreakdown:

    computer_fours: int
    human_fours: int
    computer_open_threes: float       #These can be fractions because the gravity discount reduces their value.
    human_open_threes: float          #These can be fractions because the gravity discount reduces their value.
    computer_open_twos: float         #These can be fractions because the gravity discount reduces their value.
    human_open_twos: float            #These can be fractions because the gravity discount reduces their value.
    computer_center_discs: int
    human_center_discs: int
    raw_score: float
    value: float


#Its main addition is that it considers whether empty cells in a promising line can actually be reached under gravity.
class GravityAwareHeuristic(Heuristic):
    def __init__(self, weights: HeuristicWeights = HeuristicWeights(), connect_length: int = 4,
                 support_discount: float = 0.5) -> None:

        #calls the parent constructor, which stores the weights and validates the connect length.
        super().__init__(weights, connect_length)

        #rejects invalid discounts. The value must be finite, greater than 0, and at most 1.
        if not math.isfinite(support_discount) or not 0 < support_discount <= 1:
            raise ValueError("support_discount must be in (0, 1]")

        #control how much credit to remove for each required support move
        self.support_discount = support_discount

    #examines the board and returns all the feature counts and the final score.
    def breakdown(self, board: Board) -> GravityHeuristicBreakdown:

        #Completed fours are whole numbers.
        comp_fours = human_fours = 0

        #open-three and open-two totals are floats because discounted features can contribute partial credit.
        comp_threes = human_threes = 0.0
        comp_twos = human_twos = 0.0

        grid = board.grid

        #Examine every four-cell window
        for window in build_windows(board.rows, board.cols, self.connect_length):

            #For each one,count each player’s discs:
            comp_count = sum(grid[row][col].owner is Owner.COMPUTER for row, col in window)
            human_count = sum(grid[row][col].owner is Owner.HUMAN for row, col in window)
            empty_count = self.connect_length - comp_count - human_count

            #If both players have discs in the same window, neither player can complete that window into four of their own discs
            if comp_count and human_count:
                continue

            #If all four cells belong to the computer, it adds one completed four.
            if comp_count == self.connect_length:
                comp_fours += 1

            elif comp_count == 3 and empty_count == 1:

                #evaluator first asks how many support moves are needed to reach the empty target cell
                support = self._support_moves(board, window)

                #It then adds a discounted amount to the computer’s open-three total.
                comp_threes += self.support_discount ** support
            elif comp_count == 2 and empty_count == 2:

                #evaluator first asks how many support moves are needed to reach the empty target cells
                support = self._support_moves(board, window)

                #It then adds a discounted amount to the computer’s open-three total.
                comp_twos += self.support_discount ** support

            if human_count == self.connect_length:
                human_fours += 1
            elif human_count == 3 and empty_count == 1:
                support = self._support_moves(board, window)
                human_threes += self.support_discount ** support
            elif human_count == 2 and empty_count == 2:
                support = self._support_moves(board, window)
                human_twos += self.support_discount ** support

        #count discs in the center column
        comp_center, human_center = self._center_counts(board)
        weights = self.weights

        #Each feature is weighted, and the human’s total is subtracted from the computer’s
        raw_score = (
            weights.fours * (comp_fours - human_fours)
            + weights.open_threes * (comp_threes - human_threes)
            + weights.open_twos * (comp_twos - human_twos)
            + weights.center_control * (comp_center - human_center)
        )

        #A positive value favors the computer; a negative value favors the human.
        value = _normalize(raw_score, weights.normalization_scale)

        #returns a GravityHeuristicBreakdown containing the counts, raw score, and normalized value.
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

    #counts the distinct empty cells that need to be filled before the empty target cells in a window become playable.
    @staticmethod
    def _support_moves(board: Board, window: tuple) -> int:

        #it collects the empty cells that are part of the window
        targets = {
            (row, col) for row, col in window
            if board.cell(row, col).owner is Owner.EMPTY
        }

        #prevents the same support cell from being counted more than once.
        supports = set()

        for row, col in targets:

            #for each target, it looks at the cells below it in the same column
            #Empty cells below the target are support cells: a disc must land in those spaces before a disc can reach the target
            for lower_row in range(row + 1, board.rows):
                position = (lower_row, col)

                #avoids counting an empty cell twice when it is both part of the window and below another target cell.
                if position not in targets and board.cell(*position).owner is Owner.EMPTY:
                    supports.add(position)

        #count is used by breakdown to calculate the gravity discount
        return len(supports)
