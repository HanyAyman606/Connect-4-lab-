from __future__ import annotations

import math
from dataclasses import dataclass

from core.board import Board
from core.owner import Owner
from core.rules import build_windows
from heuristics.heuristic_common import _count_owner_fours, _index_windows, _normalize
from heuristics.window_heuristic import Heuristic


#how much each feature contributes to the score
@dataclass(frozen=True, slots=True)
class OpportunityHeuristicWeights:

    fours: float = 100.0                #Completed four-cell lines already on the board.
    scoring_moves: float = 20.0         #number of legal columns where the player could immediately make one or more fours.
    best_four_gain: float = 15.0        #the largest number of fours the player could create with one drop.
    total_four_gain: float = 5.0        #the sum of possible fours across all scoring columns.
    center_control: float = 2.0         #discs in the center column or columns.
    normalization_scale: float = 1000.0 #controls how strongly the raw score is compressed into (-1, 1).

    #checks that feature weights are finite and nonnegative, and that the normalization scale is positive.
    def __post_init__(self) -> None:
        values = (self.fours, self.scoring_moves, self.best_four_gain,
                  self.total_four_gain, self.center_control)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("feature weights must be finite and non-negative")
        if not math.isfinite(self.normalization_scale) or self.normalization_scale <= 0:
            raise ValueError("normalization_scale must be finite and positive")

#holds the details of one evaluation
@dataclass(frozen=True, slots=True)
class OpportunityHeuristicBreakdown:

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

    #checks that connect_length is 4, saves the weights, and prepares two caches:
    def __init__(self, weights: OpportunityHeuristicWeights = OpportunityHeuristicWeights(),connect_length: int = 4) -> None:
        if connect_length != 4:
            raise ValueError("this heuristic currently supports connect_length=4")
        self.weights = weights
        self.connect_length = connect_length

        #store board windows and the cell-to-window index by board dimensions.
        #They avoid rebuilding the same data for every evaluation during a search.
        self._windows_cache: dict[tuple[int, int], tuple] = {}
        self._window_index_cache: dict[tuple[int, int], dict] = {}

    #lets the evaluator be called like a function
    def __call__(self, board: Board) -> float:
        return self.breakdown(board).value

    def breakdown(self, board: Board) -> OpportunityHeuristicBreakdown:

        #The board dimensions identify which cached window set to use.
        cache_key = (board.rows, board.cols)
        windows = self._windows_cache.get(cache_key)

        #If these dimensions have not been seen before, the method builds the windows and the cell-to-window index.
        if windows is None:
            windows = build_windows(board.rows, board.cols, self.connect_length)
            self._windows_cache[cache_key] = windows

        window_index = self._window_index_cache.get(cache_key)
        if window_index is None:
            window_index = _index_windows(windows)
            self._window_index_cache[cache_key] = window_index

        #count four-cell windows already occupied by each player.
        comp_fours = _count_owner_fours(board, Owner.COMPUTER, windows)
        human_fours = _count_owner_fours(board, Owner.HUMAN, windows)

        """
        Each call returns three numbers:
        1. How many columns can immediately produce at least one four.
        2. The largest number of fours obtainable from one column.
        3. The total number of fours obtainable across all playable columns.
        """
        comp_moves, comp_best, comp_total = self._scoring_opportunities(
            board, Owner.COMPUTER, window_index,
        )
        human_moves, human_best, human_total = self._scoring_opportunities(
            board, Owner.HUMAN, window_index,
        )


        comp_center, human_center = Heuristic._center_counts(board)

        weights = self.weights

        #multiply each feature difference by its weight, then adds the results:
        raw_score = (
            weights.fours * (comp_fours - human_fours)
            + weights.scoring_moves * (comp_moves - human_moves)
            + weights.best_four_gain * (comp_best - human_best)
            + weights.total_four_gain * (comp_total - human_total)
            + weights.center_control * (comp_center - human_center)
        )

        #returns all the counts and scores
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

    #examines each column where a disc can legally land:
    @staticmethod
    def _scoring_opportunities(board: Board, owner: Owner,window_index: dict) -> tuple[int, int, int]:
        gains = []
        for column in board.valid_moves():

            #landing is the actual row and column where a disc would land if that column were played
            landing = (board.lowest_empty_row(column), column)

            #For each such window, it checks whether all the other three cells already belong to the
            #player being evaluated. If they do, dropping a disc at landing would complete that four,
            # so the window adds one to gain.
            gain = sum(
                all(board.cell(row, col).owner is owner
                    for row, col in window if (row, col) != landing)
                for window in window_index.get(landing, ())
            )

            #that column is a scoring move
            if gain > 0:
                gains.append(gain)
        #scoring move,best gain,total gain
        return len(gains), max(gains, default=0), sum(gains)
