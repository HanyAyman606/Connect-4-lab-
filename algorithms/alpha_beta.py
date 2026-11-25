"""Depth-limited Minimax with alpha-beta pruning.

The evaluator is supplied by the caller so the search can be reused with
different heuristic functions. Values are always from the computer's point of
view: MAX is the computer and MIN is the human.
"""

from __future__ import annotations

from typing import Callable, Optional

from core.board import Board
from core.game import Game, GameState
from core.owner import Owner
from algorithms.ordering import MoveOrderer, four_gain_center_first
from tree_essentials import (
    LeafKind,
    Role,
    SearchResult,
    SearchStats,
    create_recorder,
)

#evaluator is a function that accepts a board and returns a number.our heuristic will fill this role
Evaluator = Callable[[Board], float]

class AlphaBetaSearcher:

    def __init__(self, evaluator: Evaluator,move_orderer: MoveOrderer = four_gain_center_first) -> None:
        if not callable(evaluator):
            raise TypeError("evaluator must be callable")
        if not callable(move_orderer):
            raise TypeError("move_orderer must be callable")

        #evaluator:Scores a non-terminal cutoff board from the computer's perspective.
        self._evaluate = evaluator

        #Returns the legal columns in the order to explore them.
        self._order_moves = move_orderer

    #Run one search; K is the number of moves (plies) from the root.
    def search(self, game: Game, state: GameState, k: int, *, record: bool = True, max_record_depth: Optional[int] = None,
               max_record_nodes: Optional[int] = None) -> SearchResult:
        from tree_essentials.search_limits import validate_k

        #checks that K is a positive whole number.
        k = validate_k(k)

        #creates a tree recorder by default.
        recorder = create_recorder(
            record=record,
            max_depth=max_record_depth,
            max_nodes=max_record_nodes,
        )

        #creates counters and a timer.
        stats = SearchStats()

        #start the search timer
        stats.start_timer()

        #determines whether the root is MAX or MIN based on whose turn it is.
        root_role = self._role_for(game.to_move(state))

        #performs the recursive search, starting at depth 0 with alpha = -infinity and beta = +infinity.
        value, best_column = self._visit(
            game=game,
            state=state,
            depth=0,
            k=k,
            alpha=float("-inf"),
            beta=float("inf"),
            role=root_role,
            column=None,
            recorder=recorder,
            stats=stats,
        )

        #The timer stops after finding the best value and move from the root's perspective
        stats.stop_timer()

        #SearchResult packages the best column, score, K, statistics, and recorded tree.
        return SearchResult(
            best_column=best_column,
            value=value,
            k=k,
            algorithm="alpha-beta",
            stats=stats,
            root=recorder.root,
            tree_truncated=recorder.truncated,
        )

    #Evaluate one node, then recurse over its children if needed."""
    def _visit(self, game: Game, state: GameState, depth: int, k: int,
               alpha: float, beta: float, role: Role, column: Optional[int],
               recorder, stats: SearchStats) -> tuple[float, Optional[int]]:

        #It counts the node and records its depth
        stats.visited += 1
        stats.max_depth = max(stats.max_depth, depth)

        #starts recording this node,including the move that led to it,its MAX/MIN role,depth,and alpha/beta values.
        node = recorder.enter(column, role, depth, alpha, beta)

        #if the board is full,it gets the exact score using game.utility(state).
        # This check comes before the K cutoff so a full board always gets an exact score.
        if game.is_terminal(state):
            value = game.utility(state)
            stats.terminal_leaves += 1
            recorder.leaf(node, LeafKind.TERMINAL, value, state.board)
            return value, None

        #if depth has reached K,it calls the supplied evaluator and records the result as an EVAL leaf.
        if depth >= k:
            value = self._evaluate(state.board)
            stats.evaluations += 1
            recorder.leaf(node, LeafKind.EVAL, value, state.board)
            return value, None

        #get the legal columns and orders them with the configured move-ordering function.
        legal_columns = game.actions(state)

        # A well-formed non-terminal game state should always have a move.
        # Retain a safe leaf case for custom Game implementations.
        if not legal_columns:
            value = game.utility(state)
            stats.terminal_leaves += 1
            recorder.leaf(node, LeafKind.TERMINAL, value, state.board)
            return value, None

        columns = self._order_moves(game, state, legal_columns)

        stats.expanded += 1
        best_column: Optional[int] = None
        pruned_columns = []

        if role is Role.MAX:
            value = float("-inf")

            # explore each column by calling game.result(...) to make the next state,then recursively calls _visit(...)
            # with the opposite role.
            for index, candidate in enumerate(columns):
                child_state = game.result(state, candidate)
                child_value, _ = self._visit(
                    game, child_state, depth + 1, k, alpha, beta,
                    role.opposite, candidate, recorder, stats,
                )

                #At a MAX node,it keeps the highest child value and updates alpha:
                if child_value > value:
                    value, best_column = child_value, candidate
                alpha = max(alpha, value)

                #MIN already has a path that avoids this result,
                # so the remaining columns cannot affect the final choice.
                # They are recorded as pruned.
                if value >= beta:
                    pruned_columns.extend(columns[index + 1:])
                    stats.cutoffs += 1
                    stats.pruned_branches += len(columns) - index - 1
                    break
        else:
            value = float("inf")

            # explore each column by calling game.result(...) to make the next state,then recursively calls _visit(...)
            # with the opposite role.
            for index, candidate in enumerate(columns):
                child_state = game.result(state, candidate)
                child_value, _ = self._visit(
                    game, child_state, depth + 1, k, alpha, beta,
                    role.opposite, candidate, recorder, stats,
                )

                #At a MIN node, it keeps the lowest child value and updates beta
                if child_value < value:
                    value, best_column = child_value, candidate
                beta = min(beta, value)

                #MAX already has a better option elsewhere, so the remaining columns can be pruned.
                if value <= alpha:
                    pruned_columns.extend(columns[index + 1:])
                    stats.cutoffs += 1
                    stats.pruned_branches += len(columns) - index - 1
                    break

        #After exploring or pruning, recorder.exit(...) saves the chosen value, the best column, and pruned columns
        recorder.exit(node, value, best_column, pruned_columns)

        #The method returns the value and best column to its parent
        return value, best_column

    @staticmethod
    def _role_for(owner: Owner) -> Role:
        if owner is Owner.COMPUTER:
            return Role.MAX
        if owner is Owner.HUMAN:
            return Role.MIN
        raise ValueError("the side to move must be HUMAN or COMPUTER")
