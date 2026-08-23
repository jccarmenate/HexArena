"""pywebview bridge: exposes game control as plain methods JS can call via
window.pywebview.api.*, and pushes async updates (AI thinking, moves arriving
over the network) back into the page with window.evaluate_js.
"""

from __future__ import annotations

import json
import threading
from typing import Optional

from . import network
from .ai import Difficulty, HexAI
from .board import HexBoard


class Api:
    def __init__(self):
        self._window = None
        self._lock = threading.Lock()

        self._mode: Optional[str] = None  # "local" | "ai" | "host" | "client"
        self._board: Optional[HexBoard] = None
        self._turn = 1
        self._winner: Optional[int] = None
        self._history: list[tuple[int, int, int]] = []  # (player, row, col)
        self._human_player: Optional[int] = None

        self._ai: Optional[HexAI] = None
        self._host: Optional[network.HostServer] = None
        self._client: Optional[network.ClientConnection] = None

    def bind(self, window) -> None:
        self._window = window

    # ------------------------------------------------------------------
    # state helpers
    def _state_payload(self, extra: Optional[dict] = None) -> dict:
        payload = {
            "mode": self._mode,
            "size": self._board.size if self._board else None,
            "board": self._board.to_list() if self._board else None,
            "turn": self._turn,
            "winner": self._winner,
            "winPath": self._board.winning_path(self._winner) if self._board and self._winner else [],
            "history": [{"player": p, "row": r, "col": c} for p, r, c in self._history],
            "humanPlayer": self._human_player,
        }
        if extra:
            payload.update(extra)
        return payload

    def _push(self, event: str, **extra) -> None:
        if self._window is None:
            return
        payload = self._state_payload(extra)
        payload["event"] = event
        self._window.evaluate_js(f"window.onEngineEvent({json.dumps(payload)})")

    def _cleanup_network(self) -> None:
        if self._host is not None:
            self._host.close()
            self._host = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def get_state(self) -> dict:
        return self._state_payload()

    def leave_game(self) -> dict:
        self._cleanup_network()
        self._mode = None
        self._board = None
        self._winner = None
        self._history = []
        self._human_player = None
        return self._state_payload()

    # ------------------------------------------------------------------
    # starting games
    def new_local_game(self, size) -> dict:
        self._cleanup_network()
        self._mode = "local"
        self._board = HexBoard(int(size))
        self._turn = 1
        self._winner = None
        self._history = []
        self._human_player = None
        return self._state_payload()

    def new_ai_game(self, size, difficulty, human_player) -> dict:
        self._cleanup_network()
        self._mode = "ai"
        self._board = HexBoard(int(size))
        self._turn = 1
        self._winner = None
        self._history = []
        self._human_player = int(human_player)
        self._ai = HexAI(3 - self._human_player, Difficulty(difficulty))
        state = self._state_payload()
        if self._human_player != 1:
            self._trigger_ai_move()
        return state

    def host_network_game(self, size) -> dict:
        self._cleanup_network()
        self._mode = "host"
        self._human_player = network.HOST_PLAYER
        self._history = []
        self._winner = None
        self._turn = 1

        self._host = network.HostServer(
            int(size),
            on_state=self._on_network_state,
            on_peer_connected=lambda: self._push("peer_connected"),
            on_disconnect=lambda msg: self._push("peer_disconnected", message=msg),
        )
        ip, port = self._host.start()
        self._board = self._host.board
        return {**self._state_payload(), "ip": ip, "port": port}

    def join_network_game(self, ip: str, port) -> dict:
        self._cleanup_network()
        self._mode = "client"
        self._history = []
        self._winner = None

        def on_ready(size: int, your_player: int) -> None:
            self._board = HexBoard(int(size))
            self._turn = 1
            self._human_player = your_player
            self._push("joined")

        self._client = network.ClientConnection(
            ip,
            int(port),
            on_ready=on_ready,
            on_state=self._on_network_state,
            on_disconnect=lambda msg: self._push("peer_disconnected", message=msg),
        )
        try:
            self._client.connect()
        except OSError as exc:
            self._mode = None
            return {"error": str(exc)}
        return {"ok": True}

    def _on_network_state(self, state: dict) -> None:
        self._board = HexBoard.from_list(state["board"])
        self._turn = state["turn"]
        self._winner = state["winner"]
        self._push("state")

    # ------------------------------------------------------------------
    # moves
    def play_move(self, row, col) -> dict:
        row, col = int(row), int(col)
        if self._mode == "local":
            return self._play_local(row, col)
        if self._mode == "ai":
            return self._play_ai(row, col)
        if self._mode == "host" and self._host is not None:
            self._host.submit_local_move(row, col)
            return self._state_payload()
        if self._mode == "client" and self._client is not None:
            self._client.submit_move(row, col)
            return {"pending": True}
        return self._state_payload()

    def _play_local(self, row: int, col: int) -> dict:
        if self._winner is not None or self._board is None:
            return self._state_payload()
        if not self._board.place(row, col, self._turn):
            return self._state_payload()
        self._history.append((self._turn, row, col))
        if self._board.check_connection(self._turn):
            self._winner = self._turn
        else:
            self._turn = 3 - self._turn
        return self._state_payload()

    def _play_ai(self, row: int, col: int) -> dict:
        if self._winner is not None or self._board is None or self._turn != self._human_player:
            return self._state_payload()
        if not self._board.place(row, col, self._turn):
            return self._state_payload()
        self._history.append((self._turn, row, col))
        if self._board.check_connection(self._turn):
            self._winner = self._turn
            return self._state_payload()
        self._turn = 3 - self._turn
        self._trigger_ai_move()
        return self._state_payload()

    def _trigger_ai_move(self) -> None:
        threading.Thread(target=self._ai_move_worker, daemon=True).start()

    def _ai_move_worker(self) -> None:
        self._push("thinking")
        board, ai = self._board, self._ai
        move = ai.choose_move(board.clone())
        with self._lock:
            if self._board is not board or self._winner is not None:
                return  # a new game started while the AI was thinking
            self._board.place(*move, ai.player)
            self._history.append((ai.player, move[0], move[1]))
            if self._board.check_connection(ai.player):
                self._winner = ai.player
            else:
                self._turn = self._human_player
        self._push("ai_move")

    def undo(self) -> dict:
        if self._mode not in ("local", "ai") or self._board is None or not self._history:
            return self._state_payload()
        steps = 2 if self._mode == "ai" and len(self._history) >= 2 else 1
        for _ in range(steps):
            if not self._history:
                break
            _player, r, c = self._history.pop()
            self._board.unplace(r, c)
        self._winner = None
        if self._mode == "ai":
            self._turn = self._human_player
        else:
            self._turn = 3 - self._history[-1][0] if self._history else 1
        return self._state_payload()
