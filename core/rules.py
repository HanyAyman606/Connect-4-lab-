from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.board import Board
    from core.disc import Disc

DIRECTIONS = ((0, 1), (1, 0), (1, 1), (1, -1))


@lru_cache(maxsize=None)
def build_windows(rows: int, cols: int, length: int) -> tuple:
    windows = []
    for row in range(rows):
        for col in range(cols):
            for d_row, d_col in DIRECTIONS:
                end_row = row + (length - 1) * d_row
                end_col = col + (length - 1) * d_col
                if 0 <= end_row < rows and 0 <= end_col < cols:
                    windows.append(
                        tuple((row + i * d_row, col + i * d_col) for i in range(length))
                    )
    return tuple(windows)


class Rules:
    __slots__ = ("_rows", "_cols", "_connect_length", "_windows")

    def __init__(self, rows: int, cols: int, connect_length: int = 4) -> None:
        if not (isinstance(rows, int) and isinstance(cols, int) and rows >= 1 and cols >= 1):
            raise ValueError("rows and cols must be positive integers")
        if not (isinstance(connect_length, int) and 2 <= connect_length <= max(rows, cols)):
            raise ValueError("connect_length must fit inside the board")
        self._rows = rows
        self._cols = cols
        self._connect_length = connect_length
        self._windows = build_windows(rows, cols, connect_length)

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def connect_length(self) -> int:
        return self._connect_length

    @property
    def windows(self) -> tuple:
        return self._windows

    def count_fours(self, board: Board, disc: Disc) -> int:
        if disc.is_empty:
            raise ValueError("cannot count connected-fours of the empty disc")
        grid = board.grid
        return sum(
            1 for window in self._windows
            if all(grid[row][col] is disc for row, col in window)
        )

    def score(self, board: Board, disc: Disc, opponent_disc: Disc) -> int:
        return self.count_fours(board, disc) - self.count_fours(board, opponent_disc)
