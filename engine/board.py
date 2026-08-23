"""Canonical Hex board and rules.

Single source of truth for adjacency, legality and win detection — used by the
AI, the network layer and (indirectly, via the pywebview API) the UI. There is
exactly one neighbor scheme in the whole app, so the AI and the win-checker can
never disagree about what "connected" means.
"""

from __future__ import annotations

from collections import deque
from functools import lru_cache

EMPTY = 0

# Ordered by angle so that consecutive entries are 60 degrees apart. This
# ordering matters for BRIDGES below: a bridge target is the sum of two
# angularly-adjacent directions, "carried" by those same two cells.
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (-1, 0), (-1, 1), (0, 1), (1, 0), (1, -1), (0, -1),
)

BRIDGES: tuple[tuple[tuple[int, int], tuple[int, int], tuple[int, int]], ...] = tuple(
    (
        (DIRECTIONS[i][0] + DIRECTIONS[(i + 1) % 6][0], DIRECTIONS[i][1] + DIRECTIONS[(i + 1) % 6][1]),
        DIRECTIONS[i],
        DIRECTIONS[(i + 1) % 6],
    )
    for i in range(6)
)


class HexBoard:
    """size x size Hex board. Player 1 connects top<->bottom, player 2 left<->right."""

    def __init__(self, size: int):
        if size <= 0:
            raise ValueError("size debe ser positivo")
        self.size = size
        self.cells = [[EMPTY] * size for _ in range(size)]

    def clone(self) -> "HexBoard":
        b = HexBoard(self.size)
        b.cells = [row[:] for row in self.cells]
        return b

    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.size and 0 <= c < self.size

    def get(self, r: int, c: int) -> int:
        return self.cells[r][c]

    def place(self, r: int, c: int, player: int) -> bool:
        if player not in (1, 2):
            raise ValueError("player debe ser 1 o 2")
        if not self.in_bounds(r, c) or self.cells[r][c] != EMPTY:
            return False
        self.cells[r][c] = player
        return True

    def unplace(self, r: int, c: int) -> None:
        self.cells[r][c] = EMPTY

    def legal_moves(self) -> list[tuple[int, int]]:
        n = self.size
        return [(r, c) for r in range(n) for c in range(n) if self.cells[r][c] == EMPTY]

    def is_full(self) -> bool:
        return all(cell != EMPTY for row in self.cells for cell in row)

    def neighbors(self, r: int, c: int) -> list[tuple[int, int]]:
        return _neighbor_table(self.size)[r * self.size + c]

    def check_connection(self, player: int) -> bool:
        return self._bfs(player) is not None

    def winning_path(self, player: int) -> list[tuple[int, int]]:
        parents = self._bfs(player)
        if parents is None:
            return []
        n = self.size
        end = None
        for cell, _ in parents.items():
            r, c = cell
            if (player == 1 and r == n - 1) or (player == 2 and c == n - 1):
                end = cell
                break
        if end is None:
            return []
        path = []
        cur = end
        while cur is not None:
            path.append(cur)
            cur = parents[cur]
        return path

    def _bfs(self, player: int):
        """BFS from the player's starting edge. Returns {cell: parent_or_None}
        reaching the goal edge, or None if not connected."""
        if player not in (1, 2):
            raise ValueError("player debe ser 1 o 2")
        n = self.size
        parents: dict[tuple[int, int], tuple[int, int] | None] = {}
        queue: deque[tuple[int, int]] = deque()

        if player == 1:
            for c in range(n):
                if self.cells[0][c] == 1:
                    parents[(0, c)] = None
                    queue.append((0, c))
        else:
            for r in range(n):
                if self.cells[r][0] == 2:
                    parents[(r, 0)] = None
                    queue.append((r, 0))

        reached = False
        while queue:
            r, c = queue.popleft()
            if (player == 1 and r == n - 1) or (player == 2 and c == n - 1):
                reached = True
                break
            for nr, nc in self.neighbors(r, c):
                if (nr, nc) not in parents and self.cells[nr][nc] == player:
                    parents[(nr, nc)] = (r, c)
                    queue.append((nr, nc))

        return parents if reached else None

    def to_list(self) -> list[list[int]]:
        return [row[:] for row in self.cells]

    @classmethod
    def from_list(cls, cells: list[list[int]]) -> "HexBoard":
        b = cls(len(cells))
        b.cells = [row[:] for row in cells]
        return b


@lru_cache(maxsize=None)
def _neighbor_table(size: int) -> tuple[tuple[tuple[int, int], ...], ...]:
    table = []
    for r in range(size):
        for c in range(size):
            table.append(tuple(
                (r + dr, c + dc)
                for dr, dc in DIRECTIONS
                if 0 <= r + dr < size and 0 <= c + dc < size
            ))
    return tuple(table)
