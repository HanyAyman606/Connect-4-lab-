"""Public evaluation functions used by the search and diagnostic output."""

from __future__ import annotations

from core.board import Board
from heuristics.window_heuristic import Heuristic, HeuristicBreakdown
from heuristics.gravity_heuristic import (
    GravityAwareHeuristic,
    GravityHeuristicBreakdown,
)

from heuristics.opportunity_heuristic import (
    OpportunityHeuristicBreakdown,
    ScoringOpportunityHeuristic,
)


DEFAULT_HEURISTIC = Heuristic()
GRAVITY_AWARE_HEURISTIC = GravityAwareHeuristic()
SCORING_OPPORTUNITY_HEURISTIC = ScoringOpportunityHeuristic()


#Evaluate a cutoff board with the default weighted heuristic.
def evaluate(board: Board) -> float:
    return DEFAULT_HEURISTIC(board)

#Return the feature counts and scores behind the default evaluation.
def explain_evaluation(board: Board) -> HeuristicBreakdown:
    return DEFAULT_HEURISTIC.breakdown(board)

# Evaluate with candidate windows discounted by gravity support moves.
def evaluate_gravity_aware(board: Board) -> float:
    return GRAVITY_AWARE_HEURISTIC(board)

#Return the gravity-aware feature breakdown for a board.
def explain_gravity_aware(board: Board) -> GravityHeuristicBreakdown:
    return GRAVITY_AWARE_HEURISTIC.breakdown(board)

#Evaluate current fours and legal moves that immediately add fours.
def evaluate_scoring_opportunities(board: Board) -> float:
    return SCORING_OPPORTUNITY_HEURISTIC(board)


#  Return current-score and immediate-scoring-option features.
def explain_scoring_opportunities(board: Board) -> OpportunityHeuristicBreakdown:
    return SCORING_OPPORTUNITY_HEURISTIC.breakdown(board)


HEURISTIC_MODELS = {
    "windows": evaluate,
    "gravity": evaluate_gravity_aware,
    "opportunities": evaluate_scoring_opportunities,
}


DIFFICULTY_MODELS = {
    "easy": evaluate_scoring_opportunities,
    "intermediate": evaluate_gravity_aware,
    "hard": evaluate,
}


__all__ = [
    "evaluate", "explain_evaluation",
    "evaluate_gravity_aware", "explain_gravity_aware",
    "evaluate_scoring_opportunities", "explain_scoring_opportunities",
    "HEURISTIC_MODELS", "DIFFICULTY_MODELS",
]



