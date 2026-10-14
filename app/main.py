import asyncio
import time, json, math, os, random
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import Response, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import config, board, db, settings, tts, avatars, train
from .games import Game, MODE_NAMES, RULES, finishable
from .effects import wled, EVENTS

SIM = config.SIM
STATIC = os.path.join(os.path.dirname(__file__), "static")
CAL_WARN_MM = float(os.environ.get("CAL_WARN_MM", 20))

clients: set[WebSocket] = set()
S = {"game": None, "await_takeout": False, "saved": None, "bulloff": None, "errors": []}
loop: asyncio.AbstractEventLoop | None = None
detector = None


@asynccontextmanager
async def lifespan(_app):
    global loop, detector
    loop = asyncio.get_running_loop()
    _h = loop.get_exception_handler()
    def _quiet(lp, ctx):   # Windows: Browser schließt Verbindung → harmloser ConnectionResetError (WinError 10054)
        if isinstance(ctx.get("exception"), (ConnectionResetError, ConnectionAbortedError)):
            return
        (_h or lp.default_exception_handler)(ctx) if _h is None else _h(lp, ctx)
    loop.set_exception_handler(_quiet)
    if not SIM:
        from .vision import Detector, init_resolution
        await asyncio.to_thread(init_resolution, config.CAMERAS)
        detector = Detector(config.CAMERAS, on_detector_event)
        detector.start()
    mon = asyncio.create_task(monitor())
    warm_speech()
    await emit([])
    yield
    mon.cancel()


app = FastAPI(title="Bulls'n'Bier", lifespan=lifespan)

# ---------------- Zugangsschutz (optional, z. B. Demo im Internet) ----------------
# ACCESS_KEY=geheim → einmal https://host/?key=geheim öffnen, danach merkt sich der Browser das per Cookie.
ACCESS_KEY = os.environ.get("ACCESS_KEY", "").strip()


class KeyGate:
    def __init__(self, app):
        self.inner = app

    async def __call__(self, scope, receive, send):
        if not ACCESS_KEY or scope["type"] not in ("http", "websocket") or scope.get("path") == "/healthz":
            return await self.inner(scope, receive, send)
        from urllib.parse import parse_qs
        from http.cookies import SimpleCookie
        qs = parse_qs(scope.get("query_string", b"").decode())
        hdr = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        ck = SimpleCookie(hdr.get("cookie", ""))
        ok = (ck.get("bnb_key") and ck["bnb_key"].value == ACCESS_KEY) or qs.get("key", [""])[0] == ACCESS_KEY
        if ok:
            if qs.get("key") and scope["type"] == "http":   # Cookie setzen
                async def send2(msg):
                    if msg["type"] == "http.response.start":
                        msg.setdefault("headers", []).append(
                            (b"set-cookie", f"bnb_key={ACCESS_KEY}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax".encode()))
                    await send(msg)
                return await self.inner(scope, receive, send2)
            return await self.inner(scope, receive, send)
        if scope["type"] == "websocket":
            return await send({"type": "websocket.close", "code": 4401})
        body = "<!doctype html><meta charset=utf-8><title>Bulls'n'Bier</title><body style='font:18px sans-serif;padding:40px'>" \
               "<form>Zugangsschlüssel: <input name=key autofocus> <button>Los</button></form>".encode()
        await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/html; charset=utf-8")]})
        await send({"type": "http.response.body", "body": body})


app.add_middleware(KeyGate)


# ---------------- Zustand → Clients ----------------
async def broadcast(msg):
    data = json.dumps(msg)
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.discard(ws)


def bulloff_info():
    b = S["bulloff"]
    if not b:
        return None
    return {"players": b["players"], "round": b["round"], "throws": b["throws"],
            "current": b["order"][len(b["throws"])] if len(b["throws"]) < len(b["order"]) else None}


def state_msg(calls=None, fx=None, **extra):
    g = S["game"]
    m = {"type": "state", "game": g.summary() if g else None, "await_takeout": S["await_takeout"],
         "sim": SIM, "detector": detector_info(), "calls": calls or [], "fx": fx,
         "bulloff": bulloff_info(), "errors": S["errors"]}
    m.update(extra)
    return m


def detector_info():
    if not detector:
        return {"running": False}
    return {"running": True, "fps": round(detector.fps, 1), "paused": detector.paused,
            "cams": [{"id": c.id, "src": c.src, "ok": c.ok, "cal": c.id in detector.H} for c in detector.cams]}


# ---------------- Ereignisse → Effekte (WLED + Browser) ----------------
PRIO = ["match_won", "high_finish", "leg_won", "shanghai", "score_180", "bust", "gotcha", "halved",
        "score_140", "score_100", "dart_bull", "dart_triple", "dart_double", "dart_miss", "score_low",
        "dart_single", "game_start", "dart_unknown", "cal_warn"]


def call_fx(c):
    k = c["k"]
    if k == "dart":
        n = c["d"]
        return "dart_bull" if n in ("BULL", "25") else "dart_miss" if n == "MISS" else \
            {"D": "dart_double", "T": "dart_triple"}.get(n[0], "dart_single")
    if k == "turn":
        p = c.get("points", 0)
        return "score_180" if p == 180 else "score_140" if p >= 140 else "score_100" if p >= 100 else \
            "score_low" if c.get("x01") and p < 20 else None
    if k == "leg":
        return "high_finish" if c.get("checkout", 0) >= 100 else "leg_won"
    return {"start": "game_start", "bust": "bust", "halved": "halved", "gotcha": "gotcha",
            "shanghai": "shanghai", "match": "match_won", "unknown": "dart_unknown",
            "cal_warn": "cal_warn"}.get(k)


def base_state():
    g = S["game"]
    if any(e["k"] == "cam_error" for e in S["errors"]):
        return ("cam_error", {})
    if detector and detector.paused:
        return ("paused", {})
    if S["bulloff"]:
        return ("bulloff", {"p": bulloff_info()["current"] or 0})
    if not g:
        return ("idle", {})
    st = g.state
    if st["winner"] is not None:
        return ("match_won", {"p": st["winner"]})
    p = st["current"]
    if S["await_takeout"]:
        return ("takeout", {"p": p})
    rem = g.remaining()
    if rem and g.mode in ("x01", "random_checkout", "gotcha") and finishable(rem, g.opts.get("out", "double")):
        return ("checkout", {"p": p})
    return ("next_player", {"p": p})


def pcolor(i):
    ps = S["game"].players if S["game"] else (S["bulloff"]["players"] if S["bulloff"] else [])
    return ps[i].get("color") if i is not None and 0 <= i < len(ps) else None


def with_color(ctx):
    if ctx and "p" in ctx:
        return {**ctx, "color": pcolor(ctx["p"])}
    return ctx


async def emit(calls, **extra):
    keys = [k for k in (call_fx(c) for c in calls) if k]
    trig = min(keys, key=PRIO.index) if keys else None
    ctx = next(({"p": c["p"]} for c in calls if "p" in c and call_fx(c) == trig), None)
    if ctx is None:
        g = S["game"]
        ctx = {"p": g.state["current"]} if g else {}
    base = base_state()
    if trig == "match_won":
        trig = None  # Sieger ist Grundzustand (bleibt bis zum nächsten Spiel)
    fx = {"trigger": trig, "ctx": ctx, "base": base[0], "base_ctx": base[1]}
    await broadcast(state_msg(calls, fx, **extra))
    await wled.update((base[0], with_color(base[1])), trig, with_color(ctx))


# ---------------- Caller-Events ----------------
def next_call(g):
    st = g.state
    c = {"k": "next", "p": st["current"]}
    rem = g.remaining()
    if rem is not None:
        c["score"] = rem
        c["finish"] = finishable(rem, g.opts.get("out", "double"))
    t = g.target()
    if t:
        c["target"] = t
    return c


def turn_calls(g):
    st, calls = g.state, []
    ev = st["last_turn"] or {}
    p = ev.get("p", 0)
    if ev.get("bust"):
        calls.append({"k": "bust", "p": p})
    elif ev.get("halved"):
        calls.append({"k": "halved", "p": p})
    elif ev.get("leg_won") is None and "points" in ev and g.mode != "cricket":
        calls.append({"k": "turn", "points": ev["points"], "p": p, "x01": g.mode == "x01"})
    for i in ev.get("gotcha") or []:
        calls.append({"k": "gotcha", "p": i})
    if ev.get("shanghai"):
        calls.append({"k": "shanghai", "p": p})
    if st.get("winner") is not None:
        calls.append({"k": "match", "p": st["winner"]})
        if not S.get("saved"):
            S["saved"] = db.save_game(g)
    elif ev.get("leg_won") is not None:
        calls.append({"k": "leg", "p": ev["leg_won"], "checkout": ev.get("checkout", 0)})
        calls.append(next_call(g))
    else:
        calls.append(next_call(g))
    return calls


# ---------------- Reihenfolge ----------------
ROT_FILE = os.path.join(config.DATA, "rotation.json")


def _pkey(p):
    return f"id:{p['id']}" if p.get("id") is not None else f"g:{p['name'].lower()}"


def order_players(ps, opts, bulloff=False):
    """Erstes Spiel einer Runde: Zufallsreihenfolge. Danach bleibt die Reihenfolge gleich,
    es beginnt aber jedes Spiel der Nächste (in Legs rotiert die Engine selbst weiter)."""
    try:
        with open(ROT_FILE, encoding="utf-8") as f:
            rot = json.load(f)
    except Exception:
        rot = {}
    key = "|".join(sorted(_pkey(p) for p in ps))
    r = rot.get(key)
    by = {_pkey(p): p for p in ps}
    if r and set(r["order"]) == set(by):
        ps = [by[k] for k in r["order"]]
        first = r["next"] % len(ps)
    else:
        random.shuffle(ps)
        first = 0
    opts = {**opts, "first": first}
    if not bulloff:
        rot[key] = {"order": [_pkey(p) for p in ps], "next": (first + 1) % len(ps)}
        with open(ROT_FILE, "w", encoding="utf-8") as f:
            json.dump(rot, f)
    return ps, opts


# ---------------- Bull-Off ----------------
async def bulloff_dart(s, pos):
    b = S["bulloff"]
    i = b["order"][len(b["throws"])]
    dist = math.hypot(*pos) if pos else 999.0
    b["throws"].append({"p": i, "d": s["name"], "dist": round(dist, 1)})
    calls = [{"k": "dart", "d": s["name"]}]
    if len(b["throws"]) < len(b["order"]):
        calls.append({"k": "bulloff", "p": b["order"][len(b["throws"])]})
        return await emit(calls)
    best = min(t["dist"] for t in b["throws"])
    top = [t["p"] for t in b["throws"] if abs(t["dist"] - best) < 2]
    if len(top) > 1:  # Gleichstand -> nur diese nochmal
        b["order"], b["throws"], b["round"] = top, [], b["round"] + 1
        S["await_takeout"] = True
        calls.append({"k": "bulloff", "p": top[0]})
        return await emit(calls)
    w = top[0]
    S["bulloff"] = None
    await start_game(b["mode"], b["players"], {**b["opts"], "first": w}, calls + [{"k": "bulloff_win", "p": w}], takeout=True)


async def start_game(mode, ps, opts, pre_calls=None, takeout=False):
    S["game"] = Game(mode, ps, opts)
    S["saved"] = None
    S["await_takeout"] = takeout
    if detector and not takeout:
        detector.reset_reference()
    await emit((pre_calls or []) + [{"k": "start", "p": S["game"].state["current"]}])


# ---------------- Spiel-Logik ----------------
async def handle_dart(s, pos=None, source="cam"):
    g = S["game"]
    if S["await_takeout"]:
        if source == "cam" or (source == "sim" and not settings.load()["game"]["auto_next_sim"]):
            if source == "sim":
                await broadcast({"type": "warn", "msg": "Erst „Pfeile gezogen“ drücken"})
            return  # Abpraller / 4. Pfeil ignorieren
        S["await_takeout"] = False
    if S["bulloff"]:
        return await bulloff_dart(s, pos)
    if not g or g.state.get("winner") is not None:
        await broadcast({"type": "dart_free", "score": s, "pos": pos})
        return await emit([{"k": "dart", "d": s["name"]}])
    s = {**s, "pos": pos}
    g.add_dart(s)
    turn = g.turns[-1] if g.turns else None
    calls = [{"k": "dart", "d": s["name"], "p": turn["p"] if turn else 0}]
    if turn and turn["closed"]:
        S["await_takeout"] = True
        calls += turn_calls(g)
    await emit(calls, dart=s)


async def handle_takeout():
    g = S["game"]
    calls = [{"k": "takeout"}]
    if g and not S["await_takeout"] and g.turns and not g.turns[-1]["closed"] \
            and g.state.get("winner") is None:
        g.next_turn()
        calls += turn_calls(g)
    S["await_takeout"] = False
    if detector:
        detector.reset_reference()
    await emit(calls, takeout=True)


def on_detector_event(ev):
    if loop:
        asyncio.run_coroutine_threadsafe(_on_ev(ev), loop)


async def _on_ev(ev, source="cam"):
    if ev["type"] == "dart":
        # Nur warnen, wenn sich die Kameras wiederholt nicht einig sind (eine abweichende Cam ist normal: verdeckt/schräg)
        bad = ev.get("n", 0) >= 2 and ev.get("agree", 0) < 2 and ev.get("spread", 0) > CAL_WARN_MM
        S["calhist"] = (S.get("calhist", []) + [bad])[-6:]
        if bad and sum(S["calhist"]) >= 3 and time.time() - S.get("calwarn_t", 0) > 120:
            S["calwarn_t"] = time.time()
            await broadcast({"type": "warn", "msg": "Kameras oft uneinig – Kalibrierung prüfen"})
            b = base_state()
            await wled.update((b[0], with_color(b[1])), "cal_warn", {})
        await handle_dart({**ev["score"], "sid": ev.get("sid")}, [ev["x"], ev["y"]], source)
    elif ev["type"] == "takeout":
        await handle_takeout()
    elif ev["type"] == "dart_unknown":
        S["last_unknown"] = (ev.get("sid"), time.time())
        await broadcast({"type": "warn", "msg": "Pfeil erkannt, Position unklar – bitte manuell eintragen"})
        await emit([{"k": "unknown"}])


async def monitor():
    """Kamera-/Kalibrierungsstatus überwachen → Fehler-Ereignisse."""
    while True:
        await asyncio.sleep(2)
        if not detector:
            continue
        errs = []
        for c in detector.cams:
            if not c.ok:
                errs.append({"k": "cam_error", "msg": f"Kamera {int(c.id) + 1} ({c.src}) nicht verbunden"})
            elif c.id not in detector.H:
                errs.append({"k": "cam_error", "msg": f"Kamera {int(c.id) + 1} nicht kalibriert"})
        if errs != S["errors"]:
            new = len(errs) > len(S["errors"])
            S["errors"] = errs
            await emit([{"k": "cam_error"}] if new else [])


# ---------------- WebSocket ----------------
@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    b = base_state()
    await websocket.send_text(json.dumps(state_msg(fx={"trigger": None, "ctx": {}, "base": b[0], "base_ctx": b[1]})))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)


# ---------------- API: Spiel ----------------
@app.get("/api/state")
def api_state():
    return state_msg()


@app.get("/api/modes")
def api_modes():
    return {k: {"name": MODE_NAMES[k], "defaults": RULES[k].defaults} for k in RULES}


@app.post("/api/game")
async def api_game(body: dict):
    ps = []
    known = {p["id"]: p for p in db.players()}
    for p in body.get("players", []):
        if isinstance(p, int) and p in known:
            ps.append(dict(known[p]))
        elif isinstance(p, str) and p.strip():
            ps.append({"id": None, "name": p.strip(), "spoken": "", "seed": p.strip(), "guest": True})
    if not ps:
        raise HTTPException(400, "Keine Spieler")
    used = {p.get("color") for p in ps if p.get("color")}
    for p in ps:  # Gäste: freie Spielerfarbe, Farbe folgt dem Spieler
        if not p.get("color"):
            pref = db.PALETTE[sum(map(ord, p["name"].lower())) % 8]  # wie die Gast-Pille in „Neues Spiel“
            free = [c for c in db.PALETTE if c not in used]
            p["color"] = pref if pref not in used else random.choice(free) if free else random.choice(db.PALETTE)
            used.add(p["color"])
    mode = body.get("mode", "x01")
    if mode not in RULES:
        raise HTTPException(400, "Unbekannter Modus")
    opts = body.get("opts") or {}
    ps, opts = order_players(ps, opts, body.get("bulloff"))
    S["await_takeout"] = False
    if detector:
        detector.reset_reference()
    warm_players(ps, mode, opts)
    if body.get("bulloff") and len(ps) > 1:
        S["game"] = None
        S["bulloff"] = {"players": ps, "order": list(range(len(ps))), "throws": [], "round": 1,
                        "mode": mode, "opts": opts}
        await emit([{"k": "bulloff", "p": 0}])
        return {"ok": True}
    S["bulloff"] = None
    await start_game(mode, ps, opts)
    return {"ok": True}


@app.delete("/api/game")
async def api_end():
    S["game"], S["bulloff"], S["await_takeout"] = None, None, False
    await emit([])
    return {"ok": True}


def _with_ring(s, pos):
    if pos and s["mult"] == 1 and s["seg"] not in (0, 25):
        s["ring"] = "inner" if math.hypot(*pos) < board.R_TRIPLE_IN else "outer"
    return s


@app.get("/api/train")
def api_train():
    return train.stats()


@app.post("/api/train/collect")
def api_train_collect(body: dict):
    train.set_collect(body.get("on", True))
    return train.stats()


@app.get("/api/train/next")
def api_train_next(after: str = None):
    m = train.next_todo(after)
    if m and detector and m.get("status") == "corrected" and m.get("pos"):   # korrigierte Position → Vorschlag neu
        import numpy as np
        for cid, Hm in detector.H.items():
            if cid in m.get("size", {}):
                v = np.linalg.inv(Hm) @ np.array([m["pos"][0], m["pos"][1], 1.0])
                m.setdefault("proposal", {})[cid] = [float(v[0] / v[2]), float(v[1] / v[2])]
    return m or {}


@app.get("/api/train/{sid}/{cid}.jpg")
def api_train_img(sid: str, cid: str):
    p = train.image_path(sid, cid) if sid.replace("-", "").isdigit() and cid.isdigit() else None
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg")


@app.post("/api/train/{sid}")
def api_train_mark(sid: str, body: dict):
    """tips: {cid: [x, y] | null}  (null = Spitze in dieser Kamera nicht sichtbar) · skip: true = Wurf verwerfen"""
    if not train.read(sid):
        raise HTTPException(404)
    if body.get("delete"):
        train.remove(sid)
    elif body.get("skip"):
        train.update(sid, status="skip")
    else:
        kw = {"status": "ok", "tips": body.get("tips", {})}
        if body.get("name"):
            kw["name"] = body["name"]
        train.update(sid, **kw)
    return train.stats()


@app.post("/api/dart")
async def api_dart(body: dict):
    try:
        s = board.from_name(body["name"])
    except Exception:
        raise HTTPException(400, "Ungültiges Feld")
    pos = body.get("pos") or board.board_point_for(s["name"])
    sid, t = S.get("last_unknown") or (None, 0)
    if sid and time.time() - t < 30:   # Pfeil war gesehen, aber nicht erkannt → von Hand nachgetragen = Label
        S["last_unknown"] = None
        train.update(sid, status="corrected", name=s["name"], pos=body.get("pos"))
    await handle_dart({**_with_ring(s, pos), "sid": sid}, pos, "manual")
    return {"ok": True}


@app.post("/api/edit")
async def api_edit(body: dict):
    g = S["game"]
    if not g:
        raise HTTPException(400)
    s = board.from_name(body["name"])
    pos = body.get("pos") or board.board_point_for(s["name"])
    ti = body.get("ti")
    ti = len(g.turns) - 1 if ti is None else int(ti)
    winner_before = g.state.get("winner")
    try:
        old = g.turns[ti]["darts"][int(body["i"])]
    except (IndexError, KeyError):
        old = {}
    sid = old.get("sid")
    if sid and old.get("name") != s["name"]:   # Training: Erkennung lag falsch → Label korrigieren
        train.update(sid, status="corrected", name=s["name"], pos=body.get("pos"), detected=old.get("name"))
    g.edit_dart(int(body["i"]), {**_with_ring(s, pos), "pos": pos, "sid": sid}, ti)
    calls = [{"k": "corrected", "d": s["name"]}]
    if g.state.get("winner") is not None and winner_before is None:
        calls += turn_calls(g)
    if g.state.get("winner") is None and S.get("saved"):
        S["saved"] = None  # Sieg wurde wegkorrigiert
    await emit(calls)
    return {"ok": True}


@app.post("/api/undo")
async def api_undo():
    if S["game"] and not S.get("saved"):
        S["game"].undo()
        S["await_takeout"] = False
    await emit([])
    return {"ok": True}


@app.post("/api/next")
async def api_next():
    await handle_takeout()
    return {"ok": True}


# ---------------- API: Spieler / Stats ----------------
@app.get("/api/players")
def api_players():
    return db.players()


@app.get("/api/players/cards")
def api_player_cards():
    return db.player_cards()


@app.post("/api/players")
def api_add_player(body: dict):
    try:
        return db.add_player(body)
    except ValueError as ex:
        raise HTTPException(400, str(ex))


@app.put("/api/players/{pid}")
def api_upd_player(pid: int, body: dict):
    return db.update_player(pid, body)


@app.get("/api/avatar/styles")
def api_avatar_styles():
    return {"styles": [[k, v[0], bool(v[1])] for k, v in avatars.STYLES.items()], "ci": avatars.CI}


@app.get("/api/avatar")
async def api_avatar(seed: str, style: str = avatars.DEFAULT_STYLE, accent: str = "ci"):
    data = await asyncio.to_thread(avatars.get, seed, style, accent)
    if not data:
        raise HTTPException(404)
    return Response(data, media_type="image/svg+xml", headers={"Cache-Control": "max-age=31536000"})


@app.delete("/api/players/{pid}")
def api_del_player(pid: int):
    db.del_player(pid)
    return db.players()


@app.get("/api/stats/{pid}")
def api_stats(pid: int, period: str = "all"):
    return db.player_stats(pid, period)


@app.get("/api/today")
def api_today():
    return db.today()


@app.get("/api/records")
def api_records():
    return db.records()


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
    return {c.id: detector.points(c.id) for c in detector.cams} if detector else {}


@app.post("/api/cal/{cid}")
async def api_cal(cid: str, body: dict):
    _cam(cid)
    pts = {k: [float(v[0]), float(v[1])] for k, v in body["points"].items()}
    detector.set_cal(cid, pts)
    await emit([])
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
    await emit([])
    return {"ok": True}


# ---------------- Einstellungen ----------------
@app.get("/api/settings")
def api_settings():
    return settings.load()


@app.put("/api/settings")
async def api_settings_save(body: dict):
    data = settings.save(body)
    await broadcast({"type": "settings", "settings": data})
    if "caller" in body or "texts" in body:
        warm_speech()
    if "wled" in body:
        await wled.update(base_state(), None, {}, force=True)
    return data


@app.delete("/api/settings")
async def api_settings_reset():
    data = settings.reset()
    await broadcast({"type": "settings", "settings": data})
    return data


@app.get("/api/events")
def api_events():
    return {k: {"label": v[0], "group": v[1]} for k, v in EVENTS.items()}


# ---------------- WLED ----------------
@app.post("/api/wled/test/{key}")
async def api_wled_test(key: str, body: dict | None = None):
    if key not in EVENTS:
        raise HTTPException(404)
    p = (body or {}).get("p", 0)
    await broadcast({"type": "fx_test", "fx": {"trigger": key, "ctx": {"p": p}}})
    b = base_state()
    await wled.test(key, {"p": p, "color": (body or {}).get("color") or pcolor(p)}, (b[0], with_color(b[1])))
    return {"ok": wled.last_error is None, "error": wled.last_error}


@app.get("/api/wled/info")
async def api_wled_info():
    try:
        info = await wled.fetch("/json")
        return {"ok": True, "name": info["info"]["name"], "ver": info["info"]["ver"],
                "leds": info["info"]["leds"]["count"], "effects": info.get("effects", []),
                "presets": await _presets()}
    except Exception as ex:
        return {"ok": False, "error": str(ex)}


async def _presets():
    try:
        p = await wled.fetch("/presets.json")
        return {k: v.get("n", f"Preset {k}") for k, v in p.items() if k != "0" and isinstance(v, dict)}
    except Exception:
        return {}


# ---------------- Sprachausgabe (Piper) ----------------
@app.get("/api/tts")
async def api_tts(text: str, voice: str = "", rate: float = 1.0):
    try:
        wav = await asyncio.to_thread(tts.synth, text, voice, rate)
    except tts.TTSError as ex:
        raise HTTPException(503, str(ex))
    return Response(wav, media_type="audio/wav", headers={"Cache-Control": "max-age=86400"})


@app.get("/api/tts/voices")
def api_tts_voices():
    return {**tts.status(), "warm": tts.warm_status()}


def _voice_cfg():
    c = settings.load()
    cc = c["caller"]
    return c, cc["piper_voice"].get(cc["lang"], ""), float(cc["rate"])


def warm_speech():
    """Häufige Ansagen (Felder, Zahlen) vorab erzeugen, damit Piper im Spiel sofort spricht."""
    c, voice, rate = _voice_cfg()
    if c["caller"]["engine"] != "piper":
        return
    T = c["texts"][c["caller"]["lang"]]
    tts.warm(tts.base_phrases(T), voice, rate, prio=1)
    warm_players(db.players(), "none", {}, prio_hi=4)


def warm_players(ps, mode, opts, prio_hi=2, prio_lo=6):
    c, voice, rate = _voice_cfg()
    if c["caller"]["engine"] != "piper":
        return
    T = c["texts"][c["caller"]["lang"]]
    names = [(p.get("spoken") or "").strip() or p["name"] for p in ps]
    scores = [n for n in range(2, 171) if finishable(n, opts.get("out", "double"))] if mode in ("x01", "random_checkout") else []
    hi, _ = tts.player_phrases(T, names, [])
    key = "next_remaining" if len(ps) > 1 else "remaining"
    lo = [tts._fill(T[key], name=n, score=sc) for sc in scores for n in names]  # kleine Reste zuerst
    tts.warm(hi, voice, rate, prio=prio_hi)
    tts.warm(lo, voice, rate, prio=prio_lo)


@app.post("/api/tts/download")
async def api_tts_download(body: dict):
    try:
        await asyncio.to_thread(tts.download, body["voice"])
    except Exception as ex:
        raise HTTPException(500, f"Download fehlgeschlagen: {ex}")
    return tts.status()


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
    s = board.score(x, y)
    await _on_ev({"type": "dart", "x": x, "y": y, "score": s, "cams": {}}, "sim")
    return {"x": x, "y": y, "score": s}


@app.post("/api/sim/takeout")
async def api_sim_takeout():
    await _on_ev({"type": "takeout"})
    return {"ok": True}


@app.post("/api/sim/event/{kind}")
async def api_sim_event(kind: str):
    """Simulator: Fehlerfälle auslösen (unknown, cam_error, cal_warn, clear)."""
    if not SIM:
        raise HTTPException(403)
    if kind == "unknown":
        await _on_ev({"type": "dart_unknown"})
    elif kind == "cal_warn":
        await broadcast({"type": "warn", "msg": "Kameras weichen 31 mm ab – Kalibrierung prüfen"})
        await emit([{"k": "cal_warn"}])
    elif kind == "cam_error":
        S["errors"] = [{"k": "cam_error", "msg": "Kamera 2 (simuliert) nicht verbunden"}]
        await emit([{"k": "cam_error"}])
    elif kind == "clear":
        S["errors"] = []
        await emit([])
    return {"ok": True}


@app.api_route("/healthz", methods=["GET", "HEAD"])
def healthz():
    return {"ok": True}   # für Reverse-Proxy-Healthchecks, auch ohne Zugangsschlüssel erreichbar


@app.api_route("/remote", methods=["GET", "HEAD"])
def remote():
    return FileResponse(os.path.join(STATIC, "remote.html"))


@app.api_route("/", methods=["GET", "HEAD"])
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
