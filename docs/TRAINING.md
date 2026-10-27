# Pfeil-Netz trainieren & verbessern

```
Darts-Rechner ── Hochladen ──▶ Nextcloud ◀── Herunterladen ── Trainings-Rechner
      ▲                       BullsnBier-Sync                       │ Trainieren
      └──── Modell installieren ◀──── models/tips.onnx ◀── Veröffentlichen
```

## Nextcloud vorbereiten (einmal)

1. Nextcloud → Ordner `BullsnBier-Sync` anlegen.
2. Einstellungen › Sicherheit › **App-Passwort erstellen** (z. B. „BullsnBier“).
3. WebDAV-Adresse: Nextcloud › Dateien › Einstellungen (unten links), dann `/BullsnBier-Sync` anhängen:
   `https://cloud.example.de/remote.php/dav/files/BENUTZER/BullsnBier-Sync`

## Darts-Rechner (`config.env`)

**Empfohlen – Freigabelinks (Board sieht nichts, kann nur hochladen bzw. Modell lesen):**

Nextcloud: `BullsnBier-Sync/train` → Teilen › Link › **Dateiablage (nur Hochladen)** + Passwort ·
`BullsnBier-Sync/models` → Teilen › Link › **Nur lesen** + Passwort

```ini
SYNC_UPLOAD_LINK=https://cloud.example.de/s/AbCdEf
SYNC_UPLOAD_PASS=geheim1
SYNC_MODEL_LINK=https://cloud.example.de/s/GhIjKl
SYNC_MODEL_PASS=geheim2
SETUP_NAME=Buschi
SYNC_AUTO_UPLOAD=1         # markierte Würfe selbst hochladen (ab 10 Stück oder alle 12 h, nie während eines Spiels)
SYNC_AUTO_MODEL=0          # 1 = neues Modell beim Start automatisch installieren
```

Alternativ Konto-Zugang (sieht alles): `SYNC_URL` / `SYNC_USER` / `SYNC_PASS` (App-Passwort).

```bash
sudo systemctl restart dartcam
```

Im Browser: **Kameras › Trainingsdaten**
- Würfe markieren (korrigierte/unerkannte zuerst) → **Hochladen** (oder automatisch)
- **Neues Modell installieren** · **Altes Modell** (zurück)

## Trainings-Rechner (Windows)

Einmal einrichten:

```powershell
cd $HOME\Desktop\BullsnBier
git pull
.\.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
.\.venv\Scripts\pip install ultralytics onnx onnxslim
```

Start: **`BnB-Trainer.bat`** doppelklicken → WebDAV-Adresse von `BullsnBier-Sync` (Konto, nur hier!), Benutzer, App-Passwort, Render-Ordner eintragen.

| Knopf | macht |
|---|---|
| 1 · Herunterladen | neue Würfe aus der Cloud → `tipdata_real\<Board>\` |
| 2 · Trainieren | Renders + echte Würfe (×3 gewichtet), baut auf dem letzten Modell auf → `data\models\tips.onnx` |
| 3 · Veröffentlichen | zeigt alt/neu-Genauigkeit, lädt Modell hoch (alte Version → `models/archiv/`) |

Ohne Oberfläche:

```powershell
.\.venv\Scripts\python tools\train_tips.py --render C:\BnB_Render --app tipdata_real\Buschi --model tipdata\history\best_….pt --epochs 30
.\.venv\Scripts\python tools\train_tips.py --resume      # nach Strg+C
.\.venv\Scripts\python tools\train_tips.py --export      # nur ONNX erzeugen
```

## Trainingsmodus mit Autodarts (Linux)

Bulls'n'Bier gibt die Kameras an Autodarts weiter und vergleicht jeden Wurf. Einig → Trainingsbild automatisch markiert. Uneinig → Kameras › Trainingsdaten: **Autodarts stimmt** / **BnB stimmt** / selbst anklicken.

```bash
cd ~/BullsnBier && git pull
bash tools/autodarts-setup.sh          # virtuelle Kameras /dev/video10-12, Recht für Autodarts-Dienst
sudo systemctl restart dartcam
```

1. Kameras › Trainingsdaten › **Trainingsmodus** an
2. `http://localhost:3180` → Kameras **BnB Cam 1–3** wählen → in Autodarts kalibrieren (einmalig)
3. Spielen. Nach ~12 einigen Würfen ist die Umrechnung gelernt (Anzeige „gelernt ± x mm“).

Prüfen:
```bash
curl -s http://localhost:3180/api/state | python3 -m json.tool
journalctl -u dartcam -f | grep -i "autodarts\|proxy"
```

Optionen in `config.env`: `AD_URL`, `AD_PROXY_DEVS`, `AD_AGREE_MM=4`, `AD_TRUST_SOLO=0`, `AD_MANAGE=1`.

## Markieren am Handy

`http://<darts-pc>:8090/mark` (oder Fernbedienung → **Pfeile markieren**)

- Tippen = Kreuz springt · Ziehen = Kreuz bewegt sich langsam (Fein/Mittel/Grob), Lupe zeigt 5× vergrößert
- Zuerst kommen nur Würfe zum Prüfen (Autodarts uneinig, nicht erkannt, korrigiert) · Haken „auch automatisch erkannte“ für alle

## C4D-Szene aus den Kamerabildern (Kameras + Board-Textur)

```bash
python tools/c4d_scene.py bullsnbier-snapshot.zip          # Snapshot aus der App (Kameras › Snapshot)
python tools/c4d_scene.py ordner --init klicks.json        # nur Bilder: Startpunkte von Hand
```
→ `c4d_szene/c4d_bullsnbier_szene.py` (Textur eingebettet) · `board_textur.jpg` · `calibration.json` · `kontrolle.jpg`
