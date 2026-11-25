"""Tune window-heuristic weights with hill climbing and a genetic algorithm.

Both methods optimize three feature weights while keeping the completed-four
weight fixed at 100. They play against the original untuned window heuristic
at the same K, move ordering, seeds, and opening lengths. A separate higher-budget
validation compares the best candidate from each method with the baseline.

Example:
    python -m experiments.tune_heuristic --budget 12 --rounds 1 --validation-rounds 5
"""

from __future__ import annotations

import argparse
import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from algorithms.ordering import four_gain_center_first
from experiments.compare_heuristics import AgentConfig, play_matchup
from heuristics.evaluation import evaluate_baseline
from heuristics.window_heuristic import Heuristic, HeuristicWeights


WeightVector = tuple[float, float, float]  # open threes, open twos, center
WEIGHT_GRIDS = (
    (4.0, 6.0, 8.0, 10.0, 12.0, 16.0, 20.0),
    (0.0, 1.0, 2.0, 3.0, 5.0, 8.0),
    (0.0, 1.0, 2.0, 4.0, 6.0),
)
BASE_WEIGHTS: WeightVector = (10.0, 3.0, 2.0)


@dataclass(frozen=True, slots=True)
class Fitness:
    """Balanced head-to-head results for one weight vector."""

    wins: int
    draws: int
    losses: int
    games: int
    margin_sum: float

    @property
    def average_margin(self) -> float:
        return self.margin_sum / self.games if self.games else 0.0


def evaluator_for(weights: WeightVector) -> Heuristic:
    """Create the window evaluator represented by the three tuned weights."""
    open_threes, open_twos, center_control = weights
    return Heuristic(HeuristicWeights(
        fours=100.0,
        open_threes=open_threes,
        open_twos=open_twos,
        center_control=center_control,
        normalization_scale=1000.0,
    ))


def evaluate_weights(weights: WeightVector, k: int, rounds: int,
                     seeds: tuple[int, ...]) -> Fitness:
    """Measure a candidate against baseline on the same seeded openings."""
    candidate = AgentConfig(
        "candidate", evaluator_for(weights), four_gain_center_first,
    )
    baseline = AgentConfig("baseline", evaluate_baseline, four_gain_center_first)
    wins = draws = losses = games = 0
    margin_sum = 0.0
    for seed in seeds:
        result = play_matchup(
            candidate, baseline, k=k, rounds=rounds,
            opening_plies=4, seed=seed,
        )
        wins += result.wins_a
        draws += result.draws
        losses += result.wins_b
        games += result.games
        margin_sum += result.margin_a_total
    return Fitness(wins, draws, losses, games, margin_sum)


def _neighbors(weights: WeightVector) -> list[WeightVector]:
    neighbors = []
    for index, grid in enumerate(WEIGHT_GRIDS):
        current_index = grid.index(weights[index])
        for next_index in (current_index - 1, current_index + 1):
            if 0 <= next_index < len(grid):
                candidate = list(weights)
                candidate[index] = grid[next_index]
                neighbors.append(tuple(candidate))
    return neighbors


def hill_climb(budget: int, rng: random.Random,
               score) -> tuple[WeightVector, Fitness, list[tuple[WeightVector, Fitness]]]:
    """Run bounded random-restart hill climbing from the default weights."""
    evaluated: dict[WeightVector, Fitness] = {}
    history = []

    def assess(weights: WeightVector) -> Fitness:
        if weights not in evaluated and len(evaluated) < budget:
            fitness = score(weights)
            evaluated[weights] = fitness
            history.append((weights, fitness))
        return evaluated[weights]

    current = BASE_WEIGHTS
    while len(evaluated) < budget:
        if current not in evaluated:
            assess(current)
        current_fitness = evaluated[current]
        neighbors = [candidate for candidate in _neighbors(current)
                     if candidate not in evaluated]
        if not neighbors:
            current = _random_weights(rng, set(evaluated))
            if current is None:
                break
            continue

        neighbor_scores = []
        for candidate in neighbors:
            if len(evaluated) >= budget:
                break
            neighbor_scores.append((candidate, assess(candidate)))
        if not neighbor_scores:
            break
        best_neighbor, best_fitness = max(
            neighbor_scores, key=lambda item: item[1].average_margin,
        )
        if best_fitness.average_margin > current_fitness.average_margin:
            current = best_neighbor
        else:
            current = _random_weights(rng, set(evaluated))
            if current is None:
                break

    best_weights, best_fitness = max(
        evaluated.items(), key=lambda item: item[1].average_margin,
    )
    return best_weights, best_fitness, history


def genetic_search(budget: int, population_size: int, rng: random.Random,
                   score) -> tuple[WeightVector, Fitness, list[tuple[WeightVector, Fitness]]]:
    """Run a small genetic algorithm over discrete weight ranges."""
    population_size = min(population_size, budget)
    population = [BASE_WEIGHTS]
    while len(population) < population_size:
        candidate = _random_weights(rng, set(population))
        if candidate is None:
            break
        population.append(candidate)

    evaluated: dict[WeightVector, Fitness] = {}
    history = []
    while len(evaluated) < budget and population:
        for candidate in population:
            if candidate in evaluated:
                continue
            if len(evaluated) >= budget:
                break
            fitness = score(candidate)
            evaluated[candidate] = fitness
            history.append((candidate, fitness))

        ranked = sorted(evaluated.items(), key=lambda item: item[1].average_margin,
                        reverse=True)
        parent_pool = [weights for weights, _ in ranked[:max(2, len(ranked) // 2)]]
        next_population = [parent_pool[0]]
        seen = set(next_population)
        while len(next_population) < population_size:
            if len(seen) >= _total_weight_vectors():
                break
            first = rng.choice(parent_pool)
            second = rng.choice(parent_pool)
            child = tuple(rng.choice((first[i], second[i])) for i in range(3))
            if rng.random() < 0.8:
                child = _mutate(child, rng)
            if child in seen or child in evaluated:
                child = _random_weights(rng, set(evaluated) | seen)
                if child is None:
                    break
            seen.add(child)
            next_population.append(child)
        population = next_population

    best_weights, best_fitness = max(
        evaluated.items(), key=lambda item: item[1].average_margin,
    )
    return best_weights, best_fitness, history


def _mutate(weights: WeightVector, rng: random.Random) -> WeightVector:
    result = list(weights)
    index = rng.randrange(len(result))
    options = [value for value in WEIGHT_GRIDS[index] if value != result[index]]
    result[index] = rng.choice(options)
    return tuple(result)


def _random_weights(rng: random.Random,
                    excluded: set[WeightVector]) -> Optional[WeightVector]:
    remaining = [
        (open_threes, open_twos, center)
        for open_threes in WEIGHT_GRIDS[0]
        for open_twos in WEIGHT_GRIDS[1]
        for center in WEIGHT_GRIDS[2]
        if (open_threes, open_twos, center) not in excluded
    ]
    return rng.choice(remaining) if remaining else None


def _total_weight_vectors() -> int:
    return len(WEIGHT_GRIDS[0]) * len(WEIGHT_GRIDS[1]) * len(WEIGHT_GRIDS[2])


def validate(weights: WeightVector, k_values: tuple[int, ...], rounds: int,
             seeds: tuple[int, ...]) -> list[tuple[int, Fitness]]:
    """Evaluate a candidate against baseline at each requested validation K."""
    validated = []
    for k in k_values:
        fitness = evaluate_weights(weights, k, rounds, seeds)
        validated.append((k, fitness))
    return validated


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=2,
                        help="training depth (default: 2; validate separately at K=2,3)")
    parser.add_argument("--budget", type=int, default=12,
                        help="unique weight vectors evaluated by each method (default: 12)")
    parser.add_argument("--population", type=int, default=6,
                        help="genetic algorithm population size (default: 6)")
    parser.add_argument("--rounds", type=int, default=1,
                        help="four balanced games per seed and candidate (default: 1)")
    parser.add_argument("--validation-rounds", type=int, default=5,
                        help="four games per seed for final validation (default: 5)")
    parser.add_argument("--validation-ks", type=int, nargs="+", default=[2, 3],
                        help="depths used for final validation (default: 2 3)")
    parser.add_argument("--seed", type=int, default=20261126)
    parser.add_argument("--csv", type=Path,
                        default=Path("experiments/heuristic_tuning.csv"))
    args = parser.parse_args(argv)
    if args.k < 1 or args.budget < 2 or args.population < 2:
        parser.error("K must be positive; budget and population must be at least 2")
    if args.rounds < 1 or args.validation_rounds < 1:
        parser.error("round counts must be at least 1")
    if not args.validation_ks or any(k < 1 for k in args.validation_ks):
        parser.error("every validation K must be a positive integer")

    training_seeds = (args.seed, args.seed + 1)
    validation_seeds = (args.seed + 100, args.seed + 101)
    rng = random.Random(args.seed)
    cache: dict[WeightVector, Fitness] = {}

    def score(weights: WeightVector) -> Fitness:
        if weights not in cache:
            cache[weights] = evaluate_weights(weights, args.k, args.rounds, training_seeds)
        return cache[weights]

    print(
        f"Tuning at K={args.k}: {args.budget} candidates per method, "
        f"{args.rounds * 4 * len(training_seeds)} training games per candidate."
    )
    hill_weights, hill_fitness, hill_history = hill_climb(args.budget, rng, score)
    print(
        f"Hill climbing best: weights=(100, {hill_weights[0]:g}, "
        f"{hill_weights[1]:g}, {hill_weights[2]:g}), "
        f"training margin={hill_fitness.average_margin:+.3f}"
    )
    ga_weights, ga_fitness, ga_history = genetic_search(
        args.budget, args.population, rng, score,
    )
    print(
        f"Genetic algorithm best: weights=(100, {ga_weights[0]:g}, "
        f"{ga_weights[1]:g}, {ga_weights[2]:g}), "
        f"training margin={ga_fitness.average_margin:+.3f}"
    )

    validation_ks = tuple(args.validation_ks)
    print(
        f"\nValidation uses {args.validation_rounds * 4 * len(validation_seeds)} "
        "games per K, with new seeds."
    )
    validation_rows = []
    for method, weights in (("hill_climbing", hill_weights),
                            ("genetic_algorithm", ga_weights)):
        for k, fitness in validate(
            weights, validation_ks, args.validation_rounds, validation_seeds,
        ):
            print(
                f"{method:18} K={k}: {fitness.wins}-{fitness.draws}-{fitness.losses}, "
                f"avg margin={fitness.average_margin:+.3f} over {fitness.games} games"
            )
            validation_rows.append((method, k, weights, fitness))

    rows = []
    for method, history in (("hill_climbing", hill_history),
                            ("genetic_algorithm", ga_history)):
        for index, (weights, fitness) in enumerate(history, start=1):
            rows.append({
                "phase": "training",
                "method": method,
                "candidate": index,
                "k": args.k,
                "open_threes": weights[0],
                "open_twos": weights[1],
                "center_control": weights[2],
                "wins": fitness.wins,
                "draws": fitness.draws,
                "losses": fitness.losses,
                "games": fitness.games,
                "average_score_margin": fitness.average_margin,
            })
    for method, k, weights, fitness in validation_rows:
        rows.append({
            "phase": "validation",
            "method": method,
            "candidate": "best",
            "k": k,
            "open_threes": weights[0],
            "open_twos": weights[1],
            "center_control": weights[2],
            "wins": fitness.wins,
            "draws": fitness.draws,
            "losses": fitness.losses,
            "games": fitness.games,
            "average_score_margin": fitness.average_margin,
        })

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with args.csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote tuning history to {args.csv}")
    print("Compare validation margins before changing the game's default weights.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
