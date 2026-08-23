// Dev-only stand-in for window.pywebview.api, so the UI can be exercised in a
// plain browser tab. Mirrors just enough of engine/board.py + engine/api.py
// to drive the screens; NOT the real AI or the real network layer.
(function () {
  if (window.pywebview) return;

  const DIRS = [[-1,0],[-1,1],[0,1],[1,0],[1,-1],[0,-1]];

  function emptyBoard(size) {
    return Array.from({ length: size }, () => Array(size).fill(0));
  }

  function neighbors(size, r, c) {
    const out = [];
    for (const [dr, dc] of DIRS) {
      const nr = r + dr, nc = c + dc;
      if (nr >= 0 && nr < size && nc >= 0 && nc < size) out.push([nr, nc]);
    }
    return out;
  }

  function checkConnection(board, size, player) {
    const visited = Array.from({ length: size }, () => new Uint8Array(size));
    const queue = [];
    if (player === 1) {
      for (let c = 0; c < size; c++) if (board[0][c] === 1) { queue.push([0, c]); visited[0][c] = 1; }
    } else {
      for (let r = 0; r < size; r++) if (board[r][0] === 2) { queue.push([r, 0]); visited[r][0] = 1; }
    }
    while (queue.length) {
      const [r, c] = queue.shift();
      if ((player === 1 && r === size - 1) || (player === 2 && c === size - 1)) return true;
      for (const [nr, nc] of neighbors(size, r, c)) {
        if (!visited[nr][nc] && board[nr][nc] === player) { visited[nr][nc] = 1; queue.push([nr, nc]); }
      }
    }
    return false;
  }

  function legalMoves(board, size) {
    const out = [];
    for (let r = 0; r < size; r++) for (let c = 0; c < size; c++) if (board[r][c] === 0) out.push([r, c]);
    return out;
  }

  const state = {
    mode: null, size: null, board: null, turn: 1, winner: null,
    history: [], humanPlayer: null,
  };

  function payload(extra) {
    return Object.assign({
      mode: state.mode, size: state.size, board: state.board, turn: state.turn,
      winner: state.winner, winPath: [], history: state.history, humanPlayer: state.humanPlayer,
    }, extra || {});
  }

  function fireEvent(event, extra) {
    const p = payload(Object.assign({ event }, extra || {}));
    setTimeout(() => window.onEngineEvent && window.onEngineEvent(p), 0);
    return p;
  }

  function resolved(v) { return Promise.resolve(v); }

  function dumbAiMove(size, board) {
    const moves = legalMoves(board, size);
    return moves[Math.floor(Math.random() * moves.length)];
  }

  function applyMove(player, r, c) {
    state.board[r][c] = player;
    state.history.push({ player, row: r, col: c });
    if (checkConnection(state.board, state.size, player)) {
      state.winner = player;
      return true;
    }
    state.turn = 3 - player;
    return false;
  }

  function maybeAiTurn() {
    if (state.mode !== 'ai' || state.winner || state.turn === state.humanPlayer) return;
    fireEvent('thinking');
    setTimeout(() => {
      const aiPlayer = 3 - state.humanPlayer;
      const [r, c] = dumbAiMove(state.size, state.board);
      applyMove(aiPlayer, r, c);
      fireEvent('ai_move');
    }, 500);
  }

  const api = {
    get_state: () => resolved(payload()),

    leave_game: () => {
      state.mode = null; state.board = null; state.winner = null; state.history = []; state.humanPlayer = null;
      return resolved(payload());
    },

    new_local_game: (size) => {
      state.mode = 'local'; state.size = size; state.board = emptyBoard(size);
      state.turn = 1; state.winner = null; state.history = []; state.humanPlayer = null;
      return resolved(payload());
    },

    new_ai_game: (size, difficulty, humanPlayer) => {
      state.mode = 'ai'; state.size = size; state.board = emptyBoard(size);
      state.turn = 1; state.winner = null; state.history = []; state.humanPlayer = humanPlayer;
      const p = payload();
      maybeAiTurn();
      return resolved(p);
    },

    host_network_game: (size) => {
      state.mode = 'host'; state.size = size; state.board = emptyBoard(size);
      state.turn = 1; state.winner = null; state.history = []; state.humanPlayer = 1;
      setTimeout(() => fireEvent('peer_connected'), 1800);
      return resolved(Object.assign(payload(), { ip: '192.168.1.42', port: 51137 }));
    },

    join_network_game: (ip, port) => {
      state.mode = 'client'; state.size = 7; state.board = emptyBoard(7);
      state.turn = 1; state.winner = null; state.history = []; state.humanPlayer = 2;
      setTimeout(() => fireEvent('joined'), 900);
      return resolved({ ok: true });
    },

    play_move: (row, col) => {
      if (state.winner || !state.board || state.board[row][col] !== 0) return resolved(payload());
      if (state.mode === 'ai' && state.turn !== state.humanPlayer) return resolved(payload());
      applyMove(state.turn, row, col);
      const p = payload();
      if (state.mode === 'ai') maybeAiTurn();
      return resolved(p);
    },

    undo: () => {
      if (!state.history.length) return resolved(payload());
      const steps = (state.mode === 'ai' && state.history.length >= 2) ? 2 : 1;
      for (let i = 0; i < steps && state.history.length; i++) {
        const last = state.history.pop();
        state.board[last.row][last.col] = 0;
      }
      state.winner = null;
      state.turn = state.mode === 'ai' ? state.humanPlayer
        : (state.history.length ? 3 - state.history[state.history.length - 1].player : 1);
      return resolved(payload());
    },
  };

  window.pywebview = { api };
  setTimeout(() => document.dispatchEvent(new Event('pywebviewready')), 0);
})();
