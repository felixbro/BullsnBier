import asyncio, json, os, random, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, board, db, settings
from .games import Game, checkout

SIM = config.SIM
STATIC = os.path.join(os.path.dirname(__file__), "static")

clients: set[WebSocket] = set()
S = {"game": None, "await_takeout": False, "last_event": None, "saved": None}
loop: asyncio.AbstractEventLoop | None = None
detector = None


@asynccontextmanager
async def lifespan(_app):
    global loop, detector
    loop = asyncio.get_running_loop()
    if not SIM:
        from .vision import Detector
        detector = Detector(config.CAMERAS, on_detector_event)
        detector.start()
    yield


app = FastAPI(title="DartCam", lifespan=lifespan)


# ---------------- Broadcast ----------------
async def broadcast(msg):
    data = json.dumps(msg)
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.discard(ws)


def state_msg(calls=None, **extra):
    g = S["game"]
    m = {"type": "state", "game": g.summary() if g else None, "await_takeout": S["await_takeout"],
         "sim": SIM, "detector": detector_info(), "calls": calls or []}
    m.update(extra)
    return m


def detector_info():
    if not detector:
        return {"running": False}
    return {"running": True, "fps": round(detector.fps, 1), "paused": detector.paused,
            "cams": [{"id": c.id, "src": c.src, "ok": c.ok, "cal": c.id in detector.H} for c in detector.cams]}


# ---------------- Caller-Events (Text baut der Browser aus den Vorlagen) ----------------
def next_call(g):
    """Ansage für den Spieler, der jetzt dran ist."""
    st = g.state
    p = st["current"]
    c = {"k": "next", "p": p}
    if g.mode == "x01":
        sc = st["players"][p]["score"]
        c["score"] = sc
        c["finish"] = bool(st["players"][p]["opened"] and checkout(sc, 3, g.opts["out"]))
    return c


def turn_calls(g, turn):
    """Events nach einer abgeschlossenen Aufnahme."""
    st, calls = g.state, []
    ev = st["last_turn"] or {}
    if ev.get("bust"):
        calls.append({"k": "bust"})
    elif g.mode == "x01" and ev.get("leg_won") is None:
        calls.append({"k": "turn", "points": ev.get("points", 0)})
    if st.get("winner") is not None:
        calls.append({"k": "match", "p": st["winner"]})
        if not S.get("saved"):
            S["saved"] = db.save_game(g)
    elif ev.get("leg_won") is not None:
        calls.append({"k": "leg", "p": ev["leg_won"]})
        calls.append(next_call(g))
    else:
        calls.append(next_call(g))
    return calls


# ---------------- Spiel-Logik ----------------
async def handle_dart(s, pos=None, source="cam"):
    g = S["game"]
    if not g or g.state.get("winner") is not None:
        await broadcast({"type": "dart_free", "score": s, "pos": pos,
                         "calls": [{"k": "dart", "d": s["name"]}]})
        return
    if S["await_takeout"]:
        if source == "cam" or (source == "sim" and not settings.load()["game"]["auto_next_sim"]):
            if source == "sim":
                await broadcast({"type": "warn", "msg": "Erst „Pfeile gezogen“ drücken"})
            return  # Abpraller / 4. Pfeil ignorieren
        S["await_takeout"] = False  # manuell/Simulator: nächste Aufnahme beginnt direkt
    s = {**s, "pos": pos}
    g.add_dart(s)
    turn = g.turns[-1] if g.turns else None
    calls = [{"k": "dart", "d": s["name"]}]
    if turn and turn["closed"]:
        calls += turn_calls(g, turn)
        S["await_takeout"] = True
    await broadcast(state_msg(calls, dart=s))


async def handle_takeout():
    g = S["game"]
    calls = [{"k": "takeout"}]
    if g and not S["await_takeout"] and g.turns and not g.turns[-1]["closed"] \
            and g.state.get("winner") is None:
        g.next_turn()  # Aufnahme mit < 3 Darts beenden
        calls += turn_calls(g, g.turns[-1])
    S["await_takeout"] = False
    if detector:
        detector.reset_reference()
    await broadcast(state_msg(calls, takeout=True))


def on_detector_event(ev):
    if loop:
        asyncio.run_coroutine_threadsafe(_on_ev(ev), loop)


async def _on_ev(ev, source="cam"):
    S["last_event"] = {**ev, "ts": time.time()}
    if ev["type"] == "dart":
        await handle_dart(ev["score"], [ev["x"], ev["y"]], source)
    elif ev["type"] == "takeout":
        await handle_takeout()
    elif ev["type"] == "dart_unknown":
        await broadcast({"type": "warn", "msg": "Pfeil erkannt, Position unklar – bitte manuell eintragen"})


# ---------------- WebSocket ----------------
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_text(json.dumps(state_msg()))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)


# ---------------- API: Spiel ----------------
@app.get("/api/state")
def api_state():
    return state_msg()


@app.post("/api/game")
async def api_game(body: dict):
    ps = []
    known = {p["id"]: p for p in db.players()}
    for p in body.get("players", []):
        if isinstance(p, int) and p in known:
            ps.append(known[p])
        elif isinstance(p, str) and p.strip():
            ps.append({"id": None, "name": p.strip(), "spoken": ""})
    if not ps:
        raise HTTPException(400, "Keine Spieler")
    S["game"] = Game(body.get("mode", "x01"), ps, body.get("opts"))
    S["saved"] = None
    S["await_takeout"] = False
    if detector:
        detector.reset_reference()
    await broadcast(state_msg([{"k": "start", "p": 0}]))
    return {"ok": True}


@app.delete("/api/game")
async def api_end():
    S["game"] = None
    await broadcast(state_msg())
    return {"ok": True}


@app.post("/api/dart")
async def api_dart(body: dict):
    try:
        s = board.from_name(body["name"])
    except Exception:
        raise HTTPException(400, "Ungültiges Feld")
    pos = body.get("pos") or board.board_point_for(s["name"])
    await handle_dart(s, pos, "manual")
    return {"ok": True}


@app.post("/api/edit")
async def api_edit(body: dict):
    g = S["game"]
    if not g:
        raise HTTPException(400)
    s = board.from_name(body["name"])
    t = g.turns[-1] if g.turns else None
    if t is not None and t["closed"] and S["await_takeout"]:
        t["closed"] = False  # letzte Aufnahme wieder öffnen
    pos = body.get("pos") or board.board_point_for(s["name"])
    g.edit_dart(int(body["i"]), {**s, "pos": pos})
    calls = [{"k": "corrected", "d": s["name"]}]
    t = g.turns[-1] if g.turns else None
    if t and t["closed"]:
        S["await_takeout"] = True
        if g.state.get("winner") is not None or (g.state["last_turn"] or {}).get("leg_won") is not None:
            calls += turn_calls(g, t)
    await broadcast(state_msg(calls))
    return {"ok": True}


@app.post("/api/undo")
async def api_undo():
    if S["game"] and not S.get("saved"):
        S["game"].undo()
        S["await_takeout"] = False
    await broadcast(state_msg())
    return {"ok": True}


@app.post("/api/next")
async def api_next():
    await handle_takeout()
    return {"ok": True}


# ---------------- API: Spieler / Stats ----------------
@app.get("/api/players")
def api_players():
    return db.players()


@app.post("/api/players")
def api_add_player(body: dict):
    return db.add_player(body["name"])


@app.put("/api/players/{pid}")
def api_upd_player(pid: int, body: dict):
    return db.update_player(pid, body.get("name"), body.get("spoken"))


@app.delete("/api/players/{pid}")
def api_del_player(pid: int):
    db.del_player(pid)
    return db.players()


@app.get("/api/stats/{pid}")
def api_stats(pid: int):
    return db.player_stats(pid)


@app.get("/api/games")
def api_games():
    return db.recent_games()


# ---------------- API: Kameras / Kalibrierung ----------------
def _cam(cid):
    if not detector:
        raise HTTPException(404, "Simulator-Modus – keine Kameras")
    for c in detector.cams:
        if c.id == cid:
            return c
    raise HTTPException(404)


@app.get("/api/cam/{cid}.jpg")
def api_cam_jpg(cid: str, overlay: int = 0):
    c = _cam(cid)
    return Response(c.jpeg(detector.overlay(cid) if overlay else None), media_type="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.get("/api/cam/{cid}/stream")
async def api_cam_stream(cid: str, overlay: int = 1):
    c = _cam(cid)

    async def gen():
        while True:
            jpg = c.jpeg(detector.overlay(cid) if overlay else None)
            yield b"--f\r\nContent-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            await asyncio.sleep(0.1)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=f")


@app.get("/api/cal")
def api_cal_get():
    return detector.cal if detector else {}


@app.post("/api/cal/{cid}")
async def api_cal(cid: str, body: dict):
    _cam(cid)
    pts = {k: [float(v[0]), float(v[1])] for k, v in body["points"].items()}
    detector.set_cal(cid, pts)
    await broadcast(state_msg())
    return {"ok": True, "calibrated": cid in detector.H}


@app.post("/api/detect/reset")
async def api_reset():
    if detector:
        detector.reset_reference()
    return {"ok": True}


@app.post("/api/detect/pause")
async def api_pause(body: dict):
    if detector:
        detector.paused = bool(body.get("paused"))
    await broadcast(state_msg())
    return {"ok": True}


# ---------------- Einstellungen ----------------
@app.get("/api/settings")
def api_settings():
    return settings.load()


@app.put("/api/settings")
async def api_settings_save(body: dict):
    data = settings.save(body)
    await broadcast({"type": "settings", "settings": data})
    return data


@app.delete("/api/settings")
async def api_settings_reset():
    data = settings.reset()
    await broadcast({"type": "settings", "settings": data})
    return data


# ---------------- Simulator ----------------
@app.post("/api/sim/throw")
async def api_sim(body: dict | None = None):
    if not SIM:
        raise HTTPException(403, "Nur im Simulator-Modus")
    body = body or {}
    if "x" in body:
        x, y = float(body["x"]), float(body["y"])
    else:
        aim = board.board_point_for(body.get("aim", "T20")) or (0, 0)
        sd = float(body.get("spread", 18))
        x, y = random.gauss(aim[0], sd), random.gauss(aim[1], sd)
    await _on_ev({"type": "dart", "x": x, "y": y, "score": board.score(x, y), "cams": {}}, "sim")
    return {"x": x, "y": y, "score": board.score(x, y)}


@app.post("/api/sim/takeout")
async def api_sim_takeout():
    await _on_ev({"type": "takeout"})
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
