from core.board import Board
from core.disc import Disc, EMPTY_DISC
from core.owner import Owner
from core.player import Player

RED = Disc(Owner.HUMAN, "red")
YELLOW = Disc(Owner.COMPUTER, "yellow")


class ScriptedPlayer(Player):
    def get_move(self, game, state):
        return game.actions(state)[0]


def board_from(lines):
    symbols = {".": EMPTY_DISC, "X": RED, "O": YELLOW}
    grid = tuple(tuple(symbols[ch] for ch in line) for line in lines)
    return Board(len(grid), len(grid[0]), grid)
