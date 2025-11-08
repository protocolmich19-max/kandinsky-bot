import random
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple, Union

Player = int  # 1 for white, -1 for black
Point = Union[int, str]  # board index, "bar", or "off"


class BackgammonGame:
    POINTS = 24
    CHECKERS_PER_PLAYER = 15

    def __init__(self, game_id: str):
        self.id = game_id
        self.board: List[int] = [0] * self.POINTS
        self.bar: Dict[Player, int] = {1: 0, -1: 0}
        self.borne_off: Dict[Player, int] = {1: 0, -1: 0}
        self.players: Dict[Player, Dict[str, Any]] = {}
        self.current_player: Optional[Player] = None
        self.dice: List[int] = []
        self.moves_left: List[int] = []
        self.history: List[Dict[str, Any]] = []
        self.started: bool = False
        self.winner: Optional[Player] = None
        self.last_roll: Dict[Player, Tuple[int, int]] = {}
        self.reset_board()

    def reset_board(self) -> None:
        """Place checkers in the classic short backgammon layout."""
        self.board = [0] * self.POINTS
        # White pieces (player 1)
        self.board[23] = 2
        self.board[12] = 5
        self.board[7] = 3
        self.board[5] = 5
        # Black pieces (player -1)
        self.board[0] = -2
        self.board[11] = -5
        self.board[16] = -3
        self.board[18] = -5
        self.bar = {1: 0, -1: 0}
        self.borne_off = {1: 0, -1: 0}
        self.current_player = None
        self.dice = []
        self.moves_left = []
        self.history = []
        self.started = False
        self.winner = None
        self.last_roll = {}

    def add_player(self, sid: str, nickname: str) -> Optional[Player]:
        if 1 not in self.players:
            self.players[1] = {"sid": sid, "nickname": nickname}
            return 1
        if -1 not in self.players:
            self.players[-1] = {"sid": sid, "nickname": nickname}
            return -1
        return None

    def remove_player(self, sid: str) -> None:
        for player, info in list(self.players.items()):
            if info.get("sid") == sid:
                del self.players[player]
                if self.started and player == self.current_player:
                    self.current_player = -player if -player in self.players else None
                break
        if len(self.players) < 2:
            self.started = False
            self.current_player = None
            self.dice = []
            self.moves_left = []

    def player_color(self, player: Player) -> str:
        return "white" if player == 1 else "black"

    def start_if_ready(self) -> None:
        if len(self.players) == 2 and not self.started:
            self.started = True
            self.opening_roll()

    def opening_roll(self) -> None:
        while True:
            white_roll = random.randint(1, 6)
            black_roll = random.randint(1, 6)
            if white_roll != black_roll:
                break
        if white_roll > black_roll:
            self.current_player = 1
            self.dice = [white_roll, black_roll]
        else:
            self.current_player = -1
            self.dice = [black_roll, white_roll]
        if self.dice[0] == self.dice[1]:
            self.moves_left = [self.dice[0]] * 4
        else:
            self.moves_left = self.dice.copy()
        self.last_roll[self.current_player] = (self.dice[0], self.dice[1])

    def roll_dice(self, player: Player) -> Tuple[int, int]:
        if self.winner is not None:
            raise ValueError("The game is finished")
        if self.current_player != player:
            raise ValueError("Not your turn")
        if self.moves_left:
            raise ValueError("You must use all dice before rolling again")
        d1 = random.randint(1, 6)
        d2 = random.randint(1, 6)
        self.dice = [d1, d2]
        self.moves_left = [d1, d2] if d1 != d2 else [d1] * 4
        self.last_roll[player] = (d1, d2)
        return d1, d2

    def other_player(self, player: Player) -> Player:
        return -player

    def direction(self, player: Player) -> int:
        return -1 if player == 1 else 1

    def entry_point(self, player: Player, die: int) -> int:
        if player == 1:
            return 24 - die
        return die - 1

    def can_bear_off(self, player: Player) -> bool:
        if self.bar[player] > 0:
            return False
        if player == 1:
            return all(self.board[i] <= 0 for i in range(6, self.POINTS))
        return all(self.board[i] >= 0 for i in range(0, self.POINTS - 6))

    def furthest_checker_index(self, player: Player) -> Optional[int]:
        if player == 1:
            indices = [i for i in range(6) if self.board[i] > 0]
        else:
            indices = [i for i in range(18, self.POINTS) if self.board[i] < 0]
        return max(indices) if indices else None

    def is_move_legal(self, player: Player, source: Point, dest: Point, die: int) -> bool:
        if die not in self.moves_left:
            return False
        if self.winner is not None:
            return False
        direction = self.direction(player)
        if self.bar[player] > 0 and source != "bar":
            return False
        if source == "bar":
            if self.bar[player] <= 0:
                return False
            if not isinstance(dest, int):
                return False
            expected = self.entry_point(player, die)
            if dest != expected:
                return False
        else:
            if not isinstance(source, int):
                return False
            if self.board[source] * player <= 0:
                return False
            target_index = source + direction * die
            if isinstance(dest, str) and dest != "off":
                return False
            if dest == "off":
                if not self.can_bear_off(player):
                    return False
                if player == 1:
                    if target_index != -1:
                        highest = self.furthest_checker_index(player)
                        if highest is not None and source != highest:
                            return False
                else:
                    if target_index != self.POINTS:
                        highest = self.furthest_checker_index(player)
                        if highest is not None and source != highest:
                            return False
            else:
                if dest != target_index:
                    return False
        if dest == "off":
            return True
        if not isinstance(dest, int):
            return False
        point_value = self.board[dest]
        if point_value * player <= -2:
            return False
        return True

    def apply_move(self, player: Player, source: Point, dest: Point, die: int) -> None:
        if not self.is_move_legal(player, source, dest, die):
            raise ValueError("Illegal move")
        if source == "bar":
            self.bar[player] -= 1
        else:
            assert isinstance(source, int)
            self.board[source] -= player
        if dest == "off":
            self.borne_off[player] += 1
        else:
            assert isinstance(dest, int)
            if self.board[dest] * player == -1:
                self.board[dest] = 0
                self.bar[self.other_player(player)] += 1
            self.board[dest] += player
        self.moves_left.remove(die)
        self.history.append({
            "player": self.player_color(player),
            "from": source,
            "to": dest,
            "die": die,
        })
        if self.borne_off[player] >= self.CHECKERS_PER_PLAYER:
            self.winner = player
        if not self.moves_left or not self.has_any_legal_moves(player):
            self.end_turn(player, automatic=True)

    def end_turn(self, player: Player, automatic: bool = False) -> None:
        if self.current_player != player:
            raise ValueError("Not your turn")
        if not automatic and self.moves_left and self.has_any_legal_moves(player):
            raise ValueError("You still have legal moves")
        self.dice = []
        self.moves_left = []
        if self.winner is None:
            next_player = self.other_player(player)
            self.current_player = next_player if next_player in self.players else None
        else:
            self.current_player = None

    def has_any_legal_moves(self, player: Player) -> bool:
        if not self.moves_left:
            return False
        moves = self.compute_legal_moves(player)
        return bool(moves)

    def compute_legal_moves(self, player: Player) -> List[Dict[str, Any]]:
        if self.current_player != player or not self.moves_left or self.winner is not None:
            return []
        moves: List[Dict[str, Any]] = []
        dice_counts = Counter(self.moves_left)
        for die, count in dice_counts.items():
            for _ in range(count):
                if self.bar[player] > 0:
                    dest = self.entry_point(player, die)
                    if self.board[dest] * player > -2:
                        moves.append({"from": "bar", "to": dest, "die": die})
                    continue
                for idx in range(self.POINTS):
                    if self.board[idx] * player <= 0:
                        continue
                    dest = idx + self.direction(player) * die
                    if dest < 0 or dest >= self.POINTS:
                        if self.can_bear_off(player):
                            furthest = self.furthest_checker_index(player)
                            if furthest is None:
                                continue
                            if player == 1 and idx != furthest and dest != -1:
                                continue
                            if player == -1 and idx != furthest and dest != self.POINTS:
                                continue
                            moves.append({"from": idx, "to": "off", "die": die})
                        continue
                    point_value = self.board[dest]
                    if point_value * player <= -2:
                        continue
                    moves.append({"from": idx, "to": dest, "die": die})
        return moves

    def serialize_players(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for player, info in self.players.items():
            result[self.player_color(player)] = {
                "nickname": info.get("nickname"),
                "sid": info.get("sid"),
            }
        return result

    def to_dict(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {
            "id": self.id,
            "board": self.board,
            "bar": {"white": self.bar[1], "black": self.bar[-1]},
            "borneOff": {"white": self.borne_off[1], "black": self.borne_off[-1]},
            "players": self.serialize_players(),
            "currentPlayer": self.player_color(self.current_player) if self.current_player else None,
            "dice": self.dice,
            "movesLeft": self.moves_left,
            "history": self.history[-10:],
            "winner": self.player_color(self.winner) if self.winner else None,
        }
        if self.current_player:
            moves = self.compute_legal_moves(self.current_player)
            state["legalMoves"] = [
                {
                    "player": self.player_color(self.current_player),
                    "from": move["from"],
                    "to": move["to"],
                    "die": move["die"],
                }
                for move in moves
            ]
        else:
            state["legalMoves"] = []
        return state
