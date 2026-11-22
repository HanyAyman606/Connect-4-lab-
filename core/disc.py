from __future__ import annotations

from core.owner import Owner

__all__ = ["Disc", "EMPTY_DISC"]

# Characters used when a board is printed in the console.
_SYMBOLS = {Owner.EMPTY: ".", Owner.HUMAN: "X", Owner.COMPUTER: "O"}


class Disc:

    __slots__ = ("_owner", "_color")

    _registry: dict = {}

    def __new__(cls, owner: int, color: str | None = None) -> "Disc":
        """Return the shared disc for this key, creating it the first time."""
        owner = Owner(owner)                  # accepts 1 or Owner.HUMAN
        cls._validate(owner, color)

        key = (owner, color)
        disc = cls._registry.get(key)
        if disc is None:
            disc = super().__new__(cls)
            # object.__setattr__ bypasses the immutability guard below.
            object.__setattr__(disc, "_owner", owner)
            object.__setattr__(disc, "_color", color)
            cls._registry[key] = disc
        return disc

    @staticmethod
    def _validate(owner: Owner, color: str | None) -> None:
        """The empty disc has no color; a player's disc needs a color key."""
        if owner is Owner.EMPTY:
            if color is not None:
                raise ValueError("The empty disc cannot have a color")
        elif not isinstance(color, str) or not color:
            raise ValueError("A player's disc needs a non-empty color key")

    # ------------------------------------------------------------------ data
    @property
    def owner(self) -> Owner:
        return self._owner

    @property
    def color(self) -> str | None:
        return self._color

    @property
    def key(self) -> tuple:
        return (self._owner, self._color)

    @property
    def is_empty(self) -> bool:
        return self._owner is Owner.EMPTY

    @property
    def symbol(self) -> str:
        return _SYMBOLS[self._owner]

    # --------------------------------------------------------------- queries
    def belongs_to(self, owner: int) -> bool:
        return self._owner == owner

    # ----------------------------------------------------------- immutability
    def __setattr__(self, name, value):
        raise AttributeError("Disc is immutable")

    def __delattr__(self, name):
        raise AttributeError("Disc is immutable")

    # -------------------------------------------------- copying and pickling
    def __reduce__(self):
      
        return (Disc, (int(self._owner), self._color))

    def __copy__(self) -> "Disc":
        return self                    # shared and immutable: no copy needed

    def __deepcopy__(self, memo) -> "Disc":
        return self

    # --------------------------------------------------------------- display
    def __repr__(self) -> str:
        return f"Disc({self._owner.name}, {self._color!r})"

    def __str__(self) -> str:
        return self.symbol


EMPTY_DISC = Disc(Owner.EMPTY)
