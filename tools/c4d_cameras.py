"""Kameras aus der Kalibrierung für Cinema 4D berechnen.

  python tools/c4d_cameras.py bullsnbier-snapshot.zip      (oder calibration.json)
  → schreibt c4d_bullsnbier_cameras.py  → in C4D: Erweiterungen › Skript-Manager › Laden › Ausführen

Modell: alle Kameras gleiche Brennweite, Hauptpunkt in Bildmitte, ohne Linsenverzeichnung.
Board-Koordinaten mm (x rechts, y oben, z zum Spieler) → C4D cm (X, Y, -Z): Board-Fläche schaut nach -Z.
"""
import json, math, os, sys, zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import board  # noqa: E402

SENSOR = 36.0  # mm, C4D-Sensorbreite


def load(path):
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            return json.loads(z.read("calibration.json"))
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def focal_from_h(G, cx, cy):
    """Brennweite (px), bei der die Homographie am ehesten eine starre Ebene ist."""
    best = (1e9, None)
    for f in range(200, 4000, 2):
        A = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ G
        a1, a2 = A[:, 0], A[:, 1]
        n1, n2 = np.linalg.norm(a1), np.linalg.norm(a2)
        e = (a1 @ a2 / (n1 * n2)) ** 2 + ((n1 - n2) / n1) ** 2
        best = min(best, (e, f))
    return best[1]


def main(path, out="c4d_bullsnbier_cameras.py"):
    d = load(path)
    W, H = d["res"]
    cx, cy = W / 2, H / 2
    cams = {k: c for k, c in d["cams"].items() if c.get("H")}
    fs = {k: focal_from_h(np.linalg.inv(np.array(c["H"])), cx, cy) for k, c in cams.items()}
    f = float(np.median(list(fs.values())))
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
    print(f"Brennweite: {f:.0f} px  (je Kamera: {', '.join(f'Cam {int(k)+1}: {v}' for k, v in fs.items())})"
          f"  → horizontaler Bildwinkel {math.degrees(2 * math.atan(cx / f)):.0f}°")
    rows = []
    for k, c in sorted(cams.items()):
        keys = [p for p in c["points"] if p in board.CAL_POINTS]
        obj = np.array([[*board.CAL_POINTS[p], 0.0] for p in keys])
        img = np.array([c["points"][p] for p in keys], float)
        ok, rv, tv = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_IPPE)
        err = np.linalg.norm(cv2.projectPoints(obj, rv, tv, K, None)[0].reshape(-1, 2) - img, axis=1).max()
        R, _ = cv2.Rodrigues(rv)
        C = (-R.T @ tv).ravel()
        conv = lambda v: [float(v[0]) / 10, float(v[1]) / 10, -float(v[2]) / 10]   # mm → cm, z gespiegelt
        unit = lambda v: [float(v[0]), float(v[1]), -float(v[2])]
        rows.append({"name": f"Cam {int(k) + 1}", "off": conv(C), "v1": unit(R[0]), "v2": unit(-R[1]), "v3": unit(R[2])})
        warn = "  ⚠ Kalibrierung ungenau – neu klicken!" if err > 6 else ""
        print(f"Cam {int(k)+1}: Position {C[0]:.0f}/{C[1]:.0f}/{C[2]:.0f} mm · Höhe über Board {C[2]:.0f} mm · "
              f"Winkel {math.degrees(math.atan2(C[1], C[0])):.0f}° · Fehler {err:.1f} px{warn}")

    focus = f * SENSOR / W
    script = f'''# Bulls'n'Bier · Kameras aus der Kalibrierung (erzeugt von tools/c4d_cameras.py)
# Board: Mitte = Ursprung, Fläche schaut nach -Z, 20 oben. Einheiten cm.
import c4d
CAMS = {json.dumps(rows)}
RES = ({W}, {H})
FOCUS, SENSOR = {focus:.3f}, {SENSOR}
RINGS = {{"Bull": {board.R_OUTER_BULL / 10}, "Triple innen": {board.R_TRIPLE_IN / 10}, "Triple außen": {board.R_TRIPLE_OUT / 10},
         "Double innen": {board.R_DOUBLE_IN / 10}, "Double außen": {board.R_DOUBLE_OUT / 10}}}

def main():
    doc = c4d.documents.GetActiveDocument()
    rig = c4d.BaseObject(c4d.Onull); rig.SetName("BnB_Rig"); doc.InsertObject(rig)
    for c in CAMS:
        cam = c4d.BaseObject(c4d.Ocamera); cam.SetName(c["name"])
        m = c4d.Matrix(c4d.Vector(*c["off"]), c4d.Vector(*c["v1"]), c4d.Vector(*c["v2"]), c4d.Vector(*c["v3"]))
        cam.SetMg(m)
        cam[c4d.CAMERA_FOCUS] = FOCUS
        cam[c4d.CAMERAOBJECT_APERTURE] = SENSOR
        cam.InsertUnderLast(rig)
    ref = c4d.BaseObject(c4d.Onull); ref.SetName("Board_Referenz (Ringe)"); ref.InsertUnderLast(rig)
    for name, r in RINGS.items():   # Kreise in der Board-Ebene (XY) zum Ausrichten des Board-Modells
        s = c4d.BaseObject(c4d.Osplinecircle); s.SetName(name)
        s[c4d.PRIM_CIRCLE_RADIUS] = r
        s[c4d.PRIM_PLANE] = 0   # XY
        s.InsertUnderLast(ref)
    rd = doc.GetActiveRenderData()
    rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES] = RES
    rd[c4d.RDATA_FILMASPECT] = RES[0] / RES[1]
    c4d.EventAdd()

if __name__ == "__main__":
    main()
'''
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(script)
    print(f"\n→ {out}  (in C4D: Skript-Manager › Laden › Ausführen)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], *(sys.argv[2:3]))
