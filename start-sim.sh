#!/usr/bin/env bash
# DartCam SIMULATOR (Linux) – aufs Board klicken = Wurf
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt || exit 1
fi
[ -f config.env ] || cp config.env.example config.env
.venv/bin/python run.py --sim --data data-sim "$@"
