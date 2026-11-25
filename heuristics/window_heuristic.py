from __future__ import annotations
import math
from dataclasses import dataclass
from core.board import Board
from core.owner import Owner
from core.rules import build_windows
from heuristics.heuristic_common import _normalize

#Weights for the board features,all measured computer minus human.
@dataclass(frozen=True, slots=True)
class HeuristicWeights:

    fours: float = 100.0                    #value for each completed four-cell window
    open_threes: float = 10.0               #value for each window with three of one player’s discs and one empty cell
    open_twos: float = 3.0                  #value for each window with two of one player’s discs and two empty cells
    center_control: float = 2.0             #value for each disc in a center column
    normalization_scale: float = 1000.0     #controls the final score’s scale

    #checks that feature weights are finite and nonnegative, and that the normalization scale is positive
    def __post_init__(self) -> None:
        feature_weights = (self.fours, self.open_threes,
                           self.open_twos, self.center_control)
        if any(not math.isfinite(weight) or weight < 0 for weight in feature_weights):
            raise ValueError("feature weights must be finite and non-negative")
        if not math.isfinite(self.normalization_scale) or self.normalization_scale <= 0:
            raise ValueError("normalization_scale must be finite and positive")

#Feature counts and scores for one evaluated board.
#How many completed fours, open threes, open twos, and center discs each player has
@dataclass(frozen=True, slots=True)
class HeuristicBreakdown:

    computer_fours: int
    human_fours: int
    computer_open_threes: int
    human_open_threes: int
    computer_open_twos: int
    human_open_twos: int
    computer_center_discs: int
    human_center_discs: int
    raw_score: float          #the weighted computer score minus the weighted human score
    value: float              #the normalized score returned to the search


class Heuristic:
    def __init__(self, weights: HeuristicWeights = HeuristicWeights(), connect_length: int = 4) -> None:
        if connect_length != 4:
            raise ValueError("this heuristic currently supports connect_length=4")
        self.weights = weights
        self.connect_length = connect_length

    #lets a Heuristic instance be passed directly to AlphaBetaSearcher as an evaluator
    #Calling it is equivalent to asking for the full breakdown and returning just the final value.
    def __call__(self, board: Board) -> float:
        return self.breakdown(board).value

    #Count features and return both raw and normalized scores.
    def breakdown(self, board: Board) -> HeuristicBreakdown:
        comp_fours = human_fours = 0
        comp_threes = human_threes = 0
        comp_twos = human_twos = 0
        grid = board.grid

        #ask build_windows for every possible group of four neighboring cells on the board.
        #That includes horizontal, vertical, and diagonal windows.
        for window in build_windows(board.rows, board.cols, self.connect_length):

            #For each window, it counts computer-owned discs and human-owned discs
            comp_count = sum(grid[row][col].owner is Owner.COMPUTER for row, col in window)
            human_count = sum(grid[row][col].owner is Owner.HUMAN for row, col in window)
            empty_count = self.connect_length - comp_count - human_count

            # Mixed-color windows cannot become a four for either player.
            #If both players have discs in the window, it is blocked and skipped.
            if comp_count and human_count:
                continue

            #If all four cells belong to one player, it counts as a completed four.
            if comp_count == self.connect_length:
                comp_fours += 1

            #If one player has three discs and one cell is empty, it counts as an open three.
            elif comp_count == 3 and empty_count == 1:
                comp_threes += 1

            #If one player has two discs and two cells are empty, it counts as an open two.
            elif comp_count == 2 and empty_count == 2:
                comp_twos += 1

            #If all four cells belong to one player, it counts as a completed four.
            if human_count == self.connect_length:
                human_fours += 1

            #If one player has three discs and one cell is empty, it counts as an open three.
            elif human_count == 3 and empty_count == 1:
                human_threes += 1

            #If one player has two discs and two cells are empty, it counts as an open two.
            elif human_count == 2 and empty_count == 2:
                human_twos += 1

        #count central disks for each player
        comp_center, human_center = self._center_counts(board)

        #get the assigned weights to each board feature
        weights = self.weights

        #multiply each feature count by its weight,separately for each player,
        #then subtracts the human’s total from the computer’s
        #So a positive raw score favors the computer, and a negative score favors the human.
        raw_score = (
            weights.fours * (comp_fours - human_fours)
            + weights.open_threes * (comp_threes - human_threes)
            + weights.open_twos * (comp_twos - human_twos)
            + weights.center_control * (comp_center - human_center)
        )

        # This monotonic transform preserves feature ordering and bounds every
        # non-terminal estimate strictly between -1 and +1.

        value = _normalize(raw_score, self.weights.normalization_scale)

        return HeuristicBreakdown(
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

    #counts each player’s discs in the middle column.On a board with an even number of columns,
    #it counts the two middle columns. This gives a small preference to central positions,
    #which can participate in more possible windows.
    @staticmethod
    def _center_counts(board: Board) -> tuple[int, int]:

        left_center = (board.cols - 1) // 2
        right_center = board.cols // 2
        center_columns = {left_center, right_center}
        computer = human = 0
        for row in range(board.rows):
            for col in center_columns:
                owner = board.cell(row, col).owner
                if owner is Owner.COMPUTER:
                    computer += 1
                elif owner is Owner.HUMAN:
                    human += 1
        return computer, human
