const socket = io();

const setupSection = document.getElementById('setup');
const gameSection = document.getElementById('game');
const createForm = document.getElementById('create-form');
const joinForm = document.getElementById('join-form');
const boardTop = document.getElementById('top-row');
const boardBottom = document.getElementById('bottom-row');
const gameCodeEl = document.getElementById('game-code');
const playerColorEl = document.getElementById('player-color');
const statusEl = document.getElementById('game-status');
const diceEl = document.getElementById('dice');
const playersEl = document.getElementById('players');
const rollBtn = document.getElementById('roll');
const endTurnBtn = document.getElementById('end-turn');
const whiteBorneEl = document.getElementById('white-borne');
const blackBorneEl = document.getElementById('black-borne');
const barWhiteEl = document.getElementById('bar-white');
const barBlackEl = document.getElementById('bar-black');
const offWhiteEl = document.getElementById('off-white');
const offBlackEl = document.getElementById('off-black');

let currentGameId = null;
let playerColor = null;
let gameState = null;
let selectedSource = null;

const colorTitles = {
  white: 'белых',
  black: 'чёрных',
};

function toggleView(inGame) {
  if (inGame) {
    setupSection.hidden = true;
    gameSection.hidden = false;
  } else {
    setupSection.hidden = false;
    gameSection.hidden = true;
  }
}

function renderBoard(state) {
  boardTop.innerHTML = '';
  boardBottom.innerHTML = '';

  const topPoints = [...Array(12).keys()].map((i) => 23 - i);
  const bottomPoints = [...Array(12).keys()].map((i) => i);

  const makePoint = (index, row) => {
    const point = document.createElement('div');
    point.className = 'point disabled';
    point.dataset.index = index;
    const checkersCount = Math.abs(state.board[index]);
    const color = state.board[index] > 0 ? 'white' : state.board[index] < 0 ? 'black' : null;
    const stack = document.createElement('div');
    stack.className = 'stack';

    if (checkersCount > 0 && color) {
      for (let i = 0; i < checkersCount; i += 1) {
        const checker = document.createElement('div');
        checker.className = `checker ${color}`;
        stack.appendChild(checker);
      }
    }

    point.appendChild(stack);

    if (row === 'top') {
      point.classList.add('top-point');
    }

    return point;
  };

  topPoints.forEach((idx) => boardTop.appendChild(makePoint(idx, 'top')));
  bottomPoints.forEach((idx) => boardBottom.appendChild(makePoint(idx, 'bottom')));
}

function renderBar(state) {
  const whiteCount = state.bar.white;
  const blackCount = state.bar.black;
  barWhiteEl.innerHTML = '';
  barBlackEl.innerHTML = '';

  for (let i = 0; i < whiteCount; i += 1) {
    const checker = document.createElement('div');
    checker.className = 'checker white';
    barWhiteEl.appendChild(checker);
  }
  for (let i = 0; i < blackCount; i += 1) {
    const checker = document.createElement('div');
    checker.className = 'checker black';
    barBlackEl.appendChild(checker);
  }
}

function renderDice(state) {
  diceEl.innerHTML = '';
  (state.dice || []).forEach((value) => {
    const die = document.createElement('div');
    die.className = 'die';
    die.textContent = value;
    diceEl.appendChild(die);
  });
}

function renderPlayers(state) {
  playersEl.innerHTML = '';
  const entries = Object.entries(state.players || {});
  entries.forEach(([color, info]) => {
    const item = document.createElement('li');
    const dot = document.createElement('span');
    dot.className = `color-indicator ${color}`;
    dot.style.background = color === 'white' ? '#f5f5f5' : '#111';
    const label = document.createElement('span');
    label.textContent = `${info.nickname || 'Игрок'} (${color === 'white' ? 'Белые' : 'Чёрные'})`;
    item.append(dot, label);
    playersEl.appendChild(item);
  });
}

function renderState(state) {
  gameState = state;
  if (selectedSource !== null) {
    const stillValid = (state.legalMoves || []).some((move) => move.player === playerColor && move.from === selectedSource);
    if (!stillValid) {
      selectedSource = null;
    }
  }
  renderBoard(state);
  renderBar(state);
  renderDice(state);
  renderPlayers(state);
  whiteBorneEl.textContent = state.borneOff.white;
  blackBorneEl.textContent = state.borneOff.black;

  if (state.winner) {
    statusEl.textContent = `Победа игрока ${state.winner === 'white' ? 'за белых' : 'за чёрных'}!`;
  } else if (!state.currentPlayer) {
    statusEl.textContent = 'Ожидаем подключение соперника...';
  } else if (state.currentPlayer === playerColor) {
    if (!state.dice || state.dice.length === 0) {
      statusEl.textContent = 'Ваш ход. Бросьте кости.';
    } else {
      statusEl.textContent = 'Ваш ход. Сделайте перемещение.';
    }
  } else if (playerColor) {
    statusEl.textContent = 'Ход соперника.';
  } else {
    const actor = state.currentPlayer === 'white' ? 'белые' : 'чёрные';
    statusEl.textContent = `Сейчас ходят ${actor}.`;
  }

  rollBtn.disabled = !playerColor || state.winner || state.currentPlayer !== playerColor || (state.dice && state.dice.length > 0);
  const hasMoves = (state.legalMoves || []).some((move) => move.player === playerColor);
  endTurnBtn.disabled = !playerColor || state.winner || state.currentPlayer !== playerColor || (state.movesLeft && state.movesLeft.length > 0 && hasMoves);
  updateHighlights();
}

function handlePointClick(index) {
  if (!gameState || gameState.winner) return;
  if (gameState.currentPlayer !== playerColor) return;
  const movesFromPoint = (gameState.legalMoves || []).filter((move) => move.player === playerColor && move.from === index);
  if (movesFromPoint.length === 0) return;

  if (selectedSource === index) {
    selectedSource = null;
    updateHighlights();
    return;
  }

  selectedSource = index;
  updateHighlights();
}

function updateHighlights() {
  const moves = (gameState?.legalMoves || []).filter((move) => move.player === playerColor);
  const isPlayersTurn = gameState && playerColor && gameState.currentPlayer === playerColor;
  const barCount = (gameState?.bar?.[playerColor] ?? 0);

  document.querySelectorAll('.point').forEach((point) => {
    const idx = Number(point.dataset.index);
    const movesFromPoint = moves.filter((move) => move.from === idx);
    let enabled = false;
    let highlight = false;

    if (isPlayersTurn) {
      if (selectedSource === null) {
        enabled = barCount === 0 && movesFromPoint.length > 0;
      } else if (selectedSource === 'bar') {
        enabled = moves.filter((move) => move.from === 'bar').some((move) => move.to === idx);
        highlight = enabled;
      } else if (selectedSource === idx) {
        enabled = true;
        highlight = true;
      } else {
        const movesFromSelected = moves.filter((move) => move.from === selectedSource);
        enabled = movesFromSelected.some((move) => move.to === idx);
        highlight = enabled;
      }
    }

    point.classList.toggle('disabled', !enabled);
    point.classList.toggle('highlight', highlight);
  });

  [barWhiteEl, barBlackEl].forEach((barEl) => {
    const color = barEl.dataset.color;
    const movesFromBar = moves.filter((move) => move.from === 'bar' && color === playerColor);
    const canSelectBar = isPlayersTurn && movesFromBar.length > 0;
    const isSelected = selectedSource === 'bar' && playerColor === color;
    barEl.classList.toggle('highlight', isSelected);
    barEl.classList.toggle('disabled', !canSelectBar);
  });

  [offWhiteEl, offBlackEl].forEach((offEl) => {
    const color = offEl.dataset.color;
    const movesToOff = moves.filter((move) => move.from === selectedSource && move.to === 'off' && playerColor === color);
    const shouldHighlight = isPlayersTurn && movesToOff.length > 0;
    offEl.classList.toggle('highlight', shouldHighlight);
    offEl.classList.toggle('disabled', !shouldHighlight);
  });
}

function handleBarClick(color) {
  if (!gameState || gameState.currentPlayer !== playerColor || playerColor !== color) return;
  if (selectedSource === 'bar') {
    selectedSource = null;
    updateHighlights();
    return;
  }
  const movesFromBar = (gameState.legalMoves || []).filter((move) => move.player === playerColor && move.from === 'bar');
  if (movesFromBar.length === 0) return;
  selectedSource = 'bar';
  updateHighlights();
}

function handleDestinationClick(target) {
  if (!gameState || gameState.currentPlayer !== playerColor) return;
  const moves = (gameState.legalMoves || []).filter((move) => move.player === playerColor && move.from === selectedSource);
  const move = moves.find((m) => m.to === target);
  if (!move) return;
  socket.emit('make_move', {
    gameId: currentGameId,
    color: playerColor,
    from: move.from,
    to: move.to,
    die: move.die,
  });
  selectedSource = null;
  updateHighlights();
}

function setupBoardListeners() {
  boardTop.addEventListener('click', (event) => {
    const target = event.target.closest('.point');
    if (!target) return;
    const index = Number(target.dataset.index);
    if (selectedSource !== null && selectedSource !== 'bar') {
      if (index === selectedSource) {
        handlePointClick(index);
      } else {
        handleDestinationClick(index);
      }
    } else {
      handlePointClick(index);
    }
  });

  boardBottom.addEventListener('click', (event) => {
    const target = event.target.closest('.point');
    if (!target) return;
    const index = Number(target.dataset.index);
    if (selectedSource !== null && selectedSource !== 'bar') {
      if (index === selectedSource) {
        handlePointClick(index);
      } else {
        handleDestinationClick(index);
      }
    } else {
      handlePointClick(index);
    }
  });

  barWhiteEl.addEventListener('click', () => handleBarClick('white'));
  barBlackEl.addEventListener('click', () => handleBarClick('black'));
  offWhiteEl.addEventListener('click', () => handleBearOff('white'));
  offBlackEl.addEventListener('click', () => handleBearOff('black'));
}

function handleBearOff(color) {
  if (!gameState || gameState.currentPlayer !== playerColor || playerColor !== color) return;
  const move = (gameState.legalMoves || []).find(
    (item) => item.player === playerColor && item.from === selectedSource && item.to === 'off',
  );
  if (!move) return;
  socket.emit('make_move', {
    gameId: currentGameId,
    color: playerColor,
    from: move.from,
    to: move.to,
    die: move.die,
  });
  selectedSource = null;
  updateHighlights();
}

createForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(createForm);
  const nickname = formData.get('nickname')?.toString().trim() || 'Игрок';
  socket.emit('create_game', { nickname });
});

joinForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const formData = new FormData(joinForm);
  const gameId = formData.get('gameId')?.toString().trim().toUpperCase();
  const nickname = formData.get('nickname')?.toString().trim() || 'Игрок';
  if (!gameId) {
    alert('Введите код комнаты.');
    return;
  }
  socket.emit('join_game', { gameId, nickname });
});

rollBtn.addEventListener('click', () => {
  if (!currentGameId || !playerColor) return;
  socket.emit('roll_dice', { gameId: currentGameId, color: playerColor });
});

endTurnBtn.addEventListener('click', () => {
  if (!currentGameId || !playerColor) return;
  socket.emit('end_turn', { gameId: currentGameId, color: playerColor });
});

socket.on('game_created', ({ gameId, color, state }) => {
  currentGameId = gameId;
  playerColor = color;
  toggleView(true);
  gameCodeEl.textContent = gameId;
  playerColorEl.textContent = colorTitles[color] || '—';
  renderState(state);
});

socket.on('game_joined', ({ gameId, color, state }) => {
  currentGameId = gameId;
  playerColor = color;
  toggleView(true);
  gameCodeEl.textContent = gameId;
  playerColorEl.textContent = colorTitles[color] || '—';
  renderState(state);
});

socket.on('game_update', (state) => {
  renderState(state);
});

socket.on('error', ({ message }) => {
  alert(message);
});

setupBoardListeners();
