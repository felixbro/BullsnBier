"""SQLite: Spieler, Spiele, Statistik."""
import json, os, sqlite3, time

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
if "spoken" not in [r[1] for r in con.execute("PRAGMA table_info(players)")]:
    con.execute("ALTER TABLE players ADD COLUMN spoken TEXT")
    con.commit()


def players():
    return [dict(r) for r in con.execute("SELECT id,name,COALESCE(spoken,'') spoken FROM players ORDER BY name")]


def update_player(pid, name=None, spoken=None):
    if name is not None and name.strip():
        con.execute("UPDATE players SET name=? WHERE id=?", (name.strip(), pid))
    if spoken is not None:
        con.execute("UPDATE players SET spoken=? WHERE id=?", (spoken.strip(), pid))
    con.commit()
    return players()


def add_player(name):
    con.execute("INSERT OR IGNORE INTO players(name,created) VALUES(?,?)", (name.strip(), time.time()))
    con.commit()
    return players()


def del_player(pid):
    con.execute("DELETE FROM players WHERE id=?", (pid,))
    con.commit()


def save_game(game):
    st = game.state
    cur = con.execute("INSERT INTO games(mode,opts,players,winner,turns,ts) VALUES(?,?,?,?,?,?)",
                      (game.mode, json.dumps(game.opts), json.dumps(game.players), st["winner"],
                       json.dumps([{k: v for k, v in t.items() if not k.startswith("_")}
                                   for t in game.turns]), time.time()))
    gid = cur.lastrowid
    for i, p in enumerate(game.players):
        s = _player_stats(game, i)
        con.execute("INSERT INTO stats VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (gid, p.get("id"), game.mode, int(st["winner"] == i), s["darts"], s["points"],
                     s["first9"], s["t180"], s["t140"], s["t100"], s["best_co"], s["co_att"],
                     s["co_hit"], time.time()))
    con.commit()
    return gid


def _player_stats(game, i):
    from .games import finishable
    s = dict(darts=0, points=0, first9=0.0, t180=0, t140=0, t100=0, best_co=0, co_att=0, co_hit=0)
    out = game.opts.get("out", "double")
    leg_turns = {}
    for t in game.turns:
        if t["p"] != i:
            continue
        s["darts"] += len(t["darts"])
        if game.mode != "x01":
            continue
        start = t.get("_start", 0)
        rem = start
        bust = False
        pts = 0
        # Punkte über Differenz (Bust = 0)
        for d in t["darts"]:
            if finishable(rem, out) and rem > 0:
                s["co_att"] += 1
            rem -= d["value"]
            if rem < 0 or (rem == 1 and out != "single"):
                bust = True
                break
            if rem == 0:
                s["co_hit"] += 1
                s["best_co"] = max(s["best_co"], start)
                break
        pts = 0 if bust else sum(d["value"] for d in t["darts"])
        s["points"] += pts
        s["t180"] += pts == 180
        s["t140"] += 140 <= pts < 180
        s["t100"] += 100 <= pts < 140
        leg_turns.setdefault(t["leg"], []).append(pts)
    f9 = [sum(v[:3]) / 3 for v in leg_turns.values() if v]
    s["first9"] = round(sum(f9) / len(f9), 2) if f9 else 0
    return s


def player_stats(pid):
    r = con.execute("""SELECT COUNT(*) games, SUM(won) wins, SUM(darts) darts, SUM(points) points,
        AVG(NULLIF(first9,0)) first9, SUM(t180) t180, SUM(t140) t140, SUM(t100) t100,
        MAX(best_co) best_co, SUM(co_att) co_att, SUM(co_hit) co_hit
        FROM stats WHERE player_id=? AND mode='x01'""", (pid,)).fetchone()
    d = dict(r)
    d["avg3"] = round(3 * (d["points"] or 0) / d["darts"], 2) if d["darts"] else 0
    d["co_pct"] = round(100 * (d["co_hit"] or 0) / d["co_att"], 1) if d["co_att"] else 0
    d["first9"] = round(d["first9"] or 0, 2)
    hist = con.execute("""SELECT ts, ROUND(3.0*points/NULLIF(darts,0),2) avg FROM stats
        WHERE player_id=? AND mode='x01' ORDER BY ts DESC LIMIT 30""", (pid,)).fetchall()
    d["history"] = [dict(h) for h in reversed(hist)]
    allm = con.execute("SELECT COUNT(*) g, SUM(won) w FROM stats WHERE player_id=?", (pid,)).fetchone()
    d["all_games"], d["all_wins"] = allm["g"], allm["w"] or 0
    return d


def recent_games(limit=20):
    rows = con.execute("SELECT id,mode,players,winner,ts FROM games ORDER BY ts DESC LIMIT ?", (limit,))
    out = []
    for r in rows:
        ps = json.loads(r["players"])
        out.append({"id": r["id"], "mode": r["mode"], "players": [p["name"] for p in ps],
                    "winner": ps[r["winner"]]["name"] if r["winner"] is not None else None, "ts": r["ts"]})
    return out
