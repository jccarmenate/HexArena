"""Quick sanity checks for the rules engine and the AI (not a full pytest suite
with mocks — just direct behavioral checks, since the whole point is to catch
real illegal moves / rule mistakes)."""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.board import HexBoard, BRIDGES
from engine.ai import HexAI, Difficulty, _bridge_replies


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


def test_bridge_patterns_are_real_bridges():
    # Each pattern's two carriers must be the only common neighbors of the pair.
    b = HexBoard(9)
    for offset, d1, d2 in BRIDGES:
        a = (4, 4)
        other = (a[0] + offset[0], a[1] + offset[1])
        common = set(b.neighbors(*a)) & set(b.neighbors(*other))
        assert common == {(a[0] + d1[0], a[1] + d1[1]), (a[0] + d2[0], a[1] + d2[1])}, offset
    print("ok: all 6 bridge patterns have exactly the two declared carriers")


def test_bridge_reply_answers_intrusion_in_all_patterns():
    for offset, d1, d2 in BRIDGES:
        a = (4, 4)
        other = (a[0] + offset[0], a[1] + offset[1])
        k1 = (a[0] + d1[0], a[1] + d1[1])
        k2 = (a[0] + d2[0], a[1] + d2[1])
        for hit, expected in ((k1, k2), (k2, k1)):
            b = HexBoard(9)
            b.place(*a, 1)
            b.place(*other, 1)
            b.place(*hit, 2)
            assert _bridge_replies(b, 1, hit) == {expected}, (offset, hit)
    print("ok: intrusion into either carrier of any of the 6 patterns is answered")


def test_bridge_reply_ignores_intact_and_irrelevant_moves():
    b = HexBoard(7)
    b.place(3, 3, 1)
    b.place(1, 4, 1)
    assert _bridge_replies(b, 1, None) == set()          # intact bridge: nothing urgent
    b.place(5, 5, 2)
    assert _bridge_replies(b, 1, (5, 5)) == set()        # opponent played far away
    assert _bridge_replies(b, 2, (5, 5)) == set()        # not the opponent's move from 2's view
    b2 = HexBoard(7)
    b2.place(3, 3, 1)
    b2.place(1, 4, 1)
    b2.place(2, 3, 2)
    b2.place(2, 4, 2)                                    # both carriers taken: bridge is dead
    assert _bridge_replies(b2, 1, (2, 4)) == set()
    print("ok: no reply for intact bridges, distant moves or already-cut bridges")


def test_rollout_policy_answers_intrusion():
    import time
    from engine.ai import DIFFICULTY_PARAMS

    b = HexBoard(7)
    b.place(3, 3, 1)
    b.place(1, 4, 1)
    b.place(2, 3, 2)
    ai = HexAI(1, Difficulty.HARD)
    params = DIFFICULTY_PARAMS[Difficulty.HARD]
    for _ in range(30):
        firsts = ai._rollout(b, 1, time.perf_counter(), params, last_move=(2, 3))[1][0][0]
        assert firsts == (2, 4), firsts
    print("ok: rollout policy always answers a bridge intrusion")


def test_rollout_policy_leaves_intact_bridge_alone():
    # Red bridge (3,3)<->(1,4) with both carriers (2,3),(2,4) empty. The bridge is
    # already safe, so spending the move on a carrier is wasted: the rollout policy
    # must not systematically fill it.
    import time
    from engine.ai import DIFFICULTY_PARAMS

    b = HexBoard(7)
    b.place(3, 3, 1)
    b.place(1, 4, 1)
    ai = HexAI(1, Difficulty.HARD)
    params = DIFFICULTY_PARAMS[Difficulty.HARD]
    firsts = [ai._rollout(b, 1, time.perf_counter(), params)[1][0][0] for _ in range(60)]
    in_carriers = sum(1 for m in firsts if m in ((2, 3), (2, 4)))
    assert in_carriers < len(firsts), "policy filled the intact bridge every single time"
    print("ok: rollout policy does not systematically fill an intact bridge")


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
