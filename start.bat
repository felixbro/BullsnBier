@echo off
REM DartCam LIVE mit Kameras
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo [DartCam] Erstelle Python-Umgebung ...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if not exist .venv\Scripts\python.exe (
    echo Python 3.10+ nicht gefunden. Installieren: https://www.python.org/downloads/  ^(Haken "Add to PATH"^)
    pause & exit /b 1
  )
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
if not exist config.env copy config.env.example config.env >nul

start "" http://localhost:8090
.venv\Scripts\python run.py
pause
