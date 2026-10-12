# Bulls’n’Bier unter Linux installieren

Getestet für Debian/Ubuntu, Raspberry Pi OS und den Autodarts-Mini-PC. Zwei Wege:

| | Weg A: fertiges Paket | Weg B: aus dem Quellcode |
|---|---|---|
| Voraussetzung | nichts (kein Python nötig) | Python 3.10+ |
| Rechner | x86-64 (Intel/AMD) | x86-64 **und** ARM (Raspberry Pi) |
| Updates | neues Paket laden | `git pull` |
| Empfohlen für | schnell ausprobieren, Simulator | Dauerbetrieb am Board |

---

## Weg A – fertiges Paket

```bash
cd ~
wget https://github.com/felixbro/BullsnBier/releases/latest/download/BullsnBier-linux-x64.tar.gz
tar xzf BullsnBier-linux-x64.tar.gz
cd BullsnBier
./BullsnBier --sim --open          # Simulator, Browser öffnet sich
```

Einrichten (Startmenü-Einträge, Stimme, Kamera-Zugriff):

```bash
./install.sh                       # Startmenü: „Bulls'n'Bier“ und „Bulls'n'Bier Simulator“
./BullsnBier --get-voice           # natürliche Stimmen laden (ca. 110 MB)
sudo usermod -aG video $USER       # Kamera-Zugriff, danach einmal ab- und anmelden
```

Live mit Kameras und Autostart als Dienst:

```bash
./BullsnBier --list-cameras        # zeigt z. B. CAMERAS=/dev/v4l/by-path/…
nano ~/.local/share/bullsnbier/config.env    # CAMERAS=… eintragen (Vorlage: config.env.example)
./install.sh --service             # startet bei jedem Hochfahren, Port 8090
```

Daten, Stimmen und `config.env` liegen in `~/.local/share/bullsnbier/`.

---

## Weg B – aus dem Quellcode (empfohlen am Board)

```bash
sudo apt install -y git
git clone https://github.com/felixbro/BullsnBier.git
cd BullsnBier
./install.sh
```

`install.sh` erledigt:
- Pakete (Python, v4l-utils) und eine eigene Python-Umgebung `.venv`
- natürliche Stimmen (Piper)
- Kamera-Zugriff (Gruppe `video`)
- **alte Autodarts-Dienste stoppen**, damit die Kameras frei sind
- systemd-Dienst `dartcam` (startet automatisch)

Danach Kameras eintragen:

```bash
.venv/bin/python run.py --list-cameras
nano config.env                    # CAMERAS=/dev/video0,/dev/video2,/dev/video4
sudo systemctl restart dartcam
```

Aufrufen: `http://<IP-des-Rechners>:8090` – am Handy öffnet sich automatisch die Fernbedienung.

Ohne Dienst bzw. zum Testen:

```bash
./start-sim.sh                     # Simulator (eigene Daten in data-sim/)
./start.sh                         # live im Vordergrund
```

---

## Kameras kalibrieren

1. Im Browser **Kameras** öffnen – alle drei Bilder müssen live laufen.
2. Je Kamera die 4 Punkte auf der **Außenkante des Doppelrings** anklicken: **20 → 6 → 3 → 11**.
3. Testwurf: In **Live** muss das richtige Feld erscheinen.
4. Meldung „Kalibrierung ungenau“ = Kameras sehen den Pfeil an unterschiedlichen Stellen → Punkte der betroffenen Kamera neu setzen.

Tipps: konstantes Licht (LED-Ring), Kameras fest montiert, jede Kamera an einem eigenen USB-Port, 1280×720 mit MJPG (Standard).

---

## Bedienung im Alltag

| Was | Befehl |
|---|---|
| Status | `systemctl status dartcam` |
| Log live | `journalctl -u dartcam -f` |
| Neu starten | `sudo systemctl restart dartcam` |
| Stoppen | `sudo systemctl stop dartcam` |
| Update | `cd ~/BullsnBier && git pull && sudo systemctl restart dartcam` |
| Backup | Ordner `data/` sichern (Spieler, Statistik, Einstellungen) |

Weg A: `systemctl --user status bullsnbier`, `journalctl --user -u bullsnbier -f`.

---

## Wichtige Einstellungen (`config.env`)

```ini
CAMERAS=/dev/video0,/dev/video2,/dev/video4   # oder rtsp://… / http://…
CAM_W=1280
CAM_H=720
PORT=8090
ACCESS_KEY=                 # gesetzt = Zugang nur mit /?key=…
```

---

## Probleme

| Problem | Lösung |
|---|---|
| Kamera schwarz / „Kamera fehlt“ | `v4l2-ctl --list-devices`; Autodarts-Dienst aus? (`systemctl status autodarts`); Gruppe `video` (neu anmelden) |
| Nur 1–2 Kameras laufen | USB-Bandbreite: Kameras auf verschiedene Ports, kein passiver Hub |
| Keine Ansage | einmal in den Browser tippen (Autoplay-Sperre); Stimme laden: `run.py --get-voice` |
| Handy erreicht nichts | gleiche WLAN/LAN? Firewall: `sudo ufw allow 8090/tcp` |
| Port belegt | `PORT=8091` in `config.env` |

## Entfernen

```bash
sudo systemctl disable --now dartcam
sudo rm /etc/systemd/system/dartcam.service
rm -rf ~/BullsnBier                 # inkl. Daten!
```
