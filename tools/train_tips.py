"""Pfeilspitzen-Erkennung trainieren (YOLO, „Spitze als kleines Objekt“ wie DeepDarts).

Einrichten (einmalig, Windows, NVIDIA):
  .venv\\Scripts\\pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
  .venv\\Scripts\\pip install ultralytics onnx onnxslim

Training:
  .venv\\Scripts\\python tools\\train_tips.py --render "C:\\...\\BnB_Render" [--app data\\train] [--epochs 80]
Nur prüfen (Labels einzeichnen, kein Training):
  .venv\\Scripts\\python tools\\train_tips.py --render "C:\\...\\BnB_Render" --check

Ergebnis: data/models/tips.onnx  (die App lädt es später automatisch)
"""
import argparse, json, os, random, shutil, sys

import cv2

BOX = 0.022     # Kantenlänge der Box um die Spitze, relativ zur Bildbreite (~28 px bei 1280)
VAL = 0.1       # Anteil Validierung (nach Frames getrennt, nicht nach Kameras)


def render_samples(root):
    """C4D-Renderings: <root>/<frame>/camN.jpg + labels.json → [(bild, [(u, v), …], gruppe)]"""
    out = []
    for fr in sorted(os.listdir(root)):
        lp = os.path.join(root, fr, "labels.json")
        if not os.path.exists(lp):
            continue
        L = json.load(open(lp, encoding="utf-8"))
        for cam, darts in L["cams"].items():
            img = os.path.join(root, fr, cam + ".jpg")
            if os.path.exists(img):
                tips = [(d["u"], d["v"]) for d in darts if d.get("visible") and d.get("kind") == "stuck" and d["u"] is not None]
                out.append((img, tips, "r" + fr))
    return out


def app_samples(root):
    """Gesammelte echte Würfe der App: nur markierte (status ok). Ältere Pfeile im Bild müssen auch markiert sein."""
    metas = {}
    for sid in os.listdir(root):
        p = os.path.join(root, sid, "meta.json")
        if os.path.exists(p):
            metas[sid] = json.load(open(p, encoding="utf-8"))
    out = []
    for sid, m in metas.items():
        if m.get("status") != "ok":
            continue
        chain = [m] + [metas.get(s) for s in m.get("prev", [])]
        if any(c is None or c.get("status") != "ok" for c in chain):
            continue   # Bild enthält unmarkierte Pfeile → wäre falsches Training
        for cid in m.get("size", {}):
            img = os.path.join(root, sid, f"cam{cid}.jpg")
            if os.path.exists(img):
                tips = [tuple(c["tips"][cid]) for c in chain if c.get("tips", {}).get(cid)]
                out.append((img, tips, "a" + sid))
    return out


def build(samples, work):
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        shutil.rmtree(os.path.join(work, sub), ignore_errors=True)
        os.makedirs(os.path.join(work, sub), exist_ok=True)
    groups = sorted({g for _, _, g in samples})
    random.Random(1).shuffle(groups)
    val = set(groups[:max(1, int(len(groups) * VAL))])
    n = {"train": 0, "val": 0, "tips": 0}
    for i, (img, tips, g) in enumerate(samples):
        split = "val" if g in val else "train"
        h, w = cv2.imread(img, cv2.IMREAD_REDUCED_GRAYSCALE_2).shape[:2]
        w, h = w * 2, h * 2
        name = f"{i:07d}"
        dst = os.path.join(work, "images", split, name + ".jpg")
        try:
            os.link(img, dst)          # Hardlink spart Platz
        except OSError:
            shutil.copy(img, dst)
        lines = []
        for u, v in tips:
            if 0 <= u < w and 0 <= v < h:
                lines.append(f"0 {u / w:.6f} {v / h:.6f} {BOX:.6f} {BOX * w / h:.6f}")
        open(os.path.join(work, "labels", split, name + ".txt"), "w").write("\n".join(lines))
        n[split] += 1
        n["tips"] += len(lines)
    yaml = os.path.join(work, "data.yaml")
    open(yaml, "w").write(f"path: {os.path.abspath(work)}\ntrain: images/train\nval: images/val\nnames:\n  0: tip\n")
    print(f"Datensatz: {n['train']} Trainings- / {n['val']} Validierungsbilder · {n['tips']} Spitzen → {work}")
    return yaml


def check(samples, out, k=12):
    os.makedirs(out, exist_ok=True)
    for img, tips, g in random.Random(2).sample(samples, min(k, len(samples))):
        im = cv2.imread(img)
        for u, v in tips:
            cv2.circle(im, (int(u), int(v)), 10, (0, 255, 0), 2)
        cv2.imwrite(os.path.join(out, g + "_" + os.path.basename(img)), im)
    print(f"Kontrollbilder: {out}")


def main():
    ap = argparse.ArgumentParser(description="Pfeilspitzen-Netz trainieren")
    ap.add_argument("--render", action="append", default=[], help="Ordner mit C4D-Frames (mehrfach möglich)")
    ap.add_argument("--app", action="append", default=[], help="Ordner data/train der App (mehrfach möglich)")
    ap.add_argument("--work", default="tipdata", help="Arbeitsordner für den Datensatz")
    ap.add_argument("--model", default="yolo11n.pt", help="Startmodell (n = klein/schnell, s = genauer)")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--batch", type=int, default=-1, help="-1 = automatisch nach Grafikspeicher")
    ap.add_argument("--out", default=os.path.join("data", "models", "tips.onnx"))
    ap.add_argument("--check", action="store_true", help="nur Labels einzeichnen")
    a = ap.parse_args()

    samples = [s for r in a.render for s in render_samples(r)] + [s for r in a.app for s in app_samples(r)]
    if not samples:
        sys.exit("Keine Bilder gefunden – Pfade prüfen (--render / --app).")
    print(f"{len(samples)} Bilder · {sum(len(t) for _, t, _ in samples)} sichtbare Spitzen")
    if a.check:
        return check(samples, os.path.join(a.work, "check"))

    yaml = build(samples, a.work)
    from ultralytics import YOLO
    model = YOLO(a.model)
    model.train(data=yaml, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, project=os.path.join(a.work, "runs"), name="tips",
                exist_ok=True, rect=False, mosaic=1.0, degrees=8, translate=0.1, scale=0.3, fliplr=0.5,
                hsv_h=0.02, hsv_s=0.6, hsv_v=0.5, close_mosaic=10, patience=25, plots=True)
    best = os.path.join(a.work, "runs", "tips", "weights", "best.pt")
    onnx = YOLO(best).export(format="onnx", imgsz=a.imgsz, opset=12, simplify=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    shutil.copy(onnx, a.out)
    print(f"\nFertig → {a.out}   (Kurven/Beispiele: {os.path.join(a.work, 'runs', 'tips')})")


if __name__ == "__main__":
    main()
