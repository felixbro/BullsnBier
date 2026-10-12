"""DiceBear-Avatare (Stil "notionists", SVG, transparenter Grund – Styleguide §6.3).
Einmal laden und lokal speichern: danach offline, kein Name geht erneut an einen fremden Server."""
import hashlib, os, urllib.parse, urllib.request

from .config import DATA

DIR = os.path.join(DATA, "avatars")
STYLE = "notionists"
URL = "https://api.dicebear.com/9.x/{style}/svg?seed={seed}&backgroundColor=transparent"


def path(seed):
    return os.path.join(DIR, hashlib.sha1(f"{STYLE}|{seed}".encode()).hexdigest()[:20] + ".svg")


def get(seed):
    """SVG-Bytes oder None (offline/Fehler -> Silhouette bleibt)."""
    seed = (seed or "").strip()[:80] or "Gast"
    p = path(seed)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    try:
        url = URL.format(style=STYLE, seed=urllib.parse.quote(seed))
        req = urllib.request.Request(url, headers={"User-Agent": "BullsNBier/1.0"})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = r.read()
        if not data.lstrip().startswith(b"<svg"):
            return None
        os.makedirs(DIR, exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return data
    except Exception:
        return None
