@echo off
REM DartCam bei Windows-Anmeldung automatisch starten (live). Entfernen: schtasks /delete /tn DartCam /f
cd /d "%~dp0"
schtasks /create /tn DartCam /sc onlogon /rl limited /f /tr "\"%~dp0.venv\Scripts\pythonw.exe\" \"%~dp0run.py\""
echo Autostart eingerichtet.
pause
