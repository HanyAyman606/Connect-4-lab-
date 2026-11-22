from __future__ import annotations

from core.disc import Disc, EMPTY_DISC


class InvalidMoveError(ValueError):
    pass


class Board:
    __slots__ = ("_rows", "_cols", "_grid")

    def __init__(self, rows: int, cols: int, grid: tuple | None = None) -> None:
        if grid is None:
            if not (isinstance(rows, int) and isinstance(cols, int) and rows >= 1 and cols >= 1):
                raise ValueError("rows and cols must be positive integers")
            grid = tuple(tuple(EMPTY_DISC for _ in range(cols)) for _ in range(rows))
        self._rows = rows
        self._cols = cols
        self._grid = grid

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def grid(self) -> tuple:
        return self._grid

    def cell(self, row: int, col: int) -> Disc:
        return self._grid[row][col]

    def valid_moves(self) -> tuple:
        return tuple(col for col, cell in enumerate(self._grid[0]) if cell is EMPTY_DISC)

    def is_valid_move(self, col: int) -> bool:
        return 0 <= col < self._cols and self._grid[0][col] is EMPTY_DISC

    def is_full(self) -> bool:
        return all(cell is not EMPTY_DISC for cell in self._grid[0])

    def lowest_empty_row(self, col: int) -> int:
        if not 0 <= col < self._cols:
            raise InvalidMoveError(f"column {col} is outside the board")
        for row in range(self._rows - 1, -1, -1):
            if self._grid[row][col] is EMPTY_DISC:
                return row
        raise InvalidMoveError(f"column {col} is full")

    def drop(self, col: int, disc: Disc) -> Board:
        if disc.is_empty:
            raise InvalidMoveError("the empty disc cannot be dropped")
        row = self.lowest_empty_row(col)
        old_row = self._grid[row]
        new_row = old_row[:col] + (disc,) + old_row[col + 1:]
        new_grid = self._grid[:row] + (new_row,) + self._grid[row + 1:]
        return Board(self._rows, self._cols, new_grid)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board):
            return NotImplemented
        return self._grid == other._grid

    def __hash__(self) -> int:
        return hash(self._grid)

    def __str__(self) -> str:
        return "\n".join(" ".join(cell.symbol for cell in row) for row in self._grid)

    def __repr__(self) -> str:
        return f"Board({self._rows}x{self._cols})"
