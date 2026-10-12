"""Zentrale Konfiguration aus Umgebungsvariablen / config.env."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


_load_env_file(os.path.join(ROOT, "config.env"))

DATA = os.environ.setdefault("DATA_DIR", os.path.join(ROOT, "data"))
os.makedirs(DATA, exist_ok=True)
SIM = os.environ.get("SIM", "0") == "1"
import sys
_DEFAULT_CAMS = "0,1,2" if sys.platform.startswith("win") else "/dev/video0,/dev/video2,/dev/video4"
CAMERAS = [c.strip() for c in os.environ.get("CAMERAS", _DEFAULT_CAMS).split(",") if c.strip()]
