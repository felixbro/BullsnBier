#!/usr/bin/env bash
# DartCam LIVE im Vordergrund (ohne Dienst) – z. B. zum Testen
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt || exit 1
  .venv/bin/python run.py --get-voice
fi
[ -f config.env ] || cp config.env.example config.env
.venv/bin/python run.py "$@"
