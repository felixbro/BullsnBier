#!/usr/bin/env bash
# Trainingsmodus mit Autodarts einrichten: virtuelle Kameras + Recht, den Autodarts-Dienst zu starten/stoppen.
#   bash tools/autodarts-setup.sh
set -e
U="${SUDO_USER:-$USER}"
N="${CAMS:-3}"
NR=$(seq -s, 10 $((9 + N)))
LBL=$(for i in $(seq 1 "$N"); do printf "BnB Cam %s," "$i"; done); LBL="${LBL%,}"

echo "== Pakete"
if command -v apt-get >/dev/null; then sudo apt-get install -y v4l2loopback-dkms v4l2loopback-utils ffmpeg v4l-utils
elif command -v dnf >/dev/null; then sudo dnf install -y v4l2loopback ffmpeg v4l-utils || echo "   Fedora: v4l2loopback kommt aus RPM Fusion"
fi

echo "== Virtuelle Kameras /dev/video${NR//,/, /dev/video}"
echo "v4l2loopback" | sudo tee /etc/modules-load.d/bnb-loopback.conf >/dev/null
echo "options v4l2loopback devices=$N video_nr=$NR card_label=\"$LBL\" exclusive_caps=1" | sudo tee /etc/modprobe.d/bnb-loopback.conf >/dev/null
sudo modprobe -r v4l2loopback 2>/dev/null || true
sudo modprobe v4l2loopback || { echo "!! Modul lädt nicht – bei Secure Boot: im BIOS ausschalten oder den DKMS-Schlüssel (MOK) registrieren"; exit 1; }
v4l2-ctl --list-devices | grep -A1 "BnB Cam" || true

echo "== Autodarts-Dienst darf von Bulls'n'Bier gestartet/gestoppt werden"
SC=$(command -v systemctl)
echo "$U ALL=(root) NOPASSWD: $SC start autodarts, $SC stop autodarts" | sudo tee /etc/sudoers.d/bnb-autodarts >/dev/null
sudo chmod 440 /etc/sudoers.d/bnb-autodarts
sudo visudo -cf /etc/sudoers.d/bnb-autodarts
sudo systemctl disable autodarts 2>/dev/null || true   # startet nur noch mit dem Trainingsmodus

echo "Fertig. Weiter: Bulls'n'Bier → Kameras › Trainingsdaten → Trainingsmodus an → in Autodarts (http://localhost:3180) die Kameras „BnB Cam 1–$N“ wählen und kalibrieren."
