"""Compare heuristic evaluators and move ordering by full-board self-play.

Examples:
    python -m experiments.compare_heuristics --mode all --ks 1 2 3 --rounds 5
    python -m experiments.compare_heuristics --mode heuristics --k 3 --csv results.csv

Heuristic comparisons hold move ordering fixed. Ordering comparisons hold the
heuristic fixed. Each matchup rotates which configuration is COMPUTER/HUMAN
and which player moves first.
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Callable, Optional

from heuristics.evaluation import (
    evaluate,
    evaluate_gravity_aware,
    evaluate_nonlinear_window,
)
from algorithms.alpha_beta import AlphaBetaSearcher
from algorithms.ordering import (
    center_first,
    four_gain_center_first,
    tactical_center_first,
    threat_center_first,
)
from core.disc import Disc
from core.board import Board
from core.game import Game, GameState
from core.owner import Owner
from core.player import Player
from core.rules import Rules


@dataclass(frozen=True, slots=True)
class AgentConfig:
    """One evaluator and move orderer used by a self-play participant."""

    name: str
    evaluator: Callable
    move_orderer: Callable


@dataclass(slots=True)
class MatchupResult:
    """Aggregated outcome and per-search costs for one head-to-head matchup."""

    agent_a: str
    agent_b: str
    games: int = 0
    wins_a: int = 0
    draws: int = 0
    wins_b: int = 0
    margin_a_total: int = 0
    searches_a: int = 0
    searches_b: int = 0
    nodes_a: int = 0
    nodes_b: int = 0
    pruned_a: int = 0
    pruned_b: int = 0
    cutoffs_a: int = 0
    cutoffs_b: int = 0
    seconds_a: float = 0.0
    seconds_b: float = 0.0

    @property
    def average_margin_a(self) -> float:
        return self.margin_a_total / self.games if self.games else 0.0

    def csv_row(self, k: int, rounds: int, experiment: str,
                opening_plies: int, seed: int) -> dict:
        return {
            "experiment": experiment,
            "k": k,
            "rounds": rounds,
            "opening_plies": opening_plies,
            "seed": seed,
            "agent_a": self.agent_a,
            "agent_b": self.agent_b,
            "games": self.games,
            "wins_a": self.wins_a,
            "draws": self.draws,
            "wins_b": self.wins_b,
            "average_score_margin_a": self.average_margin_a,
            "average_nodes_per_search_a": self.nodes_a / self.searches_a if self.searches_a else 0,
            "average_nodes_per_search_b": self.nodes_b / self.searches_b if self.searches_b else 0,
            "average_pruned_branches_per_search_a": self.pruned_a / self.searches_a if self.searches_a else 0,
            "average_pruned_branches_per_search_b": self.pruned_b / self.searches_b if self.searches_b else 0,
            "average_cutoffs_per_search_a": self.cutoffs_a / self.searches_a if self.searches_a else 0,
            "average_cutoffs_per_search_b": self.cutoffs_b / self.searches_b if self.searches_b else 0,
            "average_search_ms_a": 1000 * self.seconds_a / self.searches_a if self.searches_a else 0,
            "average_search_ms_b": 1000 * self.seconds_b / self.searches_b if self.searches_b else 0,
        }


class _DemoPlayer(Player):
    """Game requires Player objects, while this runner asks the search directly."""

    def get_move(self, game: Game, state: GameState) -> int:
        raise RuntimeError("the comparison runner calls its searchers directly")


HEURISTICS = {
    "windows": evaluate,
    "gravity": evaluate_gravity_aware,
    "nonlinear_window": evaluate_nonlinear_window,
}
ORDERINGS = {
    "center": center_first,
    "four_gain_center": four_gain_center_first,
    "threat_center": threat_center_first,
    "tactical": tactical_center_first,
}


def play_matchup(agent_a: AgentConfig, agent_b: AgentConfig,
                 k: int, rounds: int, opening_plies: int, seed: int) -> MatchupResult:
    """Play a balanced set of full games between two agent configurations."""
    result = MatchupResult(agent_a.name, agent_b.name)
    openings = _make_openings(rounds, opening_plies, seed)

    for game_index in range(rounds * 4):
        # Balance both disc/role assignment and first move across four games.
        a_owner = Owner.COMPUTER if game_index % 2 == 0 else Owner.HUMAN
        b_owner = Game.opponent(a_owner)
        first = Owner.COMPUTER if (game_index // 2) % 2 == 0 else Owner.HUMAN

        human = _DemoPlayer(Disc(Owner.HUMAN, "demo-human"), "Demo human")
        computer = _DemoPlayer(Disc(Owner.COMPUTER, "demo-computer"), "Demo computer")
        game = Game(human, computer, Rules(6, 7, 4), first)
        state = game.initial_state()

        # Each set of four role/first-player rotations shares one opening.
        for column in openings[game_index // 4]:
            state = game.result(state, column)

        configs = {a_owner: agent_a, b_owner: agent_b}
        searchers = {
            owner: AlphaBetaSearcher(config.evaluator, config.move_orderer)
            for owner, config in configs.items()
        }

        while not game.is_terminal(state):
            owner = state.turn
            search_result = searchers[owner].search(game, state, k, record=False)
            if search_result.best_column is None:
                raise RuntimeError("search returned no move for a non-terminal board")
            state = game.result(state, search_result.best_column)

            if owner is a_owner:
                result.searches_a += 1
                result.nodes_a += search_result.nodes_visited
                result.pruned_a += search_result.stats.pruned_branches
                result.cutoffs_a += search_result.stats.cutoffs
                result.seconds_a += search_result.time_sec
            else:
                result.searches_b += 1
                result.nodes_b += search_result.nodes_visited
                result.pruned_b += search_result.stats.pruned_branches
                result.cutoffs_b += search_result.stats.cutoffs
                result.seconds_b += search_result.time_sec

        margin_a = game.utility(state) if a_owner is Owner.COMPUTER else -game.utility(state)
        result.games += 1
        result.margin_a_total += margin_a
        if margin_a > 0:
            result.wins_a += 1
        elif margin_a < 0:
            result.wins_b += 1
        else:
            result.draws += 1

    return result


def _make_openings(rounds: int, opening_plies: int, seed: int) -> list[tuple[int, ...]]:
    """Create reproducible legal opening sequences, one per four-game round."""
    rng = random.Random(seed)
    computer_disc = Disc(Owner.COMPUTER, "opening-computer")
    human_disc = Disc(Owner.HUMAN, "opening-human")
    openings = []
    for _ in range(rounds):
        board = Board(6, 7)
        columns = []
        for ply in range(opening_plies):
            legal = board.valid_moves()
            if not legal:
                break
            column = rng.choice(legal)
            columns.append(column)
            disc = computer_disc if ply % 2 == 0 else human_disc
            board = board.drop(column, disc)
        openings.append(tuple(columns))
    return openings


def _report(result: MatchupResult, k: int, rounds: int,
            experiment: str, opening_plies: int, seed: int) -> dict:
    games = result.games
    a_nodes = result.nodes_a / result.searches_a if result.searches_a else 0
    b_nodes = result.nodes_b / result.searches_b if result.searches_b else 0
    a_pruned = result.pruned_a / result.searches_a if result.searches_a else 0
    b_pruned = result.pruned_b / result.searches_b if result.searches_b else 0
    a_ms = 1000 * result.seconds_a / result.searches_a if result.searches_a else 0
    b_ms = 1000 * result.seconds_b / result.searches_b if result.searches_b else 0
    print(f"{result.agent_a:20} vs {result.agent_b:20} "
          f"{result.wins_a:2}-{result.draws:2}-{result.wins_b:2}  "
          f"avg margin {result.average_margin_a:+7.2f}  "
          f"nodes/search {a_nodes:8.1f} / {b_nodes:8.1f}  "
          f"pruned/search {a_pruned:6.2f} / {b_pruned:6.2f}  "
          f"ms/search {a_ms:8.2f} / {b_ms:8.2f}")
    return result.csv_row(k, rounds, experiment, opening_plies, seed)


def compare_heuristics(k: int, rounds: int, ordering_name: str,
                       opening_plies: int, seed: int,
                       names: Optional[tuple[str, ...]] = None) -> list[dict]:
    """Compare heuristic candidates under one shared ordering."""
    print(f"\nHeuristic comparison (K={k}, ordering={ordering_name})")
    print("A wins-draws-B wins; margin and cost are reported for A.")
    rows = []
    candidates = HEURISTICS.items() if names is None else (
        (name, HEURISTICS[name]) for name in names
    )
    for (name_a, evaluator_a), (name_b, evaluator_b) in combinations(candidates, 2):
        agent_a = AgentConfig(name_a, evaluator_a, ORDERINGS[ordering_name])
        agent_b = AgentConfig(name_b, evaluator_b, ORDERINGS[ordering_name])
        match = play_matchup(agent_a, agent_b, k, rounds, opening_plies, seed)
        rows.append(_report(match, k, rounds, f"heuristics/{ordering_name}", opening_plies, seed))
    return rows


def compare_orderings(k: int, rounds: int, heuristic_name: str,
                      opening_plies: int, seed: int) -> list[dict]:
    """Compare every configured ordering with one shared heuristic."""
    print(f"\nOrdering comparison (K={k}, heuristic={heuristic_name})")
    print("A wins-draws-B wins; margin and cost are reported for A.")
    evaluator = HEURISTICS[heuristic_name]
    rows = []
    for (name_a, orderer_a), (name_b, orderer_b) in combinations(ORDERINGS.items(), 2):
        agent_a = AgentConfig(name_a, evaluator, orderer_a)
        agent_b = AgentConfig(name_b, evaluator, orderer_b)
        match = play_matchup(agent_a, agent_b, k, rounds, opening_plies, seed)
        rows.append(_report(match, k, rounds, f"orderings/{heuristic_name}", opening_plies, seed))
    return rows


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("all", "heuristics", "orderings"),
                        default="all", help="which comparisons to run")
    parser.add_argument("--k", type=int,
                        help="one search depth (backward-compatible single-K option)")
    parser.add_argument("--ks", type=int, nargs="+",
                        help="one or more search depths, e.g. --ks 1 2 3")
    parser.add_argument("--rounds", type=int, default=1,
                        help="four balanced games per matchup per round (default: 1)")
    parser.add_argument("--opening-plies", type=int, default=4,
                        help="seeded random opening moves per game (default: 4; use 0 for empty starts)")
    parser.add_argument("--seed", type=int, default=2026,
                        help="seed for reproducible randomized openings (default: 2026)")
    parser.add_argument("--fixed-order", choices=tuple(ORDERINGS), default="center",
                        help="shared ordering for heuristic comparisons")
    parser.add_argument("--heuristic", choices=tuple(HEURISTICS), default="windows",
                        help="shared heuristic for the ordering comparison")
    parser.add_argument("--compare", nargs=2, choices=tuple(HEURISTICS),
                        metavar=("HEURISTIC_A", "HEURISTIC_B"),
                        help="compare only these two heuristics (heuristic mode)")
    parser.add_argument("--csv", type=Path,
                        help="optional path to write machine-readable results")
    args = parser.parse_args(argv)
    if args.k is not None and args.ks is not None:
        parser.error("use either --k or --ks, not both")
    k_values = args.ks if args.ks is not None else ([args.k] if args.k is not None else [2])
    if any(k < 1 for k in k_values):
        parser.error("all K values must be at least 1")
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    if not 0 <= args.opening_plies < 42:
        parser.error("--opening-plies must be between 0 and 41 so agents get a turn")

    if args.compare and args.mode != "heuristics":
        parser.error("--compare can only be used with --mode heuristics")
    heuristic_count = len(args.compare) if args.compare else len(HEURISTICS)
    heuristic_matchups = (
        heuristic_count * (heuristic_count - 1) // 2
        if args.mode in ("all", "heuristics") else 0
    )
    ordering_matchups = 0
    if args.mode in ("all", "orderings"):
        ordering_matchups = len(HEURISTICS if args.mode == "all" else (args.heuristic,)) * (
            len(ORDERINGS) * (len(ORDERINGS) - 1) // 2
        )
    total_games = (heuristic_matchups + ordering_matchups) * len(k_values) * args.rounds * 4
    print(f"Planned {total_games} games at K={','.join(map(str, k_values))}; "
          f"{args.rounds} round(s), {args.opening_plies} random opening plies, seed={args.seed}.")

    rows = []
    for k in k_values:
        if args.mode in ("all", "heuristics"):
            rows.extend(compare_heuristics(
                k, args.rounds, args.fixed_order, args.opening_plies, args.seed,
                tuple(args.compare) if args.compare else None,
            ))
        if args.mode in ("all", "orderings"):
            if args.mode == "all":
                print("\nOrdering results are separated by heuristic to avoid mixing effects.")
                heuristic_names = tuple(HEURISTICS)
            else:
                heuristic_names = (args.heuristic,)
            for heuristic_name in heuristic_names:
                rows.extend(compare_orderings(
                    k, args.rounds, heuristic_name, args.opening_plies, args.seed,
                ))

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        with args.csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nWrote results to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
