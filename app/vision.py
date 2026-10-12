"""Kamera-Erfassung + Pfeilerkennung (Differenzbild, Spitze, Homographie, Fusion)."""
import json, math, os, sys, threading, time
import cv2
import numpy as np

from . import board

from .config import DATA
CAL_FILE = os.path.join(DATA, "calibration.json")

# --- Tuning (per ENV überschreibbar) ---
W, H = int(os.environ.get("CAM_W", 1280)), int(os.environ.get("CAM_H", 720))
MOTION_PX = int(os.environ.get("MOTION_PX", 400))       # Pixel-Änderung = Bewegung
STABLE_FRAMES = int(os.environ.get("STABLE_FRAMES", 6))
DART_MIN = int(os.environ.get("DART_MIN", 250))          # min. Fläche eines Pfeils
DART_MAX = int(os.environ.get("DART_MAX", 40000))        # darüber = Hand/Takeout
DIFF_THR = int(os.environ.get("DIFF_THR", 28))
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


def find_tip(diff_mask, Hm):
    """Größte Kontur = Pfeil. Spitze = schmaleres Ende der Hauptachse."""
    cnts, _ = cv2.findContours(diff_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    area = cv2.contourArea(c)
    if area < DART_MIN:
        return None
    pts = c.reshape(-1, 2).astype(np.float32)
    vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_L2, 0, 0.01, 0.01).flatten()
    d = np.array([vx, vy])
    proj = (pts - [x0, y0]) @ d
    perp = np.abs((pts - [x0, y0]) @ np.array([-vy, vx]))
    lo, hi = proj.min(), proj.max()
    span = max(hi - lo, 1)
    band = span * 0.15
    w_lo = perp[proj < lo + band].mean() if (proj < lo + band).any() else 1e9
    w_hi = perp[proj > hi - band].mean() if (proj > hi - band).any() else 1e9
    end = lo if w_lo < w_hi else hi
    sel = pts[np.abs(proj - end) < 3]
    tip = sel.mean(axis=0) if len(sel) else (np.array([x0, y0]) + d * end)
    tip = (float(tip[0]), float(tip[1]))
    # Plausibilität: falls schmales Ende außerhalb, anderes Ende testen
    if Hm is not None:
        bx, by = to_board(Hm, tip)
        if math.hypot(bx, by) > 230:
            other = hi if end == lo else lo
            alt = np.array([x0, y0]) + d * other
            ax, ay = to_board(Hm, alt)
            if math.hypot(ax, ay) < math.hypot(bx, by):
                tip = (float(alt[0]), float(alt[1]))
    return {"tip": tip, "area": float(area)}


def fuse(points):
    """Median-Fusion mehrerer Kamera-Schätzungen, Ausreißer verwerfen."""
    if not points:
        return None
    arr = np.array(points)
    med = np.median(arr, axis=0)
    good = arr[np.linalg.norm(arr - med, axis=1) <= FUSE_MM]
    p = good.mean(axis=0) if len(good) else med
    return float(p[0]), float(p[1])


def open_capture(src):
    """Plattformgerecht öffnen: Windows = DirectShow (Index 0,1,2 …), Linux = V4L2 (/dev/videoX)."""
    s = str(src).strip()
    if sys.platform.startswith("win"):
        idx = int(s) if s.isdigit() else s
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap = cv2.VideoCapture(idx, cv2.CAP_MSMF)
        return cap
    if s.isdigit():
        return cv2.VideoCapture(int(s), cv2.CAP_V4L2)
    if s.startswith("/dev/"):
        return cv2.VideoCapture(s, cv2.CAP_V4L2)
    return cv2.VideoCapture(s)  # z. B. RTSP/HTTP-Stream oder Videodatei


def list_cameras(max_idx=10):
    """Verfügbare Kameras finden (für --list-cameras)."""
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
            found.append({"src": c, "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                          "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})
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
        self.cap = open_capture(self.src)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
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
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
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
        self.state = "idle"
        self.stable = 0
        self.paused = False
        self.reset_flag = True
        self.fps = 0.0

    def reload_cal(self):
        self.H = {}
        for c in self.cams:
            pts = self.cal.get(c.id)
            if pts:
                Hm = homography(pts)
                if Hm is not None:
                    self.H[c.id] = Hm

    def set_cal(self, cid, pts):
        self.cal[cid] = pts
        save_cal(self.cal)
        self.reload_cal()

    def overlay(self, cid):
        return overlay_points(self.H[cid]) if cid in self.H else None

    def reset_reference(self):
        """Board ist leer -> neue Referenz."""
        self.reset_flag = True

    def run(self):
        for c in self.cams:
            c.open()
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

    def evaluate(self, frames):
        areas, results = {}, {}
        for k, g in frames.items():
            m = mask(g, self.ref.get(k, g))
            areas[k] = int(cv2.countNonZero(m))
            if DART_MIN <= areas[k] <= DART_MAX:
                r = find_tip(m, self.H.get(k))
                if r and k in self.H:
                    bx, by = to_board(self.H[k], r["tip"])
                    if math.hypot(bx, by) < 260:
                        results[k] = (bx, by)
        big = max(areas.values()) if areas else 0

        if big > DART_MAX:
            # Hand im Bild / Pfeile gezogen? Gegen leeres Board prüfen
            empty_area = max(int(cv2.countNonZero(mask(frames[k], self.empty.get(k, frames[k]))))
                             for k in frames)
            self.ref = dict(frames)
            if empty_area < DART_MIN:
                self.empty = dict(frames)
                self.on_event({"type": "takeout"})
            return
        if big < DART_MIN:
            return  # Rauschen
        self.ref = dict(frames)
        p = fuse(list(results.values()))
        if p is None:
            self.on_event({"type": "dart_unknown", "areas": areas})
            return
        s = board.score(*p)
        self.on_event({"type": "dart", "x": p[0], "y": p[1], "score": s,
                       "cams": {k: list(v) for k, v in results.items()}})
