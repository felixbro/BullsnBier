"""Persistente Einstellungen (data/settings.json). Caller-Texte als Vorlagen mit {platzhaltern}."""
import copy, json, os

from .config import DATA
FILE = os.path.join(DATA, "settings.json")

DEFAULTS = {
    "caller": {
        "enabled": True,
        "lang": "de",
        "rate": 1.0,
        "pitch": 1.0,
        "volume": 1.0,
        # Was angesagt wird
        "say_start": True,
        "say_dart": True,
        "say_turn": True,
        "say_bust": True,
        "say_next": True,           # wer ist dran
        "say_remaining": "finish",  # off | finish | always
        "say_leg": True,
        "say_match": True,
        "say_correction": True,
        "say_takeout": False,
    },
    "texts": {
        "de": {
            "start": "Game on! {name} beginnt.",
            "single": "{n}", "double": "Doppel {n}", "triple": "Triple {n}",
            "bull": "Bullseye", "outer": "Bull", "miss": "Daneben",
            "turn": "{points}", "noscore": "Kein Score", "t180": "Einhundertachtzig!",
            "bust": "Überworfen!",
            "next": "{name}, du bist dran.",
            "remaining": "{name}, du brauchst {score}.",
            "next_remaining": "{name}, du brauchst {score}.",
            "leg": "Game shot! Leg für {name}.",
            "match": "Game shot and the match! {name} gewinnt!",
            "corrected": "Korrigiert: {dart}",
            "takeout": "Pfeile ziehen",
        },
        "en": {
            "start": "Game on! {name} to throw first.",
            "single": "{n}", "double": "Double {n}", "triple": "Treble {n}",
            "bull": "Bullseye", "outer": "Bull", "miss": "Miss",
            "turn": "{points}", "noscore": "No score", "t180": "One hundred and eighty!",
            "bust": "Bust!",
            "next": "{name}, you're up.",
            "remaining": "{name}, you require {score}.",
            "next_remaining": "{name}, you require {score}.",
            "leg": "Game shot! Leg to {name}.",
            "match": "Game shot and the match! {name}!",
            "corrected": "Corrected: {dart}",
            "takeout": "Remove darts",
        },
    },
    "game": {
        "auto_next_sim": True,   # Simulator: Klick nach 3 Darts startet nächste Aufnahme
    },
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = _merge(DEFAULTS, json.load(f))
    except Exception:
        return copy.deepcopy(DEFAULTS)
    for lang, texts in data["texts"].items():  # leeres Feld = Standardtext
        for k, v in texts.items():
            if not str(v).strip() and k in DEFAULTS["texts"].get(lang, {}):
                texts[k] = DEFAULTS["texts"][lang][k]
    return data


def save(data):
    os.makedirs(DATA, exist_ok=True)
    merged = _merge(load(), data)
    with open(FILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    return merged


def reset():
    if os.path.exists(FILE):
        os.remove(FILE)
    return load()
