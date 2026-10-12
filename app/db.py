"""SQLite: Spieler, Spiele, Statistik."""
import json, os, sqlite3, time
from collections import Counter

from .config import DATA

con = sqlite3.connect(os.path.join(DATA, "dartcam.db"), check_same_thread=False)
con.row_factory = sqlite3.Row
con.executescript("""
CREATE TABLE IF NOT EXISTS players(id INTEGER PRIMARY KEY, name TEXT UNIQUE, created REAL);
CREATE TABLE IF NOT EXISTS games(id INTEGER PRIMARY KEY, mode TEXT, opts TEXT, players TEXT,
  winner INTEGER, turns TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS stats(game_id INTEGER, player_id INTEGER, mode TEXT, won INTEGER,
  darts INTEGER, points INTEGER, first9 REAL, t180 INTEGER, t140 INTEGER, t100 INTEGER,
  best_co INTEGER, co_att INTEGER, co_hit INTEGER, ts REAL);
""")


def _add_cols(table, cols):
    have = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
    for c, typ in cols:
        if c not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {c} {typ}")
    con.commit()


_add_cols("players", [("spoken", "TEXT"), ("nick", "TEXT"), ("color", "TEXT"), ("hand", "TEXT"), ("seed", "TEXT")])
_add_cols("stats", [("legs_won", "INTEGER"), ("legs", "INTEGER"), ("best_leg", "INTEGER"),
                    ("best_co_way", "TEXT"), ("name", "TEXT")])

PALETTE = ["#6FA8FF", "#FF7A6B", "#5FCB92", "#FFD66B", "#B79CFF", "#FFB27A", "#7FDDEB", "#FF8FC2"]
FIELDS = "id,name,COALESCE(spoken,'') spoken,COALESCE(nick,'') nick,color,COALESCE(hand,'R') hand,COALESCE(seed,name) seed"


def players():
    out = [dict(r) for r in con.execute(f"SELECT {FIELDS} FROM players ORDER BY id")]
    for i, p in enumerate(out):
        p["color"] = p["color"] or PALETTE[i % len(PALETTE)]
    return out


def player(pid):
    return next((p for p in players() if p["id"] == pid), None)


def free_color():
    used = Counter(p["color"] for p in players())
    return min(PALETTE, key=lambda c: (used[c], PALETTE.index(c)))


def add_player(data):
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Name fehlt")
    cur = con.execute("INSERT OR IGNORE INTO players(name,created,spoken,nick,color,hand,seed) VALUES(?,?,?,?,?,?,?)",
                      (name, time.time(), (data.get("spoken") or "").strip(), (data.get("nick") or "").strip(),
                       data.get("color") or free_color(), data.get("hand") or "R", (data.get("seed") or name).strip()))
    con.commit()
    if cur.rowcount == 0:
        raise ValueError("Name existiert schon")
    return player(cur.lastrowid)


def update_player(pid, data):
    for k in ("name", "spoken", "nick", "color", "hand", "seed"):
        if k in data and data[k] is not None:
            v = str(data[k]).strip()
            if k == "name" and not v:
                continue
            con.execute(f"UPDATE players SET {k}=? WHERE id=?", (v, pid))
    con.commit()
    return player(pid)


def del_player(pid):
    con.execute("DELETE FROM players WHERE id=?", (pid,))
    con.commit()


# ---------------- Spiel speichern ----------------
def save_game(game):
    st = game.state
    cur = con.execute("INSERT INTO games(mode,opts,players,winner,turns,ts) VALUES(?,?,?,?,?,?)",
                      (game.mode, json.dumps(game.opts), json.dumps(game.players), st["winner"],
                       json.dumps([{k: v for k, v in t.items() if k[0] != "_" or k == "_start"}
                                   for t in game.turns]), time.time()))
    gid = cur.lastrowid
    log = st.get("leg_log", [])
    for i, p in enumerate(game.players):
        s = _player_stats(game, i)
        con.execute("""INSERT INTO stats(game_id,player_id,mode,won,darts,points,first9,t180,t140,t100,best_co,
            co_att,co_hit,ts,legs_won,legs,best_leg,best_co_way,name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (gid, p.get("id"), game.mode, int(st["winner"] == i), s["darts"], s["points"],
                     s["first9"], s["t180"], s["t140"], s["t100"], s["best_co"], s["co_att"],
                     s["co_hit"], time.time(), log.count(i), len(log), s["best_leg"],
                     json.dumps(s["best_co_way"]), p.get("name")))
    con.commit()
    return gid


def _player_stats(game, i):
    from .games import finishable
    s = dict(darts=0, points=0, first9=0.0, t180=0, t140=0, t100=0, best_co=0, co_att=0, co_hit=0,
             best_leg=None, best_co_way=[])
    out = game.opts.get("out", "double")
    leg_turns, leg_darts = {}, {}
    for t in game.turns:
        if t["p"] != i:
            continue
        s["darts"] += len(t["darts"])
        leg_darts[t["leg"]] = leg_darts.get(t["leg"], 0) + len(t["darts"])
        if game.mode not in ("x01", "random_checkout"):
            continue
        start = t.get("_start", 0)
        rem, bust = start, False
        for d in t["darts"]:
            if 0 < rem and finishable(rem, out):
                s["co_att"] += 1
            rem -= d["value"]
            if rem < 0 or (rem == 1 and out != "single"):
                bust = True
                break
            if rem == 0:
                s["co_hit"] += 1
                if start > s["best_co"]:
                    s["best_co"], s["best_co_way"] = start, [x["name"] for x in t["darts"]]
                if game.mode == "x01" and int(game.opts.get("start", 0)) == 501:
                    n = leg_darts[t["leg"]]
                    s["best_leg"] = n if s["best_leg"] is None else min(s["best_leg"], n)
                break
        pts = 0 if bust else sum(d["value"] for d in t["darts"])
        s["points"] += pts
        s["t180"] += pts == 180
        s["t140"] += 140 <= pts < 180
        s["t100"] += 100 <= pts < 140
        leg_turns.setdefault(t["leg"], []).append(pts)
    f9 = [sum(v[:3]) / len(v[:3]) for v in leg_turns.values() if v]
    s["first9"] = round(sum(f9) / len(f9), 2) if f9 else 0
    return s


# ---------------- Auswertung ----------------
PERIODS = {"today": None, "7d": 7 * 86400, "30d": 30 * 86400, "all": 0}


def since_ts(period):
    if period == "today":
        lt = time.localtime()
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    sec = PERIODS.get(period, 0)
    return time.time() - sec if sec else 0


def _avg(points, darts):
    return round(3 * (points or 0) / darts, 1) if darts else 0


def player_stats(pid, period="all"):
    since = since_ts(period)
    r = dict(con.execute("""SELECT COUNT(*) games, SUM(won) wins, SUM(darts) darts, SUM(points) points,
        AVG(NULLIF(first9,0)) first9, SUM(t180) t180, SUM(t140) t140, SUM(t100) t100,
        MAX(best_co) best_co, SUM(co_att) co_att, SUM(co_hit) co_hit
        FROM stats WHERE player_id=? AND mode IN ('x01','random_checkout') AND ts>=?""", (pid, since)).fetchone())
    d = {k: r[k] or 0 for k in r}
    d["avg3"] = _avg(d["points"], d["darts"])
    d["co_pct"] = round(100 * d["co_hit"] / d["co_att"]) if d["co_att"] else 0
    d["first9"] = round(d["first9"], 1)
    way = con.execute("SELECT best_co_way FROM stats WHERE player_id=? AND ts>=? AND best_co=? AND best_co>0 LIMIT 1",
                      (pid, since, d["best_co"])).fetchone()
    d["best_co_way"] = json.loads(way[0]) if way and way[0] else []
    d["t180_7d"] = con.execute("SELECT COALESCE(SUM(t180),0) FROM stats WHERE player_id=? AND ts>=?",
                               (pid, time.time() - 7 * 86400)).fetchone()[0]
    lg = con.execute("SELECT COALESCE(SUM(legs_won),0), COALESCE(SUM(legs),0), COUNT(*), COALESCE(SUM(won),0) "
                     "FROM stats WHERE player_id=? AND ts>=?", (pid, since)).fetchone()
    d["legs_won"], d["legs"], d["all_games"], d["all_wins"] = lg
    # Vergleich zum Vorzeitraum
    prev = con.execute("SELECT SUM(points), SUM(darts) FROM stats WHERE player_id=? AND mode IN ('x01','random_checkout') "
                       "AND ts>=? AND ts<?", (pid, since - 30 * 86400, since)).fetchone() if since else (None, None)
    d["avg3_prev"] = _avg(prev[0], prev[1]) if prev and prev[1] else None
    hist = con.execute("""SELECT ts, points, darts FROM stats WHERE player_id=? AND mode IN ('x01','random_checkout')
        AND darts>0 AND ts>=? ORDER BY ts DESC LIMIT 20""", (pid, since)).fetchall()
    d["history"] = [{"ts": h[0], "avg": _avg(h[1], h[2])} for h in reversed(hist)]
    d["favorites"] = favorites(pid, since)
    return d


def favorites(pid, since, top=6):
    c, total = Counter(), 0
    for g in con.execute("SELECT players, turns FROM games WHERE ts>=?", (since,)):
        ps = json.loads(g[0])
        idx = [i for i, p in enumerate(ps) if p.get("id") == pid]
        if not idx:
            continue
        for t in json.loads(g[1]):
            if t.get("p") in idx:
                for d in t["darts"]:
                    n = "Bull" if d["name"] in ("BULL", "25") else d["name"]
                    c[n] += 1
                    total += 1
    return [{"field": k, "pct": round(100 * v / total)} for k, v in c.most_common(top)] if total else []


def fav_double(pid):
    c = Counter()
    for g in con.execute("SELECT players, turns FROM games"):
        ps = json.loads(g[0])
        idx = [i for i, p in enumerate(ps) if p.get("id") == pid]
        for t in json.loads(g[1]) if idx else []:
            if t.get("p") in idx:
                c.update("Bull" if d["name"] == "BULL" else d["name"] for d in t["darts"] if d.get("mult") == 2)
    return c.most_common(1)[0][0] if c else "–"


def player_cards():
    """Kennzahlen für die Spieler-Übersicht."""
    out = []
    for p in players():
        r = con.execute("SELECT SUM(points), SUM(darts) FROM stats WHERE player_id=? AND mode IN ('x01','random_checkout')",
                        (p["id"],)).fetchone()
        n = con.execute("SELECT COUNT(*) FROM stats WHERE player_id=?", (p["id"],)).fetchone()[0]
        out.append({**p, "avg3": _avg(r[0], r[1]), "games": n, "fav_double": fav_double(p["id"])})
    return out


def today():
    since = since_ts("today")
    rows = con.execute("""SELECT player_id, name, SUM(CASE WHEN mode IN ('x01','random_checkout') THEN points END) p,
        SUM(CASE WHEN mode IN ('x01','random_checkout') THEN darts END) d, COALESCE(SUM(legs_won),0) lw
        FROM stats WHERE ts>=? GROUP BY COALESCE(player_id, name)""", (since,)).fetchall()
    rank = [{"id": r[0], "name": r[1], "avg3": _avg(r[2], r[3]), "legs": r[4]} for r in rows]
    rank.sort(key=lambda x: (-x["avg3"], -x["legs"]))
    tot = con.execute("SELECT SUM(points), SUM(darts), COALESCE(SUM(t180),0), COALESCE(MAX(best_co),0) FROM stats "
                      "WHERE ts>=? AND mode IN ('x01','random_checkout')", (since,)).fetchone()
    guests = set()
    for g in con.execute("SELECT players FROM games"):
        guests.update(p["name"] for p in json.loads(g[0]) if not p.get("id"))
    return {"rank": rank, "avg3": _avg(tot[0], tot[1]), "t180": tot[2], "high": tot[3],
            "players": len(players()), "guests": len(guests)}


def records():
    rec = []
    r = con.execute("SELECT best_co, name FROM stats WHERE best_co>0 ORDER BY best_co DESC, ts LIMIT 1").fetchone()
    if r:
        rec.append({"label": "Höchstes Finish", "value": f"{r[0]} · {r[1]}"})
    r = con.execute("SELECT best_leg, name FROM stats WHERE best_leg>0 ORDER BY best_leg, ts LIMIT 1").fetchone()
    if r:
        rec.append({"label": "Kürzestes Leg (501)", "value": f"{r[0]} Darts · {r[1]}"})
    r = con.execute("""SELECT SUM(t180) n, name FROM stats GROUP BY COALESCE(player_id,name), date(ts,'unixepoch','localtime')
        ORDER BY n DESC LIMIT 1""").fetchone()
    if r and r[0]:
        rec.append({"label": "Meiste 180er an einem Abend", "value": f"{r[0]} · {r[1]}"})
    return rec


def recent_games(limit=20):
    from .games import MODE_NAMES
    out = []
    for r in con.execute("SELECT id,mode,opts,players,winner,ts FROM games ORDER BY ts DESC LIMIT ?", (limit,)):
        ps, o = json.loads(r["players"]), json.loads(r["opts"])
        legs = [x[0] for x in con.execute("SELECT legs_won FROM stats WHERE game_id=? ORDER BY rowid", (r["id"],))]
        out.append({"id": r["id"], "mode": r["mode"], "mode_name": MODE_NAMES.get(r["mode"], r["mode"]), "opts": o,
                    "players": [p["name"] for p in ps], "player_ids": [p.get("id") for p in ps],
                    "winner": ps[r["winner"]]["name"] if r["winner"] is not None else None,
                    "legs": legs, "darts": con.execute("SELECT MAX(darts) FROM stats WHERE game_id=?", (r["id"],)).fetchone()[0],
                    "ts": r["ts"]})
    return out
