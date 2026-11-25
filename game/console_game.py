"""Console human-versus-computer game entry point.

Run with ``python3 -m game.console_game``. The human always moves first, and the game
continues until the board is full, as required by the assignment rules.
"""

from __future__ import annotations

from game.ai_player import AIPlayer
from algorithms.alpha_beta import AlphaBetaSearcher
from heuristics.evaluation import DIFFICULTY_MODELS
from core.disc import Disc
from core.game import Game
from core.owner import Owner
from core.rules import Rules
from tree_essentials import TreePrinter
from tree_essentials.search_limits import InvalidKError, assess_k, parse_k
from game.human_player import ConsoleHumanPlayer




#This asks for K before the game starts.
def _prompt_k() -> int:
    while True:
        try:

            #parse_k accepts only a positive whole number.
            k = parse_k(input("Choose search depth K (try 2-4): "))

        #If K is invalid, the function displays the error and prompts again.
        except InvalidKError as error:
            print(f"Invalid K: {error}")
            continue

        #estimates the search size and displays a warning for large K.
        assessment = assess_k(k, columns=7, moves_left=6 * 7)
        print(assessment.message)

        #return the validated K.
        return k

#this function picks how the board is evaluated,while K sets how far alpha-beta searches.
def _prompt_difficulty():

    #display Easy, Intermediate, and Hard
    choices = (
        ("easy", "Scoring-opportunity heuristic"),
        ("intermediate", "Gravity-aware heuristic"),
        ("hard", "Window heuristic"),
    )
    print("\nChoose AI difficulty:")
    for index, (key, label) in enumerate(choices, start=1):
        print(f"  {index}. {key.title()} — {label}")

    while True:
        answer = input("Choose difficulty [1-3, default 3]: ").strip()

        #Pressing Enter selects Hard by default
        if not answer:
            answer = "3"
        if answer.isdecimal() and 1 <= int(answer) <= len(choices):
            key, label = choices[int(answer) - 1]
            print(f"Selected {key.title()} ({label}).")
            return DIFFICULTY_MODELS[key]
        print(f"Enter a number from 1 to {len(choices)}.")

#print the column numbers,board, and symbol legend.
def _show_board(game: Game, state) -> None:
    print("\n" + " ".join(str(column + 1) for column in range(game.rules.cols)))
    print(state.board)
    print("X = human, O = computer")


def run_console_game() -> None:
    """Play one complete human-versus-computer game in the terminal."""

    print("Connect Four: score connected-four windows until the board is full.")

    #ask for K and the difficulty.
    k = _prompt_k()
    evaluator = _prompt_difficulty()

    #create the 6-row, 7-column board with four-cell scoring windows.
    rules = Rules(rows=6, cols=7, connect_length=4)

    #create the human and AI players.The AI gets an AlphaBetaSearcher configured with the selected evaluator
    #and the chosen K.
    human = ConsoleHumanPlayer(Disc(Owner.HUMAN, "human"), "Human")
    computer = AIPlayer(
        Disc(Owner.COMPUTER, "computer"),
        AlphaBetaSearcher(evaluator),
        k,
    )

    #It creates the Game, with the human moving first.
    game = Game(human, computer, rules, first=Owner.HUMAN)
    state = game.initial_state()
    tree_printer = TreePrinter()

    #It loops until the board is full:-
    while not game.is_terminal(state):

        #Displays the board.
        _show_board(game, state)

        #Gets a move from the current player.
        owner = game.to_move(state)
        player = game.player_of(owner)

        if owner is Owner.COMPUTER:
            print(f"\n{player.name} is searching (K={k})...")

        column = player.get_move(game, state)

        #After a computer move, prints the search tree from computer.last_search.
        if owner is Owner.COMPUTER:
            search_result = computer.last_search
            if search_result is not None:
                tree_printer.show(search_result)
            print(f"Computer chooses column {column + 1}.")

        #Applies the move to get the next game state.
        state = game.result(state, column)

    _show_board(game, state)

    #At the end, it counts each player’s completed four-cell windows and prints the winner or a draw.
    human_fours = game.fours(state, Owner.HUMAN)
    computer_fours = game.fours(state, Owner.COMPUTER)
    print("\nFinal score (connected-four windows):")
    print(f"Human: {human_fours}  |  Computer: {computer_fours}")

    winner = game.winner(state)
    if winner is Owner.EMPTY:
        print("The game is a draw.")
    elif winner is Owner.HUMAN:
        print("You win!")
    else:
        print("The computer wins.")


def main() -> int:
    try:
        run_console_game()
    except (EOFError, KeyboardInterrupt):
        print("\nGame ended.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
