"""Spiele als Replay-Engine: Der Zustand wird immer komplett aus der Wurfliste neu berechnet.
Dadurch funktionieren Korrektur und Undo an beliebiger Stelle.

Neuer Modus = Klasse mit init/turn/best/view (+ optional remaining/target) und Eintrag in RULES."""
import math, random
from functools import lru_cache

BOGEY = {169, 168, 166, 165, 163, 162, 159}


def out_ok(d, out):
    return out == "single" or (out == "double" and d["mult"] == 2) or (out == "master" and d["mult"] in (2, 3))


def finishable(rem, out):
    return 0 < rem <= 170 and checkout(rem, 3, out) is not None


def field_label(f, n):
    if n == 25:
        return {"S": "Bull", "O": "Bull", "D": "Bullseye", "T": "Bullseye", "*": "Bull"}.get(f, "Bull")
    return {"S": f"Single {n}", "O": f"Single {n} außen", "D": f"Doppel {n}", "T": f"Triple {n}", "*": str(n)}[f]


def field_hit(d, f, n):
    """Trifft Dart d das Feld f (S/O/D/T/*) auf Zahl n?"""
    if d["seg"] != n:
        return False
    if n == 25:
        return d["name"] == "BULL" if f in ("D", "T") else True
    if f == "*":
        return True
    if f == "S":
        return d["mult"] == 1
    if f == "O":
        return d["mult"] == 1 and d.get("ring") != "inner"
    return d["mult"] == {"D": 2, "T": 3}[f]


class Rules:
    defaults = {}
    rounds_fixed = None          # feste Rundenzahl (Bermuda, Shanghai …)
    higher_wins = True

    def __init__(self, g):
        self.g, self.o = g, g.opts

    def rnd(self, *k):
        return random.Random("|".join(map(str, (self.o["seed"],) + k)))

    def round_limit(self):
        return self.rounds_fixed or self.o.get("max_rounds") or 0

    def start_leg(self, st):
        pass

    def init(self, st, i):
        return {}

    def turn(self, st, t):
        return {}

    def score_of(self, p):
        return p.get("score", 0)

    def best(self, st):
        ps = st["players"]
        key = (lambda i: self.score_of(ps[i])) if self.higher_wins else (lambda i: -self.score_of(ps[i]))
        return max(range(len(ps)), key=key)

    def view(self, st, i):
        return {"main": self.score_of(st["players"][i])}

    def remaining(self, st, i):
        return None

    def target(self, st, i):
        return None


# ---------------- X01 ----------------
class X01(Rules):
    defaults = {"start": 501, "in": "single", "out": "double", "bull": "25/50", "max_rounds": 0}
    higher_wins = False

    def start_score(self, st):
        return int(self.o["start"])

    def start_leg(self, st):
        st["leg_start"] = self.start_score(st)

    def init(self, st, i):
        return {"score": st["leg_start"], "opened": self.o["in"] == "single"}

    def val(self, d):
        return 50 if (self.o["bull"] == "50/50" and d["name"] == "25") else d["value"]

    def turn(self, st, t):
        p = st["players"][st["current"]]
        start, rem, opened = p["score"], p["score"], p["opened"]
        t["_start"] = start
        out = self.o["out"]
        for d in t["darts"]:
            if not opened:
                if (self.o["in"] == "double" and d["mult"] == 2) or (self.o["in"] == "master" and d["mult"] in (2, 3)):
                    opened = True
                else:
                    continue
            new = rem - self.val(d)
            if new < 0 or (new == 0 and not out_ok(d, out)) or (new == 1 and out != "single"):
                return {"bust": True, "points": 0}
            rem = new
            if rem == 0:
                p["score"], p["opened"] = 0, opened
                return {"points": start, "checkout": start, "leg_won": st["current"]}
        p["score"], p["opened"] = rem, opened
        return {"points": start - rem}

    def view(self, st, i):
        p = st["players"][i]
        return {"main": p["score"], "sub": "" if p["opened"] else f"{self.o['in'].capitalize()}-In"}

    def remaining(self, st, i):
        p = st["players"][i]
        return p["score"] if p["opened"] else None


class RandomCheckout(X01):
    defaults = {"min": 61, "max": 170, "out": "double", "in": "single", "bull": "25/50", "max_rounds": 0}

    def start_score(self, st):
        lo, hi = sorted((int(self.o["min"]), int(self.o["max"])))
        cands = [n for n in range(max(2, lo), min(170, hi) + 1) if finishable(n, self.o["out"])] or [40]
        return self.rnd("leg", st["leg"]).choice(cands)

    def view(self, st, i):
        return {"main": st["players"][i]["score"], "sub": f"Ziel {st['leg_start']}"}


# ---------------- Gotcha ----------------
class Gotcha(Rules):
    defaults = {"target": 301, "out": "single", "max_rounds": 0}

    def init(self, st, i):
        return {"score": 0}

    def turn(self, st, t):
        me, ps, T = st["current"], st["players"], int(self.o["target"])
        start = ps[me]["score"]
        cur = start
        for d in t["darts"]:
            new = cur + d["value"]
            if new > T or (new == T and not out_ok(d, self.o["out"])) or \
               (T - new == 1 and self.o["out"] != "single"):
                ps[me]["score"] = start
                return {"bust": True, "points": 0}
            cur = new
            if cur == T:
                ps[me]["score"] = cur
                return {"points": cur - start, "leg_won": me}
        ps[me]["score"] = cur
        caught = [i for i, o in enumerate(ps) if i != me and cur > 0 and o["score"] == cur]
        for i in caught:
            ps[i]["score"] = 0
        return {"points": cur - start, "gotcha": caught}

    def remaining(self, st, i):
        return int(self.o["target"]) - st["players"][i]["score"]

    def view(self, st, i):
        return {"main": st["players"][i]["score"], "sub": f"noch {self.remaining(st, i)}"}


# ---------------- Count Up ----------------
class CountUp(Rules):
    defaults = {"max_rounds": 8}

    def init(self, st, i):
        return {"score": 0}

    def turn(self, st, t):
        pts = sum(d["value"] for d in t["darts"])
        st["players"][st["current"]]["score"] += pts
        return {"points": pts}

    def view(self, st, i):
        return {"main": st["players"][i]["score"], "sub": f"Runde {min(st['round'], self.round_limit())}/{self.round_limit()}"}


# ---------------- Cricket ----------------
class Cricket(Rules):
    defaults = {"variant": "standard", "numbers": "cricket", "max_rounds": 0}

    def nums(self):
        return list(range(10 if self.o["numbers"] == "tactics" else 15, 21))[::-1] + [25]

    def init(self, st, i):
        return {"marks": {str(k): 0 for k in self.nums()}, "score": 0}

    @staticmethod
    def hits(d):
        return (2 if d["name"] == "BULL" else 1) if d["seg"] == 25 else d["mult"]

    def turn(self, st, t):
        me, ps, var = st["current"], st["players"], self.o["variant"]
        before = [p["score"] for p in ps]
        marks = 0
        for d in t["darts"]:
            k = str(d["seg"])
            if k not in ps[me]["marks"]:
                continue
            h = self.hits(d)
            have = ps[me]["marks"][k]
            close = min(h, 3 - have)
            extra = h - close
            ps[me]["marks"][k] = have + close
            marks += h
            val = 25 if d["seg"] == 25 else d["seg"]
            open_opp = [i for i, o in enumerate(ps) if i != me and o["marks"][k] < 3]
            if extra and open_opp and var == "standard":
                ps[me]["score"] += extra * val
            elif extra and open_opp and var == "cutthroat":
                for i in open_opp:
                    ps[i]["score"] += extra * val
            if self.won(ps, me):
                return {"points": ps[me]["score"] - before[me], "marks": marks, "leg_won": me}
        return {"points": ps[me]["score"] - before[me], "marks": marks}

    def won(self, ps, me):
        if not all(v >= 3 for v in ps[me]["marks"].values()):
            return False
        others = [o["score"] for i, o in enumerate(ps) if i != me]
        if self.o["variant"] == "cutthroat":
            return all(ps[me]["score"] <= s for s in others)
        if self.o["variant"] == "noscore":
            return True
        return all(ps[me]["score"] >= s for s in others)

    def best(self, st):
        ps = st["players"]
        m = lambda i: sum(ps[i]["marks"].values())
        if self.o["variant"] == "cutthroat":
            return min(range(len(ps)), key=lambda i: (ps[i]["score"], -m(i)))
        return max(range(len(ps)), key=lambda i: (ps[i]["score"], m(i)))

    def view(self, st, i):
        p = st["players"][i]
        return {"main": p["score"] if self.o["variant"] != "noscore" else sum(p["marks"].values()),
                "marks": p["marks"], "sub": ""}


# ---------------- Bermuda ----------------
BERMUDA = [12, 13, 14, "D", 15, 16, 17, "T", 18, 19, 20, "25", "B"]


class Bermuda(Rules):
    defaults = {}
    rounds_fixed = len(BERMUDA)

    def init(self, st, i):
        return {"score": 0}

    def tgt(self, st):
        return BERMUDA[min(st["round"], len(BERMUDA)) - 1]

    @staticmethod
    def hit(d, tg):
        if tg == "D":
            return d["mult"] == 2
        if tg == "T":
            return d["mult"] == 3
        if tg == "25":
            return d["seg"] == 25
        if tg == "B":
            return d["name"] == "BULL"
        return d["seg"] == tg

    def turn(self, st, t):
        p, tg = st["players"][st["current"]], self.tgt(st)
        pts = sum(d["value"] for d in t["darts"] if self.hit(d, tg))
        if (len(t["darts"]) >= 3 or t.get("closed")) and pts == 0:
            lost = p["score"] - p["score"] // 2
            p["score"] //= 2
            return {"points": 0, "halved": lost}
        p["score"] += pts
        return {"points": pts}

    def target(self, st, i):
        tg = self.tgt(st)
        return {"D": "beliebiges Doppel", "T": "beliebiges Triple", "25": "Bull", "B": "Bullseye"}.get(tg, str(tg))

    def view(self, st, i):
        return {"main": st["players"][i]["score"], "sub": f"Runde {min(st['round'], 13)}/13"}


# ---------------- Shanghai ----------------
class Shanghai(Rules):
    defaults = {"range": "1-20"}

    @property
    def rounds_fixed(self):
        return 7 if self.o["range"] == "1-7" else 20

    def init(self, st, i):
        return {"score": 0}

    def turn(self, st, t):
        n = min(st["round"], self.rounds_fixed)
        hits = [d for d in t["darts"] if d["seg"] == n]
        pts = sum(d["value"] for d in hits)
        st["players"][st["current"]]["score"] += pts
        if {d["mult"] for d in hits} >= {1, 2, 3}:
            return {"points": pts, "shanghai": True, "leg_won": st["current"]}
        return {"points": pts}

    def target(self, st, i):
        return str(min(st["round"], self.rounds_fixed))

    def view(self, st, i):
        return {"main": st["players"][i]["score"], "sub": f"Runde {min(st['round'], self.rounds_fixed)}/{self.rounds_fixed}"}


# ---------------- Around the Clock / Round the World ----------------
class AroundTheClock(Rules):
    defaults = {"field": "*", "order": "asc", "hits": 1, "max_rounds": 0}

    def seq(self):
        nums = list(range(1, 21))
        if self.o["order"] == "desc":
            nums.reverse()
        elif self.o["order"] == "random":
            self.rnd("order").shuffle(nums)
        return nums + [25]

    def init(self, st, i):
        st.setdefault("seq", self.seq())
        return {"idx": 0, "cnt": 0, "score": 0}

    def turn(self, st, t):
        p, seq, need = st["players"][st["current"]], st["seq"], int(self.o["hits"])
        n_hit = 0
        for d in t["darts"]:
            if p["idx"] >= len(seq):
                break
            if field_hit(d, self.o["field"], seq[p["idx"]]):
                n_hit += 1
                p["cnt"] += 1
                if p["cnt"] >= need:
                    p["idx"], p["cnt"] = p["idx"] + 1, 0
                    if p["idx"] >= len(seq):
                        return {"hits": n_hit, "leg_won": st["current"]}
        return {"hits": n_hit}

    def score_of(self, p):
        return p["idx"] * 10 + p["cnt"]

    def target(self, st, i):
        p = st["players"][i]
        return field_label(self.o["field"], st["seq"][min(p["idx"], len(st["seq"]) - 1)])

    def view(self, st, i):
        p, seq = st["players"][i], st["seq"]
        n = seq[min(p["idx"], len(seq) - 1)]
        need = int(self.o["hits"])
        return {"main": "Bull" if n == 25 else n,
                "sub": f"{p['idx']}/{len(seq)}" + (f" · {p['cnt']}/{need}" if need > 1 else "")}


class RoundTheWorld(AroundTheClock):
    defaults = {"order": "asc", "max_rounds": 0}

    def turn(self, st, t):
        p, seq = st["players"][st["current"]], st["seq"]
        pts = 0
        for d in t["darts"]:
            if p["idx"] < len(seq) and d["seg"] == seq[p["idx"]]:
                pts += d["value"]
                p["score"] += d["value"]
                p["idx"] += 1
                if p["idx"] >= len(seq):
                    return {"points": pts, "leg_won": st["current"]}
        return {"points": pts}

    def score_of(self, p):
        return p["idx"] * 1000 + p["score"]

    def target(self, st, i):
        n = st["seq"][min(st["players"][i]["idx"], len(st["seq"]) - 1)]
        return "Bull" if n == 25 else str(n)

    def view(self, st, i):
        p, seq = st["players"][i], st["seq"]
        n = seq[min(p["idx"], len(seq) - 1)]
        return {"main": "Bull" if n == 25 else n, "sub": f"{p['idx']}/{len(seq)} · {p['score']} P"}


# ---------------- Segment Training ----------------
class SegmentTraining(Rules):
    defaults = {"segment": 20, "field": "S", "end": "darts", "count": 33}

    def round_limit(self):
        return math.ceil(int(self.o["count"]) / 3) if self.o["end"] == "darts" else 0

    def init(self, st, i):
        return {"hits": 0, "darts": 0, "turns": 0}

    def field_for(self, st, i):
        f = self.o["field"]
        if f == "random":
            return self.rnd("seg", st["leg"], i, st["players"][i]["turns"]).choice(["S", "D", "T"])
        return f

    def turn(self, st, t):
        me = st["current"]
        p, f, n = st["players"][me], self.field_for(st, me), int(self.o["segment"])
        t["_field"] = f
        h = 0
        for d in t["darts"]:
            p["darts"] += 1
            if field_hit(d, f, n):
                h += 1
                p["hits"] += 1
                if self.o["end"] == "hits" and p["hits"] >= int(self.o["count"]):
                    return {"hits": h, "leg_won": me}
        if len(t["darts"]) >= 3 or t.get("closed"):
            p["darts"] += 3 - min(3, len(t["darts"]))  # nicht erkannte Darts zählen mit
            p["turns"] += 1
        return {"hits": h}

    def score_of(self, p):
        return p["hits"] * 1000 - p["darts"] if self.o["end"] == "hits" else p["hits"]

    def target(self, st, i):
        return field_label(self.field_for(st, i), int(self.o["segment"]))

    def view(self, st, i):
        p = st["players"][i]
        q = round(100 * p["hits"] / p["darts"]) if p["darts"] else 0
        goal = f"{p['hits']}/{self.o['count']} Treffer" if self.o["end"] == "hits" else f"{p['darts']}/{self.o['count']} Darts"
        return {"main": p["hits"], "sub": f"{goal} · {q}%"}


RULES = {"x01": X01, "cricket": Cricket, "bermuda": Bermuda, "shanghai": Shanghai, "gotcha": Gotcha,
         "atc": AroundTheClock, "rtw": RoundTheWorld, "countup": CountUp,
         "random_checkout": RandomCheckout, "segment": SegmentTraining}

MODE_NAMES = {"x01": "X01", "cricket": "Cricket", "bermuda": "Bermuda", "shanghai": "Shanghai",
              "gotcha": "Gotcha", "atc": "Around the Clock", "rtw": "Round the World",
              "countup": "Count Up", "random_checkout": "Random Checkout", "segment": "Segment Training"}


class Game:
    def __init__(self, mode, players, opts=None):
        if mode not in RULES:
            raise ValueError(mode)
        self.mode = mode
        self.players = players
        base = {"legs": 1, "sets": 0, **RULES[mode].defaults}
        self.opts = {**base, **{k: v for k, v in (opts or {}).items() if v is not None}}
        self.opts.setdefault("seed", random.randrange(1 << 30))
        self.rules = RULES[mode](self)
        self.turns = []
        self.state = {}
        self.replay()

    # ---------- API ----------
    def add_dart(self, s):
        if self.state.get("winner") is not None:
            return
        t = self._open_turn()
        t["darts"].append(s)
        self.replay()

    def next_turn(self):
        if self.turns and not self.turns[-1]["closed"]:
            self.turns[-1]["closed"] = True
        self.replay()

    def edit_dart(self, i, s, ti=None):
        """ti = Index der Aufnahme (None = offene bzw. letzte)."""
        if ti is None:
            ti = len(self.turns) - 1
        if 0 <= ti < len(self.turns) and 0 <= i < len(self.turns[ti]["darts"]):
            self.turns[ti]["darts"][i] = s
        self.replay()

    def undo(self):
        if not self.turns:
            return
        t = self.turns[-1]
        if t["darts"]:
            t["darts"].pop()
            t["closed"] = False
        if not t["darts"]:
            self.turns.pop()
        self.replay()

    def _open_turn(self):
        if self.turns and not self.turns[-1]["closed"]:
            return self.turns[-1]
        t = {"p": self.state["current"], "leg": self.state["leg"], "darts": [], "closed": False}
        self.turns.append(t)
        return t

    # ---------- Replay ----------
    def _new_leg(self, st):
        st["round"] = 1
        st.pop("seq", None)
        self.rules.start_leg(st)
        st["players"] = []
        for i in range(len(self.players)):
            st["players"].append(self.rules.init(st, i))

    def replay(self):
        n, R, o = len(self.players), self.rules, self.opts
        st = {"leg": 0, "set": 0, "leg_starter": 0, "current": 0, "legs_won": [0] * n,
              "sets_won": [0] * n, "winner": None, "last_turn": None, "last_by_player": [None] * n,
              "leg_log": []}
        self._new_leg(st)
        for ti, t in enumerate(self.turns):
            st["_ti"] = ti
            t["p"], t["leg"] = st["current"], st["leg"]
            ev = R.turn(st, t)
            t["pts"] = ev.get("points", 0)
            if len(t["darts"]) >= 3 or ev.get("bust") or ev.get("leg_won") is not None:
                t["closed"] = True
            if not t["closed"]:
                continue
            me = st["current"]
            st["last_turn"] = {"p": me, "ti": ti, "darts": t["darts"], **ev}
            st["last_by_player"][me] = st["last_turn"]
            won = ev.get("leg_won")
            if won is None:
                st["current"] = (me + 1) % n
                if st["current"] == st["leg_starter"]:
                    st["round"] += 1
                    lim = R.round_limit()
                    if lim and st["round"] > lim:
                        won = R.best(st)
                        st["last_turn"]["leg_won"] = won
                        st["last_turn"]["by_rounds"] = True
            if won is not None:
                if self._leg_won(st, won):
                    break
        st.pop("_ti", None)
        open_t = self.turns[-1] if self.turns and not self.turns[-1]["closed"] else None
        st["turn"] = {"p": st["current"], "darts": open_t["darts"] if open_t else [],
                      "ti": len(self.turns) - 1 if open_t else None}
        st["round_limit"] = R.round_limit()
        st["views"] = [R.view(st, i) for i in range(n)]
        st["targets"] = [R.target(st, i) for i in range(n)]
        st["checkout"] = None
        if st["winner"] is None and self.mode in ("x01", "random_checkout"):
            rem = R.remaining(st, st["current"])
            if rem:
                st["checkout"] = checkout(rem, 3 - len(st["turn"]["darts"]), o["out"])
        self.state = st

    def _leg_won(self, st, w):
        n, o = len(self.players), self.opts
        st["leg_log"].append(w)
        st["legs_won"][w] += 1
        sets, legs = int(o["sets"]), int(o["legs"])
        if sets:
            if st["legs_won"][w] >= legs:
                st["sets_won"][w] += 1
                st["legs_won"] = [0] * n
                st["set"] += 1
                if st["sets_won"][w] >= sets:
                    st["winner"] = w
                    return True
        elif st["legs_won"][w] >= legs:
            st["winner"] = w
            return True
        st["leg"] += 1
        st["leg_starter"] = (st["leg_starter"] + 1) % n
        st["current"] = st["leg_starter"]
        self._new_leg(st)
        return False

    def remaining(self, i=None):
        return self.rules.remaining(self.state, self.state["current"] if i is None else i)

    def target(self, i=None):
        return self.rules.target(self.state, self.state["current"] if i is None else i)

    def summary(self):
        return {"mode": self.mode, "mode_name": MODE_NAMES[self.mode], "players": self.players,
                "opts": self.opts, "state": self.state,
                "turns": [{k: v for k, v in t.items() if not k.startswith("_")} for t in self.turns]}


# ---------------- Checkout-Tabelle ----------------
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
