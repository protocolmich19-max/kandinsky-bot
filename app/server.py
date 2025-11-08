import os
import uuid
from typing import Dict

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room

from game.backgammon import BackgammonGame


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "backgammon-secret")
socketio = SocketIO(app, cors_allowed_origins="*")

games: Dict[str, BackgammonGame] = {}


def game_state(game: BackgammonGame) -> Dict:
    return game.to_dict()


def color_to_player(color: str) -> int:
    if color == "white":
        return 1
    if color == "black":
        return -1
    raise ValueError("Unknown player color")


def normalize_point(value):
    if value in ("bar", "off"):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("create_game")
def handle_create(data):
    nickname = (data or {}).get("nickname", "Игрок 1")
    game_id = uuid.uuid4().hex[:6].upper()
    game = BackgammonGame(game_id)
    games[game_id] = game
    color = game.add_player(request.sid, nickname)
    join_room(game_id)
    emit(
        "game_created",
        {
            "gameId": game_id,
            "color": game.player_color(color),
            "state": game_state(game),
        },
    )


@socketio.on("join_game")
def handle_join(data):
    game_id = (data or {}).get("gameId")
    nickname = (data or {}).get("nickname", "Игрок 2")
    if not game_id or game_id not in games:
        emit("error", {"message": "Партия не найдена."})
        return
    game = games[game_id]
    if len(game.players) >= 2 and request.sid not in [p["sid"] for p in game.players.values()]:
        emit("error", {"message": "Комната уже заполнена."})
        return
    if request.sid not in [p["sid"] for p in game.players.values()]:
        color = game.add_player(request.sid, nickname)
    else:
        color = next(
            (player for player, info in game.players.items() if info.get("sid") == request.sid),
            None,
        )
    join_room(game_id)
    if len(game.players) == 2:
        game.start_if_ready()
    emit(
        "game_joined",
        {
            "gameId": game_id,
            "color": game.player_color(color) if color else None,
            "state": game_state(game),
        },
    )
    socketio.emit("game_update", game_state(game), room=game_id)


@socketio.on("roll_dice")
def handle_roll(data):
    game_id = (data or {}).get("gameId")
    color = (data or {}).get("color")
    try:
        player = color_to_player(color)
    except ValueError:
        emit("error", {"message": "Неверный игрок."})
        return
    game = games.get(game_id)
    if not game:
        emit("error", {"message": "Партия не найдена."})
        return
    if player not in game.players or game.players[player].get("sid") != request.sid:
        emit("error", {"message": "Вы не участвуете в этой партии."})
        return
    try:
        game.roll_dice(player)
    except ValueError as exc:
        emit("error", {"message": str(exc)})
        return
    socketio.emit("game_update", game_state(game), room=game_id)


@socketio.on("make_move")
def handle_move(data):
    game_id = (data or {}).get("gameId")
    color = (data or {}).get("color")
    source = normalize_point((data or {}).get("from"))
    dest = normalize_point((data or {}).get("to"))
    die = (data or {}).get("die")
    try:
        player = color_to_player(color)
    except ValueError:
        emit("error", {"message": "Неверный игрок."})
        return
    game = games.get(game_id)
    if not game:
        emit("error", {"message": "Партия не найдена."})
        return
    if player not in game.players or game.players[player].get("sid") != request.sid:
        emit("error", {"message": "Вы не участвуете в этой партии."})
        return
    try:
        die_value = int(die)
    except (TypeError, ValueError):
        emit("error", {"message": "Неверное значение кости."})
        return
    try:
        game.apply_move(player, source, dest, die_value)
    except ValueError as exc:
        emit("error", {"message": str(exc)})
        return
    socketio.emit("game_update", game_state(game), room=game_id)


@socketio.on("end_turn")
def handle_end_turn(data):
    game_id = (data or {}).get("gameId")
    color = (data or {}).get("color")
    try:
        player = color_to_player(color)
    except ValueError:
        emit("error", {"message": "Неверный игрок."})
        return
    game = games.get(game_id)
    if not game:
        emit("error", {"message": "Партия не найдена."})
        return
    if player not in game.players or game.players[player].get("sid") != request.sid:
        emit("error", {"message": "Вы не участвуете в этой партии."})
        return
    try:
        game.end_turn(player)
    except ValueError as exc:
        emit("error", {"message": str(exc)})
        return
    socketio.emit("game_update", game_state(game), room=game_id)


@socketio.on("disconnect")
def handle_disconnect():
    empty_games = []
    for game_id, game in games.items():
        if request.sid in [info.get("sid") for info in game.players.values()]:
            game.remove_player(request.sid)
            leave_room(game_id)
            socketio.emit("game_update", game_state(game), room=game_id)
            if not game.players:
                empty_games.append(game_id)
            break
    for gid in empty_games:
        games.pop(gid, None)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
