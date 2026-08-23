"""Host+client smoke test over 127.0.0.1, standing in for two separate PCs."""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import network

host_states = []
client_states = []
client_ready = {}
events = []


def on_host_state(state):
    host_states.append(state)


def on_client_ready(size, player):
    client_ready["size"] = size
    client_ready["player"] = player


def on_client_state(state):
    client_states.append(state)


def on_disconnect(msg):
    events.append(("disconnect", msg))


if __name__ == "__main__":
    host = network.HostServer(
        size=5,
        on_state=on_host_state,
        on_peer_connected=lambda: events.append(("peer_connected",)),
        on_disconnect=lambda msg: on_disconnect(msg),
        port=0,
    )
    ip, port = host.start()
    print(f"host listening on {ip}:{port}")

    client = network.ClientConnection(
        "127.0.0.1", port,
        on_ready=on_client_ready,
        on_state=on_client_state,
        on_disconnect=on_disconnect,
    )
    client.connect()

    time.sleep(0.3)
    assert client_ready == {"size": 5, "player": network.CLIENT_PLAYER}, client_ready
    assert ("peer_connected",) in events

    # host plays (3,3) as player 1
    assert host.submit_local_move(3, 3)
    time.sleep(0.2)
    assert client_states[-1]["board"][3][3] == 1
    assert client_states[-1]["turn"] == 2

    # client tries to move out of turn -> host player still 1's turn conceptually,
    # but it IS player 2's turn now, so this should succeed
    client.submit_move(0, 0)
    time.sleep(0.2)
    assert host.board.get(0, 0) == 2
    assert host_states[-1]["turn"] == 1

    # client attempts an illegal move (occupied cell) -> should be ignored, no new state
    n_before = len(client_states)
    client.submit_move(3, 3)
    time.sleep(0.2)
    assert len(client_states) == n_before, "illegal move should not produce a new state"

    host.close()
    client.close()
    print("ok: host/client stay in sync over TCP")
