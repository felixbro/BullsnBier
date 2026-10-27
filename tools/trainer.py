"""Bulls'n'Bier · Trainer – drei Knöpfe: Herunterladen · Trainieren · Veröffentlichen.

Start: Doppelklick auf BnB-Trainer.bat (Windows) bzw.  .venv/bin/python tools/trainer.py
Einstellungen landen in tools/trainer.json (nicht im Git).
"""
import csv, glob, json, os, queue, shutil, subprocess, sys, tempfile, threading, time, zipfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from app.sync import Remote  # noqa: E402

CFG = os.path.join(ROOT, "tools", "trainer.json")
REAL = os.path.join(ROOT, "tipdata_real")
HIST = os.path.join(ROOT, "tipdata", "history")
MODEL = os.path.join(ROOT, "data", "models", "tips.onnx")
DEF = {"url": "", "user": "", "pass": "", "render": r"C:\BnB_Render", "epochs": 30}


def load_cfg():
    try:
        return {**DEF, **json.load(open(CFG, encoding="utf-8"))}
    except Exception:
        return dict(DEF)


def run_dir():
    for d in (os.path.join("tipdata", "runs", "tips"), os.path.join("runs", "detect", "tipdata", "runs", "tips")):
        if os.path.exists(os.path.join(d, "weights", "best.pt")):
            return d
    return None


def best_map(d):
    """Beste mAP50-95 aus results.csv."""
    try:
        rows = list(csv.DictReader(open(os.path.join(d, "results.csv"))))
        key = next(k for k in rows[0] if "mAP50-95" in k)
        return round(max(float(r[key]) for r in rows), 3)
    except Exception:
        return None


class App:
    def __init__(self, root):
        self.root, self.cfg, self.q, self.busy = root, load_cfg(), queue.Queue(), False
        root.title("Bulls'n'Bier · Trainer")
        root.geometry("860x620")
        f = ttk.Frame(root, padding=14); f.pack(fill="both", expand=True)
        self.v = {k: tk.StringVar(value=str(self.cfg[k])) for k in DEF}
        rows = [("Cloud-Ordner (WebDAV-URL)", "url"), ("Benutzer", "user"), ("App-Passwort", "pass"),
                ("Render-Ordner", "render"), ("Epochen", "epochs")]
        for i, (lbl, k) in enumerate(rows):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(f, textvariable=self.v[k], width=80, show="•" if k == "pass" else "")
            e.grid(row=i, column=1, sticky="we", pady=2)
            if k == "render":
                ttk.Button(f, text="…", width=3, command=self.pick).grid(row=i, column=2)
        f.columnconfigure(1, weight=1)
        b = ttk.Frame(f); b.grid(row=len(rows), column=0, columnspan=3, pady=12, sticky="we")
        self.btns = [ttk.Button(b, text="1 · Herunterladen", command=lambda: self.go(self.download)),
                     ttk.Button(b, text="2 · Trainieren", command=lambda: self.go(self.train)),
                     ttk.Button(b, text="3 · Veröffentlichen", command=lambda: self.go(self.publish))]
        for x in self.btns:
            x.pack(side="left", expand=True, fill="x", padx=4, ipady=8)
        self.info = ttk.Label(f, text=""); self.info.grid(row=len(rows) + 1, column=0, columnspan=3, sticky="w")
        self.log = tk.Text(f, height=20, bg="#202020", fg="#DDF96A", font=("Consolas", 9))
        self.log.grid(row=len(rows) + 2, column=0, columnspan=3, sticky="nsew")
        f.rowconfigure(len(rows) + 2, weight=1)
        self.refresh(); root.after(200, self.pump)

    # ── Helfer ──
    def pick(self):
        d = filedialog.askdirectory(initialdir=self.v["render"].get() or ROOT)
        if d:
            self.v["render"].set(d)

    def save(self):
        self.cfg = {k: (int(v.get() or 30) if k == "epochs" else v.get().strip()) for k, v in self.v.items()}
        json.dump(self.cfg, open(CFG, "w", encoding="utf-8"), indent=1)

    def remote(self):
        if not self.cfg["url"]:
            raise RuntimeError("Cloud-Ordner fehlt")
        return Remote(self.cfg["url"], self.cfg["user"], self.cfg["pass"])

    def say(self, s):
        self.q.put(s.rstrip("\n") + "\n")

    def pump(self):
        while not self.q.empty():
            s = self.q.get()
            if s.startswith("\r"):
                self.log.delete("end-2l", "end-1l")
            self.log.insert("end", s.lstrip("\r")); self.log.see("end")
        self.root.after(200, self.pump)

    def refresh(self):
        n = sum("meta.json" in f for _, _, f in os.walk(REAL)) if os.path.isdir(REAL) else 0
        d = run_dir()
        self.info.config(text=f"Echte Würfe lokal: {n} · letztes Training: Genauigkeit {best_map(d) if d else '–'} · "
                              f"Modell: {'vorhanden' if os.path.exists(MODEL) else 'fehlt'}")

    def go(self, fn):
        if self.busy:
            return
        self.save(); self.busy = True
        for x in self.btns:
            x.state(["disabled"])

        def work():
            try:
                fn()
            except Exception as e:
                self.say(f"FEHLER: {e}")
                self.root.after(0, lambda: messagebox.showerror("Fehler", str(e)))
            finally:
                self.busy = False
                self.root.after(0, lambda: ([x.state(["!disabled"]) for x in self.btns], self.refresh()))
        threading.Thread(target=work, daemon=True).start()

    # ── 1 · Herunterladen ──
    def download(self):
        r = self.remote()
        done_f = os.path.join(REAL, "_downloaded.json")
        os.makedirs(REAL, exist_ok=True)
        done = set(json.load(open(done_f))) if os.path.exists(done_f) else set()
        new = 0
        files = []   # (Board, Pfad in der Cloud) – Ordner train/<Board>/ oder flache Ablage train/<Board>__batch_….zip
        for e in r.ls("train"):
            if e.endswith(".zip"):
                files.append((e.split("__")[0] if "__" in e else "Board", f"train/{e}"))
            else:
                files += [(e, f"train/{e}/{z}") for z in r.ls(f"train/{e}") if z.endswith(".zip")]
        for setup, path in files:
                key = path[len("train/"):]
                if key in done:
                    continue
                self.say(f"↓ {key}")
                tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False); tmp.close()
                r.get(path, tmp.name)
                with zipfile.ZipFile(tmp.name) as zf:
                    zf.extractall(os.path.join(REAL, setup))
                os.remove(tmp.name)
                done.add(key); new += 1
                json.dump(sorted(done), open(done_f, "w"))
        self.say(f"Fertig: {new} neue Pakete." if new else "Nichts Neues in der Cloud.")

    # ── 2 · Trainieren ──
    def train(self):
        d = run_dir()
        os.makedirs(HIST, exist_ok=True)
        base = "yolo11n.pt"
        if d:   # bisheriges Modell sichern und darauf aufbauen (Feinschliff statt von vorn)
            base = os.path.join(HIST, f"best_{time.strftime('%Y%m%d-%H%M')}.pt")
            shutil.copyfile(os.path.join(d, "weights", "best.pt"), base)
            self.say(f"Basis: {os.path.relpath(base)} (Genauigkeit bisher {best_map(d)})")
        cmd = [sys.executable, "-u", os.path.join("tools", "train_tips.py"), "--model", base, "--epochs", str(self.cfg["epochs"])]
        if self.cfg["render"] and os.path.isdir(self.cfg["render"]):
            cmd += ["--render", self.cfg["render"]]
        for p in sorted(glob.glob(os.path.join(REAL, "*"))):
            if os.path.isdir(p):
                cmd += ["--app", p]
        self.say("> " + " ".join(cmd[2:]))
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        buf = b""
        while True:
            ch = p.stdout.read(1)
            if not ch:
                break
            if ch in b"\r\n":
                if buf.strip():
                    self.say(("\r" if ch == b"\r" else "") + buf.decode("utf-8", "replace"))
                buf = b""
            else:
                buf += ch
        if p.wait() != 0:
            raise RuntimeError("Training abgebrochen – siehe Log")
        self.say(f"Training fertig · Genauigkeit {best_map(run_dir())}")

    # ── 3 · Veröffentlichen ──
    def publish(self):
        if not os.path.exists(MODEL):
            raise RuntimeError("data/models/tips.onnx fehlt – erst trainieren")
        r = self.remote()
        old = r.get("models/latest.json")
        old = json.loads(old) if old else {}
        d = run_dir()
        info = {"version": time.strftime("%Y-%m-%d %H:%M:%S"), "map": best_map(d) if d else None,
                "real": sum("meta.json" in f for _, _, f in os.walk(REAL)) if os.path.isdir(REAL) else 0}
        ok = []
        self.root.after(0, lambda: ok.append(messagebox.askyesno(
            "Veröffentlichen?", f"Neu:  Genauigkeit {info['map']} · {info['real']} echte Würfe\n"
                                f"Cloud: {old.get('version', '–')} · Genauigkeit {old.get('map', '–')}\n\nNeues Modell hochladen?")))
        while not ok:
            time.sleep(0.1)
        if not ok[0]:
            return self.say("Abgebrochen.")
        self.say("Ordner prüfen …")
        r.mkdirs("models/archiv")
        if old and "tips.onnx" in r.ls("models"):   # Vorgänger in der Cloud aufheben (serverseitig kopieren)
            name = f"models/archiv/tips_{str(old.get('version', 'alt')).replace(':', '').replace(' ', '_')}.onnx"
            self.say(f"Altes Modell → {name}")
            try:
                r.copy("models/tips.onnx", name)
            except Exception as e:
                self.say(f"  Archivieren übersprungen: {e}")
        self.say(f"Lade tips.onnx hoch ({os.path.getsize(MODEL) / 1e6:.1f} MB) …")
        r.put_file("models/tips.onnx", MODEL)
        self.say("Schreibe latest.json …")
        r.put_bytes("models/latest.json", json.dumps(info).encode())
        self.say(f"Veröffentlicht: {info['version']} – am Darts-Rechner unter Kameras › Trainingsdaten installieren.")


if __name__ == "__main__":
    tk_root = tk.Tk()
    App(tk_root)
    tk_root.mainloop()
