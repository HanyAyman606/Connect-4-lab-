"""Composable move-ordering rules used by adversarial search.

Move ordering changes the amount of alpha-beta pruning, not the minimax value.
The default strategy prioritizes four-making moves, then limits the opponent's
immediate four-making options, then prefers central columns.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable, Iterable, Tuple

from core.game import Game, GameState
from core.rules import build_windows

#An ordering rule looks at one candidate column and returns its priority key.
OrderingRule = Callable[[Game, GameState, int], tuple]

#applies one or more rules to all legal columns and returns those columns in priority order.
MoveOrderer = Callable[[Game, GameState, Iterable[int]], Tuple[int, ...]]


#combines ranking rules into one move orderer.The *rules syntax means it can receive any number of rules as separate argument
#The rule results are compared in order, like a sequence of priorities. So in:
def combine_orderings(*rules: OrderingRule) -> MoveOrderer:

    if not rules:
        raise ValueError("provide at least one ordering rule")
    if any(not callable(rule) for rule in rules):
        raise TypeError("every ordering rule must be callable")

    #Receives the game, current state, and legal columns.
    def order(game: Game, state: GameState,legal_columns: Iterable[int]) -> Tuple[int, ...]:

        #Converts the columns to a tuple so they can be used consistently.
        columns = tuple(legal_columns)

        #Sort them using a key made by calling every rule for each column
        return tuple(sorted(
            columns,
            key=lambda column: tuple(rule(game, state, column) for rule in rules),
        ))

    return order

#if the player whose turn it is drops in this column, how many new fours do they create?
def four_gain_first(game: Game, state: GameState, column: int) -> tuple:

    mover = game.to_move(state)
    gained = _four_gain(state.board, column, mover, game.rules.connect_length)

    # Sorting is ascending, so negate the gain to put larger gains first.
    return (-gained,)


def fewer_opponent_four_chances(game: Game, state: GameState,column: int) -> tuple:

    #simulates the candidate move, then checks each column the opponent could play next.
    # It counts how many of those replies would increase the opponent’s four count. A smaller count sorts first.
    after_our_move = game.result(state, column)
    opponent = after_our_move.turn
    opportunities = 0
    for reply in game.actions(after_our_move):
        if _four_gain(after_our_move.board, reply, opponent,
                      game.rules.connect_length) > 0:
            opportunities += 1
    return (opportunities,)


def center_preference(game: Game, state: GameState, column: int) -> tuple:

    #Get the total number of columns on this board.
    width = state.board.cols

    #For an odd width this is the middle column; for an even width it is between the two middle columns.
    center = (width - 1) / 2

    #The first value prefers the closest column; the second breaks ties toward the smaller column number.
    return abs(column - center), column


center_first = combine_orderings(center_preference)
"""Center-only ordering, retained as a simple baseline for comparisons."""

four_gain_center_first = combine_orderings(
    four_gain_first,
    center_preference,
)
"""Cheap tactical ordering: create fours first, then prefer the center."""

threat_center_first = combine_orderings(
    fewer_opponent_four_chances,
    center_preference,
)
"""Threat-focused ordering: limit replies first, then prefer the center."""

tactical_center_first = combine_orderings(
    four_gain_first,
    fewer_opponent_four_chances,
    center_preference,
)
"""Default ordering: score gain, opponent threat reduction, then center."""

#builds an index that answers: “Which connect-four windows include this cell?”
#@lru_cache decorator saves the result for each board size and connect length
#Since those dimensions don’t change during a game, the next call can reuse the index instead of rebuilding it.
@lru_cache(maxsize=None)
def _windows_by_cell(rows: int, cols: int, connect_length: int) -> dict:
    index: dict = {}

    #gets all the possible windows from build_windows
    for window in build_windows(rows, cols, connect_length):

        #for each cell in each window, it records that window under the cell’s (row, column) coordinate.
        for cell in window:
            index.setdefault(cell, []).append(window)
    return {cell: tuple(windows) for cell, windows in index.items()}


#counts how many four-cell windows a player would complete by dropping a disc in column.
def _four_gain(board, column: int, owner, connect_length: int) -> int:

    #Finds the drop’s landing cell
    landing = (board.lowest_empty_row(column), column)

    #get only the windows containing that cell
    affected = _windows_by_cell(board.rows, board.cols, connect_length).get(landing, ())

    #For each window, checks whether all its other cells already belong to owner
    #1. Counts the windows that meet that condition.
    return sum(
        all(board.cell(row, col).owner is owner for row, col in window if (row, col) != landing) for window in affected
    )

