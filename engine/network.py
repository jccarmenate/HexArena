"""LAN multiplayer: one host, one client, plain TCP with line-delimited JSON.

The host is always the authority: it owns the real `HexBoard`, validates every
move (turn order + legality) whether it came from its own UI or from the
network, and broadcasts the resulting state to the client after each move.
The client never runs its own rules engine — it only ever renders whatever
state the host last confirmed, so the two sides cannot desync.

Scope: LAN / direct IP only. No matchmaking, no NAT traversal — for play across
the internet the host would have to forward the port themselves.
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable, Optional

from .board import HexBoard

HOST_PLAYER = 1
CLIENT_PLAYER = 2
DEFAULT_PORT = 51137


def local_ip() -> str:
    """Best-effort LAN IP to show the host user (no packets actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def _send(sock: socket.socket, obj: dict) -> None:
    sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))


def _read_lines(sock: socket.socket):
    buf = b""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                yield json.loads(line.decode("utf-8"))


class HostServer:
    def __init__(
        self,
        size: int,
        on_state: Callable[[dict], None],
        on_peer_connected: Callable[[], None],
        on_disconnect: Callable[[str], None],
        port: int = DEFAULT_PORT,
    ):
        self.board = HexBoard(size)
        self.turn = 1
        self.winner: Optional[int] = None
        self._on_state = on_state
        self._on_peer_connected = on_peer_connected
        self._on_disconnect = on_disconnect
        self._port = port
        self._server_sock: Optional[socket.socket] = None
        self._conn: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def start(self) -> tuple[str, int]:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self._port))
        srv.listen(1)
        self._server_sock = srv
        self._port = srv.getsockname()[1]
        threading.Thread(target=self._accept_loop, daemon=True).start()
        return local_ip(), self._port

    def _accept_loop(self) -> None:
        assert self._server_sock is not None
        try:
            conn, _addr = self._server_sock.accept()
        except OSError:
            return
        self._conn = conn
        _send(conn, {"type": "hello", "size": self.board.size, "your_player": CLIENT_PLAYER})
        self._on_peer_connected()
        self._broadcast_state()
        try:
            for msg in _read_lines(conn):
                if msg.get("type") == "move":
                    self._apply(CLIENT_PLAYER, msg["row"], msg["col"])
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        finally:
            self._conn = None
            self._on_disconnect("El otro jugador se desconectó.")

    def submit_local_move(self, row: int, col: int) -> bool:
        return self._apply(HOST_PLAYER, row, col)

    def _apply(self, player: int, row: int, col: int) -> bool:
        with self._lock:
            if self.winner is not None or self.turn != player:
                return False
            if not self.board.place(row, col, player):
                return False
            if self.board.check_connection(player):
                self.winner = player
            else:
                self.turn = 3 - player
        self._broadcast_state()
        return True

    def _broadcast_state(self) -> None:
        state = {
            "type": "state",
            "board": self.board.to_list(),
            "turn": self.turn,
            "winner": self.winner,
        }
        self._on_state(state)
        if self._conn is not None:
            try:
                _send(self._conn, state)
            except OSError:
                pass

    def close(self) -> None:
        for sock in (self._conn, self._server_sock):
            if sock is not None:
                try:
                    sock.close()
                except OSError:
                    pass


class ClientConnection:
    def __init__(
        self,
        ip: str,
        port: int,
        on_ready: Callable[[int, int], None],
        on_state: Callable[[dict], None],
        on_disconnect: Callable[[str], None],
    ):
        self._ip = ip
        self._port = port
        self._on_ready = on_ready
        self._on_state = on_state
        self._on_disconnect = on_disconnect
        self._sock: Optional[socket.socket] = None

    def connect(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((self._ip, self._port))
        sock.settimeout(None)
        self._sock = sock
        threading.Thread(target=self._read_loop, daemon=True).start()

    def _read_loop(self) -> None:
        assert self._sock is not None
        try:
            for msg in _read_lines(self._sock):
                mtype = msg.get("type")
                if mtype == "hello":
                    self._on_ready(msg["size"], msg["your_player"])
                elif mtype == "state":
                    self._on_state(msg)
        except (OSError, json.JSONDecodeError, KeyError):
            pass
        finally:
            self._on_disconnect("Se perdió la conexión con el anfitrión.")

    def submit_move(self, row: int, col: int) -> None:
        if self._sock is not None:
            try:
                _send(self._sock, {"type": "move", "row": row, "col": col})
            except OSError:
                pass

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
