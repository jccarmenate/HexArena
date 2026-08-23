"""Hex AI: UCT-MCTS with RAVE, Dijkstra-biased rollouts and bridge awareness.

This merges the two AI variants that used to live in the course project
(`solution.py`'s SmartPlayer and `enemy_player.py`'s EnemyPlayer) into one
engine, parameterized by Difficulty instead of being two half-duplicated
classes. It always reasons about the board through `HexBoard`, so there is no
risk of the adjacency mismatch that existed between the old `solution.py`
(constant 6-direction neighbors) and the course's `board.py` (even-r offset
neighbors).
"""

from __future__ import annotations

import heapq
import math
import random
import time
from dataclasses import dataclass
from enum import Enum

from .board import BRIDGES, HexBoard

INF = 10 ** 9


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class DifficultyParams:
    time_limit: float       # seconds of thinking time per move
    dijkstra_bias: float    # probability a rollout move is chosen greedily by distance
    use_rave: bool          # blend RAVE estimate into the tree policy
    use_bridges: bool       # bias expansion/rollout towards bridge-critical cells
    top_k: int              # sample among the top-K most-visited root children (1 = always best)


DIFFICULTY_PARAMS: dict[Difficulty, DifficultyParams] = {
    Difficulty.EASY: DifficultyParams(
        time_limit=0.6, dijkstra_bias=0.0, use_rave=False, use_bridges=False, top_k=3,
    ),
    Difficulty.MEDIUM: DifficultyParams(
        time_limit=2.0, dijkstra_bias=0.35, use_rave=True, use_bridges=False, top_k=1,
    ),
    Difficulty.HARD: DifficultyParams(
        time_limit=4.5, dijkstra_bias=0.6, use_rave=True, use_bridges=True, top_k=1,
    ),
}

UCT_C = 1.0
RAVE_K = 250.0


class _Node:
    __slots__ = ("move", "parent", "player", "children", "visits", "wins", "rave_v", "rave_w", "untried")

    def __init__(self, move, parent, player, untried):
        self.move = move
        self.parent = parent
        self.player = player            # player who just moved to reach this node
        self.children: list["_Node"] = []
        self.visits = 0
        self.wins = 0
        self.rave_v: dict[tuple[int, int], int] = {}
        self.rave_w: dict[tuple[int, int], int] = {}
        self.untried = untried

    def fully_expanded(self) -> bool:
        return not self.untried

    def best_child(self, use_rave: bool) -> "_Node":
        log_n = math.log(self.visits)
        best, best_score = self.children[0], -math.inf
        for child in self.children:
            q = child.wins / child.visits
            u = UCT_C * math.sqrt(log_n / child.visits)
            if use_rave:
                rv = self.rave_v.get(child.move, 0)
                rq = self.rave_w.get(child.move, 0) / rv if rv else 0.0
                beta = math.sqrt(RAVE_K / (RAVE_K + 3.0 * child.visits))
                score = (1 - beta) * q + beta * rq + u
            else:
                score = q + u
            if score > best_score:
                best_score, best = score, child
        return best


class HexAI:
    def __init__(self, player: int, difficulty: Difficulty = Difficulty.MEDIUM):
        self.player = player
        self.difficulty = difficulty
        self.params = DIFFICULTY_PARAMS[difficulty]
        self._rng = random.Random()

    def choose_move(self, board: HexBoard) -> tuple[int, int]:
        start = time.perf_counter()
        opp = 3 - self.player
        legal = board.legal_moves()
        if not legal:
            return (0, 0)
        if len(legal) == board.size * board.size:
            c = board.size // 2
            return (c, c)

        cands = _candidates(board, legal)

        for m in cands:
            b = board.clone()
            b.place(*m, self.player)
            if b.check_connection(self.player):
                return m
        for m in cands:
            b = board.clone()
            b.place(*m, opp)
            if b.check_connection(opp):
                return m

        return self._mcts(board, cands, start)

    def _mcts(self, board: HexBoard, cands: list[tuple[int, int]], start: float) -> tuple[int, int]:
        params = self.params
        # Iteration cap purely as a safety net; the real cutoff is the time budget.
        budget = 20000 if board.size <= 7 else 9000 if board.size <= 11 else 3000 if board.size <= 16 else 1000
        root = _Node(None, None, 3 - self.player, list(cands))

        iterations = 0
        while iterations < budget and time.perf_counter() - start < params.time_limit:
            self._playout(root, board, self.player, start, params)
            iterations += 1

        if not root.children:
            return cands[0]

        ranked = sorted(root.children, key=lambda c: c.visits, reverse=True)
        top = ranked[: max(1, params.top_k)]
        return self._rng.choice(top).move

    def _playout(self, root: _Node, board: HexBoard, root_player: int, start: float, params: DifficultyParams) -> None:
        node = root
        b = board.clone()
        current = root_player
        path = [node]

        while node.children and node.fully_expanded():
            node = node.best_child(params.use_rave)
            b.place(*node.move, current)
            current = 3 - current
            path.append(node)
            if b.check_connection(node.player):
                break

        if node.untried and not b.check_connection(1) and not b.check_connection(2):
            move = self._pick_expansion(b, node.untried, current, params)
            node.untried.remove(move)
            b.place(*move, current)
            child = _Node(move, node, current, _candidates(b, b.legal_moves()))
            node.children.append(child)
            node = child
            path.append(node)
            current = 3 - current

        winner, rollout_moves = self._rollout(b, current, start, params)

        for n in path:
            n.visits += 1
            if winner == n.player:
                n.wins += 1
        if params.use_rave:
            for i, n in enumerate(path[:-1]):
                mover = path[i + 1].player
                for mv, mp in rollout_moves:
                    if mp == mover:
                        n.rave_v[mv] = n.rave_v.get(mv, 0) + 1
                        if winner == mover:
                            n.rave_w[mv] = n.rave_w.get(mv, 0) + 1

    def _pick_expansion(self, board: HexBoard, untried: list[tuple[int, int]], player: int, params: DifficultyParams) -> tuple[int, int]:
        if params.use_bridges:
            carriers = _bridge_carriers(board, player) | _bridge_carriers(board, 3 - player)
            preferred = [m for m in untried if m in carriers]
            if preferred:
                untried = preferred
        if params.dijkstra_bias and self._rng.random() < params.dijkstra_bias:
            return min(untried, key=lambda m: _dijkstra_after(board, m, player))
        return self._rng.choice(untried)

    def _rollout(self, board: HexBoard, current: int, start: float, params: DifficultyParams):
        b = board.clone()
        played: list[tuple[tuple[int, int], int]] = []
        player = current
        while True:
            if b.check_connection(1):
                return 1, played
            if b.check_connection(2):
                return 2, played
            if time.perf_counter() - start >= params.time_limit + 1.0:
                return 0, played  # hard safety valve, should not normally trigger
            cands = _candidates(b, b.legal_moves())
            if not cands:
                return 0, played

            move = None
            if params.use_bridges:
                carriers = _bridge_carriers(b, player)
                threatened = [m for m in cands if m in carriers]
                if threatened:
                    move = self._rng.choice(threatened)
            if move is None and params.dijkstra_bias and self._rng.random() < params.dijkstra_bias:
                move = min(cands, key=lambda m: _dijkstra_after(b, m, player))
            if move is None:
                move = self._rng.choice(cands)

            b.place(*move, player)
            played.append((move, player))
            player = 3 - player


def _candidates(board: HexBoard, legal: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for r in range(board.size):
        for c in range(board.size):
            if board.get(r, c):
                for nr, nc in board.neighbors(r, c):
                    if board.get(nr, nc) == 0:
                        out.add((nr, nc))
    return list(out) if out else legal


def _bridge_carriers(board: HexBoard, player: int) -> set[tuple[int, int]]:
    carriers: set[tuple[int, int]] = set()
    n = board.size
    for r in range(n):
        for c in range(n):
            if board.get(r, c) != player:
                continue
            for (dr, dc), (d1r, d1c), (d2r, d2c) in BRIDGES:
                br, bc = r + dr, c + dc
                if not board.in_bounds(br, bc) or board.get(br, bc) != player:
                    continue
                k1, k2 = (r + d1r, c + d1c), (r + d2r, c + d2c)
                if board.in_bounds(*k1) and board.in_bounds(*k2) and board.get(*k1) == 0 and board.get(*k2) == 0:
                    carriers.add(k1)
                    carriers.add(k2)
    return carriers


def _dijkstra_after(board: HexBoard, move: tuple[int, int], player: int) -> float:
    b = board.clone()
    b.place(*move, player)
    return _dijkstra(b, player)


def _dijkstra(board: HexBoard, player: int) -> float:
    n = board.size
    dist = [INF] * (n * n)
    pq: list[tuple[int, int]] = []

    if player == 1:
        for c in range(n):
            v = board.get(0, c)
            cost = 0 if v == player else (1 if v == 0 else INF)
            if cost < INF:
                dist[c] = cost
                heapq.heappush(pq, (cost, c))
        goal = lambda r, c: r == n - 1
    else:
        for r in range(n):
            v = board.get(r, 0)
            cost = 0 if v == player else (1 if v == 0 else INF)
            if cost < INF:
                dist[r * n] = cost
                heapq.heappush(pq, (cost, r * n))
        goal = lambda r, c: c == n - 1

    while pq:
        d, idx = heapq.heappop(pq)
        if d > dist[idx]:
            continue
        r, c = divmod(idx, n)
        if goal(r, c):
            return float(d)
        for nr, nc in board.neighbors(r, c):
            v = board.get(nr, nc)
            step = 0 if v == player else (1 if v == 0 else INF)
            if step >= INF:
                continue
            nd = d + step
            ni = nr * n + nc
            if nd < dist[ni]:
                dist[ni] = nd
                heapq.heappush(pq, (nd, ni))
    return 1000.0
