const BOARD_TOP_ORDER = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23];
const BOARD_BOTTOM_ORDER = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0];

const state = {
  gameId: null,
  playerId: null,
  color: null,
  socket: null,
  data: null,
  selected: null,
  lastMessage: "",
};

const setupSection = document.getElementById("setup");
const gameArea = document.getElementById("game-area");
const boardTop = document.getElementById("board-top");
const boardBottom = document.getElementById("board-bottom");
const barSlots = {
  white: document.querySelector('.bar-slot[data-bar="white"]'),
  black: document.querySelector('.bar-slot[data-bar="black"]'),
};
const bearoffWhite = document.getElementById("bearoff-white");
const bearoffBlack = document.getElementById("bearoff-black");
const playersList = document.getElementById("players-list");
const spectatorsEl = document.getElementById("spectators");
const diceValues = document.getElementById("dice-values");
const turnIndicator = document.getElementById("turn-indicator");
const messageEl = document.getElementById("message");
const rollBtn = document.getElementById("roll-btn");
const passBtn = document.getElementById("pass-btn");
const gameIdEl = document.getElementById("game-id");
const roleLabel = document.getElementById("role-label");
const copyLinkBtn = document.getElementById("copy-link");
const leaveBtn = document.getElementById("leave-btn");

const pointElements = new Map();

function buildBoard() {
  boardTop.innerHTML = "";
  boardBottom.innerHTML = "";
  pointElements.clear();

  const createRow = (order, container, rowClass) => {
    order.forEach((index, idx) => {
      if (idx === 6) {
        const gap = document.createElement("div");
        gap.className = "gap-cell";
        container.appendChild(gap);
      }
      const point = createPoint(index, rowClass, idx);
      container.appendChild(point);
      pointElements.set(index, point);
    });
  };

  createRow(BOARD_TOP_ORDER, boardTop, "top");
  createRow(BOARD_BOTTOM_ORDER, boardBottom, "bottom");
}

function createPoint(index, rowClass, idx) {
  const point = document.createElement("div");
  const segmentIndex = idx % 6;
  const colorClass = segmentIndex % 2 === 0 ? "light" : "dark";
  point.className = `point ${rowClass} ${colorClass}`;
  point.dataset.index = index;
  point.dataset.row = rowClass;
  const stack = document.createElement("div");
  stack.className = `checker-stack ${rowClass}`;
  point.appendChild(stack);
  const label = document.createElement("span");
  label.className = "point-label";
  label.textContent = index + 1;
  point.appendChild(label);
  point.addEventListener("click", () => handlePointClick(point));
  return point;
}

function handlePointClick(point) {
  if (!state.data || !state.color) return;
  if (state.data.winner) return;
  const index = Number(point.dataset.index);
  const count = state.data.board[index];
  const isMyChecker = (state.color === "white" && count > 0) || (state.color === "black" && count < 0);
  if (!state.selected) {
    if (!isMyTurn() || !isMyChecker) return;
    selectFrom({ type: "point", index, element: point });
    return;
  }

  if (state.selected.type === "point" && state.selected.index === index) {
    clearSelection();
    return;
  }

  attemptMove({ type: "point", index, element: point });
}

function handleBarClick(color) {
  if (!state.data || !state.color || color !== state.color) return;
  if (!isMyTurn()) return;
  if (state.data.bar[color] <= 0) return;
  const slot = barSlots[color];
  if (!slot) return;
  selectFrom({ type: "bar", color, element: slot });
}

function handleBearOffClick(color) {
  if (!state.data || !state.color || color !== state.color) return;
  if (!isMyTurn()) return;
  if (!state.selected || state.selected.type !== "point") return;
  attemptMove({ type: "bear-off", color, element: color === "white" ? bearoffWhite : bearoffBlack });
}

function selectFrom(data) {
  clearSelection();
  state.selected = data;
  if (data.element) {
    data.element.classList.add("selected");
  }
}

function clearSelection() {
  if (state.selected && state.selected.element) {
    state.selected.element.classList.remove("selected");
  }
  state.selected = null;
}

function attemptMove(target) {
  if (!state.selected || !state.data) return;
  const die = computeDie(state.selected, target);
  if (!die) {
    setMessage("Нет подходящего значения кости", "warn");
    return;
  }
  let fromPoint;
  let toPoint;
  if (state.selected.type === "bar") {
    fromPoint = "bar";
  } else {
    fromPoint = state.selected.index;
  }
  if (target.type === "bear-off") {
    toPoint = "bear_off";
  } else {
    toPoint = target.index;
  }
  sendMove(fromPoint, toPoint, die);
  clearSelection();
}

function computeDie(from, to) {
  if (!state.data || !state.color) return null;
  const pending = [...state.data.pending_moves];
  if (pending.length === 0) return null;

  const color = state.color;
  const sorted = pending.sort((a, b) => a - b);

  const takeDie = (distance, allowGreater = false) => {
    if (distance <= 0) return null;
    for (const value of sorted) {
      if (value === distance) return value;
    }
    if (allowGreater) {
      for (const value of sorted) {
        if (value > distance) return value;
      }
    }
    return null;
  };

  if (from.type === "bar" && typeof to.index === "number") {
    if (color === "white") {
      const die = 24 - to.index;
      return takeDie(die);
    }
    const die = to.index + 1;
    return takeDie(die);
  }

  if (from.type === "point" && typeof from.index === "number") {
    if (to.type === "bear-off") {
      if (color === "white") {
        const distance = from.index + 1;
        return takeDie(distance, true);
      }
      const distance = 24 - from.index;
      return takeDie(distance, true);
    }
    if (typeof to.index === "number") {
      if (color === "white") {
        const distance = from.index - to.index;
        return takeDie(distance);
      }
      const distance = to.index - from.index;
      return takeDie(distance);
    }
  }
  return null;
}

async function sendMove(from_point, to_point, die) {
  if (!state.gameId || !state.playerId) return;
  try {
    const response = await fetch(`/api/games/${state.gameId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        player_id: state.playerId,
        from_point,
        to_point,
        die,
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось выполнить ход");
    }
    const data = await response.json();
    if (data.result && data.result.message) {
      setMessage(data.result.message);
    }
    state.data = data.state;
    render();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function isMyTurn() {
  return (
    !!state.data &&
    !!state.color &&
    state.data.current_player === state.color &&
    !state.data.winner
  );
}

function render() {
  renderRole();
  renderPlayers();
  renderBoard();
  renderBar();
  renderBearoff();
  renderDice();
  renderStatus();
  updateControls();
}

function renderRole() {
  if (!state.gameId) return;
  gameIdEl.textContent = state.gameId;
  if (!state.color || !state.data) {
    roleLabel.textContent = "";
    return;
  }
  if (state.color === "spectator") {
    roleLabel.textContent = "Вы наблюдаете за партией";
  } else {
    const colorLabel = state.color === "white" ? "белыми" : "чёрными";
    roleLabel.textContent = `Вы играете ${colorLabel}`;
  }
}

function renderPlayers() {
  playersList.innerHTML = "";
  if (!state.data) return;
  ["white", "black"].forEach((color) => {
    const info = state.data.players[color];
    const li = document.createElement("li");
    li.textContent = info ? `${info.name} (${color === "white" ? "белые" : "чёрные"})` : `${color === "white" ? "Белые" : "Чёрные"}: ожидаем`; 
    if (state.color === color) {
      li.classList.add("me");
    }
    playersList.appendChild(li);
  });
  if (state.data.spectators && state.data.spectators.length > 0) {
    spectatorsEl.textContent = `Наблюдатели: ${state.data.spectators.join(", ")}`;
  } else {
    spectatorsEl.textContent = "";
  }
}

function renderBoard() {
  if (!state.data) return;
  for (const [index, point] of pointElements.entries()) {
    const stack = point.querySelector(".checker-stack");
    stack.innerHTML = "";
    point.classList.remove("own");
    const count = state.data.board[index];
    const absCount = Math.abs(count);
    if (absCount === 0) continue;
    const color = count > 0 ? "white" : "black";
    for (let i = 0; i < absCount; i += 1) {
      const checker = document.createElement("div");
      checker.className = `checker ${color}`;
      stack.appendChild(checker);
    }
    if (state.color === color && isMyTurn()) {
      point.classList.add("own");
    }
  }
}

function renderBar() {
  if (!state.data) return;
  ["white", "black"].forEach((color) => {
    const slot = barSlots[color];
    if (!slot) return;
    slot.innerHTML = "";
    const count = state.data.bar[color];
    for (let i = 0; i < count; i += 1) {
      const checker = document.createElement("div");
      checker.className = `checker ${color}`;
      slot.appendChild(checker);
    }
    slot.classList.toggle("active", isMyTurn() && state.color === color && count > 0);
  });
}

function renderBearoff() {
  if (!state.data) return;
  updateBearoffStack(bearoffWhite, state.data.borne_off.white, "white");
  updateBearoffStack(bearoffBlack, state.data.borne_off.black, "black");
}

function updateBearoffStack(container, count, color) {
  container.innerHTML = "";
  const label = document.createElement("span");
  label.className = "bearoff-count";
  label.textContent = `${count} / 15`;
  container.appendChild(label);
  const stack = document.createElement("div");
  stack.className = "bearoff-checkers";
  for (let i = 0; i < Math.min(count, 15); i += 1) {
    const checker = document.createElement("div");
    checker.className = `checker small ${color}`;
    stack.appendChild(checker);
  }
  container.appendChild(stack);
}

function renderDice() {
  diceValues.innerHTML = "";
  if (!state.data) return;
  const dice = state.data.dice.length > 0 ? state.data.dice : state.data.last_roll;
  if (!dice || dice.length === 0) {
    diceValues.textContent = "—";
    return;
  }
  dice.forEach((value, idx) => {
    const die = document.createElement("div");
    die.className = "die";
    die.textContent = value;
    if (idx >= state.data.pending_moves.length) {
      die.classList.add("used");
    }
    diceValues.appendChild(die);
  });
}

function renderStatus() {
  if (!state.data) return;
  if (state.data.winner) {
    const winner = state.data.winner === "white" ? "Белые" : "Чёрные";
    turnIndicator.textContent = `${winner} победили!`;
  } else {
    const current = state.data.current_player === "white" ? "Ход белых" : "Ход чёрных";
    turnIndicator.textContent = current;
  }
  messageEl.textContent = state.lastMessage;
}

function updateControls() {
  const canRoll = isMyTurn() && state.data && state.data.dice.length === 0;
  const canPass = isMyTurn() && state.data && state.data.pending_moves.length === 0 && state.data.dice.length === 0;
  rollBtn.disabled = !canRoll;
  passBtn.disabled = !canPass;
}

function setMessage(text, type = "info") {
  state.lastMessage = text;
  messageEl.textContent = text;
  messageEl.dataset.type = type;
}

async function createGame(event) {
  event.preventDefault();
  const form = event.target;
  const name = form.name.value.trim() || "Игрок 1";
  try {
    const response = await fetch("/api/games", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      throw new Error("Не удалось создать игру");
    }
    const data = await response.json();
    enterGame(data);
    setMessage("Комната создана. Поделитесь ID с другом!");
  } catch (err) {
    setMessage(err.message, "error");
  }
}

async function joinGame(event) {
  event.preventDefault();
  const form = event.target;
  const name = form.name.value.trim() || "Игрок";
  const code = form.code.value.trim();
  if (!code) {
    setMessage("Введите ID партии", "warn");
    return;
  }
  try {
    const response = await fetch(`/api/games/${code}/join`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось войти в игру");
    }
    const data = await response.json();
    enterGame({ ...data, joined: true });
    setMessage("Вы присоединились к партии");
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function enterGame(payload) {
  state.gameId = payload.game_id;
  state.playerId = payload.player_id;
  state.color = payload.color;
  state.data = payload.state;
  state.selected = null;
  buildBoard();
  setupSection.classList.add("hidden");
  gameArea.classList.remove("hidden");
  render();
  connectSocket();
}

function connectSocket() {
  if (!state.gameId || !state.playerId) return;
  if (state.socket) {
    state.socket.close();
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socketUrl = `${protocol}://${window.location.host}/ws/games/${state.gameId}?player_id=${state.playerId}`;
  const socket = new WebSocket(socketUrl);
  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "state") {
      state.data = payload.state;
      render();
    } else if (payload.type === "error") {
      setMessage(payload.message, "error");
    }
  };
  socket.onclose = () => {
    if (state.gameId) {
      setMessage("Соединение по WebSocket разорвано", "warn");
    }
  };
  socket.onerror = () => {
    setMessage("Ошибка WebSocket", "error");
  };
  state.socket = socket;
}

async function rollDice() {
  if (!state.gameId || !state.playerId) return;
  try {
    const response = await fetch(`/api/games/${state.gameId}/roll`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: state.playerId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось бросить кости");
    }
    const data = await response.json();
    if (data.result && data.result.message) {
      setMessage(data.result.message);
    } else {
      setMessage("Кости брошены");
    }
    state.data = data.state;
    render();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

async function passTurn() {
  if (!state.gameId || !state.playerId) return;
  try {
    const response = await fetch(`/api/games/${state.gameId}/pass`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: state.playerId }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Не удалось передать ход");
    }
    const data = await response.json();
    if (data.result && data.result.message) {
      setMessage(data.result.message);
    }
    state.data = data.state;
    render();
  } catch (err) {
    setMessage(err.message, "error");
  }
}

function leaveGame() {
  if (state.socket) {
    state.socket.close();
    state.socket = null;
  }
  state.gameId = null;
  state.playerId = null;
  state.color = null;
  state.data = null;
  state.selected = null;
  pointElements.clear();
  boardTop.innerHTML = "";
  boardBottom.innerHTML = "";
  setupSection.classList.remove("hidden");
  gameArea.classList.add("hidden");
  setMessage("Вы вышли из комнаты", "info");
}

async function copyLink() {
  if (!state.gameId) return;
  const url = `${window.location.origin}/?game=${state.gameId}`;
  try {
    await navigator.clipboard.writeText(url);
    setMessage("Ссылка скопирована в буфер обмена");
  } catch (err) {
    setMessage("Не удалось скопировать ссылку", "warn");
  }
}

function setupEventListeners() {
  const createForm = document.getElementById("create-form");
  const joinForm = document.getElementById("join-form");
  createForm.addEventListener("submit", createGame);
  joinForm.addEventListener("submit", joinGame);
  barSlots.white.addEventListener("click", () => handleBarClick("white"));
  barSlots.black.addEventListener("click", () => handleBarClick("black"));
  bearoffWhite.addEventListener("click", () => handleBearOffClick("white"));
  bearoffBlack.addEventListener("click", () => handleBearOffClick("black"));
  rollBtn.addEventListener("click", rollDice);
  passBtn.addEventListener("click", passTurn);
  leaveBtn.addEventListener("click", leaveGame);
  copyLinkBtn.addEventListener("click", copyLink);

  const params = new URLSearchParams(window.location.search);
  const prefill = params.get("game");
  if (prefill) {
    const codeInput = document.getElementById("join-code");
    codeInput.value = prefill;
  }
}

setupEventListeners();
