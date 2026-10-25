"""Trainingsdaten sammeln: pro Wurf die Bilder aller Kameras + Label (Board-Position, Wert, Spitze je Kamera).

Ordner DATA/train/<sid>/  →  cam0.jpg, cam1.jpg, … + meta.json
meta.status:  auto (erkannt, unbestätigt) · ok (Spitze markiert/bestätigt) · corrected (Wert korrigiert) · unknown · skip
             review (BnB und Autodarts uneinig → in der Markieransicht wählen)
"""
import json, os, shutil, threading, time

from .config import DATA

TRAIN_DIR = os.path.join(DATA, "train")
SET_FILE = os.path.join(TRAIN_DIR, "_settings.json")
MAX = int(os.environ.get("TRAIN_MAX", 5000))
_lock = threading.Lock()


def _settings():
    try:
        with open(SET_FILE) as f:
            return json.load(f)
    except Exception:
        return {"collect": True}


def collecting():
    return bool(_settings().get("collect", True))


def set_collect(on):
    os.makedirs(TRAIN_DIR, exist_ok=True)
    with open(SET_FILE, "w") as f:
        json.dump({**_settings(), "collect": bool(on)}, f)


def _ids():
    if not os.path.isdir(TRAIN_DIR):
        return []
    return sorted(d for d in os.listdir(TRAIN_DIR) if not d.startswith("_") and os.path.isdir(os.path.join(TRAIN_DIR, d)))


def read(sid):
    try:
        with open(os.path.join(TRAIN_DIR, sid, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write(sid, meta):
    p = os.path.join(TRAIN_DIR, sid, "meta.json")
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    os.replace(p + ".tmp", p)


def save(images, meta):
    """images: {cid: jpeg-bytes}. Rückgabe sid oder None."""
    if not collecting():
        return None
    with _lock:
        ids = _ids()
        if len(ids) >= MAX:   # Ring: älteste unmarkierte zuerst löschen
            old = next((i for i in ids if (read(i) or {}).get("status") in ("auto", "unknown", "skip")), ids[0])
            shutil.rmtree(os.path.join(TRAIN_DIR, old), ignore_errors=True)
        sid = time.strftime("%Y%m%d-%H%M%S-") + f"{int(time.time() * 1000) % 1000:03d}"
        d = os.path.join(TRAIN_DIR, sid)
        os.makedirs(d, exist_ok=True)
        for cid, jpg in images.items():
            with open(os.path.join(d, f"cam{cid}.jpg"), "wb") as f:
                f.write(jpg)
        _write(sid, {"sid": sid, "t": time.time(), **meta})
        return sid


def update(sid, **kw):
    with _lock:
        m = read(sid)
        if m is None:
            return None
        m.update(kw)
        _write(sid, m)
        return m


def remove(sid):
    shutil.rmtree(os.path.join(TRAIN_DIR, sid), ignore_errors=True)


def image_path(sid, cid):
    p = os.path.join(TRAIN_DIR, sid, f"cam{cid}.jpg")
    return p if os.path.exists(p) else None


def stats():
    n = {"total": 0, "ok": 0, "todo": 0, "review": 0}
    for i in _ids():
        st = (read(i) or {}).get("status")
        n["total"] += 1
        if st == "ok":
            n["ok"] += 1
        elif st in ("auto", "corrected", "unknown", "review"):
            n["todo"] += 1
            n["review"] += st == "review"
    return {**n, "collect": collecting(), "dir": TRAIN_DIR}


def next_todo(after=None):
    """Nächster Wurf zum Markieren (neueste zuerst): Autodarts-Abweichungen, dann korrigierte/unklare, dann automatische."""
    ids = list(reversed(_ids()))
    if after in ids:
        ids = ids[ids.index(after) + 1:]
    best = {}
    for i in ids:
        st = (read(i) or {}).get("status")
        if st == "review":
            return read(i)
        rank = {"corrected": 1, "unknown": 1, "auto": 2}.get(st)
        if rank and rank not in best:
            best[rank] = i
    return read(best[min(best)]) if best else None
