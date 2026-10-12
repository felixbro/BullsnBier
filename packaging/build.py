"""Fertige App bauen (PyInstaller). Aufruf aus dem Repo-Ordner:  python packaging/build.py
Ergebnis: dist/BullsnBier/ (Ordner mit BullsnBier[.exe]) – unter Linux zusätzlich dist/BullsnBier-linux-x64.tar.gz"""
import os, platform, shutil, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
SEP = ";" if os.name == "nt" else ":"
args = [
    sys.executable, "-m", "PyInstaller", "run.py", "--name", "BullsnBier", "--noconfirm", "--clean", "--console",
    "--icon", os.path.join("packaging", "icon.ico"),
    "--add-data", f"app/static{SEP}app/static",
    "--collect-all", "piper", "--collect-all", "onnxruntime",
    "--collect-submodules", "uvicorn", "--collect-submodules", "websockets",
    "--hidden-import", "app.main",
]
for m in ("matplotlib", "pandas", "scipy", "tkinter", "PIL", "IPython", "pytest", "playwright", "lxml", "cryptography"):
    args += ["--exclude-module", m]
subprocess.check_call(args)
for f in ("README.md", "config.env.example", "packaging/linux-install.sh", "packaging/icon.png"):
    if f.endswith(".sh") and sys.platform.startswith("win"):
        continue
    shutil.copy(f, os.path.join("dist", "BullsnBier", os.path.basename(f).replace("linux-install", "install")))
if not sys.platform.startswith("win"):
    out = os.path.join("dist", f"BullsnBier-linux-{platform.machine().replace('x86_64', 'x64')}.tar.gz")
    with tarfile.open(out, "w:gz") as t:
        t.add(os.path.join("dist", "BullsnBier"), arcname="BullsnBier")
    print("→", out)
