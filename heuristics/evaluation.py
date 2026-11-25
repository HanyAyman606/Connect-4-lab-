"""Public evaluation functions used by the search and diagnostic output."""

from __future__ import annotations

from core.board import Board
from heuristics.window_heuristic import Heuristic, HeuristicBreakdown
from heuristics.gravity_heuristic import (
    GravityAwareHeuristic,
    GravityHeuristicBreakdown,
)

from heuristics.nonlinear_window_heuristic import NonlinearWindowHeuristic


DEFAULT_HEURISTIC = Heuristic()
GRAVITY_AWARE_HEURISTIC = GravityAwareHeuristic()
NONLINEAR_WINDOW_HEURISTIC = NonlinearWindowHeuristic()


#Evaluate a cutoff board with the default weighted heuristic.
def evaluate(board: Board) -> float:
    return DEFAULT_HEURISTIC(board)

#Return the feature counts and scores behind the default evaluation.
def explain_evaluation(board: Board) -> HeuristicBreakdown:
    return DEFAULT_HEURISTIC.breakdown(board)


def evaluate_gravity_aware(board: Board) -> float:
    """Evaluate with candidate windows discounted by gravity support moves."""
    return GRAVITY_AWARE_HEURISTIC(board)


def explain_gravity_aware(board: Board) -> GravityHeuristicBreakdown:
    """Return the gravity-aware feature breakdown for a board."""
    return GRAVITY_AWARE_HEURISTIC.breakdown(board)

def evaluate_nonlinear_window(board: Board) -> float:
    """Evaluate with nonlinear window growth and gravity accessibility."""
    return NONLINEAR_WINDOW_HEURISTIC(board)



