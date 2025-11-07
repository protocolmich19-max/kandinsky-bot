import asyncio
from typing import Dict, Optional, Union

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from .game import Game, GameError

app = FastAPI(title="Short Backgammon Online")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

_games: Dict[str, Game] = {}
_games_lock = asyncio.Lock()


class CreateGameRequest(BaseModel):
    name: str = Field(default="Игрок 1", max_length=40)


class JoinGameRequest(BaseModel):
    name: str = Field(default="Игрок", max_length=40)


class PlayerRequest(BaseModel):
    player_id: str


class MoveRequest(PlayerRequest):
    from_point: Union[int, str]
    to_point: Union[int, str]
    die: int


async def get_game(game_id: str) -> Game:
    game = _games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Партия не найдена")
    return game


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/games")
async def create_game(payload: CreateGameRequest) -> Dict[str, object]:
    async with _games_lock:
        game = Game()
        _games[game.state.id] = game
    async with game.lock:
        color, player_id = game.assign_player(payload.name, preferred="white")
        state = game.serialize(player_id)
    return {"game_id": game.state.id, "player_id": player_id, "color": color, "state": state}


@app.post("/api/games/{game_id}/join")
async def join_game(game_id: str, payload: JoinGameRequest, game: Game = Depends(get_game)) -> Dict[str, object]:
    async with game.lock:
        color, player_id = game.assign_player(payload.name)
        state = game.serialize(player_id)
    await game.broadcast()
    return {"game_id": game_id, "player_id": player_id, "color": color, "state": state}


@app.get("/api/games/{game_id}")
async def get_state(game_id: str, player_id: Optional[str] = None, game: Game = Depends(get_game)) -> Dict[str, object]:
    async with game.lock:
        state = game.serialize(player_id)
    return {"state": state}


@app.post("/api/games/{game_id}/roll")
async def roll(game_id: str, payload: PlayerRequest, game: Game = Depends(get_game)) -> Dict[str, object]:
    async with game.lock:
        try:
            result = game.roll_dice(payload.player_id)
            state = game.serialize(payload.player_id)
        except GameError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    await game.broadcast()
    return {"result": result, "state": state}


@app.post("/api/games/{game_id}/move")
async def move(game_id: str, payload: MoveRequest, game: Game = Depends(get_game)) -> Dict[str, object]:
    async with game.lock:
        try:
            result = game.move_checker(
                player_id=payload.player_id,
                from_point=payload.from_point,
                to_point=payload.to_point,
                die=payload.die,
            )
            state = game.serialize(payload.player_id)
        except GameError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    await game.broadcast()
    return {"result": result, "state": state}


@app.post("/api/games/{game_id}/pass")
async def pass_turn(game_id: str, payload: PlayerRequest, game: Game = Depends(get_game)) -> Dict[str, object]:
    async with game.lock:
        try:
            result = game.pass_turn(payload.player_id)
            state = game.serialize(payload.player_id)
        except GameError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
    await game.broadcast()
    return {"result": result, "state": state}


@app.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str, player_id: str) -> None:
    game = await get_game(game_id)
    async with game.lock:
        if game.get_player_color(player_id) is None:
            await websocket.close(code=4401)
            return
    await game.connect(websocket, player_id)
    try:
        async with game.lock:
            await websocket.send_json({"type": "state", "state": game.serialize(player_id)})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await game.disconnect(websocket)


__all__ = ["app"]
