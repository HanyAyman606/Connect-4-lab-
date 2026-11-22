from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.board import Board
from core.disc import Disc
from core.owner import Owner

if TYPE_CHECKING:
    from core.player import Player
    from core.rules import Rules

_OPPONENT = {Owner.HUMAN: Owner.COMPUTER, Owner.COMPUTER: Owner.HUMAN}


@dataclass(frozen=True, slots=True)
class GameState:
    board: Board
    turn: Owner


class Game:
    def __init__(self, human: Player, computer: Player, rules: Rules,
                 first: Owner = Owner.HUMAN) -> None:
        if human.owner is not Owner.HUMAN:
            raise ValueError("the human player must own the HUMAN disc")
        if computer.owner is not Owner.COMPUTER:
            raise ValueError("the computer player must own the COMPUTER disc")
        first = Owner(first)
        if first is Owner.EMPTY:
            raise ValueError("the first player must be HUMAN or COMPUTER")
        self._players = {Owner.HUMAN: human, Owner.COMPUTER: computer}
        self._discs = {Owner.HUMAN: human.disc, Owner.COMPUTER: computer.disc}
        self._rules = rules
        self._first = first

    @property
    def rules(self) -> Rules:
        return self._rules

    @property
    def human(self) -> Player:
        return self._players[Owner.HUMAN]

    @property
    def computer(self) -> Player:
        return self._players[Owner.COMPUTER]

    @property
    def first(self) -> Owner:
        return self._first

    def player_of(self, owner: Owner) -> Player:
        return self._players[owner]

    def disc_of(self, owner: Owner) -> Disc:
        return self._discs[owner]

    @staticmethod
    def opponent(owner: Owner) -> Owner:
        return _OPPONENT[owner]

    def initial_state(self) -> GameState:
        return GameState(Board(self._rules.rows, self._rules.cols), self._first)

    def to_move(self, state: GameState) -> Owner:
        return state.turn

    def actions(self, state: GameState) -> tuple:
        return state.board.valid_moves()

    def result(self, state: GameState, action: int) -> GameState:
        board = state.board.drop(action, self._discs[state.turn])
        return GameState(board, _OPPONENT[state.turn])

    def is_terminal(self, state: GameState) -> bool:
        return state.board.is_full()

    def fours(self, state: GameState, owner: Owner) -> int:
        return self._rules.count_fours(state.board, self._discs[owner])

    def utility(self, state: GameState, owner: Owner = Owner.COMPUTER) -> int:
        return self._rules.score(
            state.board, self._discs[owner], self._discs[_OPPONENT[owner]]
        )

    def winner(self, state: GameState) -> Owner:
        if not self.is_terminal(state):
            raise ValueError("the game is not over")
        difference = self.utility(state)
        if difference > 0:
            return Owner.COMPUTER
        if difference < 0:
            return Owner.HUMAN
        return Owner.EMPTY
