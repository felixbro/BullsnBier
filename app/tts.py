"""Natürliche Offline-Sprachausgabe mit Piper (https://github.com/OHF-Voice/piper1-gpl).
Läuft auf Linux + Windows ohne GPU. Stimmen liegen in data/voices, erzeugte Ansagen werden gecacht."""
import hashlib, io, logging, os, re, shutil, threading, urllib.request, wave

from .config import DATA, ROOT

VOICES_DIR = os.environ.get("VOICES_DIR", os.path.join(ROOT, "voices"))  # gemeinsam für Live + Simulator
CACHE_DIR = os.path.join(DATA, "tts-cache")
URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{fam}/{code}/{name}/{q}/{voice}{ext}?download=true"

# Empfohlene Stimmen (Name, Beschreibung, ca. MB)
CATALOG = {
    "de_DE-thorsten-high":   ("Thorsten · männlich · beste Qualität", 114),
    "de_DE-thorsten-medium": ("Thorsten · männlich · schneller", 63),
    "de_DE-kerstin-low":     ("Kerstin · weiblich", 63),
    "de_DE-ramona-low":      ("Ramona · weiblich", 63),
    "de_DE-eva_k-x_low":     ("Eva · weiblich · sehr schnell", 20),
    "de_DE-karlsson-low":    ("Karlsson · männlich", 63),
    "de_DE-pavoque-low":     ("Pavoque · männlich", 63),
    "en_GB-alan-medium":     ("Alan · British male", 63),
    "en_GB-northern_english_male-medium": ("Northern English male", 63),
    "en_GB-cori-high":       ("Cori · British female", 114),
    "en_US-lessac-high":     ("Lessac · US female", 114),
}

_loaded, _lock = {}, threading.Lock()
logging.getLogger("piper").setLevel(logging.ERROR)  # "Missing phoneme from id map" ist harmlos


class TTSError(Exception):
    pass


def available():
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def installed():
    if not os.path.isdir(VOICES_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(VOICES_DIR)
                  if f.endswith(".onnx") and os.path.exists(os.path.join(VOICES_DIR, f + ".json")))


def status():
    inst = installed()
    return {"available": available(), "installed": inst,
            "catalog": [{"id": k, "label": v[0], "mb": v[1], "installed": k in inst} for k, v in CATALOG.items()]}


def download(voice):
    m = re.match(r"^([a-z]{2,3})_([A-Z]{2})-([a-zA-Z0-9_]+)-(x_low|low|medium|high)$", voice)
    if not m:
        raise TTSError("Ungültiger Stimmenname")
    fam, reg, name, q = m.groups()
    os.makedirs(VOICES_DIR, exist_ok=True)
    for ext in (".onnx.json", ".onnx"):
        dst = os.path.join(VOICES_DIR, voice + ext)
        if os.path.exists(dst) and os.path.getsize(dst) > 0:
            continue
        url = URL.format(fam=fam, code=f"{fam}_{reg}", name=name, q=q, voice=voice, ext=ext)
        tmp = dst + ".part"
        with urllib.request.urlopen(url, timeout=30) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        os.replace(tmp, dst)


def _voice(voice):
    if voice not in _loaded:
        path = os.path.join(VOICES_DIR, voice + ".onnx")
        if not os.path.exists(path):
            raise TTSError(f"Stimme {voice} nicht installiert")
        try:
            from piper import PiperVoice
        except Exception:
            raise TTSError("Piper nicht installiert (pip install piper-tts)")
        _loaded[voice] = PiperVoice.load(path)
    return _loaded[voice]


def synth(text, voice, rate=1.0):
    text = clean(text)
    if not text:
        raise TTSError("Leerer Text")
    voice = voice or (installed() or [""])[0]
    key = hashlib.sha1(f"{voice}|{rate:.2f}|{text}".encode()).hexdigest()
    cpath = os.path.join(CACHE_DIR, key + ".wav")
    if os.path.exists(cpath):
        with open(cpath, "rb") as f:
            return f.read()
    with _lock:
        v = _voice(voice)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            try:
                from piper import SynthesisConfig
                v.synthesize_wav(text, w, syn_config=SynthesisConfig(length_scale=1.0 / max(0.3, rate)))
            except ImportError:  # ältere piper-tts-Versionen
                v.synthesize(text, w, length_scale=1.0 / max(0.3, rate))
    data = buf.getvalue()
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cpath, "wb") as f:
        f.write(data)
    return data


def clean(text):
    """Punkt direkt nach Zahl würde als Ordinalzahl gelesen („vierzigster“) → entfernen."""
    text = re.sub(r"(\d)\s*\.(?=\s*(?:$|[,;!?]))", r"\1", text.strip())
    return re.sub(r"\s+", " ", text)


# ---------------- Vorberechnung (Warmup) ----------------
# Jede Ansage wird beim ersten Mal erzeugt und dann gecacht. Damit es im Spiel sofort spricht,
# werden die häufigen Sätze vorab im Hintergrund erzeugt: Zahlen/Felder beim Start,
# Spielernamen + Restwerte beim Spielstart.
import queue as _queue

_q = _queue.PriorityQueue()
_seq = 0
_worker = None
_state = {"done": 0, "queued": 0}


def _fill(t, **v):
    return re.sub(r"\{(\w+)\}", lambda m: str(v.get(m.group(1), "")), t or "")


def dart_text(name, T):
    if name == "BULL":
        return T["bull"]
    if name == "25":
        return T["outer"]
    if name == "MISS":
        return T["miss"]
    return _fill({"S": T["single"], "D": T["double"], "T": T["triple"]}[name[0]], n=name[1:])


def base_phrases(T):
    out = [dart_text(f"{m}{n}", T) for n in range(1, 21) for m in "SDT"] + [dart_text(x, T) for x in ("BULL", "25", "MISS")]
    out += [T["t180"], T["noscore"]] + [_fill(T["turn"], points=p) for p in range(1, 180)]
    out += [T[k] for k in ("bust", "halved", "shanghai", "takeout", "unknown", "cam_error")]
    return out


def player_phrases(T, names, finish_scores):
    hi, lo = [], []
    for n in names:
        hi += [_fill(T[k], name=n) for k in ("start", "next", "leg", "match", "bulloff", "bulloff_win", "gotcha")]
        lo += [_fill(T["next_remaining"], name=n, score=s) for s in finish_scores]
        lo += [_fill(T["remaining"], name=n, score=s) for s in finish_scores]
    return hi, lo


def warm(texts, voice, rate, prio=5):
    global _seq, _worker
    if not available() or voice not in installed():
        return
    for t in texts:
        t = clean(t)
        if not t:
            continue
        key = hashlib.sha1(f"{voice}|{rate:.2f}|{t}".encode()).hexdigest()
        if os.path.exists(os.path.join(CACHE_DIR, key + ".wav")):
            continue
        _seq += 1
        _state["queued"] += 1
        _q.put((prio, _seq, t, voice, rate))
    if _worker is None or not _worker.is_alive():
        _worker = threading.Thread(target=_run, daemon=True, name="tts-warm")
        _worker.start()


def _run():
    while True:
        try:
            _, _, t, v, r = _q.get(timeout=30)
        except _queue.Empty:
            return
        try:
            synth(t, v, r)
        except Exception:
            pass
        _state["done"] += 1


def warm_status():
    return {"pending": _q.qsize(), **_state}
