"""Tiny fixed game trees used by tree-node, recorder, and printer tests.

Each tuple is an internal node whose children are the legal actions in order;
each number is a leaf evaluation. The helper runs the production alpha-beta
search over this small tree so tests exercise the real recorder and printer.
"""

from __future__ import annotations

from dataclasses import dataclass

from algorithms.alpha_beta import AlphaBetaSearcher
from core.owner import Owner
from tree_essentials import SearchResult, SearchStats, TreeRecorder, create_recorder


# The three rows are MIN replies to the root's three MAX choices.
FIGURE_6_2 = (
    (3, 12, 8),
    (2, 9, 4),
    (14, 5, 2),
)

# A three-ply lecture example with a cutoff at each of three different nodes.
PRUNING_EXAMPLE = (
    (
        (4, 3),
        (6, 8),
    ),
    (
        (2,),
        (9,),
        (10,),
    ),
    (
        (5, 4, 5),
        (7, 9),
    ),
)


@dataclass(frozen=True, slots=True)
class _BoardAtPath:
    path: tuple[int, ...]
    score: int | tuple

    def __str__(self) -> str:
        return str(self.score)


@dataclass(frozen=True, slots=True)
class _State:
    board: _BoardAtPath
    turn: Owner


class _TreeGame:
    """Game-shaped adapter that exposes a nested tuple as legal moves."""

    def __init__(self, tree) -> None:
        self.tree = tree

    def _at(self, path: tuple[int, ...]):
        node = self.tree
        for column in path:
            node = node[column]
        return node

    def initial_state(self) -> _State:
        return self._state(())

    def _state(self, path: tuple[int, ...]) -> _State:
        score = self._at(path)
        owner = Owner.COMPUTER if len(path) % 2 == 0 else Owner.HUMAN
        return _State(_BoardAtPath(path, score), owner)

    def to_move(self, state: _State) -> Owner:
        return state.turn

    def is_terminal(self, state: _State) -> bool:
        # These diagrams stop at the requested depth; their leaves are evals.
        return False

    def actions(self, state: _State) -> tuple[int, ...]:
        node = state.board.score
        if not isinstance(node, tuple):
            return ()
        return tuple(range(len(node)))

    def result(self, state: _State, action: int) -> _State:
        next_path = state.board.path + (action,)
        return self._state(next_path)

    def utility(self, state: _State) -> int:
        raise RuntimeError("fixed evaluation trees do not contain terminal leaves")


def _identity_order(game, state, columns):
    return tuple(columns)


def _leaf_depths(node, depth: int = 0):
    if isinstance(node, tuple):
        for child in node:
            yield from _leaf_depths(child, depth + 1)
    else:
        yield depth


def run(tree, k: int | None = None, recorder=None) -> SearchResult:
    """Search a nested tuple with production alpha-beta and optional recorder."""
    if k is None:
        k = max(_leaf_depths(tree))
    if recorder is None:
        recorder = create_recorder(True)

    game = _TreeGame(tree)
    state = game.initial_state()
    searcher = AlphaBetaSearcher(
        evaluator=lambda board: board.score,
        move_orderer=_identity_order,
    )
    stats = SearchStats()
    stats.start_timer()
    value, best_column = searcher._visit(
        game=game,
        state=state,
        depth=0,
        k=k,
        alpha=float("-inf"),
        beta=float("inf"),
        role=searcher._role_for(game.to_move(state)),
        column=None,
        recorder=recorder,
        stats=stats,
    )
    stats.stop_timer()
    return SearchResult(
        best_column=best_column,
        value=value,
        k=k,
        algorithm="alpha-beta",
        stats=stats,
        root=recorder.root,
        tree_truncated=recorder.truncated,
    )
