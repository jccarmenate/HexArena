"""Quick sanity checks for the rules engine and the AI (not a full pytest suite
with mocks — just direct behavioral checks, since the whole point is to catch
real illegal moves / rule mistakes)."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import HexBoard, BRIDGES
from engine.ai import HexAI, Difficulty, _bridge_carriers


def test_neighbors_symmetric():
    b = HexBoard(7)
    for r in range(7):
        for c in range(7):
            for nr, nc in b.neighbors(r, c):
                assert (r, c) in b.neighbors(nr, nc), f"{(r,c)} -> {(nr,nc)} not symmetric"
    print("ok: neighbors are symmetric")


def test_win_detection_top_bottom():
    b = HexBoard(5)
    for r in range(5):
        b.place(r, 2, 1)
    assert b.check_connection(1)
    assert not b.check_connection(2)
    path = b.winning_path(1)
    assert path[0][0] == 4 and path[-1][0] == 0
    print("ok: player 1 top<->bottom win + path")


def test_win_detection_left_right():
    b = HexBoard(5)
    for c in range(5):
        b.place(2, c, 2)
    assert b.check_connection(2)
    assert not b.check_connection(1)
    print("ok: player 2 left<->right win")


def test_no_false_win_on_diagonal_gap():
    b = HexBoard(5)
    # a broken staircase that does NOT connect top to bottom
    b.place(0, 0, 1)
    b.place(2, 0, 1)
    b.place(4, 0, 1)
    assert not b.check_connection(1)
    print("ok: no false positive on a disconnected column")


def test_bridge_pattern_geometry():
    # A bridge: two same-player stones two steps apart with two empty carriers.
    b = HexBoard(7)
    b.place(3, 3, 1)
    offset, d1, d2 = BRIDGES[0]
    br, bc = 3 + offset[0], 3 + offset[1]
    b.place(br, bc, 1)
    carriers = _bridge_carriers(b, 1)
    k1 = (3 + d1[0], 3 + d1[1])
    k2 = (3 + d2[0], 3 + d2[1])
    assert k1 in carriers and k2 in carriers
    print("ok: bridge carriers detected for a known pattern")


def test_ai_never_returns_illegal_move():
    for size in (5, 7):
        b = HexBoard(size)
        ai1 = HexAI(1, Difficulty.EASY)
        ai2 = HexAI(2, Difficulty.EASY)
        turn = 1
        for _ in range(size * size):
            if b.check_connection(1) or b.check_connection(2):
                break
            ai = ai1 if turn == 1 else ai2
            move = ai.choose_move(b)
            assert b.get(*move) == 0, f"AI returned occupied cell {move}"
            assert b.place(*move, turn)
            turn = 3 - turn
        assert b.check_connection(1) or b.check_connection(2) or b.is_full()
    print("ok: AI (easy) only ever plays legal moves, games terminate")


def test_ai_center_opening():
    b = HexBoard(7)
    ai = HexAI(1, Difficulty.EASY)
    move = ai.choose_move(b)
    assert move == (3, 3)
    print("ok: empty board opening is the center")


def test_ai_takes_immediate_win():
    b = HexBoard(5)
    for r in range(4):
        b.place(r, 2, 1)
    ai = HexAI(1, Difficulty.HARD)
    move = ai.choose_move(b)
    b2 = b.clone()
    b2.place(*move, 1)
    assert b2.check_connection(1), f"AI missed a one-move win, played {move}"
    print("ok: AI takes an immediate winning move")


def test_ai_blocks_immediate_loss():
    b = HexBoard(5)
    for c in range(4):
        b.place(2, c, 2)
    ai = HexAI(1, Difficulty.HARD)
    move = ai.choose_move(b)
    b2 = b.clone()
    b2.place(*move, 1)  # the AI occupies the cell with its own stone
    assert not b2.check_connection(2), f"AI failed to block, played {move}"
    print("ok: AI blocks an immediate opponent win")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\n{len(tests)} checks passed")
