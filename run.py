#!/usr/bin/env python3
"""Bulls'n'Bier (DartCam) starten.

  python run.py              # Live (Kameras laut config.env)
  python run.py --sim        # Simulator ohne Kameras
  python run.py --list-cameras
"""
import argparse, os, socket, sys

if sys.stdout is None or sys.stderr is None:  # pythonw (Autostart ohne Konsole) -> Logdatei
    _log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dartcam.log"), "a", buffering=1, encoding="utf-8")
    sys.stdout = sys.stdout or _log
    sys.stderr = sys.stderr or _log

p = argparse.ArgumentParser(description="Bulls'n'Bier")
p.add_argument("--sim", action="store_true", help="Simulator-Modus ohne Kameras")
p.add_argument("--host", default=None, help="Bind-Adresse (Standard 0.0.0.0)")
p.add_argument("--port", type=int, default=None, help="Port (Standard 8090)")
p.add_argument("--cameras", default=None, help="Kommagetrennt, z. B. /dev/video0,/dev/video2,/dev/video4")
p.add_argument("--list-cameras", action="store_true", help="Angeschlossene Kameras auflisten und beenden")
p.add_argument("--get-voice", nargs="*", metavar="STIMME", help="Piper-Stimme(n) laden, Standard: de_DE-thorsten-high en_GB-alan-medium")
p.add_argument("--data", default=None, help="Datenordner (Standard ./data)")
a = p.parse_args()

if a.sim:
    os.environ["SIM"] = "1"
if a.cameras:
    os.environ["CAMERAS"] = a.cameras
if a.data:
    os.environ["DATA_DIR"] = os.path.abspath(a.data)

from app import config  # noqa: E402  (lädt config.env)

if a.get_voice is not None:
    from app import tts
    for v in a.get_voice or ["de_DE-thorsten-high", "en_GB-alan-medium"]:
        print(f"Lade {v} …", flush=True)
        try:
            tts.download(v)
            print("  ok")
        except Exception as ex:
            print(f"  Fehler: {ex}")
    raise SystemExit(0)

if a.list_cameras:
    from app.vision import list_cameras
    cams = list_cameras()
    print("\nGefundene Kameras:" if cams else "\nKeine Kamera gefunden.")
    for c in cams:
        print(f"  {c['src']}   ({c['w']}x{c['h']})")
    if cams:
        print("\nIn config.env eintragen, z. B.:\n  CAMERAS=" + ",".join(c["src"] for c in cams[:3]))
    raise SystemExit(0)
import uvicorn  # noqa: E402

host = a.host or os.environ.get("HOST", "0.0.0.0")
port = a.port or int(os.environ.get("PORT", 8090))

try:
    ip = socket.gethostbyname(socket.gethostname())
except Exception:
    ip = "localhost"
print(f"\n  Bulls'n'Bier {'SIMULATOR' if config.SIM else 'LIVE'}  →  http://localhost:{port}   (im LAN: http://{ip}:{port})\n")
uvicorn.run("app.main:app", host=host, port=port, log_level="warning")
