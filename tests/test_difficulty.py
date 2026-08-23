"""Difficulty sanity check: Hard should consistently beat Easy. Not part of
the fast test_engine.py suite because it's slow (real thinking time budgets)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import HexBoard
from engine.ai import Difficulty, HexAI


def play_game(size, d1, d2):
    b = HexBoard(size)
    ai = {1: HexAI(1, d1), 2: HexAI(2, d2)}
    turn = 1
    for _ in range(size * size):
        move = ai[turn].choose_move(b)
        b.place(*move, turn)
        if b.check_connection(turn):
            return turn
        turn = 3 - turn
    return 0


if __name__ == "__main__":
    size = 5
    games = 4
    hard_wins = 0
    for i in range(games):
        # alternate who plays first to cancel out first-move advantage
        if i % 2 == 0:
            winner = play_game(size, Difficulty.HARD, Difficulty.EASY)
            hard_player = 1
        else:
            winner = play_game(size, Difficulty.EASY, Difficulty.HARD)
            hard_player = 2
        won = winner == hard_player
        hard_wins += won
        print(f"game {i+1}: hard was player {hard_player}, winner {winner} -> hard {'won' if won else 'lost'}")

    print(f"\nHard won {hard_wins}/{games}")
    assert hard_wins >= games * 0.75, "Hard should beat Easy convincingly"
    print("ok: difficulty ordering looks sane")
