// ══════════════════════════════════════════════════════════════
// UI state + screen wiring
// ══════════════════════════════════════════════════════════════

let ready = false;
let netInfo = { role: null, waitingPeer: false };
let lastGameConfig = null; // { mode: 'ai'|'local', size, difficulty?, humanPlayer? } — for "jugar de nuevo"

const game = {
  mode: null, size: null, board: null, turn: 1, winner: null,
  winPath: [], history: [], humanPlayer: null, thinking: false,
};

function api() { return window.pywebview.api; }

function $(id) { return document.getElementById(id); }
function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function showScreen(name) {
  if (name === 'menu') {
    show($('screen-menu'));
    hide($('screen-game'));
  } else {
    hide($('screen-menu'));
    show($('screen-game'));
    // the board sizes itself off the now-visible container, so it must be
    // shown before we measure it — re-render right after switching over.
    render();
  }
}

function showMenuPanel(which) {
  hide($('menu-root'));
  ['panel-ai', 'panel-local', 'panel-network'].forEach(id => hide($(id)));
  if (which) show($(`panel-${which}`));
  else show($('menu-root'));
}

function resetNetworkPanel() {
  hide($('network-host')); hide($('network-join')); show($('network-choice'));
  hide($('host-info')); $('join-status').textContent = '';
}

// ── menu wiring ──
document.querySelectorAll('.mode-card').forEach(card => {
  card.addEventListener('click', () => showMenuPanel(card.dataset.open));
});
document.querySelectorAll('[data-back]').forEach(el => {
  el.addEventListener('click', () => { resetNetworkPanel(); showMenuPanel(null); });
});

function startAiGame(size, difficulty, humanPlayer) {
  lastGameConfig = { mode: 'ai', size, difficulty, humanPlayer };
  return api().new_ai_game(size, difficulty, humanPlayer).then(state => {
    applyState(state);
    showScreen('game');
  });
}

function startLocalGame(size) {
  lastGameConfig = { mode: 'local', size };
  return api().new_local_game(size).then(state => {
    applyState(state);
    showScreen('game');
  });
}

$('ai-start').addEventListener('click', () => {
  const size = parseInt($('ai-size').value, 10);
  const difficulty = $('ai-difficulty').value;
  const humanPlayer = parseInt($('ai-role').value, 10);
  startAiGame(size, difficulty, humanPlayer);
});

$('local-start').addEventListener('click', () => {
  const size = parseInt($('local-size').value, 10);
  startLocalGame(size);
});

$('network-open-host').addEventListener('click', () => { resetNetworkPanel(); show($('network-host')); });
$('network-open-join').addEventListener('click', () => { resetNetworkPanel(); show($('network-join')); });

$('host-start').addEventListener('click', () => {
  const size = parseInt($('host-size').value, 10);
  netInfo = { role: 'host', waitingPeer: true };
  api().host_network_game(size).then(res => {
    applyState(res);
    $('host-info').innerHTML =
      `Comparte esto con tu rival:<br>IP: <span class="ip">${res.ip}</span> &nbsp; Puerto: <span class="ip">${res.port}</span>` +
      `<br><span class="waiting-dots">Esperando conexión</span>`;
    show($('host-info'));
  });
});

$('join-start').addEventListener('click', () => {
  const ip = $('join-ip').value.trim();
  const port = parseInt($('join-port').value, 10) || 51137;
  if (!ip) { $('join-status').textContent = 'Escribe la IP del anfitrión.'; return; }
  netInfo = { role: 'client', waitingPeer: true };
  $('join-status').textContent = 'Conectando…';
  api().join_network_game(ip, port).then(res => {
    if (res && res.error) $('join-status').textContent = 'No se pudo conectar: ' + res.error;
  });
});

$('btn-menu').addEventListener('click', () => {
  api().leave_game().then(() => {
    game.mode = null; game.board = null; game.winner = null; game.history = [];
    netInfo = { role: null, waitingPeer: false };
    resetNetworkPanel();
    showMenuPanel(null);
    showScreen('menu');
  });
});

$('btn-undo').addEventListener('click', () => {
  api().undo().then(applyState);
});

$('win-modal-again').addEventListener('click', () => {
  if (!lastGameConfig) return;
  if (lastGameConfig.mode === 'ai') {
    startAiGame(lastGameConfig.size, lastGameConfig.difficulty, lastGameConfig.humanPlayer);
  } else if (lastGameConfig.mode === 'local') {
    startLocalGame(lastGameConfig.size);
  }
});

$('win-modal-menu').addEventListener('click', () => { $('btn-menu').click(); });

// ══════════════════════════════════════════════════════════════
// engine events / state application
// ══════════════════════════════════════════════════════════════

function applyState(state) {
  if (!state || state.board === undefined) return;
  game.mode = state.mode;
  game.size = state.size;
  game.board = state.board;
  game.turn = state.turn;
  game.winner = state.winner;
  game.winPath = state.winPath || [];
  game.history = state.history || [];
  game.humanPlayer = state.humanPlayer;
  if (state.event === 'thinking') game.thinking = true;
  else if (state.event) game.thinking = false;
  render();
}

window.onEngineEvent = function (state) {
  if (state.event === 'peer_connected') {
    netInfo.waitingPeer = false;
    applyState(state);
    showScreen('game');
    return;
  }
  if (state.event === 'joined') {
    netInfo.waitingPeer = false;
    applyState(state);
    showScreen('game');
    return;
  }
  if (state.event === 'peer_disconnected') {
    applyState(state);
    setStatus(state.message || 'Se perdió la conexión.', 'warn');
    return;
  }
  applyState(state);
};

// ══════════════════════════════════════════════════════════════
// board rendering (SVG hex grid)
// ══════════════════════════════════════════════════════════════

const PAD = 20;
const HEX_R_MIN = 14;
const HEX_R_MAX = 90;

function hexCorners(cx, cy, r) {
  return Array.from({ length: 6 }, (_, i) => {
    const a = Math.PI / 180 * (60 * i - 30);
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
  }).join(' ');
}

// Pointy-top hexagons (vertex at top/bottom, per hexCorners' angles) laid out
// on axial coordinates where row/col match engine/board.py's DIRECTIONS.
// Each row shift moves half a hex-width right, matching the classic slanted
// Hex board look.
function hexCenter(row, col, R) {
  const hexW = R * Math.sqrt(3);
  const cx = PAD + hexW * col + (hexW / 2) * row;
  const cy = PAD + 1.5 * R * row;
  return [cx, cy];
}

function boardPixelSize(n, R) {
  const [lastCx, lastCy] = hexCenter(n - 1, n - 1, R);
  return { width: lastCx + R + PAD, height: lastCy + (R * Math.sqrt(3)) / 2 + PAD };
}

// Solve for the largest hex radius that fits an n x n board inside
// availW x availH (boardPixelSize is affine in R, so this is a direct solve,
// no iteration needed).
function fitHexRadius(n, availW, availH) {
  const unit = boardPixelSize(n, 1);
  const kW = unit.width - 2 * PAD;
  const kH = unit.height - 2 * PAD;
  const rw = (availW - 2 * PAD) / kW;
  const rh = (availH - 2 * PAD) / kH;
  return Math.max(HEX_R_MIN, Math.min(HEX_R_MAX, Math.min(rw, rh)));
}

function humanCanClick() {
  if (!game.board || game.winner || game.thinking) return false;
  if (game.mode === 'local') return true;
  if (game.mode === 'ai') return game.turn === game.humanPlayer;
  if (game.mode === 'host') return game.turn === 1 && !netInfo.waitingPeer;
  if (game.mode === 'client') return game.turn === game.humanPlayer;
  return false;
}

function humanMove(r, c) {
  if (!humanCanClick() || game.board[r][c] !== 0) return;
  api().play_move(r, c).then(applyState);
}

function renderBoard() {
  const svg = $('board-svg');
  if (!game.board) { svg.innerHTML = ''; return; }
  const n = game.size;

  const wrap = $('board-wrap');
  const availW = wrap.clientWidth || 600;
  const availH = wrap.clientHeight || 500;
  const R = fitHexRadius(n, availW, availH);

  const { width: W, height: H } = boardPixelSize(n, R);
  svg.setAttribute('width', W);
  svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = '';

  const edgeGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  function edgeLine(r1, c1, r2, c2, cls) {
    const [x1, y1] = hexCenter(r1, c1, R);
    const [x2, y2] = hexCenter(r2, c2, R);
    const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    l.setAttribute('x1', x1); l.setAttribute('y1', y1);
    l.setAttribute('x2', x2); l.setAttribute('y2', y2);
    l.setAttribute('stroke-width', '4');
    l.setAttribute('stroke-linecap', 'round');
    l.setAttribute('class', cls);
    l.setAttribute('opacity', '.6');
    edgeGroup.appendChild(l);
  }
  for (let c = 0; c < n - 1; c++) {
    edgeLine(0, c, 0, c + 1, 'edge-top');
    edgeLine(n - 1, c, n - 1, c + 1, 'edge-bottom');
  }
  for (let r = 0; r < n - 1; r++) {
    edgeLine(r, 0, r + 1, 0, 'edge-left');
    edgeLine(r, n - 1, r + 1, n - 1, 'edge-right');
  }
  svg.appendChild(edgeGroup);

  const winCells = new Set((game.winPath || []).map(([r, c]) => `${r},${c}`));
  const clickable = humanCanClick();

  for (let r = 0; r < n; r++) {
    for (let c = 0; c < n; c++) {
      const [cx, cy] = hexCenter(r, c, R);
      const val = game.board[r][c];
      const inWin = winCells.has(`${r},${c}`);

      const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
      let cls = 'hex-cell ';
      cls += val === 0 ? 'empty' : (val === 1 ? 'p1' : 'p2');
      if (inWin) cls += ' win-path';
      if (val !== 0 || !clickable) cls += ' blocked';
      g.setAttribute('class', cls);

      const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      poly.setAttribute('points', hexCorners(cx, cy, R - 1.5));
      g.appendChild(poly);

      if (val === 0 && clickable) {
        g.addEventListener('click', () => humanMove(r, c));
      }
      svg.appendChild(g);
    }
  }
}

function setStatus(text, cls) {
  const el = $('status');
  el.textContent = text;
  el.className = 'status' + (cls ? ' ' + cls : '');
}

function updateStatus() {
  if (!game.board) { setStatus('—'); return; }
  if (game.winner) {
    if (game.mode === 'ai') {
      setStatus(game.winner === game.humanPlayer ? '¡Ganaste! 🎉' : 'Ganó la IA — inténtalo de nuevo',
        game.winner === 1 ? 'win-p1' : 'win-p2');
    } else {
      setStatus(`Ganó ${game.winner === 1 ? 'Rojo' : 'Azul'} 🎉`, game.winner === 1 ? 'win-p1' : 'win-p2');
    }
    return;
  }
  if (game.thinking) { $('status').innerHTML = 'IA pensando<span class="dots"></span>'; $('status').className = 'status thinking'; return; }
  if (game.mode === 'host' && netInfo.waitingPeer) { setStatus('Esperando al otro jugador…', 'thinking'); return; }

  const turnLabel = game.turn === 1 ? 'Rojo' : 'Azul';
  const cls = game.turn === 1 ? 'p1-turn' : 'p2-turn';
  if (game.mode === 'ai') {
    setStatus(game.turn === game.humanPlayer ? `Tu turno (${turnLabel})` : `Turno de la IA (${turnLabel})`, cls);
  } else if (game.mode === 'local') {
    setStatus(`Turno de ${turnLabel}`, cls);
  } else if (game.mode === 'host' || game.mode === 'client') {
    setStatus(game.turn === game.humanPlayer ? `Tu turno (${turnLabel})` : `Turno del rival (${turnLabel})`, cls);
  }
}

function updateLegend() {
  if (game.mode === 'ai') {
    $('legend-p1').textContent = (game.humanPlayer === 1 ? 'Tú' : 'IA') + ' — arriba ↔ abajo';
    $('legend-p2').textContent = (game.humanPlayer === 2 ? 'Tú' : 'IA') + ' — izquierda ↔ derecha';
  } else if (game.mode === 'host' || game.mode === 'client') {
    $('legend-p1').textContent = (game.humanPlayer === 1 ? 'Tú' : 'Rival') + ' — arriba ↔ abajo';
    $('legend-p2').textContent = (game.humanPlayer === 2 ? 'Tú' : 'Rival') + ' — izquierda ↔ derecha';
  } else {
    $('legend-p1').textContent = 'Rojo — arriba ↔ abajo';
    $('legend-p2').textContent = 'Azul — izquierda ↔ derecha';
  }
}

function updateHistory() {
  const list = $('history-list');
  list.innerHTML = '';
  (game.history || []).forEach((m, i) => {
    const b = document.createElement('div');
    b.className = `move-badge p${m.player}`;
    b.textContent = `${i + 1}. P${m.player} (${m.row},${m.col})`;
    list.appendChild(b);
  });
  list.scrollTop = list.scrollHeight;
}

function updateControls() {
  const networked = game.mode === 'host' || game.mode === 'client';
  $('btn-undo').classList.toggle('hidden', networked);
  $('btn-undo').disabled = !game.history || game.history.length === 0 || !!game.winner;
}

function updateWinModal() {
  const modal = $('win-modal');
  if (!game.winner) { hide(modal); return; }

  const cls = game.winner === 1 ? 'win-p1' : 'win-p2';
  const colorLabel = game.winner === 1 ? 'Rojo' : 'Azul';
  let title;
  if (game.mode === 'ai') {
    title = game.winner === game.humanPlayer ? '¡Ganaste! 🎉' : 'Ganó la IA';
  } else if (game.mode === 'host' || game.mode === 'client') {
    title = game.winner === game.humanPlayer ? '¡Ganaste! 🎉' : 'Ganó tu rival';
  } else {
    title = `¡Ganó ${colorLabel}! 🎉`;
  }

  const titleEl = $('win-modal-title');
  titleEl.textContent = title;
  titleEl.className = cls;
  $('win-modal-sub').textContent = `Jugador ${colorLabel}`;

  const canRematch = (game.mode === 'ai' || game.mode === 'local') && lastGameConfig;
  $('win-modal-again').classList.toggle('hidden', !canRematch);

  show(modal);
}

function render() {
  renderBoard();
  updateStatus();
  updateLegend();
  updateHistory();
  updateControls();
  updateWinModal();
}

// ══════════════════════════════════════════════════════════════
// bootstrap
// ══════════════════════════════════════════════════════════════

function init() {
  ready = true;
  showMenuPanel(null);
  showScreen('menu');
}

if (window.pywebview) init();
else document.addEventListener('pywebviewready', init);

let resizeTimer = null;
window.addEventListener('resize', () => {
  if (!game.board) return;
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(renderBoard, 80);
});
