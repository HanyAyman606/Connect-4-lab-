from enum import IntEnum


class Owner(IntEnum):
  

    EMPTY = 0       # nobody: the cell holds no disc yet
    HUMAN = 1       # the human player
    COMPUTER = 2    # the AI player
