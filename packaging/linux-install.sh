#!/usr/bin/env bash
# Bulls'n'Bier (fertiges Paket) für den aktuellen Benutzer einrichten: Startmenü-Einträge + optional Autostart-Dienst.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
APPS="$HOME/.local/share/applications"; mkdir -p "$APPS"
cp "$DIR/icon.png" "$HOME/.local/share/bullsnbier-icon.png" 2>/dev/null || true
for mode in live sim; do
  [ $mode = sim ] && N="Bulls'n'Bier Simulator" A="--sim --open" || { N="Bulls'n'Bier"; A="--open"; }
  cat > "$APPS/bullsnbier-$mode.desktop" <<D
[Desktop Entry]
Type=Application
Name=$N
Exec="$DIR/BullsnBier" $A
Icon=$HOME/.local/share/bullsnbier-icon.png
Terminal=true
Categories=Game;
D
done
echo "Startmenü-Einträge angelegt."
if [ "$1" = "--service" ]; then
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/bullsnbier.service" <<S
[Unit]
Description=Bulls'n'Bier
After=network-online.target
[Service]
ExecStart=$DIR/BullsnBier
Restart=always
[Install]
WantedBy=default.target
S
  systemctl --user daemon-reload && systemctl --user enable --now bullsnbier
  loginctl enable-linger "$USER" 2>/dev/null || true
  echo "Dienst läuft: http://localhost:8090"
fi
