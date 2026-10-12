"""Spiele als Replay-Engine: Zustand wird immer aus der Wurfliste neu berechnet
(dadurch sind Korrektur/Undo trivial)."""
import copy

CRICKET_NUMS = [20, 19, 18, 17, 16, 15, 25]


def finishable(rem, out_mode):
    if out_mode == "single":
        return rem <= 60 or rem in (50,)
    if out_mode == "master":
        return rem <= 60 or rem == 50
    return (rem <= 40 and rem % 2 == 0) or rem == 50


class Game:
    def __init__(self, mode, players, opts=None):
        self.mode = mode
        self.players = players            # [{'id':..,'name':..}]
        self.opts = {"start": 501, "in": "single", "out": "double", "legs": 1, **(opts or {})}
        self.turns = []                   # [{'p': idx, 'leg': n, 'darts': [score], 'closed': bool}]
        self.state = {}
        self.replay()

    # ---------- öffentliche API ----------
    def add_dart(self, s):
        if self.state.get("winner") is not None:
            return []
        t = self._open_turn()
        t["darts"].append(s)
        return self.replay()

    def next_turn(self):
        if self.turns and not self.turns[-1]["closed"]:
            self.turns[-1]["closed"] = True
        return self.replay()

    def edit_dart(self, i, s):
        t = self._open_turn(create=False) or (self.turns[-1] if self.turns else None)
        if t and 0 <= i < len(t["darts"]):
            t["darts"][i] = s
        return self.replay()

    def undo(self):
        if not self.turns:
            return self.replay()
        t = self.turns[-1]
        if t["darts"]:
            t["darts"].pop()
            t["closed"] = False
        else:
            self.turns.pop()
            if self.turns:
                self.turns[-1]["closed"] = False
        if self.turns and not self.turns[-1]["darts"]:
            self.turns.pop()
        return self.replay()

    def _open_turn(self, create=True):
        if self.turns and not self.turns[-1]["closed"]:
            return self.turns[-1]
        if not create:
            return None
        st = self.state
        t = {"p": st["current"], "leg": st["leg"], "darts": [], "closed": False}
        self.turns.append(t)
        return t

    # ---------- Replay ----------
    def replay(self):
        n = len(self.players)
        st = {"mode": self.mode, "opts": self.opts, "leg": 0, "leg_starter": 0,
              "legs_won": [0] * n, "current": 0, "winner": None, "leg_winner": None,
              "players": [], "turn": None, "last_turn": None}
        self._init_leg(st)
        events = []
        for ti, t in enumerate(self.turns):
            t["p"], t["leg"] = st["current"], st["leg"]
            ev = self._apply_turn(st, t)
            t["pts"] = ev.get("points", 0)
            last = ti == len(self.turns) - 1
            if ev.get("leg_won") is not None:
                t["closed"] = True
            if len(t["darts"]) >= 3 or ev.get("bust"):
                t["closed"] = True
            if last:
                events.append({"turn": ev, "player": st["current"]})
            if t["closed"]:
                st["last_turn"] = {"p": st["current"], "darts": t["darts"], **ev}
                if ev.get("leg_won") is not None:
                    w = ev["leg_won"]
                    st["legs_won"][w] += 1
                    st["leg_winner"] = w
                    if st["legs_won"][w] >= self.opts["legs"]:
                        st["winner"] = w
                        break
                    st["leg"] += 1
                    st["leg_starter"] = (st["leg_starter"] + 1) % n
                    st["current"] = st["leg_starter"]
                    self._init_leg(st)
                else:
                    st["current"] = (st["current"] + 1) % n
        open_t = self.turns[-1] if self.turns and not self.turns[-1]["closed"] else None
        st["turn"] = {"p": st["current"], "darts": open_t["darts"] if open_t else []}
        if open_t and st["players"]:
            st["turn"]["start_score"] = open_t.get("_start")
        self.state = st
        self._suggest(st)
        return events

    def _init_leg(self, st):
        n = len(self.players)
        if self.mode == "x01":
            st["players"] = [{"score": self.opts["start"], "opened": self.opts["in"] == "single"}
                             for _ in range(n)]
        elif self.mode == "cricket":
            st["players"] = [{"marks": {str(k): 0 for k in CRICKET_NUMS}, "points": 0} for _ in range(n)]
        elif self.mode == "atc":
            st["players"] = [{"target": 1} for _ in range(n)]

    def _apply_turn(self, st, t):
        return getattr(self, "_turn_" + self.mode)(st, t)

    # ---------- X01 ----------
    def _turn_x01(self, st, t):
        p = st["players"][st["current"]]
        start = p["score"]
        t["_start"] = start
        rem, opened, ev = start, p["opened"], {"points": 0}
        for d in t["darts"]:
            v = d["value"]
            if not opened:
                if (self.opts["in"] == "double" and d["mult"] == 2) or \
                   (self.opts["in"] == "master" and d["mult"] in (2, 3)):
                    opened = True
                else:
                    continue
            new = rem - v
            out = self.opts["out"]
            ok_finish = (out == "single") or (out == "double" and d["mult"] == 2) or \
                        (out == "master" and d["mult"] in (2, 3))
            if new < 0 or (new == 0 and not ok_finish) or (new == 1 and out != "single"):
                ev = {"bust": True, "points": 0}
                rem = start
                break
            rem = new
            if rem == 0:
                ev = {"points": start, "checkout": start, "leg_won": st["current"]}
                break
        else:
            ev = {"points": start - rem}
        if not ev.get("bust"):
            p["score"], p["opened"] = rem, opened
        return ev

    # ---------- Cricket ----------
    def _turn_cricket(self, st, t):
        me = st["current"]
        ps = st["players"]
        pts = 0
        for d in t["darts"]:
            k = str(d["seg"])
            if k not in ps[me]["marks"]:
                continue
            hits = d["mult"] if d["seg"] != 25 else (2 if d["value"] == 50 else 1)
            have = ps[me]["marks"][k]
            close = min(hits, max(0, 3 - have))
            extra = hits - close
            ps[me]["marks"][k] = have + close
            if extra and any(o["marks"][k] < 3 for i, o in enumerate(ps) if i != me):
                val = 25 if d["seg"] == 25 else d["seg"]
                ps[me]["points"] += extra * val
                pts += extra * val
            if self._cricket_won(ps, me):
                return {"points": pts, "leg_won": me}
        return {"points": pts}

    @staticmethod
    def _cricket_won(ps, me):
        if not all(v >= 3 for v in ps[me]["marks"].values()):
            return False
        return all(ps[me]["points"] >= o["points"] for i, o in enumerate(ps) if i != me)

    # ---------- Around the Clock ----------
    def _turn_atc(self, st, t):
        p = st["players"][st["current"]]
        for d in t["darts"]:
            if d["seg"] == (p["target"] if p["target"] <= 20 else 25):
                p["target"] += 1
                if p["target"] > 21:
                    return {"leg_won": st["current"]}
        return {}

    # ---------- Checkout-Vorschlag ----------
    def _suggest(self, st):
        st["checkout"] = None
        if self.mode != "x01" or st["winner"] is not None:
            return
        p = st["players"][st["current"]]
        thrown = len(st["turn"]["darts"])
        rem = p["score"]
        if st["turn"]["darts"] and st["turn"].get("start_score") is not None:
            # während Aufnahme: Live-Restscore
            rem = self._live_rem(st)
        st["live_score"] = rem
        if p["opened"]:
            st["checkout"] = checkout(rem, 3 - thrown, self.opts["out"])

    def _live_rem(self, st):
        sim = copy.deepcopy(st["players"][st["current"]])
        t = {"darts": st["turn"]["darts"]}
        fake = {"players": [sim], "current": 0}
        self._turn_x01(fake, t)
        return sim["score"]

    def summary(self):
        return {"mode": self.mode, "players": self.players, "state": self.state,
                "turns": [{k: v for k, v in t.items() if not k.startswith("_")} for t in self.turns]}


# ---------- Checkout-Tabelle ----------
from functools import lru_cache

_ALL = [("BULL", 50, 2), ("25", 25, 1)] + [
    (f"{p}{s}", m * s, m) for s in range(20, 0, -1) for p, m in (("T", 3), ("D", 2), ("S", 1))]
_PREF_END = {"D20": 0, "D16": 0, "D8": 1, "D18": 1, "D12": 1, "D10": 1, "D4": 2, "BULL": 4}


def _last_ok(m, out):
    return out == "single" or (out == "double" and m == 2) or (out == "master" and m in (2, 3))


@lru_cache(maxsize=4096)
def checkout(rem, darts_left, out="double"):
    if rem > 180 or rem < 1 or darts_left <= 0:
        return None
    ends = [d for d in _ALL if _last_ok(d[2], out)]
    for n in range(1, darts_left + 1):
        best = None
        for end in ends:
            pre = rem - end[1]
            for combo in _setups(pre, n - 1):
                cost = _PREF_END.get(end[0], 3) + sum(0 if c.startswith("T") else 1 for c in combo)
                if best is None or cost < best[0]:
                    best = (cost, list(combo) + [end[0]])
        if best:
            return best[1]
    return None


@lru_cache(maxsize=8192)
def _setups(rem, n):
    if n == 0:
        return [()] if rem == 0 else []
    if rem <= 0:
        return []
    res = []
    for d in _ALL:
        if d[1] <= rem:
            for r in _setups(rem - d[1], n - 1):
                res.append((d[0],) + r)
                if len(res) > 40:
                    return res
    return res
