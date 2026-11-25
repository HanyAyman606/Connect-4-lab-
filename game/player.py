from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from core.disc import Disc
from core.owner import Owner

if TYPE_CHECKING:
    from core.game import Game, GameState


class Player(ABC):
    def __init__(self, disc: Disc, name: str) -> None:
        if disc.is_empty:
            raise ValueError("a player needs a non-empty disc")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("a player needs a name")
        self._disc = disc
        self._name = name.strip()

    @property
    def disc(self) -> Disc:
        return self._disc

    @property
    def owner(self) -> Owner:
        return self._disc.owner

    @property
    def color(self) -> str:
        return self._disc.color

    @property
    def name(self) -> str:
        return self._name

    @abstractmethod
    def get_move(self, game: Game, state: GameState) -> int:
        ...

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._name!r}, {self._disc!r})"
