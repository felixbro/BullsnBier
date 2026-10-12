"""DiceBear-Avatare über die HTTP-API (https://api.dicebear.com/9.x/<stil>/svg?seed=…), SVG, transparenter Grund.
Der Server holt jedes Bild einmal und speichert es unter data/avatars – danach offline.
Hintergrund = CSS (Spielerfarbe/CI-Farbe), Akzent (Kleidung/Grundfarbe) = DiceBear-Parameter, nur CI-Farben."""
import hashlib, os, urllib.parse, urllib.request

from .config import DATA

DIR = os.path.join(DATA, "avatars")
URL = "https://api.dicebear.com/9.x/{style}/svg"

# Stil -> (Anzeigename, Parameter für die Akzentfarbe oder None)
STYLES = {
    "notionists": ("Notionists", None),
    "notionists-neutral": ("Notionists neutral", None),
    "lorelei": ("Lorelei", None),
    "lorelei-neutral": ("Lorelei neutral", None),
    "adventurer": ("Adventurer", None),
    "adventurer-neutral": ("Adventurer neutral", None),
    "avataaars": ("Avataaars", "clothesColor"),
    "big-ears": ("Big Ears", None),
    "big-smile": ("Big Smile", None),
    "micah": ("Micah", "shirtColor"),
    "miniavs": ("Miniavs", None),
    "open-peeps": ("Open Peeps", "clothingColor"),
    "personas": ("Personas", "clothingColor"),
    "dylan": ("Dylan", None),
    "croodles": ("Croodles", None),
    "pixel-art": ("Pixel Art", "clothingColor"),
    "fun-emoji": ("Fun Emoji", None),
    "bottts": ("Bottts", "baseColor"),
    "thumbs": ("Thumbs", "shapeColor"),
    "shapes": ("Shapes", "shape1Color"),
}
DEFAULT_STYLE = "notionists"
# CI-Farben für Akzente (ohne #)
CI = ["DDF96A", "FF6B5E", "3DBB7A", "7FDDEB", "2AAFC4", "FFD66B", "BDC8CB", "202020"]


def norm(style, accent):
    style = style if style in STYLES else DEFAULT_STYLE
    accent = (accent or "ci").lstrip("#").upper()
    if accent != "CI" and accent not in CI:
        accent = "CI"
    return style, accent


def _path(seed, style, accent):
    return os.path.join(DIR, hashlib.sha1(f"{style}|{accent}|{seed}".encode()).hexdigest()[:20] + ".svg")


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "BullsNBier/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        data = r.read()
    return data if data.lstrip().startswith(b"<svg") else None


def get(seed, style=DEFAULT_STYLE, accent="ci"):
    """SVG-Bytes oder None (offline/Fehler -> Silhouette bleibt)."""
    seed = (seed or "").strip()[:80] or "Gast"
    style, accent = norm(style, accent)
    p = _path(seed, style, accent)
    if os.path.exists(p):
        with open(p, "rb") as f:
            return f.read()
    q = {"seed": seed, "backgroundColor": "transparent"}
    param = STYLES[style][1]
    if param:
        q[param] = ",".join(CI) if accent == "CI" else accent.lower()
    base = URL.format(style=style)
    data = None
    for query in (q, {"seed": seed, "backgroundColor": "transparent"}):  # ohne Akzent als Rückfall
        try:
            data = _fetch(base + "?" + urllib.parse.urlencode(query))
        except Exception:
            data = None
        if data or not param:
            break
    if data:
        os.makedirs(DIR, exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
    return data
