"""Trainingsmodus mit Autodarts als Lehrer.

Bulls'n'Bier liest die echten Kameras und spiegelt sie auf virtuelle Kameras (v4l2loopback),
die der Autodarts Board Manager benutzt. Jeder Wurf wird mit Autodarts verglichen:
  einig        → Trainingsbild automatisch bestätigt
  uneinig      → Status „review“ (in der Markieransicht beide Vorschläge, ein Klick wählt)
  nur Autodarts → Bild + Autodarts-Punkt (BnB hat den Pfeil übersehen) → „review“ (AD_TRUST_SOLO=1: gleich „ok“)
  nur BnB      → vermutlich Fehlalarm → „review“
Die Umrechnung Autodarts-Koordinaten → mm lernt das Modul selbst aus übereinstimmenden Würfen.
"""
import json, logging, math, os, shutil, subprocess, threading, time, urllib.request

import cv2
import numpy as np

from . import board, train
from .config import DATA

log = logging.getLogger("uvicorn.error")

AD_URL = os.environ.get("AD_URL", "http://localhost:3180").rstrip("/")
AD_SERVICE = os.environ.get("AD_SERVICE", "autodarts")
AD_MANAGE = os.environ.get("AD_MANAGE", "1") == "1"          # Autodarts-Dienst mit dem Modus starten/stoppen
DEVS = [d.strip() for d in os.environ.get("AD_PROXY_DEVS", "/dev/video10,/dev/video11,/dev/video12").split(",") if d.strip()]
PROXY_FPS = int(os.environ.get("AD_PROXY_FPS", 30))
WINDOW = float(os.environ.get("AD_WINDOW", 1.2))             # s: so weit dürfen BnB- und Autodarts-Wurf auseinander liegen
SETTLE = 0.6                                                 # s: so lange auf die andere Seite warten
AGREE_MM = float(os.environ.get("AD_AGREE_MM", 4.0))
TRUST_SOLO = os.environ.get("AD_TRUST_SOLO", "0") == "1"
SNAP_PX = 15.0                                               # Netz-Spitze statt Projektion, wenn so nah
FIT_MIN = 12
STATE = os.path.join(DATA, "coach.json")


# ───────────────────────── Kamera-Proxy ─────────────────────────
class Proxy:
    """Frames je Kamera → ffmpeg → /dev/videoN. Langsame Abnehmer bremsen die Erkennung nicht (nur letztes Bild zählt)."""

    def __init__(self):
        self.slots, self.procs, self.threads, self.err = {}, {}, {}, None
        self.on = False

    def start(self, cids):
        if not shutil.which("ffmpeg"):
            raise RuntimeError("ffmpeg fehlt (sudo apt install ffmpeg)")
        miss = [d for d in DEVS[:len(cids)] if not os.path.exists(d)]
        if miss:
            raise RuntimeError("Virtuelle Kameras fehlen: " + ", ".join(miss) + " – tools/autodarts-setup.sh ausführen")
        self.on, self.err = True, None
        for cid, dev in zip(cids, DEVS):
            self.slots[cid] = [None, threading.Event()]
            t = threading.Thread(target=self._pump, args=(cid, dev), daemon=True)
            self.threads[cid] = t
            t.start()

    def stop(self):
        self.on = False
        for s in self.slots.values():
            s[1].set()
        for p in list(self.procs.values()):
            try:
                p.stdin.close()
                p.wait(2)
            except Exception:
                p.kill()
        self.procs, self.slots = {}, {}

    def push(self, cid, frame):
        s = self.slots.get(cid)
        if s is not None:
            s[0] = frame
            s[1].set()

    def _pump(self, cid, dev):
        size = None
        while self.on:
            s = self.slots.get(cid)
            if s is None:
                return
            s[1].wait(1)
            s[1].clear()
            f = s[0]
            if f is None or not self.on:
                continue
            h, w = f.shape[:2]
            p = self.procs.get(cid)
            if p is None or p.poll() is not None or size != (w, h):
                if p is not None:
                    p.kill()
                size = (w, h)
                p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
                                      "-r", str(PROXY_FPS), "-i", "-", "-f", "v4l2", "-pix_fmt", "yuyv422", dev],
                                     stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                self.procs[cid] = p
                log.info("Kamera-Proxy: Cam %d → %s (%dx%d)", int(cid) + 1, dev, w, h)
            try:
                p.stdin.write(f.tobytes())
            except Exception:
                err = (p.stderr.read(400) or b"").decode("utf-8", "replace").strip() if p.poll() is not None else ""
                self.err = f"{dev}: {err or 'ffmpeg beendet'}"
                log.warning("Kamera-Proxy: %s", self.err)
                self.procs.pop(cid, None)
                time.sleep(2)


# ───────────────────────── Autodarts lesen ─────────────────────────
def norm_name(seg):
    """Autodarts-Segment → BnB-Name (T20, D5, S1, 25, BULL, MISS)."""
    seg = seg or {}
    name = str(seg.get("name") or "").upper()
    num, mult = seg.get("number"), seg.get("multiplier")
    if num is not None and mult is not None:
        num, mult = int(num), int(mult)
        if num == 0 or mult == 0:
            return "MISS"
        if num in (25, 50):
            return "BULL" if mult == 2 or num == 50 else "25"
        return "SDT"[mult - 1] + str(num)
    if name.startswith("M") or name == "OUTSIDE":
        return "MISS"
    try:
        return board.from_name({"DBULL": "BULL", "SBULL": "25"}.get(name, name))["name"]
    except Exception:
        return name or "?"


def parse_state(js):
    """→ (status, [{"name", "xy"}]) – tolerant gegenüber Varianten des JSON."""
    st = str(js.get("status") or js.get("event") or "")
    out = []
    for t in js.get("throws") or js.get("darts") or []:
        c = t.get("coords") or t.get("coordinates") or {}
        xy = (float(c["x"]), float(c["y"])) if isinstance(c, dict) and "x" in c and "y" in c else None
        out.append({"name": norm_name(t.get("segment") or t), "xy": xy})
    return st, out


def fit_similarity(a, b, iters=300, thr=3.0):
    """RANSAC: b ≈ s·R·a + t (Spiegelung erlaubt). Rückgabe (M 2×3, rms, inlier)."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    rng = np.random.default_rng(1)
    best = None
    for flip in (1, -1):
        af = a * [1, flip]
        for _ in range(iters):
            i = rng.choice(len(a), 2, replace=False)
            M = _sim2(af[i], b[i])
            if M is None:
                continue
            e = np.hypot(*((af @ M[:, :2].T + M[:, 2]) - b).T)
            inl = e < thr
            if best is None or inl.sum() > best[0]:
                best = (inl.sum(), flip, inl)
    if best is None or best[0] < FIT_MIN * 0.7:
        return None
    _, flip, inl = best
    af = a * [1, flip]
    M = _sim2(af[inl], b[inl])
    M = M @ np.diag([1, flip, 1])   # Spiegelung in die Matrix einrechnen → M · [x, y, 1]
    e = np.hypot(*((a[inl] @ M[:, :2].T + M[:, 2]) - b[inl]).T)
    return M, float(np.sqrt(np.mean(e ** 2))), int(inl.sum())


def _sim2(a, b):
    """Kleinste Quadrate (Umeyama, ohne Spiegelung)."""
    if len(a) < 2:
        return None
    ma, mb = a.mean(0), b.mean(0)
    A, B = a - ma, b - mb
    va = (A ** 2).sum()
    if va < 1e-9:
        return None
    sxy = (A[:, 0] * B[:, 0] + A[:, 1] * B[:, 1]).sum()
    cxy = (A[:, 0] * B[:, 1] - A[:, 1] * B[:, 0]).sum()
    s, ang = math.hypot(sxy, cxy) / va, math.atan2(cxy, sxy)
    R = s * np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    return np.hstack([R, (mb - R @ ma)[:, None]])


# ───────────────────────── Trainer ─────────────────────────
class Coach:
    def __init__(self):
        self.det = None
        self.proxy = Proxy()
        self.on, self.err, self.ad_ok, self.ad_status = False, None, False, ""
        self.q_bnb, self.q_ad = [], []
        self.lock = threading.Lock()
        self.last = None
        st = self._load()
        self.pairs = st.get("pairs", [])
        self.fit = st.get("fit")
        self.stats = st.get("stats", {"agree": 0, "differ": 0, "ad_only": 0, "bnb_only": 0})
        self.recent = st.get("recent", [])   # letzte 100 Ergebnisse (1 = einig) für die Quote
        self.want = st.get("on", False)

    # ── Zustand ──
    def _load(self):
        try:
            return json.load(open(STATE, encoding="utf-8"))
        except Exception:
            return {}

    def _save(self):
        try:
            json.dump({"on": self.on, "pairs": self.pairs[-300:], "fit": self.fit, "stats": self.stats, "recent": self.recent[-100:]},
                      open(STATE + ".tmp", "w", encoding="utf-8"))
            os.replace(STATE + ".tmp", STATE)
        except Exception as e:
            log.warning("coach.json: %s", e)

    def status(self):
        r = self.recent[-100:]
        return {"on": self.on, "error": self.err or self.proxy.err, "autodarts": self.ad_ok, "ad_status": self.ad_status,
                "url": AD_URL, "devs": DEVS, "fit": bool(self.fit), "fit_rms": self.fit and self.fit["rms"], "pairs": len(self.pairs),
                "fit_min": FIT_MIN, "stats": self.stats, "rate": round(100 * sum(r) / len(r)) if r else None, "n_rate": len(r),
                "last": self.last}

    # ── An / aus ──
    def attach(self, det):
        self.det = det
        if self.want:
            try:
                self.start()
            except Exception as e:
                self.err = str(e)

    def start(self):
        if self.on:
            return
        if not self.det:
            raise RuntimeError("Keine Kameras (Simulator)")
        self.err = None
        self.proxy.start([c.id for c in self.det.cams])
        self.det.tap = self.proxy.push
        train.set_collect(True)
        self.on = True
        self._service("start")
        threading.Thread(target=self._poll, daemon=True).start()
        threading.Thread(target=self._match_loop, daemon=True).start()
        self._save()
        log.info("Trainingsmodus mit Autodarts an")

    def stop(self):
        self.on = False
        if self.det:
            self.det.tap = None
        self.proxy.stop()
        self._service("stop")
        self._save()
        log.info("Trainingsmodus mit Autodarts aus")

    def _service(self, what):
        if not AD_MANAGE or not AD_SERVICE:
            return
        r = subprocess.run(["sudo", "-n", "systemctl", what, AD_SERVICE], capture_output=True, text=True)
        if r.returncode:
            log.warning("Autodarts-Dienst %s: %s", what, (r.stderr or r.stdout).strip())

    # ── Eingänge ──
    def bnb(self, ev):
        """Vom Detector: dart / dart_unknown."""
        if not self.on:
            return
        with self.lock:
            self.q_bnb.append({"t": time.time(), "sid": ev.get("sid"), "name": (ev.get("score") or {}).get("name"),
                               "xy": (ev["x"], ev["y"]) if "x" in ev else None})

    def _poll(self):
        n_seen, fails = None, 0
        while self.on:
            time.sleep(0.15)
            try:
                with urllib.request.urlopen(AD_URL + "/api/state", timeout=1.5) as r:
                    js = json.loads(r.read())
                fails, self.ad_ok = 0, True
            except Exception as e:
                fails += 1
                if fails > 10:
                    self.ad_ok, self.ad_status = False, f"nicht erreichbar ({e.__class__.__name__})"
                time.sleep(0.5)
                continue
            st, throws = parse_state(js)
            self.ad_status = st
            if n_seen is None or len(throws) < n_seen:   # erster Abruf oder Takeout/Reset bei Autodarts
                n_seen = len(throws)
                continue
            for t in throws[n_seen:]:
                with self.lock:
                    self.q_ad.append({"t": time.time(), **t, "snap": self._snapshot()})
            n_seen = len(throws)

    def _snapshot(self):
        """Bilder jetzt sichern – falls BnB den Pfeil übersieht, werden sie gebraucht."""
        out = {}
        for c in self.det.cams:
            with c.lock:
                if c.frame is not None:
                    out[c.id] = c.frame.copy()
        return out

    # ── Abgleich ──
    def _match_loop(self):
        while self.on:
            time.sleep(0.2)
            now = time.time()
            with self.lock:
                done = []
                for a in list(self.q_ad):   # Paare bilden: zeitlich nächster BnB-Wurf, erst wenn beide Seiten Zeit hatten
                    if now - a["t"] < SETTLE:
                        continue
                    near = [b for b in self.q_bnb if abs(b["t"] - a["t"]) <= WINDOW]
                    if near:
                        b = min(near, key=lambda b: abs(b["t"] - a["t"]))
                        self.q_ad.remove(a); self.q_bnb.remove(b); done.append((b, a))
                for a in [a for a in self.q_ad if now - a["t"] > WINDOW + SETTLE]:
                    self.q_ad.remove(a); done.append((None, a))
                for b in [b for b in self.q_bnb if now - b["t"] > WINDOW + SETTLE]:
                    self.q_bnb.remove(b); done.append((b, None))
            for b, a in done:
                try:
                    self._judge(b, a)
                except Exception as e:
                    log.warning("Abgleich: %s", e)

    def ad_mm(self, xy):
        if not xy or not self.fit:
            return None
        M = np.array(self.fit["M"])
        v = M @ [xy[0], xy[1], 1.0]
        return float(v[0]), float(v[1])

    def _uv(self, mm, cam_tips=None):
        """mm → Pixel je Kamera; liegt eine Netz-Spitze nah dran, die nehmen (genauer als die Projektion)."""
        out = {}
        for cid, Hm in self.det.H.items():
            v = np.linalg.inv(Hm) @ [mm[0], mm[1], 1.0]
            u = [float(v[0] / v[2]), float(v[1] / v[2])]
            t = (cam_tips or {}).get(cid)
            out[cid] = [round(c, 1) for c in (t if t and math.hypot(t[0] - u[0], t[1] - u[1]) < SNAP_PX else u)]
        return out

    def _learn(self, ad_xy, bnb_xy):
        self.pairs.append([list(ad_xy), list(bnb_xy)])
        n = len(self.pairs)
        if n >= FIT_MIN and (not self.fit or n % 10 == 0):
            r = fit_similarity([p[0] for p in self.pairs[-300:]], [p[1] for p in self.pairs[-300:]])
            if r:
                M, rms, inl = r
                self.fit = {"M": M.tolist(), "rms": round(rms, 2), "n": inl}
                log.info("Autodarts-Umrechnung gelernt: %d Würfe, Abweichung %.1f mm", inl, rms)

    def _judge(self, b, a):
        m = train.read(b["sid"]) if b and b.get("sid") else None
        ad_mm = self.ad_mm(a["xy"]) if a else None
        res = None
        if b and a:
            same = b["name"] == a["name"]
            if same and a["xy"] and b["xy"]:
                self._learn(a["xy"], b["xy"])
            dist = math.hypot(ad_mm[0] - b["xy"][0], ad_mm[1] - b["xy"][1]) if ad_mm and b["xy"] else None
            agree = same and (dist is None or dist <= AGREE_MM)
            res = "agree" if agree else "differ"
            if m:
                ad = {"name": a["name"], "pos": list(ad_mm) if ad_mm else None, "uv": self._uv(ad_mm, m.get("cam_tips")) if ad_mm else {}}
                if agree:
                    tips = ad["uv"] or (m.get("cam_tips") if m.get("how") == "Netz" else None)
                    if tips:
                        train.update(m["sid"], status="ok", tips=tips, ad=ad, auto_ok=True)
                    else:
                        train.update(m["sid"], ad=ad)
                else:
                    train.update(m["sid"], status="review", ad=ad, bnb=self._bnb_side(m), detected=m.get("name"))
            elif not b.get("sid"):
                res = "differ"
        elif a:
            res = "ad_only"
            if a["snap"] and train.collecting():
                imgs = {cid: cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes() for cid, f in a["snap"].items()}
                size = {cid: [f.shape[1], f.shape[0]] for cid, f in a["snap"].items()}
                uv = self._uv(ad_mm) if ad_mm else {}
                sid = train.save(imgs, {"status": "ok" if TRUST_SOLO and uv else "review", "pos": list(ad_mm) if ad_mm else None,
                                        "name": a["name"], "how": "Autodarts", "size": size, "proposal": uv, "cam_tips": {},
                                        "tips": uv if TRUST_SOLO else {}, "ad": {"name": a["name"], "pos": list(ad_mm) if ad_mm else None, "uv": uv},
                                        "prev": list(self.det.on_board)})
                if sid:
                    self.det.on_board.append(sid)
        elif b:
            res = "bnb_only"
            if m:
                train.update(m["sid"], status="review", bnb=self._bnb_side(m))
        if res:
            key = {"agree": "agree", "differ": "differ", "ad_only": "ad_only", "bnb_only": "bnb_only"}[res]
            self.stats[key] = self.stats.get(key, 0) + 1
            self.recent = (self.recent + [1 if res == "agree" else 0])[-100:]
            self.last = {"res": res, "bnb": b and b["name"], "ad": a and a["name"], "t": time.time()}
            log.info("Autodarts-Abgleich: %s (BnB %s · Autodarts %s)", res, b and b["name"], a and a["name"])
            self._save()

    def _bnb_side(self, m):
        tips = m.get("cam_tips") or {}
        if not tips and m.get("pos"):
            tips = self._uv(m["pos"])
        return {"name": m.get("name"), "pos": m.get("pos"), "uv": tips}

    def reset_fit(self):
        self.pairs, self.fit = [], None
        self._save()


coach = Coach()
