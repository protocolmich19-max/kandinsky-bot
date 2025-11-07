import asyncio
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from fastapi import WebSocket

Color = str
Point = int


@dataclass
class PlayerSlot:
    id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class GameState:
    id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    board: List[int] = field(default_factory=list)
    bar: Dict[Color, int] = field(default_factory=lambda: {"white": 0, "black": 0})
    borne_off: Dict[Color, int] = field(default_factory=lambda: {"white": 0, "black": 0})
    current_player: Color = "white"
    dice: List[int] = field(default_factory=list)
    pending_moves: List[int] = field(default_factory=list)
    last_roll: List[int] = field(default_factory=list)
    winner: Optional[Color] = None


class GameError(Exception):
    pass


class Game:
    def __init__(self, game_id: Optional[str] = None) -> None:
        self.state = GameState(id=game_id or uuid.uuid4().hex)
        self.player_slots: Dict[Color, PlayerSlot] = {
            "white": PlayerSlot(),
            "black": PlayerSlot(),
        }
        self.spectators: Dict[str, str] = {}
        self.connections: Dict[int, WebSocket] = {}
        self.connection_players: Dict[int, str] = {}
        self.lock = asyncio.Lock()
        self.reset_board()

    # --- Setup -----------------------------------------------------------------
    def reset_board(self) -> None:
        board = [0] * 24
        board[23] = 2  # white
        board[12] = 5
        board[7] = 3
        board[5] = 5

        board[0] = -2  # black
        board[11] = -5
        board[16] = -3
        board[18] = -5
        self.state.board = board
        self.state.bar = {"white": 0, "black": 0}
        self.state.borne_off = {"white": 0, "black": 0}
        self.state.current_player = "white"
        self.state.dice = []
        self.state.pending_moves = []
        self.state.last_roll = []
        self.state.winner = None

    # --- Player management -----------------------------------------------------
    def _generate_player_id(self) -> str:
        return uuid.uuid4().hex

    def assign_player(self, name: str, preferred: Optional[Color] = None) -> Tuple[str, str]:
        player_id = self._generate_player_id()
        color = None
        if preferred and self.player_slots[preferred].id is None:
            color = preferred
        else:
            for candidate in ("white", "black"):
                if self.player_slots[candidate].id is None:
                    color = candidate
                    break
        if color:
            self.player_slots[color] = PlayerSlot(id=player_id, name=name)
            return color, player_id
        self.spectators[player_id] = name
        return "spectator", player_id

    def release_player(self, player_id: str) -> None:
        for color, slot in self.player_slots.items():
            if slot.id == player_id:
                self.player_slots[color] = PlayerSlot()
                return
        self.spectators.pop(player_id, None)

    def get_player_color(self, player_id: str) -> Optional[Color]:
        for color, slot in self.player_slots.items():
            if slot.id == player_id:
                return color
        if player_id in self.spectators:
            return "spectator"
        return None

    # --- Game mechanics --------------------------------------------------------
    @staticmethod
    def opposite(color: Color) -> Color:
        return "black" if color == "white" else "white"

    def require_player(self, player_id: str) -> Color:
        color = self.get_player_color(player_id)
        if color is None or color == "spectator":
            raise GameError("Игрок не участвует в партии")
        return color

    def roll_dice(self, player_id: str) -> Dict[str, Union[str, List[int]]]:
        color = self.require_player(player_id)
        if self.state.winner:
            raise GameError("Партия уже завершена")
        if color != self.state.current_player:
            raise GameError("Сейчас очередь соперника")
        if self.state.pending_moves:
            raise GameError("Используйте текущие очки хода")
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        dice = [die1, die2]
        if die1 == die2:
            dice = [die1] * 4
        self.state.dice = dice.copy()
        self.state.pending_moves = dice.copy()
        self.state.last_roll = [die1, die2]
        if not self._has_legal_moves(color):
            self.state.dice = []
            self.state.pending_moves = []
            self._switch_turn()
            return {"message": "Ходов нет — ход переходит сопернику.", "dice": dice}
        return {"dice": dice}

    # Helpers for legal move calculations --------------------------------------
    def _home_range(self, color: Color) -> range:
        return range(0, 6) if color == "white" else range(18, 24)

    def _direction(self, color: Color) -> int:
        return -1 if color == "white" else 1

    def _entry_point(self, color: Color, die: int) -> int:
        if color == "white":
            return 24 - die
        return die - 1

    def _target_from_move(self, color: Color, from_point: int, die: int) -> int:
        return from_point + self._direction(color) * die

    def _all_points(self, color: Color) -> List[int]:
        return [i for i, value in enumerate(self.state.board) if (value > 0 and color == "white") or (value < 0 and color == "black")]

    def _has_legal_moves(self, color: Color) -> bool:
        if self.state.winner:
            return False
        pending = self.state.pending_moves
        if not pending:
            return False
        dice_values = sorted(set(pending))
        bar_count = self.state.bar[color]
        if bar_count > 0:
            for die in dice_values:
                if self._can_enter_from_bar(color, die):
                    return True
            return False
        for point in self._all_points(color):
            for die in dice_values:
                if self._can_move_from_point(color, point, die):
                    return True
        return False

    def _can_enter_from_bar(self, color: Color, die: int) -> bool:
        target = self._entry_point(color, die)
        if target < 0 or target > 23:
            return False
        occupant = self.state.board[target]
        if color == "white":
            return occupant > -2
        return occupant < 2

    def _can_move_from_point(self, color: Color, point: int, die: int) -> bool:
        if color == "white" and self.state.board[point] <= 0:
            return False
        if color == "black" and self.state.board[point] >= 0:
            return False
        target = self._target_from_move(color, point, die)
        if target < 0:
            return self._can_bear_off(color, point, die)
        if target > 23:
            return self._can_bear_off(color, point, die)
        occupant = self.state.board[target]
        if color == "white" and occupant < -1:
            return False
        if color == "black" and occupant > 1:
            return False
        return True

    def _all_checkers_in_home(self, color: Color) -> bool:
        home = self._home_range(color)
        if self.state.bar[color] > 0:
            return False
        for idx, value in enumerate(self.state.board):
            if color == "white" and value > 0 and idx not in home:
                return False
            if color == "black" and value < 0 and idx not in home:
                return False
        return True

    def _can_bear_off(self, color: Color, point: int, die: int) -> bool:
        if not self._all_checkers_in_home(color):
            return False
        if color == "white":
            distance = point + 1
            if die == distance:
                return True
            if die > distance:
                higher_points = [i for i in range(point + 1, 6) if self.state.board[i] > 0]
                return len(higher_points) == 0
            return False
        distance = 24 - point
        if die == distance:
            return True
        if die > distance:
            lower_points = [i for i in range(18, point) if self.state.board[i] < 0]
            return len(lower_points) == 0
        return False

    def move_checker(
        self,
        player_id: str,
        from_point: Union[int, str],
        to_point: Union[int, str],
        die: int,
    ) -> Dict[str, str]:
        color = self.require_player(player_id)
        if self.state.winner:
            raise GameError("Партия уже завершена")
        if color != self.state.current_player:
            raise GameError("Сейчас очередь соперника")
        if die not in self.state.pending_moves:
            raise GameError("Нет такого значения кости")
        bar_required = self.state.bar[color] > 0
        if bar_required and from_point != "bar":
            raise GameError("Сначала нужно вывести шашки с бара")
        if from_point == "bar":
            message = self._move_from_bar(color, die)
        else:
            if not isinstance(from_point, int):
                raise GameError("Некорректная точка старта")
            message = self._move_on_board(color, from_point, to_point, die)
        self.state.pending_moves.remove(die)
        if not self.state.pending_moves or not self._has_legal_moves(color):
            self._switch_turn()
        self._check_winner()
        return message

    def _move_from_bar(self, color: Color, die: int) -> Dict[str, str]:
        if self.state.bar[color] <= 0:
            raise GameError("На баре нет шашек")
        target = self._entry_point(color, die)
        if target < 0 or target > 23:
            raise GameError("Нельзя сделать такой ход")
        occupant = self.state.board[target]
        if color == "white" and occupant < -1:
            raise GameError("Пункт занят двумя шашками соперника")
        if color == "black" and occupant > 1:
            raise GameError("Пункт занят двумя шашками соперника")
        self.state.bar[color] -= 1
        self._place_checker(color, target)
        return {"message": f"Вывели шашку на пункт {target + 1}"}

    def _move_on_board(self, color: Color, from_point: int, to_point: Union[int, str], die: int) -> Dict[str, str]:
        if from_point < 0 or from_point > 23:
            raise GameError("Некорректный пункт")
        if color == "white" and self.state.board[from_point] <= 0:
            raise GameError("На пункте нет ваших шашек")
        if color == "black" and self.state.board[from_point] >= 0:
            raise GameError("На пункте нет ваших шашек")
        target = self._target_from_move(color, from_point, die)
        bearing_off = False
        if isinstance(to_point, str) and to_point == "bear_off":
            if not self._can_bear_off(color, from_point, die):
                raise GameError("Пока нельзя снимать шашки")
            bearing_off = True
        else:
            if target < 0 or target > 23:
                if not self._can_bear_off(color, from_point, die):
                    raise GameError("Такой ход невозможен")
                bearing_off = True
            else:
                if to_point != target:
                    raise GameError("Некорректный пункт назначения")
        self._remove_checker(color, from_point)
        if bearing_off:
            self.state.borne_off[color] += 1
            return {"message": "Снята шашка"}
        self._place_checker(color, target)
        return {"message": f"Ход на пункт {target + 1}"}

    def _remove_checker(self, color: Color, point: int) -> None:
        if color == "white":
            self.state.board[point] -= 1
        else:
            self.state.board[point] += 1

    def _place_checker(self, color: Color, point: int) -> None:
        occupant = self.state.board[point]
        if color == "white":
            if occupant == -1:
                self.state.board[point] = 1
                self.state.bar["black"] += 1
            else:
                self.state.board[point] += 1
        else:
            if occupant == 1:
                self.state.board[point] = -1
                self.state.bar["white"] += 1
            else:
                self.state.board[point] -= 1

    def pass_turn(self, player_id: str) -> Dict[str, str]:
        color = self.require_player(player_id)
        if color != self.state.current_player:
            raise GameError("Сейчас очередь соперника")
        if self.state.pending_moves and self._has_legal_moves(color):
            raise GameError("Ещё есть доступные ходы")
        self._switch_turn()
        return {"message": "Ход передан сопернику"}

    def _switch_turn(self) -> None:
        if self.state.pending_moves:
            self.state.pending_moves = []
        self.state.dice = []
        if not self.state.winner:
            self.state.current_player = self.opposite(self.state.current_player)

    def _check_winner(self) -> None:
        for color in ("white", "black"):
            if self.state.borne_off[color] >= 15:
                self.state.winner = color
                self.state.current_player = color

    # --- Serialization ---------------------------------------------------------
    def serialize(self, player_id: Optional[str] = None) -> Dict[str, Union[str, int, List[int], Dict[str, Union[int, str, None]]]]:
        color = self.get_player_color(player_id) if player_id else None
        players = {
            c: {"name": slot.name}
            for c, slot in self.player_slots.items()
            if slot.id is not None
        }
        state = {
            "id": self.state.id,
            "created_at": self.state.created_at.isoformat() + "Z",
            "board": self.state.board,
            "bar": self.state.bar,
            "borne_off": self.state.borne_off,
            "current_player": self.state.current_player,
            "dice": self.state.dice,
            "pending_moves": self.state.pending_moves,
            "last_roll": self.state.last_roll,
            "players": players,
            "spectators": list(self.spectators.values()),
            "winner": self.state.winner,
        }
        if color:
            state["you"] = {"role": color}
        return state

    # --- Websocket management --------------------------------------------------
    async def connect(self, websocket: WebSocket, player_id: str) -> None:
        await websocket.accept()
        key = id(websocket)
        self.connections[key] = websocket
        self.connection_players[key] = player_id

    async def disconnect(self, websocket: WebSocket) -> None:
        key = id(websocket)
        self.connections.pop(key, None)
        self.connection_players.pop(key, None)

    async def broadcast(self) -> None:
        removable = []
        for key, websocket in list(self.connections.items()):
            player_id = self.connection_players.get(key)
            try:
                payload = {"type": "state", "state": self.serialize(player_id)}
                await websocket.send_json(payload)
            except Exception:
                removable.append(websocket)
        for websocket in removable:
            await self.disconnect(websocket)
