
from __future__ import annotations
from core.board import Board
from core.owner import Owner

#Monotonically map any raw heuristic score into the open interval (-1, 1).
def _normalize(raw_score: float, scale: float) -> float:
    return raw_score / (scale + abs(raw_score))

#Count completed windows belonging to one owner.
def _count_owner_fours(board: Board, owner: Owner, windows: tuple) -> int:
    return sum(
        all(board.cell(row, col).owner is owner for row, col in window)
        for window in windows
    )

#Map each board cell to the windows that contain it.
def _index_windows(windows: tuple) -> dict[tuple[int, int], tuple]:
    index: dict[tuple[int, int], list] = {}
    for window in windows:
        for cell in window:
            index.setdefault(cell, []).append(window)
    return {cell: tuple(cell_windows) for cell, cell_windows in index.items()}
