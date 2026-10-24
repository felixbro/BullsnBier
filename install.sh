#!/usr/bin/env bash
# Bulls'n'Bier unter Linux installieren – Debian/Ubuntu/Raspberry Pi OS (apt), Fedora/RHEL (dnf), Arch (pacman)
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
USER_NAME="${SUDO_USER:-$USER}"

echo "== Pakete"
if command -v apt-get >/dev/null; then
  sudo apt-get update || echo "Hinweis: 'apt-get update' meldet Fehler (z. B. fremdes Paketdepot wie Spotify) – mache trotzdem weiter."
  sudo apt-get install -y python3 python3-venv python3-pip v4l-utils libgl1 libglib2.0-0
elif command -v dnf >/dev/null; then
  sudo dnf install -y python3 python3-pip v4l-utils mesa-libGL glib2 git
elif command -v pacman >/dev/null; then
  sudo pacman -Sy --needed --noconfirm python python-pip v4l-utils mesa glib2 git
else
  echo "Paketverwaltung nicht erkannt – Python 3.10+, v4l-utils und libGL bitte selbst installieren."
fi

echo "== Python-Umgebung"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-voice.txt || echo "Piper nicht verfügbar – Systemstimme wird genutzt"

[ -f config.env ] || cp config.env.example config.env
echo "== Natürliche Stimmen (Piper)"
.venv/bin/python run.py --get-voice || true
sudo usermod -aG video "$USER_NAME"

echo "== Alte Autodarts-Dienste stoppen (falls vorhanden)"
for s in autodarts autodartsupdater; do
  if systemctl list-unit-files | grep -q "^$s.service"; then
    sudo systemctl disable --now "$s" || true
    echo "   $s deaktiviert"
  fi
done

PORT_NR="$(grep -E '^PORT=' config.env | cut -d= -f2)"; PORT_NR="${PORT_NR:-8090}"
if command -v firewall-cmd >/dev/null && sudo firewall-cmd --state >/dev/null 2>&1; then
  echo "== Firewall: Port $PORT_NR öffnen"
  sudo firewall-cmd --permanent --add-port="$PORT_NR/tcp" && sudo firewall-cmd --reload
fi

# SELinux (Fedora): ein System-Dienst darf Programme im Home-Ordner nicht starten → Benutzer-Dienst nehmen
if command -v getenforce >/dev/null && [ "$(getenforce)" = "Enforcing" ]; then
  echo "== Benutzer-Dienst dartcam (SELinux aktiv)"
  sudo loginctl enable-linger "$USER_NAME"    # läuft auch ohne Anmeldung, startet beim Hochfahren
  UNIT_DIR="/home/$USER_NAME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/dartcam.service" <<UNIT
[Unit]
Description=Bulls n Bier (DartCam)
After=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
UNIT
  systemctl --user daemon-reload
  systemctl --user enable --now dartcam
  CTL="systemctl --user"; LOG="journalctl --user -u dartcam -f"
else
  echo "== systemd-Dienst"
  sudo tee /etc/systemd/system/dartcam.service >/dev/null <<UNIT
[Unit]
Description=Bulls n Bier (DartCam)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/run.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
  sudo systemctl daemon-reload
  sudo systemctl enable --now dartcam
  CTL="sudo systemctl"; LOG="journalctl -u dartcam -f"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')}"
echo
echo "Kameras:"; $CTL stop dartcam; .venv/bin/python run.py --list-cameras || true; $CTL start dartcam
echo
echo "Fertig → http://${IP:-localhost}:$PORT_NR"
echo "Kamera-Pfade ggf. in config.env anpassen, dann: $CTL restart dartcam   ·  Log: $LOG"
