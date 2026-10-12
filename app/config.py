"""Zentrale Konfiguration aus Umgebungsvariablen / config.env."""
import os

import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Programmcode
FROZEN = getattr(sys, "frozen", False)                               # als .exe / Linux-Binary gebaut


def _user_root():
    """Beschreibbarer Ordner für Daten, Stimmen und config.env – im Repo, oder bei der fertigen App im Benutzerprofil."""
    if not FROZEN:
        return ROOT
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "BullsnBier")
    return os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"), "bullsnbier")


USER_ROOT = _user_root()
os.makedirs(USER_ROOT, exist_ok=True)


def _load_env_file(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file(os.path.join(USER_ROOT, "config.env"))

SIM = os.environ.get("SIM", "0") == "1"
DATA = os.environ.setdefault("DATA_DIR", os.path.join(USER_ROOT, "data-sim" if SIM and FROZEN else "data"))
os.makedirs(DATA, exist_ok=True)
_DEFAULT_CAMS = "0,1,2" if sys.platform.startswith("win") else "/dev/video0,/dev/video2,/dev/video4"
CAMERAS = [c.strip() for c in os.environ.get("CAMERAS", _DEFAULT_CAMS).split(",") if c.strip()]
