"""Cinema-4D-Szene aus den Kamerabildern: Kameras + Board mit echter Textur (aus den Fotos entzerrt).

  python tools/c4d_scene.py bullsnbier-snapshot.zip            (Snapshot aus der App: Bilder + Kalibrierung)
  python tools/c4d_scene.py ORDNER --init klicks.json          (Ordner mit cam0.jpg …, Startpunkte von Hand)

Ablauf: Startwerte (Kalibrierung oder Klickpunkte) → Feinabgleich jedes Bildes mit einem Board-Muster (ECC)
→ Kameraposition (gemeinsame Brennweite) → Board-Textur aus allen Kameras → C4D-Skript.

Ausgabe (Ordner --out, Standard c4d_szene/):
  c4d_bullsnbier_szene.py   in C4D: Erweiterungen › Skript-Manager › Laden › Ausführen (Textur ist eingebettet)
  board_textur.jpg          entzerrtes Board von vorne (r = 226 mm, 20 oben)
  calibration.json          verfeinerte Punkte für die App (data/calibration.json, gleiche Kamera-Reihenfolge!)
  kontrolle.jpg             Raster über den Kamerabildern – muss genau passen
klicks.json: {"0": {"c": [x, y], "<Winkel>": [x, y], …}, …}  c = Bull-Mitte, Winkel = Draht am Double-Außenrand
             (0° = Mitte der 20, im Uhrzeigersinn; Draht 20|1 = 9°, 1|18 = 27° …)
"""
import argparse, base64, glob, json, math, os, sys, zipfile

import cv2
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app import board as B  # noqa: E402

S, R_T = 2.0, 180                     # Muster: px/mm, Radius mm
N = int(2 * R_T * S)
T = np.array([[S, 0, N / 2], [0, -S, N / 2], [0, 0, 1.0]])   # mm → Muster-px
R_BOARD = 226.0                       # mm: Board inkl. Zahlenring
TEX = 2048
SENSOR = 36.0


def mm(a, r=170.0):
    return (r * math.sin(math.radians(a)), r * math.cos(math.radians(a)))


def pattern():
    yy, xx = np.mgrid[0:N, 0:N]
    x, y = (xx - N / 2) / S, -(yy - N / 2) / S
    r = np.hypot(x, y)
    even = ((((np.degrees(np.arctan2(x, y)) + 9) % 360) // 18).astype(int) % 2 == 0)[..., None]
    img = np.zeros((N, N, 3), np.uint8); img[:] = 30
    single, ring = np.where(even, (25, 25, 25), (200, 225, 230)), np.where(even, (40, 40, 190), (60, 150, 40))
    m = r <= 170; img[m] = single[m]
    m = ((r >= 99) & (r <= 107)) | ((r >= 162) & (r <= 170)); img[m] = ring[m]
    img[r <= 15.9] = (60, 150, 40); img[r <= 6.35] = (40, 40, 190)
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), r


def refine(im, Hmm, pat, r):
    """Hmm: mm → Bild. ECC im entzerrten Raum, grob → fein."""
    Hm = Hmm @ np.linalg.inv(T); Hm /= Hm[2, 2]
    mask = ((r <= 172) & (r >= 8)).astype(np.uint8)
    cc = 0.0
    for blur in (11, 7, 3, 1):
        w = cv2.warpPerspective(im, Hm, (N, N), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
        gi = cv2.cvtColor(w, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gt = pat
        if blur > 1:
            gi, gt = cv2.GaussianBlur(gi, (blur, blur), 0), cv2.GaussianBlur(pat, (blur, blur), 0)
        C = np.eye(3, dtype=np.float32)
        try:
            cc, C = cv2.findTransformECC(gt, gi, C, cv2.MOTION_HOMOGRAPHY,
                                         (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-7), mask, 1)
        except cv2.error:
            continue
        Hm = Hm @ C.astype(float); Hm /= Hm[2, 2]
    H = Hm @ T
    return H / H[2, 2], cc


def focal_from_h(G, cx, cy):
    best = (1e9, None)
    for f in range(150, 4000, 2):
        A = np.linalg.inv(np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])) @ G
        a1, a2 = A[:, 0], A[:, 1]
        n1, n2 = np.linalg.norm(a1), np.linalg.norm(a2)
        best = min(best, ((a1 @ a2 / (n1 * n2)) ** 2 + ((n1 - n2) / n1) ** 2, f))
    return best[1]


def proj(H, pts):
    return cv2.perspectiveTransform(np.float32(pts)[None], H)[0]


def overlay(im, H):
    v = im.copy()
    for rad in (6.35, 15.9, 99, 107, 162, 170):
        ps = proj(H, [(rad * math.sin(a), rad * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 240)])
        cv2.polylines(v, [np.int32(np.round(ps * 4))], True, (0, 255, 255), 1, cv2.LINE_AA, shift=2)
    for k in range(20):
        p = proj(H, [mm(k * 18 - 9, 15.9), mm(k * 18 - 9, 170)])
        cv2.line(v, tuple(np.int32(p[0] * 4)), tuple(np.int32(p[1] * 4)), (0, 255, 255), 1, cv2.LINE_AA, shift=2)
    p = proj(H, [mm(0, 135)])[0]
    cv2.putText(v, "20", (int(p[0]) - 8, int(p[1]) + 5), 0, 0.5, (255, 0, 255), 2)
    return v


def texture(ims, Hs):
    """Board von vorne: jede Kamera entzerren, gewichtet nach Detailschärfe (Pixel pro mm²) überblenden."""
    s = TEX / (2 * R_BOARD)
    Tt = np.array([[s, 0, TEX / 2], [0, -s, TEX / 2], [0, 0, 1.0]])
    yy, xx = np.mgrid[0:TEX, 0:TEX].astype(np.float32)
    bx, by = (xx - TEX / 2) / s, -(yy - TEX / 2) / s
    inside = np.hypot(bx, by) <= R_BOARD
    acc, wsum, layers = np.zeros((TEX, TEX, 3)), np.zeros((TEX, TEX)), []
    for k, im in ims.items():
        Hk = Hs[k] @ np.linalg.inv(Tt)
        w = cv2.warpPerspective(im, Hk, (TEX, TEX), flags=cv2.INTER_CUBIC | cv2.WARP_INVERSE_MAP).astype(np.float64)
        valid = cv2.warpPerspective(np.full(im.shape[:2], 255, np.uint8), Hk, (TEX, TEX), flags=cv2.WARP_INVERSE_MAP)
        valid = cv2.erode(valid, np.ones((25, 25), np.uint8)) > 0
        # Detailschärfe = |det J| der Abbildung mm → Bild (numerisch)
        H = Hs[k]
        def P(x, y):
            d = H[2, 0] * x + H[2, 1] * y + H[2, 2]
            return (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / d, (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / d
        u0, v0 = P(bx, by); u1, v1 = P(bx + 1, by); u2, v2 = P(bx, by + 1)
        det = np.abs((u1 - u0) * (v2 - v0) - (u2 - u0) * (v1 - v0))
        wt = np.where(valid & inside, det ** 3, 0.0)
        wt = cv2.GaussianBlur(wt, (0, 0), 12)
        layers.append((w, wt, valid & inside))
    # Helligkeit angleichen (gemeinsamer Bereich)
    common = np.logical_and.reduce([l[2] for l in layers])
    ref = np.mean([l[0][common].mean(0) for l in layers], 0) if common.any() else None
    for w, wt, _ in layers:
        if ref is not None:
            w = w * (ref / np.maximum(w[common].mean(0), 1))
        acc += w * wt[..., None]; wsum += wt
    out = np.clip(acc / np.maximum(wsum, 1e-12)[..., None], 0, 255).astype(np.uint8)
    out[~inside] = 0
    return out


C4D_SCRIPT = r'''# Bulls'n'Bier · Szene aus den Kamerabildern (erzeugt von tools/c4d_scene.py)
# Board: Mitte = Ursprung, Fläche in XY, schaut nach -Z, 20 oben. Einheiten cm.
# Erzeugt: BnB_Rig (Cam 1-3), Board (Front mit Foto-Textur), Board_Korpus, Umrandung (Tisch/Wand), Umgebung + LED_Ring (Lichter)
import c4d, base64, math, os
CAMS = __CAMS__
RES = __RES__
FOCUS, SENSOR = __FOCUS__, __SENSOR__
R_BOARD, THICK = __RB__, 3.8            # cm
TEX_FILE = os.path.join(os.path.expanduser("~"), "BnB", "board_textur.jpg")
TEX_B64 = "__TEX__"
RINGS = {"Bull": 1.59, "Triple innen": 9.9, "Triple außen": 10.7, "Double innen": 16.2, "Double außen": 17.0}


def mat(doc, name, color=None, tex=None, refl=0.15):
    m = doc.SearchMaterial(name)
    if m is None:
        m = c4d.BaseMaterial(c4d.Mmaterial); m.SetName(name); doc.InsertMaterial(m)
    if color is not None:
        m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*color)
    if tex:
        sh = c4d.BaseShader(c4d.Xbitmap); sh[c4d.BITMAPSHADER_FILENAME] = tex
        m[c4d.MATERIAL_COLOR_SHADER] = sh; m.InsertShader(sh)
    m[c4d.MATERIAL_USE_REFLECTION] = refl > 0
    m.Message(c4d.MSG_UPDATE)
    return m


def front_disc(r, seg=96, rings=12):
    """Scheibe als Polygon-Objekt mit exakten UVs (Textur: 20 oben, Mitte = Bildmitte)."""
    pts = [c4d.Vector(0, 0, 0)]
    for j in range(1, rings + 1):
        rr = r * j / rings
        for i in range(seg):
            a = 6.283185307 * i / seg
            pts.append(c4d.Vector(rr * math.sin(a), rr * math.cos(a), 0))
    polys = []
    for i in range(seg):
        polys.append((0, 1 + (i + 1) % seg, 1 + i, 1 + i))
    for j in range(1, rings):
        b0, b1 = 1 + (j - 1) * seg, 1 + j * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            polys.append((b0 + i, b0 + i2, b1 + i2, b1 + i))
    obj = c4d.PolygonObject(len(pts), len(polys))
    for k, p in enumerate(pts):
        obj.SetPoint(k, p)
    uvw = c4d.UVWTag(len(polys))
    uv = lambda k: c4d.Vector(0.5 + pts[k].x / (2 * r), 0.5 - pts[k].y / (2 * r), 0)
    for k, (a, b, c, d) in enumerate(polys):
        obj.SetPolygon(k, c4d.CPolygon(a, b, c, d))
        uvw.SetSlow(k, uv(a), uv(b), uv(c), uv(d))
    obj.InsertTag(uvw)
    obj.Message(c4d.MSG_UPDATE)
    return obj


def main():
    doc = c4d.documents.GetActiveDocument()
    os.makedirs(os.path.dirname(TEX_FILE), exist_ok=True)
    with open(TEX_FILE, "wb") as f:
        f.write(base64.b64decode(TEX_B64))

    rig = c4d.BaseObject(c4d.Onull); rig.SetName("BnB_Rig"); doc.InsertObject(rig)
    for c in CAMS:
        cam = c4d.BaseObject(c4d.Ocamera); cam.SetName(c["name"])
        cam.SetMg(c4d.Matrix(c4d.Vector(*c["off"]), c4d.Vector(*c["v1"]), c4d.Vector(*c["v2"]), c4d.Vector(*c["v3"])))
        cam[c4d.CAMERA_FOCUS] = FOCUS
        cam[c4d.CAMERAOBJECT_APERTURE] = SENSOR
        cam.InsertUnderLast(rig)
    ref = c4d.BaseObject(c4d.Onull); ref.SetName("Board_Referenz (Ringe)"); ref.InsertUnderLast(rig)
    for name, r in RINGS.items():
        s = c4d.BaseObject(c4d.Osplinecircle); s.SetName(name)
        s[c4d.PRIM_CIRCLE_RADIUS] = r; s[c4d.PRIM_PLANE] = 0
        s.InsertUnderLast(ref)

    front = front_disc(R_BOARD); front.SetName("Board"); doc.InsertObject(front)
    t = front.MakeTag(c4d.Ttexture); t[c4d.TEXTURETAG_MATERIAL] = mat(doc, "Board", tex=TEX_FILE, refl=0.08)
    t[c4d.TEXTURETAG_PROJECTION] = c4d.TEXTURETAG_PROJECTION_UVW

    body = c4d.BaseObject(c4d.Ocylinder); body.SetName("Board_Korpus")
    body[c4d.PRIM_CYLINDER_RADIUS] = R_BOARD; body[c4d.PRIM_CYLINDER_HEIGHT] = THICK
    body[c4d.PRIM_CYLINDER_SEG] = 96; body[c4d.PRIM_AXIS] = 4   # +Z
    body.SetAbsPos(c4d.Vector(0, 0, THICK / 2 + 0.02))
    body.MakeTag(c4d.Ttexture)[c4d.TEXTURETAG_MATERIAL] = mat(doc, "Board_Korpus", color=(0.05, 0.05, 0.05), refl=0)
    doc.InsertObject(body)

    bg = c4d.BaseObject(c4d.Oplane); bg.SetName("Umrandung")
    bg[c4d.PRIM_PLANE_WIDTH] = bg[c4d.PRIM_PLANE_HEIGHT] = 300; bg[c4d.PRIM_AXIS] = 5   # Normale -Z
    bg.SetAbsPos(c4d.Vector(0, 0, THICK + 0.05))
    bg.MakeTag(c4d.Ttexture)[c4d.TEXTURETAG_MATERIAL] = mat(doc, "Umrandung", color=(0.32, 0.06, 0.1), refl=0)
    doc.InsertObject(bg)

    for name, pos, bright in (("Umgebung", (0, 60, -160), 0.8), ("LED_Ring", (0, 0, -45), 0.6)):
        if doc.SearchObject(name):
            continue
        l = c4d.BaseObject(c4d.Olight); l.SetName(name)
        l[c4d.LIGHT_TYPE] = c4d.LIGHT_TYPE_AREA if name == "Umgebung" else c4d.LIGHT_TYPE_OMNI
        l[c4d.LIGHT_BRIGHTNESS] = bright; l[c4d.LIGHT_SHADOWTYPE] = c4d.LIGHT_SHADOWTYPE_AREA
        l.SetAbsPos(c4d.Vector(*pos)); l.SetAbsRot(c4d.Vector(0, 0, 0))
        doc.InsertObject(l)

    rd = doc.GetActiveRenderData()
    rd[c4d.RDATA_XRES], rd[c4d.RDATA_YRES] = RES
    rd[c4d.RDATA_FILMASPECT] = RES[0] / RES[1]
    c4d.EventAdd()
    c4d.gui.MessageDialog("Szene erstellt. Textur: " + TEX_FILE)


if __name__ == "__main__":
    main()
'''


def load_input(src):
    ims, cal = {}, None
    if src.endswith(".zip"):
        with zipfile.ZipFile(src) as z:
            for n in z.namelist():
                if n.startswith("cam") and n.endswith(".jpg"):
                    ims[n[3:-4]] = cv2.imdecode(np.frombuffer(z.read(n), np.uint8), cv2.IMREAD_COLOR)
            if "calibration.json" in z.namelist():
                cal = json.loads(z.read("calibration.json"))
    else:
        for p in sorted(glob.glob(os.path.join(src, "cam*.jpg"))):
            ims[os.path.basename(p)[3:-4]] = cv2.imread(p)
        p = os.path.join(src, "calibration.json")
        if os.path.exists(p):
            cal = json.load(open(p, encoding="utf-8"))
    return ims, cal


def start_h(k, cal, clicks):
    if clicks and k in clicks:
        src, dst = [], []
        for a, p in clicks[k].items():
            src.append((0.0, 0.0) if a == "c" else mm(float(a)))
            dst.append(p)
        return cv2.findHomography(np.float32(src), np.float32(dst))[0]
    c = (cal or {}).get("cams", {}).get(k) or {}
    if c.get("H"):
        return np.linalg.inv(np.array(c["H"]))   # App: Bild → mm
    pts = {n: p for n, p in (c.get("points") or {}).items() if n in B.CAL_POINTS}
    if len(pts) >= 4:
        return cv2.findHomography(np.float32([B.CAL_POINTS[n] for n in pts]), np.float32(list(pts.values())))[0]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src", help="Snapshot-ZIP der App oder Ordner mit cam0.jpg …")
    ap.add_argument("--init", help="Startpunkte von Hand (JSON, siehe oben)")
    ap.add_argument("--out", default="c4d_szene")
    a = ap.parse_args()
    ims, cal = load_input(a.src)
    clicks = json.load(open(a.init, encoding="utf-8")) if a.init else None
    if not ims:
        sys.exit("Keine Bilder cam*.jpg gefunden")
    os.makedirs(a.out, exist_ok=True)
    pat, r = pattern()
    Hs, ctl = {}, []
    for k in sorted(ims):
        H0 = start_h(k, cal, clicks)
        if H0 is None:
            print(f"Cam {int(k) + 1}: keine Startwerte (Kalibrierung oder --init) – übersprungen"); continue
        Hs[k], cc = refine(ims[k], H0, pat, r)
        moved = np.abs(proj(Hs[k], [mm(a2) for a2 in range(0, 360, 30)]) - proj(H0, [mm(a2) for a2 in range(0, 360, 30)])).max()
        print(f"Cam {int(k) + 1}: Übereinstimmung {cc:.3f}{'  ⚠ schwach – Startpunkte prüfen' if cc < 0.8 else ''} · verschoben um max {moved:.1f} px")
        ctl.append(overlay(ims[k], Hs[k]))
    h0, w0 = next(iter(ims.values())).shape[:2]
    cv2.imwrite(os.path.join(a.out, "kontrolle.jpg"), np.hstack(ctl), [cv2.IMWRITE_JPEG_QUALITY, 90])

    # Kameras: gemeinsame Brennweite, Hauptpunkt Bildmitte
    cx, cy = w0 / 2, h0 / 2
    fs = {k: focal_from_h(H, cx, cy) for k, H in Hs.items()}
    f = float(np.median(list(fs.values())))
    K = np.array([[f, 0, cx], [0, f, cy], [0, 0, 1.0]])
    grid = [mm(a2, rr) for rr in (16, 60, 103, 135, 166) for a2 in range(0, 360, 15)] + [(0, 0)]
    rows = []
    print(f"Brennweite {f:.0f} px (je Kamera {', '.join(str(v) for v in fs.values())}) → Bildwinkel {math.degrees(2 * math.atan(cx / f)):.0f}°")
    for k, H in sorted(Hs.items()):
        obj = np.array([[x, y, 0.0] for x, y in grid])
        img = proj(H, grid)
        _, rv, tv = cv2.solvePnP(obj, img, K, None, flags=cv2.SOLVEPNP_ITERATIVE)
        err = np.linalg.norm(cv2.projectPoints(obj, rv, tv, K, None)[0].reshape(-1, 2) - img, axis=1)
        R, _ = cv2.Rodrigues(rv)
        C = (-R.T @ tv).ravel()
        rows.append({"name": f"Cam {int(k) + 1}", "off": [C[0] / 10, C[1] / 10, -C[2] / 10],
                     "v1": [R[0, 0], R[0, 1], -R[0, 2]], "v2": [-R[1, 0], -R[1, 1], R[1, 2]], "v3": [R[2, 0], R[2, 1], -R[2, 2]]})
        print(f"Cam {int(k) + 1}: Abstand zur Mitte {np.linalg.norm(C) / 10:.1f} cm · Höhe über Board {C[2] / 10:.1f} cm · "
              f"Richtung {math.degrees(math.atan2(C[0], C[1])) % 360:.0f}° · Restfehler {err.mean():.1f} px (Linsenverzeichnung)")

    tex = texture(ims, Hs)
    tp = os.path.join(a.out, "board_textur.jpg")
    cv2.imwrite(tp, tex, [cv2.IMWRITE_JPEG_QUALITY, 92])
    b64 = base64.b64encode(open(tp, "rb").read()).decode()
    script = (C4D_SCRIPT.replace("__CAMS__", json.dumps(rows)).replace("__RES__", f"({w0}, {h0})")
              .replace("__FOCUS__", f"{f * SENSOR / w0:.3f}").replace("__SENSOR__", str(SENSOR))
              .replace("__RB__", str(R_BOARD / 10)).replace("__TEX__", b64))
    open(os.path.join(a.out, "c4d_bullsnbier_szene.py"), "w", encoding="utf-8").write(script)

    # Kalibrierung für die App (verfeinerte Punkte, alle bekannten Kalibrierpunkte)
    app_cal = {k: {**{n: [round(float(v), 1) for v in proj(H, [p])[0]] for n, p in B.CAL_POINTS.items()}, "_res": [w0, h0]}
               for k, H in Hs.items()}
    json.dump(app_cal, open(os.path.join(a.out, "calibration.json"), "w"), indent=2)
    print(f"\n→ {a.out}/c4d_bullsnbier_szene.py · board_textur.jpg · calibration.json · kontrolle.jpg")


if __name__ == "__main__":
    main()
