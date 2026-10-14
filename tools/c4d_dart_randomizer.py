# Bulls'n'Bier · Trainingsdaten aus Cinema 4D
# Skript-Manager › Laden › Ausführen.  Abbrechen: ESC gedrückt halten.
#
# Szene (Namen genau so):
#   BnB_Rig          ← von c4d_bullsnbier_cameras.py (Cam 1 / Cam 2 / Cam 3)
#   Pfeil-Modelle    ← Null, darunter je Pfeil-Variante ein Null/Objekt:
#                       Achsenursprung = SPITZE, Pfeil zeigt entlang lokaler -Z (vom Board weg, zum Spieler)
#   LED_Ring         ← optional: Licht (Standard-Licht) – Helligkeit/Farbtemperatur wird variiert
#   Umgebung         ← optional: Licht – Helligkeit wird variiert
#   Hand             ← optional: Objekt mit Polygon-Mesh, wird zufällig vors Board gehalten
# Board: Mitte = Ursprung, Fläche in XY, schaut nach -Z, 20 oben. Einheiten cm.
#
# Ausgabe: OUT/000123/cam1.jpg, cam2.jpg, cam3.jpg, labels.json
import c4d, json, math, os, random, time

# ───────────────────────── Einstellungen ─────────────────────────
OUT = r"C:\Users\fb\Nextcloud\elberfeld\Projekte\BullsnBier\BnB_Render"   # Zielordner
START, COUNT = "auto", 5000   # "auto" = hinter dem letzten vorhandenen Frame weitermachen
PREVIEW = False               # True = nur Frame START in der Szene aufbauen, nichts rendern (zum Prüfen)
DEPTH = 0.6                   # cm: so tief steckt die Spitze im Board (Ursprung des Modells liegt im Board)
TILT_MAX = 25.0               # ° Neigung aus der Senkrechten
P_DARTS = [0.05, 0.30, 0.30, 0.35]   # Wahrscheinlichkeit 0/1/2/3 Pfeile
P_EDGE = 0.10                 # Anteil Pfeile außerhalb Double (Zahlenring, Miss)
P_LOOSE = 0.04                # Anteil „abgeprallt“: liegt schräg am Rand, Spitze nicht im Board
P_HAND = 0.12                 # Anteil Frames mit Hand im Bild
CAM_POS_JIT, CAM_ROT_JIT = 0.3, 0.6   # cm / ° Zufallsabweichung der Kameras
JPG_Q = (70, 95)              # JPEG-Qualität zufällig
# Echte Kamerafotos als Hintergrund (empfohlen): Ordner mit Unterordnern je Licht-Situation,
# darin cam0.jpg, cam1.jpg, cam2.jpg (= Inhalt vom „Snapshot (ZIP)“ der App, leeres Board).
# Das Board-Objekt (Name "Board", Scheibe bis inkl. Zahlenring, r ≥ 23 cm) wird dann unsichtbar und fängt nur Schatten.
BG_DIR = r""                  # z. B. r"C:\Users\fb\Nextcloud\elberfeld\Projekte\BullsnBier\BnB_Hintergrund"
# Abmessungen fürs Verdeckungs-Modell (cm): Barrel-/Schaft-Radius, Flight-Radius, Pfeillänge
R_BARREL, R_FLIGHT, LEN, FLIGHT_LEN = 0.45, 1.8, 15.0, 3.8
# Häufige Ziele (mm) – echte Würfe häufen sich hier; Rest gleichmäßig verteilt
HOT = [(0, 103), (0, 0), (-32, -98), (-107, -35), (0, 166), (166, 0), (-98, 32)]
P_HOT, HOT_SIGMA = 0.45, 22.0
# ──────────────────────────────────────────────────────────────────

SEG = [20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5]


def score(x, y):   # mm
    r = math.hypot(x, y)
    if r <= 6.35: return "BULL"
    if r <= 15.9: return "25"
    if r > 170.0: return "MISS"
    s = SEG[int(((math.degrees(math.atan2(x, y)) + 9) % 360) // 18)]
    if 99.0 <= r <= 107.0: return "T%d" % s
    if r >= 162.0: return "D%d" % s
    return "S%d" % s


# ── Vektor-Helfer (Tupel, unabhängig von c4d-Operatoren) ──
def add(a, b): return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def sub(a, b): return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def mul(a, s): return (a[0] * s, a[1] * s, a[2] * s)
def dot(a, b): return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)
def V(t): return c4d.Vector(*t)
def T(v): return (v.x, v.y, v.z)


def rotate(v, axis, ang):   # Rodrigues
    k = norm(axis); c, s = math.cos(ang), math.sin(ang)
    return add(add(mul(v, c), mul(cross(k, v), s)), mul(k, dot(k, v) * (1 - c)))


def seg_dist(p1, q1, p2, q2):
    """Kürzester Abstand zweier Strecken."""
    d1, d2, r = sub(q1, p1), sub(q2, p2), sub(p1, p2)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    c, b = dot(d1, r), dot(d1, d2)
    den = a * e - b * b
    s = min(max((b * f - c * e) / den, 0.0), 1.0) if den > 1e-9 else 0.0
    t = (b * s + f) / e if e > 1e-9 else 0.0
    if t < 0: t, s = 0.0, min(max(-c / a, 0.0), 1.0) if a > 1e-9 else 0.0
    elif t > 1: t, s = 1.0, min(max((b - c) / a, 0.0), 1.0) if a > 1e-9 else 0.0
    c1, c2 = add(p1, mul(d1, s)), add(p2, mul(d2, t))
    return math.sqrt(dot(sub(c1, c2), sub(c1, c2)))


def kelvin_rgb(k):
    t = k / 100.0
    r = 255 if t <= 66 else 329.7 * (t - 60) ** -0.1332
    g = 99.47 * math.log(t) - 161.12 if t <= 66 else 288.12 * (t - 60) ** -0.0755
    b = 255 if t >= 66 else (0 if t <= 19 else 138.52 * math.log(t - 10) - 305.04)
    return tuple(min(max(v, 0), 255) / 255.0 for v in (r, g, b))


def sample_point(rng):
    """Spitze auf dem Board (mm) + Typ."""
    u = rng.random()
    if u < P_LOOSE:
        a = rng.uniform(0, 2 * math.pi); r = rng.uniform(205, 225)
        return (r * math.sin(a), r * math.cos(a)), "loose"
    if u < P_LOOSE + P_EDGE:
        a = rng.uniform(0, 2 * math.pi); r = math.sqrt(rng.uniform(170 ** 2, 222 ** 2))
        return (r * math.sin(a), r * math.cos(a)), "stuck"
    if rng.random() < P_HOT:
        hx, hy = rng.choice(HOT)
        x, y = rng.gauss(hx, HOT_SIGMA), rng.gauss(hy, HOT_SIGMA)
        if math.hypot(x, y) < 170: return (x, y), "stuck"
    a = rng.uniform(0, 2 * math.pi); r = 170 * math.sqrt(rng.random())
    return (r * math.sin(a), r * math.cos(a)), "stuck"


def dart_frame(tip_cm, kind, rng):
    """Matrix (off, v1, v2, v3) für ein Modell mit Spitze im Ursprung, Pfeil entlang lokaler -Z."""
    if kind == "loose":   # liegt fast flach, Spitze zeigt nach außen/unten
        tilt = math.radians(rng.uniform(60, 85))
    else:
        tilt = math.radians(TILT_MAX * math.sqrt(rng.random()))
    az = rng.uniform(0, 2 * math.pi)
    back = (math.sin(tilt) * math.cos(az), math.sin(tilt) * math.sin(az), -math.cos(tilt))   # Spitze → Flight
    if kind == "loose":
        back = norm((-tip_cm[0], -tip_cm[1], -abs(back[2]) - 0.3))
    z = mul(back, -1)                               # lokale +Z zeigt ins Board
    helper = (0, 1, 0) if abs(z[1]) < 0.9 else (1, 0, 0)
    x = norm(cross(helper, z)); y = cross(z, x)
    spin = rng.uniform(0, 2 * math.pi)
    x, y = rotate(x, z, spin), rotate(y, z, spin)
    off = add((tip_cm[0], tip_cm[1], 0.0), mul(z, DEPTH if kind == "stuck" else 0.0))
    return off, x, y, z, back


def find(doc, name):
    o = doc.SearchObject(name)
    return o


def first_poly(o):
    while o:
        if o.GetType() == c4d.Opolygon: return o
        r = first_poly(o.GetDown())
        if r: return r
        o = o.GetNext()
    return None


def make_default_models(doc):
    """Kein 'Pfeil-Modelle' da → 4 einfache Pfeile aus Grundobjekten bauen (Spitze im Ursprung, entlang -Z)."""
    root = c4d.BaseObject(c4d.Onull); root.SetName("Pfeil-Modelle"); doc.InsertObject(root)
    def mat(name, rgb):
        m = c4d.BaseMaterial(c4d.Mmaterial); m.SetName(name); m[c4d.MATERIAL_COLOR_COLOR] = c4d.Vector(*rgb)
        doc.InsertMaterial(m); return m
    def part(kind, parent, name, z, m, **kw):
        o = c4d.BaseObject(kind); o.SetName(name)
        for k, v in kw.items(): o[getattr(c4d, k)] = v
        o.SetRelPos(c4d.Vector(0, 0, z)); o.InsertUnderLast(parent)
        t = o.MakeTag(c4d.Ttexture); t[c4d.TEXTURETAG_MATERIAL] = m
        return o
    steel, shaft = mat("BnB Stahl", (0.75, 0.75, 0.78)), mat("BnB Schaft", (0.08, 0.08, 0.08))
    for i, (col, barrel_len, shaft_len) in enumerate([((0.85, 0.08, 0.1), 4.6, 3.4), ((0.05, 0.05, 0.05), 5.0, 4.2),
                                                      ((0.1, 0.35, 0.9), 4.2, 2.8), ((0.95, 0.95, 0.95), 4.8, 3.6)]):
        d = c4d.BaseObject(c4d.Onull); d.SetName("Pfeil %d" % (i + 1)); d.InsertUnderLast(root)
        fl = mat("BnB Flight %d" % (i + 1), col)
        z = 0.0
        part(c4d.Ocone, d, "Spitze", z - 1.6, steel, PRIM_CONE_TRAD=0.13, PRIM_CONE_BRAD=0.03, PRIM_CONE_HEIGHT=3.2, PRIM_AXIS=5); z -= 3.2
        part(c4d.Ocylinder, d, "Barrel", z - barrel_len / 2, steel, PRIM_CYLINDER_RADIUS=0.35, PRIM_CYLINDER_HEIGHT=barrel_len, PRIM_AXIS=5); z -= barrel_len
        part(c4d.Ocylinder, d, "Schaft", z - shaft_len / 2, shaft, PRIM_CYLINDER_RADIUS=0.2, PRIM_CYLINDER_HEIGHT=shaft_len, PRIM_AXIS=5)
        zf = z - shaft_len + 1.2   # Flight sitzt hinten auf dem Schaft
        for ax in (0, 2):   # zwei gekreuzte Flächen = 4 Flügel
            part(c4d.Oplane, d, "Flight", zf - 1.9, fl, PRIM_PLANE_WIDTH=3.6, PRIM_PLANE_HEIGHT=3.8, PRIM_AXIS=ax,
                 PRIM_PLANE_SUBW=1, PRIM_PLANE_SUBH=1)
    c4d.EventAdd()
    return root


def setup_background(doc):
    """Hintergrund-Objekt mit Bitmap-Material + Compositing-Tag am Board. Rückgabe: Bitmap-Shader."""
    bg = find(doc, "BnB_Hintergrund")
    if not bg:
        bg = c4d.BaseObject(c4d.Obackground); bg.SetName("BnB_Hintergrund"); doc.InsertObject(bg)
    mat = doc.SearchMaterial("BnB_BG")
    if not mat:
        mat = c4d.BaseMaterial(c4d.Mmaterial); mat.SetName("BnB_BG"); doc.InsertMaterial(mat)
        mat[c4d.MATERIAL_USE_COLOR] = False; mat[c4d.MATERIAL_USE_REFLECTION] = False; mat[c4d.MATERIAL_USE_LUMINANCE] = True
        sh = c4d.BaseShader(c4d.Xbitmap); mat.InsertShader(sh); mat[c4d.MATERIAL_LUMINANCE_SHADER] = sh
    if not bg.GetTag(c4d.Ttexture):
        t = bg.MakeTag(c4d.Ttexture); t[c4d.TEXTURETAG_MATERIAL] = mat
    board_obj = find(doc, "Board")
    if board_obj:
        ct = board_obj.GetTag(c4d.Tcompositing) or board_obj.MakeTag(c4d.Tcompositing)
        ct[c4d.COMPOSITINGTAG_BACKGROUND] = True   # zeigt das Foto, empfängt Schatten
    else:
        print("Hinweis: kein Objekt 'Board' – Pfeile werfen keine Schatten aufs Foto.")
    return mat[c4d.MATERIAL_LUMINANCE_SHADER]


def bg_sets():
    if not BG_DIR or not os.path.isdir(BG_DIR): return []
    sets = [os.path.join(BG_DIR, d) for d in sorted(os.listdir(BG_DIR)) if os.path.isdir(os.path.join(BG_DIR, d))]
    if os.path.exists(os.path.join(BG_DIR, "cam0.jpg")): sets.append(BG_DIR)
    return [d for d in sets if os.path.exists(os.path.join(d, "cam0.jpg"))]


def project(cam, p, W, H):
    """Weltpunkt → Pixel (u, v), Tiefe z."""
    m = cam.GetMg(); off, v1, v2, v3 = T(m.off), norm(T(m.v1)), norm(T(m.v2)), norm(T(m.v3))
    d = sub(p, off); x, y, z = dot(d, v1), dot(d, v2), dot(d, v3)
    if z <= 1e-6: return None, None, z
    f = cam[c4d.CAMERA_FOCUS] / cam[c4d.CAMERAOBJECT_APERTURE] * W
    return W / 2 + f * x / z, H / 2 - f * y / z, z


def main():
    doc = c4d.documents.GetActiveDocument()
    rig, models_null = find(doc, "BnB_Rig"), find(doc, "Pfeil-Modelle")
    if not rig:
        c4d.gui.MessageDialog("Fehlt: 'BnB_Rig' – erst c4d_bullsnbier_cameras.py ausführen."); return
    if not models_null or not models_null.GetDown():
        if models_null: models_null.Remove()
        models_null = make_default_models(doc)
        c4d.gui.MessageDialog("'Pfeil-Modelle' fehlte – 4 einfache Platzhalter-Pfeile angelegt.\n"
                              "Eigene Modelle einfach darunter legen (Spitze = Ursprung, Pfeil entlang -Z) und Skript erneut starten.")
    cams = [c for c in rig.GetChildren() if c.GetType() == c4d.Ocamera]
    models = models_null.GetChildren()
    models_null.SetRenderMode(c4d.MODE_OFF); models_null.SetEditorMode(c4d.MODE_OFF)
    led, amb, hand = find(doc, "LED_Ring"), find(doc, "Umgebung"), find(doc, "Hand")
    hand_poly = first_poly(hand.GetDown()) if hand and hand.GetType() != c4d.Opolygon else hand
    base = {c.GetName(): c.GetMg() for c in cams}
    base_led = (led[c4d.LIGHT_BRIGHTNESS], led[c4d.LIGHT_COLOR]) if led else None
    base_amb = amb[c4d.LIGHT_BRIGHTNESS] if amb else None
    hand_base = hand.GetMg() if hand else None

    holder = find(doc, "BnB_Pfeile")
    if not holder:
        holder = c4d.BaseObject(c4d.Onull); holder.SetName("BnB_Pfeile"); doc.InsertObject(holder)
    while len(holder.GetChildren()) < 3:
        i = c4d.BaseObject(c4d.Oinstance); i.SetName("Pfeil %d" % (len(holder.GetChildren()) + 1)); i.InsertUnderLast(holder)
    inst = holder.GetChildren()[:3]

    rd = doc.GetActiveRenderData(); W, H = int(rd[c4d.RDATA_XRES]), int(rd[c4d.RDATA_YRES])
    bgs = bg_sets(); bg_shader = setup_background(doc) if bgs else None
    if BG_DIR and not bgs: print("Hinweis: BG_DIR ohne cam0.jpg … – rendere ohne Foto-Hintergrund.")
    bd = doc.GetActiveBaseDraw(); cam_before = bd.GetSceneCamera(doc)
    start = START
    if start == "auto":
        done = [int(d) for d in os.listdir(OUT) if d.isdigit() and os.path.exists(os.path.join(OUT, d, "labels.json"))] if os.path.isdir(OUT) else []
        start = max(done) + 1 if done else 0
        print("Starte bei Frame %d" % start)
    frames = [start] if PREVIEW else range(start, start + COUNT)
    if not PREVIEW and not os.path.isdir(OUT): os.makedirs(OUT)

    t0 = time.time()
    try:
        for n, fr in enumerate(frames):
            rng = random.Random(fr * 7919 + 13)
            # Kameras leicht verwackeln
            for c in cams:
                m = base[c.GetName()]
                off = add(T(m.off), tuple(rng.uniform(-CAM_POS_JIT, CAM_POS_JIT) for _ in range(3)))
                ax = norm((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))); ang = math.radians(rng.uniform(-CAM_ROT_JIT, CAM_ROT_JIT))
                c.SetMg(c4d.Matrix(V(off), V(rotate(T(m.v1), ax, ang)), V(rotate(T(m.v2), ax, ang)), V(rotate(T(m.v3), ax, ang))))
            # Licht
            if led:
                led[c4d.LIGHT_BRIGHTNESS] = base_led[0] * rng.uniform(0.55, 1.35)
                led[c4d.LIGHT_COLOR] = V(kelvin_rgb(rng.uniform(4000, 7500)))
            if amb:
                amb[c4d.LIGHT_BRIGHTNESS] = base_amb * rng.uniform(0.0, 1.6)
            # Pfeile
            k = rng.choices([0, 1, 2, 3], P_DARTS)[0]
            darts = []
            for i, ins in enumerate(inst):
                if i >= k:
                    ins.SetRenderMode(c4d.MODE_OFF); ins.SetEditorMode(c4d.MODE_OFF); continue
                for _ in range(20):   # nicht ineinander stecken
                    pt, kind = sample_point(rng)
                    if all(math.hypot(pt[0] - d["mm"][0], pt[1] - d["mm"][1]) > 9 for d in darts): break
                off, x, y, z, back = dart_frame((pt[0] / 10, pt[1] / 10), kind, rng)
                ins[c4d.INSTANCEOBJECT_LINK] = rng.choice(models)
                ins.SetMg(c4d.Matrix(V(off), V(x), V(y), V(z)))
                ins.SetRenderMode(c4d.MODE_UNDEF); ins.SetEditorMode(c4d.MODE_UNDEF)
                entry = (pt[0] / 10, pt[1] / 10, 0.0) if kind == "stuck" else off
                darts.append({"mm": pt, "kind": kind, "entry": entry, "back": back,
                              "score": score(*pt) if kind == "stuck" else "LOOSE"})
            # Hand
            show_hand = bool(hand) and rng.random() < P_HAND
            if hand:
                hand.SetRenderMode(c4d.MODE_UNDEF if show_hand else c4d.MODE_OFF)
                if show_hand:
                    hm = c4d.utils.HPBToMatrix(c4d.Vector(rng.uniform(-math.pi, math.pi), rng.uniform(-0.6, 0.6), rng.uniform(-math.pi, math.pi)))
                    hm.off = c4d.Vector(rng.uniform(-20, 20), rng.uniform(-20, 20), -rng.uniform(4, 18))
                    hand.SetMg(hm)
            doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)

            # Labels: Pixel je Kamera + Verdeckung
            rc = None
            if show_hand and hand_poly and hand_poly.GetType() == c4d.Opolygon:
                rc = c4d.utils.GeRayCollider(); rc.Init(hand_poly, True)
            labels = {}
            for ci, c in enumerate(cams):
                cpos = T(c.GetMg().off); out = []
                for di, d in enumerate(darts):
                    u, v, z = project(c, d["entry"], W, H)
                    vis = u is not None and 0 <= u < W and 0 <= v < H
                    why = "" if vis else "außerhalb"
                    if vis:
                        tip = d["entry"]
                        for dj, o in enumerate(darts):   # Pfeile als Kapseln: Barrel+Schaft dünn, Flight dick
                            a0 = add(o["entry"], mul(o["back"], 0.8 if dj == di else 0.0))
                            a1 = add(o["entry"], mul(o["back"], LEN - FLIGHT_LEN))
                            f0, f1 = a1, add(o["entry"], mul(o["back"], LEN))
                            if seg_dist(tip, cpos, a0, a1) < R_BARREL or seg_dist(tip, cpos, f0, f1) < R_FLIGHT:
                                vis, why = False, "Pfeil %d" % (dj + 1); break
                    if vis and rc:
                        ml = ~hand_poly.GetMg(); p0 = ml * V(cpos); p1 = ml * V(d["entry"]); dv = p1 - p0
                        if rc.Intersect(p0, dv.GetNormalized(), dv.GetLength() - 0.2):
                            vis, why = False, "Hand"
                    out.append({"u": round(u, 2) if u is not None else None, "v": round(v, 2) if v is not None else None,
                                "visible": vis, "hidden_by": why, "score": d["score"], "kind": d["kind"],
                                "board_mm": [round(d["mm"][0], 2), round(d["mm"][1], 2)]})
                labels["cam%d" % (ci + 1)] = out
            if PREVIEW:
                print(json.dumps(labels, indent=1)); break

            # Rendern
            fdir = os.path.join(OUT, "%06d" % fr)
            if not os.path.isdir(fdir): os.makedirs(fdir)
            bg_set = rng.choice(bgs) if bgs else None
            for ci, c in enumerate(cams):
                bd.SetSceneCamera(c)
                if bg_shader:   # Foto der passenden Kamera hinter die Szene
                    bg_shader[c4d.BITMAPSHADER_FILENAME] = os.path.join(bg_set, "cam%d.jpg" % ci)
                    doc.ExecutePasses(None, True, True, True, c4d.BUILDFLAGS_NONE)
                bmp = c4d.bitmaps.BaseBitmap(); bmp.Init(W, H, 24)
                if c4d.documents.RenderDocument(doc, rd.GetData(), bmp, c4d.RENDERFLAGS_EXTERNAL) != c4d.RENDERRESULT_OK:
                    raise RuntimeError("Rendern fehlgeschlagen (Frame %d, %s)" % (fr, c.GetName()))
                bc = c4d.BaseContainer(); bc[c4d.JPGSAVER_QUALITY] = rng.randint(*JPG_Q)
                bmp.Save(os.path.join(fdir, "cam%d.jpg" % (ci + 1)), c4d.FILTER_JPG, bc)
            with open(os.path.join(fdir, "labels.json"), "w") as fh:
                json.dump({"frame": fr, "res": [W, H], "hand": show_hand, "bg": os.path.basename(bg_set) if bg_set else None, "darts": len(darts), "cams": labels}, fh, indent=1)
            c4d.StatusSetBar(100.0 * (n + 1) / COUNT); el = time.time() - t0; eta = el / (n + 1) * (COUNT - n - 1)
            c4d.StatusSetText("BnB: Frame %d (%d/%d) · %.1f s/Frame · noch ca. %d min" % (fr, n + 1, COUNT, el / (n + 1), eta / 60))
            if n < 3 or n % 50 == 0: print("Frame %d: %.1f s/Frame, Rest ca. %.0f min" % (fr, el / (n + 1), eta / 60))
            st = c4d.BaseContainer()
            if c4d.gui.GetInputState(c4d.BFM_INPUT_KEYBOARD, c4d.KEY_ESC, st) and st[c4d.BFM_INPUT_VALUE]:
                print("Abgebrochen bei Frame %d – neu starten, START=\"auto\" macht automatisch weiter" % fr); break
    finally:
        if not PREVIEW:   # Szene zurücksetzen
            for c in cams: c.SetMg(base[c.GetName()])
            if led: led[c4d.LIGHT_BRIGHTNESS], led[c4d.LIGHT_COLOR] = base_led
            if amb: amb[c4d.LIGHT_BRIGHTNESS] = base_amb
            if hand: hand.SetMg(hand_base)
            if cam_before: bd.SetSceneCamera(cam_before)
        c4d.StatusClear(); c4d.EventAdd()


if __name__ == "__main__":
    main()
