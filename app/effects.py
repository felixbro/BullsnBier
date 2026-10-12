"""Ereignisse → WLED-Effekte. Gleiche Ereignis-Schlüssel steuern auch die Browser-Animationen.

WLED-JSON-API: POST http://<host>/json/state
Effekt-IDs (WLED ≥ 0.14): 0 Solid · 1 Blink · 2 Breathe · 3 Wipe · 9 Rainbow · 12 Fade · 14 Theater Rainbow
  20 Sparkle · 23 Strobe · 24 Strobe Rainbow · 25 Multi Strobe · 28 Chase · 40 Scanner · 41 Comet · 42 Fireworks
Statt Effekt kann je Ereignis auch ein WLED-Preset (ps) gewählt werden."""
import asyncio, json, urllib.request


# key: (Bezeichnung, Gruppe)
EVENTS = {
    "idle":          ("Leerlauf / kein Spiel", "Status"),
    "game_start":    ("Spielstart", "Spiel"),
    "bulloff":       ("Bull-Off läuft", "Spiel"),
    "next_player":   ("Nächster Spieler (Spielerfarbe)", "Spiel"),
    "checkout":      ("Spieler im Finish-Bereich", "Spiel"),
    "takeout":       ("Pfeile ziehen", "Spiel"),
    "dart_single":   ("Treffer Single", "Wurf"),
    "dart_double":   ("Treffer Double", "Wurf"),
    "dart_triple":   ("Treffer Triple", "Wurf"),
    "dart_bull":     ("Bull / Bullseye", "Wurf"),
    "dart_miss":     ("Daneben (Miss)", "Wurf"),
    "score_100":     ("Aufnahme 100+", "Aufnahme"),
    "score_140":     ("Aufnahme 140+", "Aufnahme"),
    "score_180":     ("180!", "Aufnahme"),
    "score_low":     ("Aufnahme unter 20 (Ups)", "Aufnahme"),
    "bust":          ("Überworfen", "Aufnahme"),
    "halved":        ("Bermuda: halbiert", "Aufnahme"),
    "gotcha":        ("Gotcha: erwischt", "Aufnahme"),
    "shanghai":      ("Shanghai!", "Aufnahme"),
    "high_finish":   ("Finish 100+", "Sieg"),
    "leg_won":       ("Leg gewonnen", "Sieg"),
    "match_won":     ("Spiel gewonnen (Winner!)", "Sieg"),
    "dart_unknown":  ("Pfeil nicht erkannt", "Fehler"),
    "cal_warn":      ("Kalibrierung ungenau", "Fehler"),
    "cam_error":     ("Kamera fehlt / nicht kalibriert", "Fehler"),
    "paused":        ("Erkennung pausiert", "Status"),
}


def E(fx, c1, c2="#000000", dur=1.5, sx=128, ix=128, bri=200, on=True):
    return {"on": on, "type": "fx", "fx": fx, "c1": c1, "c2": c2, "sx": sx, "ix": ix, "bri": bri,
            "dur": dur, "ps": 1}


# dur = Sekunden, danach zurück zum Grundzustand · dur 0 = bleibt (Grundzustand)
DEFAULTS = {
    "idle":         E(2, "#7FDDEB", bri=60, dur=0, sx=60),
    "game_start":   E(3, "#DDF96A", dur=1.4, sx=200),
    "bulloff":      E(40, "#FF6B5E", "#3DBB7A", dur=0, sx=180),
    "next_player":  E(0, "player", dur=0),
    "checkout":     E(2, "player", dur=0, sx=150),
    "takeout":      E(28, "#7FDDEB", "player", dur=0, sx=160),
    "dart_single":  E(0, "#ffffff", dur=0.4, on=False),
    "dart_double":  E(1, "#3DBB7A", dur=0.8, sx=220),
    "dart_triple":  E(1, "#FF6B5E", dur=1.2, sx=220),
    "dart_bull":    E(23, "#3DBB7A", "#FF6B5E", dur=1.4, sx=200),
    "dart_miss":    E(12, "#BDC8CB", dur=1.0, sx=200),
    "score_100":    E(28, "#DDF96A", dur=1.5, sx=200),
    "score_140":    E(41, "#FF6B5E", "#DDF96A", dur=2.0, sx=200),
    "score_180":    E(25, "#DDF96A", dur=2.4, sx=220),
    "score_low":    E(12, "#BDC8CB", dur=1.0, on=False),
    "bust":         E(23, "#FF6B5E", dur=1.5, sx=230),
    "halved":       E(1, "#FF6B5E", dur=1.5),
    "gotcha":       E(1, "#FF6B5E", "player", dur=1.5, sx=220),
    "shanghai":     E(24, "#FF6B5E", dur=1.6),
    "high_finish":  E(42, "#3DBB7A", "#DDF96A", dur=1.6),
    "leg_won":      E(42, "player", dur=2.2),
    "match_won":    E(9, "#DDF96A", dur=0, sx=180),
    "dart_unknown": E(1, "#FF6B5E", dur=1.5, sx=230),
    "cal_warn":     E(1, "#7FDDEB", "#FF6B5E", dur=2.0, sx=200),
    "cam_error":    E(1, "#FF6B5E", "#7FDDEB", dur=0, sx=160),
    "paused":       E(2, "#FF6B5E", bri=60, dur=0),
}

PLAYER_COLORS = ["#6FA8FF", "#FF7A6B", "#5FCB92", "#FFD66B", "#B79CFF", "#FFB27A", "#7FDDEB", "#FF8FC2"]  # --p1 … --p8


def hex_rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] if len(h) == 6 else [255, 255, 255]


class Wled:
    def __init__(self):
        self.base = ("idle", {})
        self.timer: asyncio.Task | None = None
        self.last_error = None

    def cfg(self):
        from . import settings  # spät importieren (settings nutzt EVENTS/DEFAULTS von hier)
        return settings.load()["wled"]

    def color(self, c, ctx):
        if c == "player":
            return hex_rgb(ctx.get("color") or PLAYER_COLORS[ctx.get("p", 0) % len(PLAYER_COLORS)])
        return hex_rgb(c)

    def payload(self, key, ctx, force=False):
        e = self.cfg()["effects"].get(key)
        if not e or not (e.get("on") or force):
            return None
        if e.get("type") == "preset":
            return {"on": True, "ps": int(e.get("ps", 1))}
        if e.get("type") == "off":
            return {"on": False}
        return {"on": True, "bri": int(e.get("bri", 200)), "tt": 0,
                "seg": {"fx": int(e.get("fx", 0)), "sx": int(e.get("sx", 128)), "ix": int(e.get("ix", 128)),
                        "col": [self.color(e.get("c1", "#ffffff"), ctx), self.color(e.get("c2", "#000000"), ctx),
                                [0, 0, 0]]}}

    async def send(self, payload):
        hosts = [h.strip() for h in self.cfg().get("hosts", "").split(",") if h.strip()]
        if not hosts or payload is None:
            return
        data = json.dumps(payload).encode()

        def post(h):
            url = h if h.startswith("http") else f"http://{h}"
            req = urllib.request.Request(url.rstrip("/") + "/json/state", data=data,
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=1.5).read()

        for h in hosts:
            try:
                await asyncio.to_thread(post, h)
                self.last_error = None
            except Exception as ex:  # WLED nicht erreichbar -> Spiel läuft weiter
                self.last_error = f"{h}: {ex}"

    async def update(self, base, trig=None, ctx=None, force=False):
        """base = (key, ctx) Grundzustand · trig = kurzer Effekt, danach zurück zum Grundzustand."""
        c = self.cfg()
        changed = force or base != self.base
        self.base = base
        if not c["enabled"]:
            return
        e = c["effects"].get(trig) if trig else None
        if e and e.get("on"):
            self._cancel()
            await self.send(self.payload(trig, ctx or {}))
            if float(e.get("dur", 0)) > 0:
                self.timer = asyncio.create_task(self._revert(float(e["dur"])))
            return
        if changed and not (self.timer and not self.timer.done()):
            await self.send(self.payload(*self.base))

    async def test(self, key, ctx, base):
        """Vorschau: Effekt zeigen, nach Effektdauer (höchstens 10 s) zurück zum Grundzustand –
        ist WLED in der App aus, gehen die LEDs danach aus."""
        self.base = base
        if not self.cfg()["effects"].get(key):
            return
        self._cancel()
        await self.send(self.payload(key, ctx, force=True))
        dur = min(10.0, float(self.cfg()["effects"][key].get("dur", 0)) or 10.0)
        self.timer = asyncio.create_task(self._revert(dur, off_if_disabled=True))

    def _cancel(self):
        if self.timer and not self.timer.done():
            self.timer.cancel()
        self.timer = None

    async def _revert(self, dur, off_if_disabled=False):
        try:
            await asyncio.sleep(dur)
            self.timer = None
            if self.cfg()["enabled"]:
                await self.send(self.payload(*self.base) or {"on": False})
            elif off_if_disabled:
                await self.send({"on": False})
        except asyncio.CancelledError:
            pass

    async def fetch(self, path):
        hosts = [h.strip() for h in self.cfg().get("hosts", "").split(",") if h.strip()]
        if not hosts:
            return None
        url = (hosts[0] if hosts[0].startswith("http") else f"http://{hosts[0]}").rstrip("/") + path
        return await asyncio.to_thread(lambda: json.loads(urllib.request.urlopen(url, timeout=2).read()))


wled = Wled()
