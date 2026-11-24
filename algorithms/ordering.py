"""Composable move-ordering rules used by adversarial search.

Move ordering changes the amount of alpha-beta pruning, not the minimax value.
The default strategy prioritizes four-making moves, then limits the opponent's
immediate four-making options, then prefers central columns.
"""

from __future__ import annotations

from typing import Callable, Iterable, Tuple

from core.game import Game, GameState

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

    #It counts that player’s fours before and after the hypothetical move and subtracts the counts
    mover = game.to_move(state)
    before = game.fours(state, mover)
    after_state = game.result(state, column)
    gained = game.fours(after_state, mover) - before

    # Sorting is ascending, so negate the gain to put larger gains first.
    return (-gained,)


def fewer_opponent_four_chances(game: Game, state: GameState,column: int) -> tuple:

    #simulates the candidate move, then checks each column the opponent could play next.
    # It counts how many of those replies would increase the opponent’s four count. A smaller count sorts first.
    after_our_move = game.result(state, column)
    opponent = after_our_move.turn
    current_fours = game.fours(after_our_move, opponent)
    opportunities = 0
    for reply in game.actions(after_our_move):
        after_reply = game.result(after_our_move, reply)
        if game.fours(after_reply, opponent) > current_fours:
            opportunities += 1
    return (opportunities,)


def center_preference(game: Game, state: GameState, column: int) -> tuple:

    #Get the total number of columns on this board.
    width = state.board.cols

    #For an odd width this is the middle column; for an even width it is between the two middle columns.
    center = (width - 1) / 2

    #The first value prefers the closest column; the second breaks ties toward the smaller column number.
    return (abs(column - center), column)


center_first = combine_orderings(center_preference)
"""Center-only ordering, retained as a simple baseline for comparisons."""

tactical_center_first = combine_orderings(
    four_gain_first,
    fewer_opponent_four_chances,
    center_preference,
)
"""Default ordering: score gain, opponent threat reduction, then center."""

