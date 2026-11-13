#!/usr/bin/env python
"""Task runner (same targets as the Makefile, works where `make` is not installed).

    python run.py setup | fetch | fixture | ingest | train | start | dev | api | web | test | audit | all | demo on|off

`start` builds the web app once and serves the fast production build (use this to show the app).
`dev` runs the slower hot-reload servers for development.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):        # Windows consoles/redirects default to cp1252 and choke on "→", "›"
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
NPM = shutil.which("npm") or "npm"


def sh(cmd, cwd=ROOT, **kw):
    print("›", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=cwd, env=ENV, check=True, **kw)


def setup():
    sh([PY, "-m", "pip", "install", "-r", "requirements.txt"])
    sh([NPM, "install", "--no-audit", "--no-fund"], cwd=ROOT / "frontend")


def fetch():
    """Download the real NASA PSI tables (checksum-verified) into data/raw/."""
    sh([PY, str(ROOT / "scripts" / "fetch_psi.py"), *sys.argv[2:]])


def fixture():
    sh([PY, "-m", "backend.fixture"])


def ingest():
    sh([PY, "-m", "backend.ingest"])


def train():
    sh([PY, "-c", "from backend.vision.pipeline import run_all; s = run_all(); print('vision mean |error| %', s['mean_abs_error_pct'])"])
    sh([PY, "-c", "from backend.models.surrogate import train_all; train_all()"])


def api():
    sh([PY, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"])


def web():
    sh([NPM, "run", "dev"], cwd=ROOT / "frontend")


def dev():
    if not (ROOT / "data" / "processed" / "tests.parquet").exists():
        all_()
    procs = [subprocess.Popen([PY, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT, env=ENV),
             subprocess.Popen([NPM, "run", "dev"], cwd=ROOT / "frontend", env=ENV, shell=os.name == "nt")]
    print("\n  Freefall Atlas → http://localhost:3000   (API http://127.0.0.1:8000/docs)\n")
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


def start():
    """Production mode: optimized build, no on-demand compilation. This is the fast path."""
    if not (ROOT / "data" / "processed" / "tests.parquet").exists():
        all_()
    sh([NPM, "run", "build"], cwd=ROOT / "frontend", shell=os.name == "nt")
    procs = [subprocess.Popen([PY, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"], cwd=ROOT, env=ENV),
             subprocess.Popen([NPM, "run", "start"], cwd=ROOT / "frontend", env=ENV, shell=os.name == "nt")]
    print("\n  Freefall Atlas → http://localhost:3000\n")
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


def audit():
    """Screens + timings of the running app → docs/audit/after/."""
    sh([PY, str(ROOT / "tests" / "audit_capture.py"), "after"])


def test():
    sh([PY, "-m", "pytest", "backend/tests", "-q"])
    smoke = ROOT / "tests" / "smoke_playwright.py"
    try:
        import playwright  # noqa: F401
        sh([PY, str(smoke)])
    except ImportError:
        print("playwright not installed — skipping browser smoke test")


def all_():
    fixture(); ingest(); train(); ingest()


def demo(state: str):
    on = state.lower() in ("on", "true", "1")
    (ROOT / "config" / "profile.yaml").write_text(
        "# Active data profile. `python run.py demo off|on`.\ninclude_demo: " + ("true" if on else "false") + "\n", encoding="utf-8")
    print(f"demo fixture {'enabled' if on else 'disabled'}; re-ingesting…")
    ingest(); train(); ingest()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    fns = {"setup": setup, "fetch": fetch, "fixture": fixture, "ingest": ingest, "train": train, "dev": dev, "start": start, "audit": audit, "api": api, "web": web,
           "test": test, "all": all_}
    if cmd == "demo":
        demo(sys.argv[2] if len(sys.argv) > 2 else "on")
    elif cmd in fns:
        fns[cmd]()
    else:
        print(__doc__)
