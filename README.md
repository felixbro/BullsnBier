# DartCam

Kamerabasierte Dart-Erkennung (Autodarts-Nachbau) – läuft unter **Linux und Windows**, jeweils live mit Kameras oder als **Simulator** zum Testen.

## Systemanforderungen

| | Minimum | Empfohlen |
|---|---|---|
| Python | 3.10 | 3.12 |
| CPU (live, 3 Kameras 720p) | 4 Kerne, z. B. Raspberry Pi 5 | x86 Mini-PC, Intel N100 oder besser |
| RAM | 2 GB | 4 GB |
| Kameras | 3× USB-UVC mit **MJPG** | Autodarts-Kameras, je an eigenem USB-Port |
| Licht | – | LED-Ring, konstantes Licht |
| Simulator | jeder PC mit Python 3.10+ und Browser | |

Sprachausgabe läuft im Browser: Windows, Android und iOS haben deutsche Stimmen. Unter Linux braucht der Browser `speech-dispatcher` + `espeak-ng` (klingt robotisch) – besser Tablet/Handy als Anzeige.

## Linux

```bash
git clone https://github.com/felixbro/DartCam.git && cd DartCam
./install.sh                 # venv, systemd-Dienst, Autodarts-Dienst aus
nano config.env              # CAMERAS=… (python run.py --list-cameras)
sudo systemctl restart dartcam
```

```bash
./start-sim.sh               # Simulator
./start.sh                   # live im Vordergrund (ohne Dienst)
journalctl -u dartcam -f     # Log
```

## Windows

```bat
git clone https://github.com/felixbro/DartCam.git
cd DartCam
install-windows.bat          :: venv + Kamera-Liste
start-sim.bat                :: Simulator
start.bat                    :: live mit Kameras (CAMERAS=0,1,2 in config.env)
autostart-windows.bat        :: optional: Start bei Anmeldung
```

Python von python.org mit Haken „Add to PATH“. Zugriff von Handy/Tablet: Windows-Firewall für Port 8090 freigeben.

## Bedienung

→ `http://<rechner>:8090`

1. **Kameras** → je Kamera Punkte 20/6/3/11 auf die Außenkante des Double-Rings setzen → Speichern
2. Board leer → **Referenz neu**
3. **Statistik** → Spieler anlegen (optional Aussprache) → **Neu** → Game on

| Aktion | |
|---|---|
| Simulator-Wurf | aufs Board klicken |
| Korrektur | Dart oben antippen → aufs Board tippen |
| Pfeile gezogen | `Enter` |
| Rückgängig | `Backspace` |

**Einstellungen:** Sprache DE/EN, Stimme pro Gerät, Tempo/Tonhöhe/Lautstärke, jede Ansage einzeln an/aus, Restpunkte (nie/Finish/immer), alle Texte editierbar mit `{name}` `{score}` `{points}` `{n}` `{dart}`.

## config.env

| Variable | Standard | |
|---|---|---|
| `CAMERAS` | Win `0,1,2` · Linux `/dev/video0,2,4` | Kameraquellen |
| `CAM_W` / `CAM_H` | 1280 / 720 | Auflösung |
| `PORT` | 8090 | |
| `DIFF_THR` | 28 | Helligkeitsschwelle |
| `DART_MIN` / `DART_MAX` | 250 / 40000 | Fläche Pfeil / ab hier Hand |
| `STABLE_FRAMES` | 6 | Ruhe-Frames bis Auswertung |
| `FUSE_MM` | 12 | Ausreißer zwischen Kameras |

Simulator-Daten liegen getrennt in `data-sim/`, Live-Daten in `data/`.
