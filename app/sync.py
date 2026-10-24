"""Abgleich Darts-Rechner ↔ Trainings-Rechner über Nextcloud (WebDAV) oder einen geteilten Ordner.

config.env:
  SYNC_URL=https://cloud.example.de/remote.php/dav/files/<user>/BullsnBier-Sync   (oder Ordnerpfad)
  SYNC_USER=<user>          SYNC_PASS=<Nextcloud-App-Passwort>
  SETUP_NAME=Buschi         (Name dieses Boards, Unterordner für die Trainingsdaten)
  SYNC_AUTO_MODEL=0         (1 = beim Start nach neuem Modell schauen und installieren)

Ohne Konto-Zugang (empfohlen am Board) – zwei Nextcloud-Freigabelinks:
  SYNC_UPLOAD_LINK=https://cloud.example.de/s/AbCd…   „Dateiablage“ (nur hochladen, nichts sehen)
  SYNC_UPLOAD_PASS=…                                   Passwort der Freigabe (optional)
  SYNC_MODEL_LINK=https://cloud.example.de/s/XyZ…     Ordner „models“, nur lesen
  SYNC_MODEL_PASS=…
  SYNC_AUTO_UPLOAD=1        markierte Würfe automatisch hochladen (wenn kein Spiel läuft)

Ablage:
  train/<SETUP_NAME>/batch_<zeit>.zip   ← Darts-Rechner lädt hoch
  models/tips.onnx + models/latest.json ← Trainings-Rechner veröffentlicht
"""
import base64, io, json, os, shutil, socket, tempfile, threading, time, urllib.parse, urllib.request, zipfile
import xml.etree.ElementTree as ET

from .config import DATA

URL = os.environ.get("SYNC_URL", "").strip().rstrip("/")
USER = os.environ.get("SYNC_USER", "").strip()
PASS = os.environ.get("SYNC_PASS", "").strip()
SETUP = os.environ.get("SETUP_NAME", "").strip() or socket.gethostname()
AUTO_MODEL = os.environ.get("SYNC_AUTO_MODEL", "0").strip() == "1"
UP_LINK, UP_PASS = os.environ.get("SYNC_UPLOAD_LINK", "").strip(), os.environ.get("SYNC_UPLOAD_PASS", "").strip()
MODEL_LINK, MODEL_PASS = os.environ.get("SYNC_MODEL_LINK", "").strip(), os.environ.get("SYNC_MODEL_PASS", "").strip()
AUTO_UPLOAD = os.environ.get("SYNC_AUTO_UPLOAD", "0").strip() == "1"
AUTO_MIN = int(os.environ.get("SYNC_AUTO_MIN", 10))   # ab so vielen fertigen Würfen hochladen (spätestens nach 12 h)
TRAIN_DIR = os.path.join(DATA, "train")
MODEL_DIR = os.path.join(DATA, "models")
UPLOADED = os.path.join(TRAIN_DIR, "_uploaded.json")
_lock = threading.Lock()


class Remote:
    """Minimaler WebDAV-Client (nur Standardbibliothek) – oder lokaler Ordner, wenn url kein http ist."""

    def __init__(self, url=URL, user=USER, pw=PASS):
        self.url, self.local = url.rstrip("/"), not url.lower().startswith("http")
        self.auth = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode() if user else None

    def _req(self, method, path, data=None, headers=None, timeout=60):
        r = urllib.request.Request(self.url + "/" + urllib.parse.quote(path.strip("/")), data=data, method=method,
                                   headers={**({"Authorization": self.auth} if self.auth else {}), **(headers or {})})
        return urllib.request.urlopen(r, timeout=timeout)

    @classmethod
    def share(cls, link, pw=""):
        """Nextcloud-Freigabelink https://host/s/TOKEN → öffentliches WebDAV (Token als Benutzer)."""
        u = urllib.parse.urlparse(link)
        parts = u.path.rstrip("/").split("/")
        if "s" not in parts:
            raise ValueError("Freigabelink erwartet: https://…/s/TOKEN")
        i = parts.index("s")
        base = f"{u.scheme}://{u.netloc}{'/'.join(parts[:i])}/public.php/webdav"
        r = cls(base, parts[i + 1], pw)
        r.is_share = True
        return r

    is_share = False

    def _p(self, path):
        return os.path.join(self.url, *path.strip("/").split("/"))

    def mkdirs(self, path):
        if self.local:
            return os.makedirs(self._p(path), exist_ok=True)
        cur = ""
        for part in [""] + path.strip("/").split("/"):   # erst den Basisordner selbst
            cur = (cur + "/" + part) if part else ""
            try:
                self._req("MKCOL", cur)
            except urllib.error.HTTPError as e:
                if e.code not in (405, 409, 301):   # 405 = existiert schon
                    raise

    def put_file(self, path, src):
        if self.local:
            os.makedirs(os.path.dirname(self._p(path)), exist_ok=True)
            return shutil.copyfile(src, self._p(path))
        with open(src, "rb") as f:
            self._req("PUT", path, data=f, headers={"Content-Length": str(os.path.getsize(src))}, timeout=600).read()

    def put_bytes(self, path, b):
        if self.local:
            os.makedirs(os.path.dirname(self._p(path)), exist_ok=True)
            return open(self._p(path), "wb").write(b)
        self._req("PUT", path, data=b, headers={"Content-Length": str(len(b))}).read()

    def get(self, path, dst=None):
        """Datei holen → bytes, oder nach dst schreiben. None, wenn es sie nicht gibt."""
        try:
            if self.local:
                if not os.path.exists(self._p(path)):
                    return None
                if dst:
                    return shutil.copyfile(self._p(path), dst)
                return open(self._p(path), "rb").read()
            with self._req("GET", path, timeout=600) as r:
                if dst:
                    with open(dst, "wb") as f:
                        shutil.copyfileobj(r, f)
                    return dst
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def ls(self, path):
        """Dateinamen in einem Ordner (leer, wenn es ihn nicht gibt)."""
        if self.local:
            p = self._p(path)
            return sorted(os.listdir(p)) if os.path.isdir(p) else []
        try:
            with self._req("PROPFIND", path, data=b'<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>',
                           headers={"Depth": "1", "Content-Type": "application/xml"}) as r:
                root = ET.fromstring(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            raise
        names = []
        for resp in root.findall("{DAV:}response"):
            href = urllib.parse.unquote(resp.findtext("{DAV:}href", "")).rstrip("/")
            names.append(href.rsplit("/", 1)[-1])
        own = urllib.parse.unquote(self.url + "/" + path.strip("/")).rstrip("/").rsplit("/", 1)[-1]
        return sorted(n for n in names[1:] if n and n != own) if names else []


def configured():
    return bool(URL or UP_LINK or MODEL_LINK)


def up_remote():
    """Ziel fürs Hochladen: Ablage-Link (flach, nur schreiben) oder Konto-Ordner train/<Board>/."""
    if UP_LINK:
        return Remote.share(UP_LINK, UP_PASS), ""
    if URL:
        return Remote(), f"train/{SETUP}/"
    raise RuntimeError("Kein Upload-Ziel: SYNC_UPLOAD_LINK oder SYNC_URL fehlt")


def model_remote():
    if MODEL_LINK:
        return Remote.share(MODEL_LINK, MODEL_PASS), ""
    if URL:
        return Remote(), "models/"
    raise RuntimeError("Keine Modell-Quelle: SYNC_MODEL_LINK oder SYNC_URL fehlt")


# ───────────── Darts-Rechner: Trainingsdaten hochladen ─────────────

def _meta(sid):
    try:
        with open(os.path.join(TRAIN_DIR, sid, "meta.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _uploaded():
    try:
        return set(json.load(open(UPLOADED)))
    except Exception:
        return set()


def pending():
    """Fertig markierte Würfe, die noch nicht hochgeladen sind (+ ältere Pfeile im selben Bild)."""
    if not os.path.isdir(TRAIN_DIR):
        return [], 0
    done, todo = _uploaded(), 0
    ready = []
    for sid in sorted(d for d in os.listdir(TRAIN_DIR) if not d.startswith("_")):
        m = _meta(sid)
        if not m:
            continue
        if m.get("status") == "ok" and sid not in done:
            ready.append(sid)
        elif m.get("status") in ("corrected", "unknown"):
            todo += 1
    return ready, todo


def upload_training():
    """Alle neuen markierten Würfe als ZIP hochladen. Rückgabe {sent, mb}."""
    with _lock:
        ready, _ = pending()
        if not ready:
            return {"sent": 0, "mb": 0}
        need = set(ready)
        for sid in ready:   # Bild enthält ältere Pfeile → deren Labels mitschicken
            need.update((_meta(sid) or {}).get("prev", []))
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False); tmp.close()
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_STORED) as z:   # JPGs sind schon komprimiert
            for sid in sorted(need):
                d = os.path.join(TRAIN_DIR, sid)
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        z.write(os.path.join(d, f), f"{sid}/{f}")
        mb = os.path.getsize(tmp.name) / 1e6
        r, pre = up_remote()
        name = f"batch_{time.strftime('%Y%m%d-%H%M%S')}.zip"
        if pre:
            r.mkdirs(pre)
        else:
            name = f"{SETUP}__{name}"   # Ablage ist flach → Board-Name in den Dateinamen
        r.put_file(pre + name, tmp.name)
        os.remove(tmp.name)
        json.dump(sorted(_uploaded() | set(ready)), open(UPLOADED, "w"))
        global LAST_UPLOAD
        LAST_UPLOAD = time.time()
        return {"sent": len(ready), "mb": round(mb, 1)}


LAST_UPLOAD = 0.0


def auto_upload_due():
    """Automatik: genug fertige Würfe oder lange nichts hochgeladen."""
    if not (AUTO_UPLOAD and (UP_LINK or URL)):
        return False
    n = len(pending()[0])
    return n >= AUTO_MIN or (n > 0 and time.time() - LAST_UPLOAD > 12 * 3600)


# ───────────── Darts-Rechner: Modell holen ─────────────

def local_model():
    try:
        return json.load(open(os.path.join(MODEL_DIR, "model.json")))
    except Exception:
        return {"version": "lokal" if os.path.exists(os.path.join(MODEL_DIR, "tips.onnx")) else None}


def remote_model():
    r, pre = model_remote()
    b = r.get(pre + "latest.json")
    return json.loads(b) if b else None


def install_model():
    """Neues Modell laden, prüfen, altes als tips.prev.onnx behalten."""
    from . import tipnet
    with _lock:
        info = remote_model()
        if not info:
            raise RuntimeError("Kein Modell veröffentlicht")
        os.makedirs(MODEL_DIR, exist_ok=True)
        tmp = os.path.join(MODEL_DIR, "tips.new.onnx")
        r, pre = model_remote()
        if not r.get(pre + "tips.onnx", tmp):
            raise RuntimeError("models/tips.onnx fehlt")
        tipnet.TipNet(tmp)   # lässt sich laden? sonst Fehler, altes bleibt
        cur, prev = os.path.join(MODEL_DIR, "tips.onnx"), os.path.join(MODEL_DIR, "tips.prev.onnx")
        if os.path.exists(cur):
            shutil.copyfile(cur, prev)
            if os.path.exists(os.path.join(MODEL_DIR, "model.json")):
                shutil.copyfile(os.path.join(MODEL_DIR, "model.json"), os.path.join(MODEL_DIR, "model.prev.json"))
        os.replace(tmp, cur)
        json.dump(info, open(os.path.join(MODEL_DIR, "model.json"), "w"))
        tipnet.reload()
        return info


def rollback_model():
    from . import tipnet
    cur, prev = os.path.join(MODEL_DIR, "tips.onnx"), os.path.join(MODEL_DIR, "tips.prev.onnx")
    if not os.path.exists(prev):
        raise RuntimeError("Kein vorheriges Modell vorhanden")
    os.replace(prev, cur)
    pj = os.path.join(MODEL_DIR, "model.prev.json")
    if os.path.exists(pj):
        os.replace(pj, os.path.join(MODEL_DIR, "model.json"))
    tipnet.reload()
    return local_model()


def status():
    ready, todo = pending()
    st = {"configured": configured(), "setup": SETUP, "ready": len(ready), "todo": todo,
          "uploaded": len(_uploaded()), "model": local_model(), "auto": AUTO_MODEL, "auto_upload": AUTO_UPLOAD,
          "mode": "Ablage-Link" if UP_LINK else ("Konto" if URL else None),
          "can_rollback": os.path.exists(os.path.join(MODEL_DIR, "tips.prev.onnx"))}
    return st


def auto_update(log=print):
    """Beim Start: neueres Modell automatisch holen (nur mit SYNC_AUTO_MODEL=1)."""
    if not (configured() and AUTO_MODEL):
        return
    try:
        rm, lm = remote_model(), local_model()
        if rm and rm.get("version") != lm.get("version"):
            install_model()
            log(f"Neues Pfeil-Modell installiert: {rm.get('version')}")
    except Exception as e:
        log(f"Modell-Update fehlgeschlagen: {e}")
