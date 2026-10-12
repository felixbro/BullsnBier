"""Dartboard-Geometrie (mm, Ursprung = Bull, y nach oben) und Scoring."""
import math

SEGMENTS = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]

R_BULL = 6.35
R_OUTER_BULL = 15.9
R_TRIPLE_IN = 99.0
R_TRIPLE_OUT = 107.0
R_DOUBLE_IN = 162.0
R_DOUBLE_OUT = 170.0

# Kalibrierpunkte: Außenkante Double-Ring, Mitte der Segmente 20 / 6 / 3 / 11
CAL_POINTS = {
    "20": (0.0, R_DOUBLE_OUT),
    "6": (R_DOUBLE_OUT, 0.0),
    "3": (0.0, -R_DOUBLE_OUT),
    "11": (-R_DOUBLE_OUT, 0.0),
}


def segment_at(x: float, y: float) -> int:
    ang = math.degrees(math.atan2(x, y)) % 360  # 0° = oben, im Uhrzeigersinn
    return SEGMENTS[int(((ang + 9) % 360) // 18)]


def score(x: float, y: float) -> dict:
    """-> {'name': 'T20', 'value': 60, 'mult': 3, 'seg': 20}"""
    r = math.hypot(x, y)
    if r <= R_BULL:
        return {"name": "BULL", "value": 50, "mult": 2, "seg": 25}
    if r <= R_OUTER_BULL:
        return {"name": "25", "value": 25, "mult": 1, "seg": 25}
    if r > R_DOUBLE_OUT:
        return {"name": "MISS", "value": 0, "mult": 0, "seg": 0}
    seg = segment_at(x, y)
    if R_TRIPLE_IN <= r <= R_TRIPLE_OUT:
        return {"name": f"T{seg}", "value": 3 * seg, "mult": 3, "seg": seg}
    if r >= R_DOUBLE_IN:
        return {"name": f"D{seg}", "value": 2 * seg, "mult": 2, "seg": seg}
    return {"name": f"S{seg}", "value": seg, "mult": 1, "seg": seg}


def from_name(name: str) -> dict:
    """Manuelle Korrektur: 'T20', 'D16', 'S5', '25', 'BULL', 'MISS'."""
    n = name.strip().upper()
    if n in ("BULL", "DB", "50"):
        return {"name": "BULL", "value": 50, "mult": 2, "seg": 25}
    if n in ("25", "SB"):
        return {"name": "25", "value": 25, "mult": 1, "seg": 25}
    if n in ("MISS", "0", "M"):
        return {"name": "MISS", "value": 0, "mult": 0, "seg": 0}
    mult = {"S": 1, "D": 2, "T": 3}.get(n[0], 1)
    seg = int(n[1:] if n[0] in "SDT" else n)
    if not 1 <= seg <= 20:
        raise ValueError(name)
    prefix = "SDT"[mult - 1]
    return {"name": f"{prefix}{seg}", "value": mult * seg, "mult": mult, "seg": seg}


def board_point_for(name: str):
    """Ungefähre Board-Position eines Feldes (für Anzeige bei manueller Eingabe)."""
    s = from_name(name)
    if s["seg"] == 25:
        return (0.0, 0.0) if s["mult"] == 2 else (0.0, 11.0)
    if s["seg"] == 0:
        return None
    r = {1: 135.0, 2: 166.0, 3: 103.0}[s["mult"]]
    ang = math.radians(SEGMENTS.index(s["seg"]) * 18)
    return (r * math.sin(ang), r * math.cos(ang))
