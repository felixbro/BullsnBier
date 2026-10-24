"""Kamera-Erfassung + Pfeilerkennung (Differenzbild, Spitze, Homographie, Fusion)."""
import json, logging, math, os, sys, threading, time
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")   # keine Warnungs-Flut bei fehlender Kamera (Status steht in der App)
import cv2
import numpy as np

from . import board, train, tipnet

from .config import DATA
CAL_FILE = os.path.join(DATA, "calibration.json")
RES_FILE = os.path.join(DATA, "camres.json")

# --- Tuning (per ENV überschreibbar) ---
_cw, _ch = os.environ.get("CAM_W", "auto").strip().lower(), os.environ.get("CAM_H", "auto").strip().lower()
AUTO_RES = not (_cw.isdigit() and _ch.isdigit())        # CAM_W=auto (Standard) → beim ersten Start ausmessen
W, H = (int(_cw), int(_ch)) if not AUTO_RES else (1280, 720)
RES_STEPS = [(1920, 1080), (1600, 900), (1280, 720), (1024, 576), (960, 540), (848, 480), (640, 480)]
BACKEND = os.environ.get("CAM_BACKEND", "").strip().lower()   # Windows: dshow | msmf | leer = automatisch
BACKEND_FIXED = bool(BACKEND)
PROBE_FPS = float(os.environ.get("PROBE_FPS", 20))      # so viele Bilder/s muss JEDE Kamera gleichzeitig schaffen
MOTION_PX = int(os.environ.get("MOTION_PX", 400))       # Pixel-Änderung = Bewegung
STABLE_FRAMES = int(os.environ.get("STABLE_FRAMES", 6))
DART_MIN = int(os.environ.get("DART_MIN", 250))          # min. Fläche eines Pfeils
DART_MAX = int(os.environ.get("DART_MAX", 40000))        # darüber = Hand/Takeout
DIFF_THR = int(os.environ.get("DIFF_THR", 28))
log = logging.getLogger("uvicorn.error")
DEBUG_DIR = os.path.join(DATA, "debug")              # letzte Würfe als Bild (Maske, Achse, Spitze) zum Prüfen
DEBUG_KEEP = int(os.environ.get("DEBUG_SHOTS", 12))
TAKEOUT_PX = int(os.environ.get("TAKEOUT_PX", 0)) or DART_MIN * 3   # Restabweichung zum leeren Board
FUSE_MM = float(os.environ.get("FUSE_MM", 12))           # Ausreißer-Grenze zwischen Kameras


def load_cal():
    try:
        with open(CAL_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cal(cal):
    os.makedirs(DATA, exist_ok=True)
    with open(CAL_FILE, "w") as f:
        json.dump(cal, f, indent=2)


def homography(img_pts: dict):
    """img_pts: {'20':[x,y], '6':..., '3':..., '11':..., optional weitere 'r,a':...}"""
    src, dst = [], []
    for k, p in img_pts.items():
        if k in board.CAL_POINTS:
            src.append(p)
            dst.append(board.CAL_POINTS[k])
    if len(src) < 4:
        return None
    Hm, _ = cv2.findHomography(np.float32(src), np.float32(dst))
    return Hm


def to_board(Hm, pt):
    v = Hm @ np.array([pt[0], pt[1], 1.0])
    return float(v[0] / v[2]), float(v[1] / v[2])


def overlay_points(Hm, n=72):
    """Board-Ringe ins Kamerabild projizieren (Kontrolle der Kalibrierung)."""
    Hi = np.linalg.inv(Hm)
    rings = []
    for r in (board.R_OUTER_BULL, board.R_TRIPLE_IN, board.R_TRIPLE_OUT,
              board.R_DOUBLE_IN, board.R_DOUBLE_OUT):
        pts = []
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            v = Hi @ np.array([r * math.sin(a), r * math.cos(a), 1.0])
            pts.append([v[0] / v[2], v[1] / v[2]])
        rings.append(pts)
    wires = []
    for i in range(20):
        a = math.radians(i * 18 + 9)
        line = []
        for r in (board.R_OUTER_BULL, board.R_DOUBLE_OUT):
            v = Hi @ np.array([r * math.sin(a), r * math.cos(a), 1.0])
            line.append([v[0] / v[2], v[1] / v[2]])
        wires.append(line)
    return {"rings": rings, "wires": wires}


def ransac_line(pts, iters=250, band=2.5, rng=None):
    """Längste gerade Struktur im Pixelhaufen (Schaft + Barrel), Flights/Schatten zählen nicht mit.
    Rückgabe (x0, y0, vx, vy, inlier) oder None."""
    if len(pts) < 20:
        return None
    rng = rng or np.random.default_rng(0)
    best, best_n = None, 0
    for _ in range(iters):
        i, j = rng.integers(0, len(pts), 2)
        d = pts[j] - pts[i]
        L = math.hypot(d[0], d[1])
        if L < 15:
            continue
        n = np.array([-d[1], d[0]]) / L
        inl = np.abs((pts - pts[i]) @ n) < band
        c = int(inl.sum())
        if c > best_n:
            best_n, best = c, inl
    if best is None or best_n < 15:
        return None
    vx, vy, x0, y0 = cv2.fitLine(pts[best], cv2.DIST_HUBER, 0, 0.01, 0.01).flatten()
    return float(x0), float(y0), float(vx), float(vy), best


def board_roi(Hm, shape, r_mm=235, up=0.45):
    """Bildbereich, in dem ein Pfeil liegen kann: Board (r ≤ 235 mm) plus Streifen darüber für Barrel/Flight."""
    h, w = shape[:2]
    Hi = np.linalg.inv(Hm)
    poly = []
    for i in range(72):
        a = 2 * math.pi * i / 72
        v = Hi @ np.array([r_mm * math.sin(a), r_mm * math.cos(a), 1.0])
        poly.append([v[0] / v[2], v[1] / v[2]])
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [np.int32(poly)], 255)
    band = max(3, int(h * up))
    # nach oben ausdehnen: Pixel gilt, wenn darunter (innerhalb band) Board liegt
    return cv2.dilate(m, np.ones((band, 1), np.uint8), anchor=(0, 0))


def find_tip(diff_mask, Hm, roi=None):
    """Pfeil finden: Teile im Board-Bereich, Achse per RANSAC (gerader Schaft),
    Spitze = unteres Ende der Achse (Kameras schauen flach aufs Board, der Pfeil ragt im Bild nach oben)."""
    if roi is not None:
        diff_mask = cv2.bitwise_and(diff_mask, roi)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(diff_mask, 8)
    if n < 2:
        return None
    big = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    area = int(stats[big, cv2.CC_STAT_AREA])
    if area < DART_MIN:
        return None
    # benachbarte Teile (Flight/Barrel getrennt) mitnehmen: erweiterte Box der größten Fläche
    x, y, w, h = (int(v) for v in stats[big, :4])
    pad = max(w, h) // 2
    box = (slice(max(0, y - pad), y + h + pad), slice(max(0, x - pad), x + w + pad))
    ys, xs = np.nonzero(diff_mask[box])
    pts = np.column_stack([xs + box[1].start, ys + box[0].start]).astype(np.float32)
    if len(pts) > 6000:
        pts = pts[np.random.default_rng(1).choice(len(pts), 6000, replace=False)]
    r = ransac_line(pts)
    if r is None:
        return None
    x0, y0, vx, vy, inl = r
    d = np.array([vx, vy])
    proj_in = (pts[inl] - [x0, y0]) @ d
    lo, hi = float(proj_in.min()), float(proj_in.max())
    # Form-Check: Pfeil = lang und gerade. Flecken (Schatten, Belichtung, Hand) fliegen raus.
    if hi - lo < 25 or inl.sum() < 0.2 * len(pts):
        return None
    a_lo, a_hi = np.array([x0, y0]) + d * lo, np.array([x0, y0]) + d * hi
    tip = a_lo if a_lo[1] > a_hi[1] else a_hi          # unteres Ende im Bild = Spitze im Board
    if Hm is not None and math.hypot(*to_board(Hm, tip)) > 235:
        return None                                      # Spitze nicht auf dem Board → kein Pfeil
    return {"tip": (float(tip[0]), float(tip[1])), "area": float(area), "line": (x0, y0, vx, vy),
            "seg": ((float(a_lo[0]), float(a_lo[1])), (float(a_hi[0]), float(a_hi[1])))}


def cal_quality(Hs):
    """Kalibrier-Check mit Kameramodell: gemeinsame Brennweite aller Kameras, je Kamera Rückprojektionsfehler (px).
    Gute Klicks: < 3 px. Über ~6 px liegt mindestens ein Punkt daneben."""
    if not Hs:
        return {}
    cx, cy = W / 2, H / 2
    def focal(G):
        best = (1e9, 0)
        for f in range(int(W * 0.15), int(W * 3), 2):
            A = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ G
            n1, n2 = np.linalg.norm(A[:, 0]), np.linalg.norm(A[:, 1])
            best = min(best, ((A[:, 0] @ A[:, 1] / (n1 * n2)) ** 2 + ((n1 - n2) / n1) ** 2, f))
        return best[1]
    f = float(np.median([focal(np.linalg.inv(Hm)) for Hm in Hs.values()]))
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
    out = {}
    for k, Hm in Hs.items():
        obj = np.array([[*board.CAL_POINTS[p], 0.0] for p in ("20-1", "6-10", "3-19", "11-14")])
        img = cv2.perspectiveTransform(obj[:, :2].reshape(-1, 1, 2), np.linalg.inv(Hm)).reshape(-1, 2)
        try:
            ok, rv, tv = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_IPPE)
            pr = cv2.projectPoints(obj, rv, tv, K, None)[0].reshape(-1, 2)
            out[k] = round(float(np.linalg.norm(pr - img, axis=1).max()), 1)
        except cv2.error:
            out[k] = None
    return out


def board_line(Hm, line):
    """Pfeilachse aus dem Kamerabild auf die Board-Ebene projizieren → (Punkt, Einheitsrichtung) in mm.
    Die Spitze steckt in der Ebene, also liegt sie auf dieser Linie – egal welches Ende im Bild die Spitze ist."""
    x0, y0, vx, vy = line
    a = np.array(to_board(Hm, (x0, y0)))
    b = np.array(to_board(Hm, (x0 + vx * 40, y0 + vy * 40)))
    d = b - a
    n = np.linalg.norm(d)
    return (a, d / n) if n > 1e-6 else None


def intersect(lines):
    """Kleinste-Quadrate-Schnittpunkt mehrerer Linien; schlechteste Linie verwerfen, wenn sie nicht passt.
    Rückgabe (Punkt, {key: Abstand mm}) oder None (zu flacher Winkel)."""
    lines = dict(lines)
    while len(lines) >= 2:
        A, B = np.zeros((2, 2)), np.zeros(2)
        for p, d in lines.values():
            nrm = np.array([-d[1], d[0]])
            M = np.outer(nrm, nrm)
            A += M
            B += M @ p
        ev = np.linalg.eigvalsh(A)
        if ev[0] < 0.04 * len(lines):   # Linien fast parallel (< ~12°)
            return None
        X = np.linalg.solve(A, B)
        res = {k: abs(float(np.array([-d[1], d[0]]) @ (X - p))) for k, (p, d) in lines.items()}
        worst = max(res, key=res.get)
        if res[worst] > FUSE_MM and len(lines) >= 3:
            del lines[worst]
            continue
        return (float(X[0]), float(X[1])), res
    return None


def fuse(points):
    """Median-Fusion mehrerer Kamera-Schätzungen, Ausreißer verwerfen."""
    if not points:
        return None
    arr = np.array(points)
    med = np.median(arr, axis=0)
    good = arr[np.linalg.norm(arr - med, axis=1) <= FUSE_MM]
    p = good.mean(axis=0) if len(good) else med
    return float(p[0]), float(p[1])


def fourcc_str(cap):
    v = int(cap.get(cv2.CAP_PROP_FOURCC)) & 0xFFFFFFFF
    t = "".join(chr((v >> 8 * i) & 0xFF) for i in range(4))
    return t if t.isalnum() else "?"


def open_capture(src):
    """Plattformgerecht öffnen: Windows = DirectShow (Index 0,1,2 …), Linux = V4L2 (/dev/videoX)."""
    s = str(src).strip()
    if sys.platform.startswith("win") and s.isdigit():
        # Ziel: MJPG (komprimiert). Bleibt eine Kamera bei YUY2, reicht die USB-Bandbreite nicht für drei.
        # DirectShow übernimmt MJPG oft nur, wenn FOURCC vor UND nach der Auflösung gesetzt wird; sonst MSMF probieren.
        apis = {"dshow": [cv2.CAP_DSHOW], "msmf": [cv2.CAP_MSMF]}.get(BACKEND, [cv2.CAP_DSHOW, cv2.CAP_MSMF])
        last = None
        for api in apis:
            cap = cv2.VideoCapture(int(s), api)
            if not cap.isOpened():
                cap.release(); continue
            mjpg = cv2.VideoWriter_fourcc(*"MJPG")
            cap.set(cv2.CAP_PROP_FOURCC, mjpg)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
            if api == cv2.CAP_DSHOW:
                cap.set(cv2.CAP_PROP_FOURCC, mjpg)   # DirectShow: FOURCC nach der Auflösung nochmal
            # MSMF: Reihenfolge FOURCC → Breite → Höhe, danach nichts mehr setzen (sonst 640x480 YUY2)
            if api == cv2.CAP_MSMF or fourcc_str(cap) == "MJPG" or api == apis[-1]:
                if last is not None:
                    last.release()
                return cap
            if last is not None:
                last.release()
            last = cap   # DSHOW ohne MJPG merken, falls MSMF gar nicht geht
        return last if last is not None else cv2.VideoCapture(int(s), cv2.CAP_DSHOW)
    if sys.platform.startswith("win"):
        return cv2.VideoCapture(s)  # RTSP/HTTP-Stream oder Videodatei
    if s.isdigit() or s.startswith("/dev/"):
        cap = cv2.VideoCapture(int(s) if s.isdigit() else s, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
        return cap
    return cv2.VideoCapture(s)  # z. B. RTSP/HTTP-Stream oder Videodatei


def set_res(w, h):
    global W, H
    W, H = int(w), int(h)


def probe_resolution(srcs, say=print):
    """Von hoch nach niedrig testen, bis ALLE Kameras gleichzeitig flüssig laufen.
    Windows: je Stufe DirectShow und Media Foundation. Rückgabe (w, h, backend)."""
    global BACKEND
    win = sys.platform.startswith("win") and all(str(x).strip().isdigit() for x in srcs)
    backends = [BACKEND] if (BACKEND_FIXED or not win) else ["dshow", "msmf"]
    for w, h in RES_STEPS:
        for be in backends:
            set_res(w, h)
            BACKEND = be
            r = test_cameras(srcs, seconds=3)
            sizes = {(c["w"], c["h"]) for c in r}
            ok = all(c["open"] and c["fps"] >= PROBE_FPS for c in r) and len(sizes) == 1
            real = sizes.pop() if len(sizes) == 1 else (w, h)
            say(f"  {w}x{h}{' ' + be if be else ''} → " + " · ".join(f"Cam {i + 1}: {c['fps']} fps {c['w']}x{c['h']} {c['fmt']}" for i, c in enumerate(r))
                + ("  ✓" if ok else ""))
            if ok and real[0] > 0:
                return real[0], real[1], be
    return RES_STEPS[-1][0], RES_STEPS[-1][1], BACKEND


def _use_backend(be):
    global BACKEND
    if not BACKEND_FIXED:
        BACKEND = be or ""


def init_resolution(srcs, force=False, say=print):
    """Auflösung festlegen: config.env (feste Zahl) > gespeichertes Messergebnis > neu messen."""
    key = ",".join(srcs)
    if not AUTO_RES and not force:
        try:
            with open(RES_FILE) as f:
                d = json.load(f)
            if d.get("srcs") == key:
                _use_backend(d.get("backend", ""))
        except Exception:
            pass
        return W, H
    if not force:
        try:
            with open(RES_FILE) as f:
                d = json.load(f)
            if d.get("srcs") == key:
                set_res(d["w"], d["h"])
                _use_backend(d.get("backend", ""))
                return W, H
        except Exception:
            pass
    say("Kamera-Auflösung wird getestet (einmalig, ca. 10–30 s) …")
    w, h, be = probe_resolution(srcs, say)
    set_res(w, h)
    _use_backend(be)
    os.makedirs(DATA, exist_ok=True)
    with open(RES_FILE, "w") as f:
        json.dump({"w": w, "h": h, "backend": be, "srcs": key}, f)
    say(f"Gespeichert: {w}x{h}{' über ' + be if be else ''}  (neu testen: python run.py --probe-res)")
    return w, h


def test_cameras(srcs, seconds=4):
    """Alle Kameras GLEICHZEITIG öffnen und Bilder zählen – zeigt USB-Bandbreiten-Probleme."""
    cams = []
    for s in srcs:
        cap = open_capture(s)   # setzt MJPG + Auflösung selbst (nochmal setzen kippt DirectShow auf YUY2)
        cams.append([s, cap, 0])
        time.sleep(0.3)
    t0 = time.time()
    while time.time() - t0 < seconds:
        for c in cams:
            if c[1].isOpened() and c[1].read()[0]:
                c[2] += 1
    out = []
    for s, cap, n in cams:
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC)) if cap.isOpened() else 0
        out.append({"src": s, "open": cap.isOpened(), "fps": round(n / seconds, 1),
                    "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                    "fmt": fourcc_str(cap) if fourcc else "-"})
        cap.release()
    return out


def list_cameras(max_idx=10):
    """Verfügbare Kameras finden (für --list-cameras). Nicht lesbare Geräte kommen mit Grund zurück."""
    found = []
    if sys.platform.startswith("win"):
        cands = [str(i) for i in range(max_idx)]
    else:
        import glob
        cands = sorted(glob.glob("/dev/v4l/by-path/*video-index0")) or sorted(glob.glob("/dev/video*"))
    for c in cands:
        cap = open_capture(c)
        ok = cap.isOpened() and cap.read()[0]
        if ok:
            found.append({"src": c, "ok": True, "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                          "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})
        elif c.startswith("/dev/"):
            if not os.access(c, os.R_OK | os.W_OK):
                why = "keine Rechte (Gruppe video – neu anmelden/neu starten)"
            elif cap.isOpened():
                why = "liefert kein Bild (belegt? läuft der Dienst dartcam?)"
            else:
                why = "lässt sich nicht öffnen (belegt durch dartcam/Autodarts?)"
            if "by-path" in c or "index0" in c or os.path.basename(c).startswith("video"):
                found.append({"src": c, "ok": False, "why": why})
        cap.release()
    return found


class Camera:
    def __init__(self, cid, src):
        self.id, self.src = cid, src
        self.cap = None
        self.frame = None
        self.lock = threading.Lock()
        self.ok = False

    def open(self):
        self.last_try = time.time()
        if self.cap is not None:
            self.cap.release()
        self.cap = open_capture(self.src)   # MJPG + Auflösung werden dort gesetzt
        exp = os.environ.get("CAM_EXPOSURE", "").strip()
        if exp:   # Belichtung fest: verhindert Helligkeitssprünge (Hand/Pfeil im Bild → ganzes Bild „ändert“ sich)
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25 if sys.platform.startswith("win") else 1)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, float(exp))
        if not sys.platform.startswith("win"):
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.ok = self.cap.isOpened()

    def read(self):
        if not self.ok:
            if time.time() - getattr(self, "last_try", 0) > 5:
                self.open()  # Kamera abgesteckt/neu verbunden -> erneut versuchen
            return None
        ok, f = self.cap.read()
        if not ok:
            self.fails = getattr(self, "fails", 0) + 1
            if self.fails > 30:
                self.ok, self.fails = False, 0
            return None
        self.fails = 0
        with self.lock:
            self.frame = f
        return f

    def jpeg(self, overlay=None):
        with self.lock:
            f = None if self.frame is None else self.frame.copy()
        if f is None:
            f = np.zeros((H, W, 3), np.uint8)
        if overlay:
            for ring in overlay["rings"]:
                cv2.polylines(f, [np.int32(ring)], False, (0, 255, 255), 1, cv2.LINE_AA)
            for w in overlay["wires"]:
                cv2.line(f, tuple(map(int, w[0])), tuple(map(int, w[1])), (0, 255, 255), 1, cv2.LINE_AA)
        return cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def gray(f):
    return cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (5, 5), 0)


def mask(a, b):
    d = cv2.absdiff(a, b)
    _, m = cv2.threshold(d, DIFF_THR, 255, cv2.THRESH_BINARY)
    m = cv2.medianBlur(m, 3)   # Rauschen weg, dünne Spitze/Schaft bleiben (Opening 3×3 hat sie gelöscht)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    return m


class Detector(threading.Thread):
    """Zustandsmaschine: IDLE -> MOVING -> (stabil) -> DART | TAKEOUT."""

    def __init__(self, sources, on_event):
        super().__init__(daemon=True)
        self.cams = [Camera(str(i), s) for i, s in enumerate(sources)]
        self.on_event = on_event
        self.cal = load_cal()
        self.H = {}
        self.reload_cal()
        self.ref, self.empty, self.prev = {}, {}, {}
        self.on_board = []   # Trainings-IDs der Pfeile, die gerade im Board stecken
        self.prev_tips = {}  # vom Netz gefundene Spitzen beim letzten Wurf (je Kamera)
        self.state = "idle"
        self.stable = 0
        self.paused = False
        self.reset_flag = True
        self.fps = 0.0

    def reload_cal(self):
        self.H, self.roi = {}, {}
        for c in self.cams:
            pts = self.points(c.id)
            if pts:
                Hm = homography(pts)
                if Hm is not None:
                    self.H[c.id] = Hm
                    self.roi[c.id] = board_roi(Hm, (H, W))

    def points(self, cid):
        """Kalibrierpunkte in aktueller Auflösung (gespeichert mit _res → bei Wechsel mitskalieren)."""
        pts = dict(self.cal.get(cid) or {})
        res = pts.pop("_res", None)
        if res and tuple(res) != (W, H):
            sx, sy = W / res[0], H / res[1]
            pts = {k: [v[0] * sx, v[1] * sy] for k, v in pts.items()}
        return pts

    def set_cal(self, cid, pts):
        self.cal[cid] = {**pts, "_res": [W, H]}
        save_cal(self.cal)
        self.reload_cal()

    def overlay(self, cid):
        return overlay_points(self.H[cid]) if cid in self.H else None

    def reset_reference(self):
        """Board ist leer -> neue Referenz."""
        self.reset_flag = True
        self.on_board = []
        self.prev_tips = {}

    def run(self):
        for c in self.cams:
            c.open()
            time.sleep(0.3)   # nacheinander öffnen wie im Test – USB-Bandbreite wird sauber ausgehandelt
        t0, n = time.time(), 0
        while True:
            frames = {}
            for c in self.cams:
                f = c.read()
                if f is not None:
                    frames[c.id] = gray(f)
            if not frames:
                time.sleep(0.2)
                continue
            n += 1
            if time.time() - t0 > 2:
                self.fps, t0, n = n / (time.time() - t0), time.time(), 0

            if self.reset_flag:
                self.ref = dict(frames)
                self.empty = dict(frames)
                self.prev = dict(frames)
                self.reset_flag, self.state, self.stable = False, "idle", 0
                continue
            if self.paused:
                self.prev = dict(frames)
                continue

            motion = max(int(cv2.countNonZero(mask(frames[k], self.prev.get(k, frames[k]))))
                         for k in frames)
            self.prev = dict(frames)

            if motion > MOTION_PX:
                self.state, self.stable = "moving", 0
                continue
            if self.state != "moving":
                continue
            self.stable += 1
            if self.stable < STABLE_FRAMES:
                continue
            self.state = "idle"
            self.evaluate(frames)

    def net_locate(self, masks):
        """Neuer Pfeil per Netz: Spitzen je Kamera finden, schon steckende abziehen, Kameras abgleichen.
        Rückgabe (p_mm, {cam: Abstand}, {cam: [u, v]}, sicher) oder None (→ alte Methode)."""
        net = tipnet.get()
        if not net or not self.H:
            return None
        cands, allt = {}, {}
        for c in self.cams:
            if c.id not in self.H:
                continue
            with c.lock:
                f = None if c.frame is None else c.frame.copy()
            if f is None:
                continue
            tips = net(f)
            allt[c.id] = tips
            prev = self.prev_tips.get(c.id, [])
            new = [t for t in tips if all(math.hypot(t[0] - a, t[1] - b) > 12 for a, b, _ in prev)]
            m = masks.get(c.id)
            if m is not None and cv2.countNonZero(m) and new:   # nahe an der Bildänderung bevorzugen
                dist = cv2.distanceTransform(255 - m, cv2.DIST_L2, 3)
                hh, ww = m.shape
                new.sort(key=lambda t: dist[min(max(int(t[1]), 0), hh - 1), min(max(int(t[0]), 0), ww - 1)] - 20 * t[2])
            cands[c.id] = [(to_board(self.H[c.id], (u, v)), sc, (u, v)) for u, v, sc in new[:2]]
        self.prev_tips = allt
        pts = [(cid, xy, sc, uv) for cid, lst in cands.items() for xy, sc, uv in lst if math.hypot(*xy) < 240]
        if not pts:
            return None
        best = None
        for cid, xy, sc, uv in pts:   # Kandidat mit den meisten zustimmenden Kameras
            sup = {}
            for cj, xj, sj, uj in pts:
                dd = math.hypot(xj[0] - xy[0], xj[1] - xy[1])
                if dd <= FUSE_MM and (cj not in sup or dd < sup[cj][0]):
                    sup[cj] = (dd, xj, sj, uj)
            key = (len(sup), sum(v[2] for v in sup.values()))
            if best is None or key > best[0]:
                best = (key, sup)
        (n, conf), sup = best
        if n < 2 and not (len(cands) == 1 and conf >= 0.7):
            return None   # Kameras uneinig → alte Methode
        p = (float(np.mean([v[1][0] for v in sup.values()])), float(np.mean([v[1][1] for v in sup.values()])))
        d = {cid: math.hypot(v[1][0] - p[0], v[1][1] - p[1]) for cid, v in sup.items()}
        uv = {cid: [round(v[3][0], 1), round(v[3][1], 1)] for cid, v in sup.items()}
        sure = n == len(allt) and n >= 2 and max(d.values()) < 4 and min(v[2] for v in sup.values()) > 0.6
        log.info("Netz: %d/%d Kameras einig, %.0f ms je Bild", n, len(allt), net.ms)
        return p, d, uv, sure

    def collect(self, dbg, p=None, score=None, how="", net_uv=None, sure=False):
        """Trainingsdaten: Farbbilder aller Kameras + Vorschlag für die Spitze je Kamera (Pixel)."""
        try:
            if not train.collecting():
                return None
            imgs, prop, tips, size = {}, {}, {}, {}
            for c in self.cams:
                with c.lock:
                    f = None if c.frame is None else c.frame.copy()
                if f is None:
                    continue
                imgs[c.id] = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
                size[c.id] = [f.shape[1], f.shape[0]]
                if p is not None and c.id in self.H:
                    v = np.linalg.inv(self.H[c.id]) @ np.array([p[0], p[1], 1.0])
                    prop[c.id] = [float(v[0] / v[2]), float(v[1] / v[2])]
                r = dbg.get(c.id, (None, None, None))[2]
                if r:
                    tips[c.id] = list(r["tip"])
            if not imgs:
                return None
            if net_uv:
                tips = dict(net_uv)
            st = "unknown" if p is None else ("ok" if sure else "auto")   # sicher = alle Kameras einig → gilt als bestätigt
            sid = train.save(imgs, {"status": st, "auto_ok": bool(sure), "pos": list(p) if p is not None else None,
                                    "name": score.get("name") if score else None, "how": how, "size": size,
                                    "proposal": prop, "cam_tips": tips, "tips": dict(net_uv) if sure else {}, "prev": list(self.on_board)})
            if sid:
                self.on_board.append(sid)
            return sid
        except Exception as e:
            log.warning("Trainingsdaten nicht gespeichert: %s", e)
            return None

    def debug_shot(self, dbg, name):
        if DEBUG_KEEP <= 0 or not dbg:
            return
        try:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            tiles = []
            for k in sorted(dbg):
                g, m, r = dbg[k]
                im = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
                im[m > 0] = (0.5 * im[m > 0] + [0, 0, 120]).astype(np.uint8)          # Maske rot
                if k in self.H:
                    ov = overlay_points(self.H[k])
                    for ring in ov["rings"]:
                        cv2.polylines(im, [np.int32(ring)], False, (106, 249, 221), 1)
                if r:
                    x0, y0, vx, vy = r["line"]
                    cv2.line(im, (int(x0 - vx * 400), int(y0 - vy * 400)), (int(x0 + vx * 400), int(y0 + vy * 400)), (255, 200, 0), 1)
                    (a1, a2) = r["seg"]
                    cv2.line(im, (int(a1[0]), int(a1[1])), (int(a2[0]), int(a2[1])), (255, 200, 0), 3)
                    cv2.circle(im, tuple(int(v) for v in r["tip"]), 6, (0, 255, 255), 2)
                for u, v, sc in self.prev_tips.get(k, []):   # Netz-Spitzen: magenta + Sicherheit
                    cv2.drawMarker(im, (int(u), int(v)), (255, 0, 255), cv2.MARKER_TILTED_CROSS, 18, 2)
                    cv2.putText(im, f"{sc:.2f}", (int(u) + 8, int(v) - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)
                cv2.putText(im, f"Cam {int(k) + 1}", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                tiles.append(im)
            h = min(t.shape[0] for t in tiles)
            tiles = [cv2.resize(t, (int(t.shape[1] * h / t.shape[0]), h)) for t in tiles]
            fn = os.path.join(DEBUG_DIR, time.strftime("%H%M%S") + f"_{name}.jpg")
            cv2.imwrite(fn, np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 80])
            old = sorted(os.listdir(DEBUG_DIR))[:-DEBUG_KEEP]
            for f in old:
                os.remove(os.path.join(DEBUG_DIR, f))
        except Exception as e:
            log.warning("Debug-Bild fehlgeschlagen: %s", e)

    def evaluate(self, frames):
        areas, results, lines, dbg, masks = {}, {}, {}, {}, {}
        for k, g in frames.items():
            m = mask(g, self.ref.get(k, g))
            masks[k] = m
            areas[k] = int(cv2.countNonZero(m))
            if DART_MIN <= areas[k] <= DART_MAX:
                r = find_tip(m, self.H.get(k), self.roi.get(k) if k in self.roi and self.roi[k].shape == g.shape else None)
                dbg[k] = (g, m, r)
                if r and k in self.H:
                    bx, by = to_board(self.H[k], r["tip"])
                    if math.hypot(bx, by) < 260:
                        results[k] = (bx, by)
                    bl = board_line(self.H[k], r["line"])
                    if bl:
                        lines[k] = bl
        big = max(areas.values()) if areas else 0
        if big < DART_MIN:
            return  # Rauschen
        # Pfeile gezogen? Board sieht (fast) wieder aus wie leer → Takeout, egal ob mit Hand dazwischen
        empty_area = max(int(cv2.countNonZero(mask(frames[k], self.empty.get(k, frames[k])))) for k in frames)
        if empty_area < TAKEOUT_PX and empty_area < big * 0.35:   # neuer Pfeil: empty_area ≈ big
            self.ref = dict(frames)
            self.empty = dict(frames)   # Lichtdrift mitnehmen
            log.info("Takeout erkannt (Rest %d px)", empty_area)
            self.on_board = []
            self.prev_tips = {}
            self.on_event({"type": "takeout"})
            return
        self.ref = dict(frames)
        if big > DART_MAX:
            return  # Hand im Bild – abwarten
        p, d, how, net_uv, net_ok = None, {}, "Spitze", None, False
        r = self.net_locate(masks)
        if r:
            p, d, net_uv, net_ok = r
            how = "Netz"
        if p is None and len(lines) >= 2:
            r = intersect(lines)
            # Schnittpunkt nur nehmen, wenn er zu mindestens einer Spitzen-Schätzung passt (Schutz vor Fehlformen)
            if r and math.hypot(*r[0]) < 260 and (not results or min(math.hypot(v[0] - r[0][0], v[1] - r[0][1]) for v in results.values()) < 25):
                p, d, how = r[0], r[1], "Achsen"
        if p is None:
            p = fuse(list(results.values()))
            if p is not None:
                d = {k: math.hypot(v[0] - p[0], v[1] - p[1]) for k, v in results.items()}
        if p is None:
            self.on_event({"type": "dart_unknown", "areas": areas, "sid": self.collect(dbg)})
            return
        s = board.score(*p)
        agree = sum(1 for v in d.values() if v <= FUSE_MM)
        spread = max(d.values(), default=0.0)
        self.debug_shot(dbg, s.get("name"))
        log.info("Dart %s (%s) · %s", s.get("name"), how, " · ".join(
            f"Cam {int(k) + 1}: {d[k]:.0f} mm" for k in sorted(d)))
        sid = self.collect(dbg, p, s, how, net_uv, net_ok)
        self.on_event({"type": "dart", "sid": sid, "x": p[0], "y": p[1], "score": s, "spread": spread, "agree": agree, "n": len(d),
                       "cams": {k: list(v) for k, v in results.items()}})
