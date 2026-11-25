"""Measure alpha-beta search cost at several depths on shared positions.

Example:
    python -m experiments.k_analysis --ks 1 2 3 4 5 6 --positions 20

Every K is searched on the same reproducible set of boards, with the same
evaluator and move ordering. This makes the depth comparison less dependent
on differences between self-play game trajectories.
"""

from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path
from statistics import mean, median
from typing import Optional

from algorithms.alpha_beta import AlphaBetaSearcher
from algorithms.ordering import (
    center_first,
    four_gain_center_first,
    tactical_center_first,
    threat_center_first,
)
from core.disc import Disc
from core.game import Game, GameState
from core.owner import Owner
from core.rules import Rules
from game.player import Player
from heuristics.evaluation import (
    evaluate,
    evaluate_gravity_aware,
    evaluate_scoring_opportunities,
)


class _AnalysisPlayer(Player):
    """Player shell used to create Game states; search selects all moves."""

    def get_move(self, game: Game, state: GameState) -> int:
        raise RuntimeError("k_analysis calls the searcher directly")


HEURISTICS = {
    "windows": evaluate,
    "gravity": evaluate_gravity_aware,
    "opportunities": evaluate_scoring_opportunities,
}
ORDERINGS = {
    "center": center_first,
    "four_gain_center": four_gain_center_first,
    "threat_center": threat_center_first,
    "tactical": tactical_center_first,
}


def make_positions(count: int, opening_plies: int, seed: int) -> list[tuple[Game, GameState]]:
    """Build reproducible legal positions from random human-first openings."""
    rng = random.Random(seed)
    rules = Rules(rows=6, cols=7, connect_length=4)
    human = _AnalysisPlayer(Disc(Owner.HUMAN, "analysis-human"), "Analysis human")
    computer = _AnalysisPlayer(Disc(Owner.COMPUTER, "analysis-computer"), "Analysis computer")
    positions = []

    for _ in range(count):
        game = Game(human, computer, rules, first=Owner.HUMAN)
        state = game.initial_state()
        for _ply in range(opening_plies):
            legal = game.actions(state)
            if not legal or game.is_terminal(state):
                break
            state = game.result(state, rng.choice(legal))
        positions.append((game, state))

    return positions


def analyze_k_values(ks: list[int], positions: list[tuple[Game, GameState]],
                     heuristic_name: str, ordering_name: str) -> list[dict]:
    """Search each shared position at each K and summarize work and time."""
    searcher = AlphaBetaSearcher(
        HEURISTICS[heuristic_name],
        ORDERINGS[ordering_name],
    )
    rows = []

    for k in ks:
        results = [searcher.search(game, state, k, record=False)
                   for game, state in positions]
        times_ms = [1000 * result.time_sec for result in results]
        row = {
            "k": k,
            "positions": len(results),
            "heuristic": heuristic_name,
            "ordering": ordering_name,
            "average_nodes_visited": mean(r.nodes_visited for r in results),
            "average_nodes_expanded": mean(r.nodes_expanded for r in results),
            "average_pruned_branches": mean(r.stats.pruned_branches for r in results),
            "average_cutoffs": mean(r.stats.cutoffs for r in results),
            "average_search_ms": mean(times_ms),
            "median_search_ms": median(times_ms),
        }
        rows.append(row)
        print(
            f"K={k:<2} positions={len(results):<3} "
            f"visited={row['average_nodes_visited']:>10.1f} "
            f"expanded={row['average_nodes_expanded']:>10.1f} "
            f"pruned={row['average_pruned_branches']:>9.1f} "
            f"avg={row['average_search_ms']:>9.3f} ms "
            f"median={row['median_search_ms']:>9.3f} ms"
        )

    return rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ks", type=int, nargs="+", default=[1, 2, 3, 4, 5, 6],
                        help="search depths to measure (default: 1 2 3 4 5 6)")
    parser.add_argument("--positions", type=int, default=20,
                        help="number of fixed random-opening positions (default: 20)")
    parser.add_argument("--opening-plies", type=int, default=5,
                        help="random human-first plies used to make each position (default: 5)")
    parser.add_argument("--seed", type=int, default=20261125,
                        help="seed for reproducible positions")
    parser.add_argument("--heuristic", choices=tuple(HEURISTICS), default="windows")
    parser.add_argument("--ordering", choices=tuple(ORDERINGS), default="four_gain_center")
    parser.add_argument("--csv", type=Path, default=Path("experiments/k_analysis.csv"),
                        help="output CSV path (default: experiments/k_analysis.csv)")
    args = parser.parse_args(argv)

    if not args.ks or any(k < 1 for k in args.ks):
        parser.error("every K must be a positive integer")
    if args.positions < 1:
        parser.error("--positions must be at least 1")
    if not 0 <= args.opening_plies < 42:
        parser.error("--opening-plies must be between 0 and 41")

    positions = make_positions(args.positions, args.opening_plies, args.seed)
    print(
        f"Alpha-beta cost analysis: heuristic={args.heuristic}, "
        f"ordering={args.ordering}, positions={args.positions}, "
        f"opening_plies={args.opening_plies}, seed={args.seed}"
    )
    print("Tree recording is off during measurement; each K uses the same positions.")
    rows = analyze_k_values(args.ks, positions, args.heuristic, args.ordering)

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote results to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
