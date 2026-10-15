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

```ini
SYNC_URL=https://cloud.example.de/remote.php/dav/files/BENUTZER/BullsnBier-Sync
SYNC_USER=BENUTZER
SYNC_PASS=xxxxx-xxxxx-xxxxx-xxxxx-xxxxx
SETUP_NAME=Buschi
SYNC_AUTO_MODEL=0          # 1 = neues Modell beim Start automatisch installieren
```

```bash
sudo systemctl restart dartcam
```

Im Browser: **Kameras › Trainingsdaten**
- Würfe markieren (korrigierte/unerkannte zuerst) → **Hochladen**
- **Neues Modell installieren** · **Altes Modell** (zurück)

## Trainings-Rechner (Windows)

Einmal einrichten:

```powershell
cd $HOME\Desktop\BullsnBier
git pull
.\.venv\Scripts\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
.\.venv\Scripts\pip install ultralytics onnx onnxslim
```

Start: **`BnB-Trainer.bat`** doppelklicken → Cloud-Adresse, Benutzer, App-Passwort, Render-Ordner eintragen.

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
