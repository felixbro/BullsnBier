#!/usr/bin/env bash
# DartCam-Installation unter Linux (Debian/Ubuntu/Raspberry Pi OS)
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
USER_NAME="${SUDO_USER:-$USER}"

echo "== Pakete"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip v4l-utils libgl1 libglib2.0-0

echo "== Python-Umgebung"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

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

echo
echo "Kameras:"; .venv/bin/python run.py --list-cameras || true
echo
echo "Fertig → http://$(hostname -I | awk '{print $1}'):$(grep -E '^PORT=' config.env | cut -d= -f2 || echo 8090)"
echo "Kamera-Pfade ggf. in config.env anpassen, dann: sudo systemctl restart dartcam"
