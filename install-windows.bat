@echo off
REM Bulls'n'Bier unter Windows einrichten (kann jederzeit erneut ausgefuehrt werden)
cd /d "%~dp0"

REM Passende Python-Version suchen: 3.12 bevorzugt (alle Pakete verfuegbar), sonst 3.13/3.11/3.10
set PY=
for %%V in (3.12 3.13 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys; assert sys.maxsize > 2**32" >nul 2>&1 && set PY=py -%%V )
)
if not defined PY ( python -c "import sys; assert sys.version_info[:2] >= (3,10) and sys.maxsize > 2**32" >nul 2>&1 && set PY=python )
if not defined PY (
  echo.
  echo Kein passendes Python gefunden. Bitte Python 3.12 ^(64-bit^) installieren:
  echo   https://www.python.org/downloads/windows/  ^(Haken "Add python.exe to PATH"^)
  pause & exit /b 1
)
echo [Bulls'n'Bier] Nutze: %PY%

REM Alte/kaputte Umgebung mit falscher Python-Version entfernen
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python -c "import sys; assert sys.version_info[:2] in [(3,10),(3,11),(3,12),(3,13)]" >nul 2>&1 || rmdir /s /q .venv
)
if not exist .venv\Scripts\python.exe (
  echo [Bulls'n'Bier] Erstelle Python-Umgebung ...
  %PY% -m venv .venv || (pause & exit /b 1)
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt || (echo. & echo Installation fehlgeschlagen. & pause & exit /b 1)

echo [Bulls'n'Bier] Natuerliche Stimme (Piper) ...
.venv\Scripts\python -m pip install -r requirements-voice.txt && (
  .venv\Scripts\python run.py --get-voice
) || (
  echo   Piper nicht verfuegbar fuer diese Python-Version - Ansagen laufen ueber die Systemstimme.
)

if not exist config.env copy config.env.example config.env >nul
echo.
.venv\Scripts\python run.py --list-cameras
echo.
echo Fertig. Kamera-Nummern ggf. in config.env eintragen (CAMERAS=0,1,2).
echo Start: start.bat (Kameras)  oder  start-sim.bat (Simulator)
pause
