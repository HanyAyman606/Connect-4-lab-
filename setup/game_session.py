"""Game session: runs the game flow one turn at a time (works for console and GUI)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.game import Game, GameState
from core.owner import Owner
from setup.session_settings import SessionSettings
from tree_essentials import PrintOptions, SearchResult, TreePrinter


@dataclass(frozen=True, slots=True)
class TurnRecord:
    """History entry for one completed move in a match."""

    turn_number: int
    owner: Owner
    column: int
    row: int
    human_fours: int
    computer_fours: int
    state_after: GameState
    search_result: Optional[SearchResult] = None


class GameSession:
    """Stateful match controller wrapping immutable ``GameState`` transitions."""

    def __init__(self, game: Game, settings: SessionSettings) -> None:
        self._game = game
        self._settings = settings
        self._state: GameState = game.initial_state()
        self._history: list[TurnRecord] = []

    @property
    def game(self) -> Game:
        return self._game

    @property
    def settings(self) -> SessionSettings:
        return self._settings

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def history(self) -> tuple[TurnRecord, ...]:
        return tuple(self._history)

    @property
    def turn_count(self) -> int:
        return len(self._history)

    @property
    def max_turns(self) -> int:
        return self._game.rules.rows * self._game.rules.cols

    @property
    def is_over(self) -> bool:
        return self._game.is_terminal(self._state)

    @property
    def to_move(self) -> Owner:
        return self._game.to_move(self._state)

    @property
    def human_fours(self) -> int:
        return self._game.fours(self._state, Owner.HUMAN)

    @property
    def computer_fours(self) -> int:
        return self._game.fours(self._state, Owner.COMPUTER)

    def apply_human_move(self, column: int) -> TurnRecord:
        """Apply a validated human drop and record the resulting state."""
        if self.is_over:
            raise RuntimeError("the board is already full")
        if self.to_move is not Owner.HUMAN:
            raise RuntimeError("it is not the human player's turn")
        landing_row = self._state.board.lowest_empty_row(column)
        next_state = self._game.result(self._state, column)
        self._state = next_state
        record = TurnRecord(
            turn_number=len(self._history) + 1,
            owner=Owner.HUMAN,
            column=column,
            row=landing_row,
            human_fours=self.human_fours,
            computer_fours=self.computer_fours,
            state_after=next_state,
            search_result=None,
        )
        self._history.append(record)
        return record

    def apply_ai_result(self, column: int, search_result: SearchResult) -> TurnRecord:
        """Apply a completed AI search move and print the mandatory console trace."""
        if self.is_over:
            raise RuntimeError("the board is already full")
        if self.to_move is not Owner.COMPUTER:
            raise RuntimeError("it is not the computer player's turn")
        landing_row = self._state.board.lowest_empty_row(column)
        next_state = self._game.result(self._state, column)
        self._state = next_state

        if self._settings.console_trace:
            from ui.tree_trace_engine import render_detailed_console_report

            max_lines = 260 if self._settings.console_max_depth is None else 120
            print(
                f"\n=== Turn {len(self._history) + 1} | {self._settings.devil_name} "
                f"(K={self._settings.k}, heuristic={self._settings.heuristic_key}) ==="
            )
            print("Current Board Before AI Move:")
            print(self._state.board)
            print(
                render_detailed_console_report(
                    search_result,
                    self._settings.heuristic_key,
                    max_tree_lines=max_lines,
                    max_table_rows=65,
                )
            )

        record = TurnRecord(
            turn_number=len(self._history) + 1,
            owner=Owner.COMPUTER,
            column=column,
            row=landing_row,
            human_fours=self.human_fours,
            computer_fours=self.computer_fours,
            state_after=next_state,
            search_result=search_result,
        )
        self._history.append(record)
        return record
