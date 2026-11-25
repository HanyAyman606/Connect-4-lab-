from core.game import Game
from game.player import Player


class ConsoleHumanPlayer(Player):
    def get_move(self, game: Game, state) -> int:

        #get the legal columns from the game
        legal_columns = game.actions(state)

        #repeatedly ask the human to choose a column. The person enters columns starting at 1,
        # but the game uses zero-based columns starting at 0, so the code subtracts one
        #If the input isn’t a number or the column is full or out of range, it asks again.
        while True:
            answer = input(
                f"{self.name}, choose a column (1-{game.rules.cols}): "
            ).strip()
            if not answer.isdecimal():
                print("Enter a column number.")
                continue
            column = int(answer) - 1
            if column not in legal_columns:
                print("That column is full or outside the board. Try again.")
                continue
            return column