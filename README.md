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

Sprachausgabe: **Piper** (natürliche Offline-Stimmen, läuft auf dem DartCam-Rechner, Linux + Windows). Fallback: Systemstimme des Browsers.

## Linux

```bash
git clone https://github.com/felixbro/DartCam.git && cd DartCam
./install.sh                 # venv, Stimmen, systemd-Dienst, Autodarts-Dienst aus
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
install-windows.bat          :: venv + Stimmen + Kamera-Liste
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

## Spiele

X01 · Cricket (Standard / Cut Throat / No Score, Tactics) · Bermuda · Shanghai · Gotcha · Around the Clock · Round the World · Count Up · Random Checkout · Segment Training
– Legs + Sets, Max. Runden, Bull 25/50 oder 50/50, Start: Reihenfolge / Zufällig / Bull-Off

## Einstellungen

| Bereich | |
|---|---|
| Anzeige | Vorwürfe ausblenden, Spielerfarben, Animationen je Ereignis |
| Sprachausgabe | DE/EN, Piper- oder Systemstimme, Tempo/Lautstärke, jede Ansage an/aus |
| Ansagetexte | alle Texte editierbar: `{name}` `{score}` `{points}` `{n}` `{dart}` `{target}` |
| WLED | IP(s), je Ereignis Effekt/Preset, Farben (auch Spielerfarbe), Tempo, Dauer, Test |

```bash
python run.py --get-voice                       # Standard-Stimmen laden
python run.py --get-voice de_DE-kerstin-low     # weitere Stimme
```

## WLED-Ereignisse

Leerlauf · Spielstart · Bull-Off · Nächster Spieler · Finish-Bereich · Pfeile ziehen · Single/Double/Triple/Bull/Miss · 100+/140+/180 · unter 20 · Überworfen · Halbiert · Gotcha · Shanghai · Finish 100+ · Leg · Winner · Nicht erkannt · Kalibrierung ungenau · Kamera fehlt · Pausiert

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
| `CAL_WARN_MM` | 20 | Abweichung zwischen Kameras → Warnung „Kalibrierung ungenau“ |

Simulator-Daten liegen getrennt in `data-sim/`, Live-Daten in `data/`, Stimmen in `voices/`.
