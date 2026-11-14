#!/usr/bin/env python
"""Task runner (the Makefile calls the same targets).

    python run.py start          one command from a clean checkout: install what is missing, ingest if
                                 needed, build the web app if needed, serve app + API on http://localhost:8000
    python run.py dev            API with auto-reload on :8000 + Vite dev server on :5173
    python run.py ingest [step]  canonical | existing | seed | fit | all (default all); see backend/ingest_cli.py
    python run.py fetch          re-download the PSI tables and check their checksums
    python run.py test           backend tests (pytest) + model parity (vitest) + browser smoke test (Playwright)
    python run.py e2e            browser smoke test only (starts the app itself)
    python run.py setup          install Python and Node dependencies
    python run.py build          build the web app into web/dist
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):        # Windows consoles/redirects default to cp1252 and choke on "→", "›"
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONWARNINGS": "ignore"}
NPM = shutil.which("npm") or "npm"
SHELL = os.name == "nt"          # npm is a .cmd on Windows
PORT = os.environ.get("PORT", "8000")


def sh(cmd, cwd=ROOT, **kw):
    print("›", " ".join(map(str, cmd)))
    return subprocess.run(cmd, cwd=cwd, env=ENV, check=True, **kw)


def _python_deps_ok() -> bool:
    return all(importlib.util.find_spec(m) for m in ("fastapi", "uvicorn", "pandas", "duckdb", "rank_bm25", "pymupdf", "sklearn", "scipy", "anthropic"))


def setup():
    sh([PY, "-m", "pip", "install", "-r", "requirements.txt"])
    if WEB.exists():
        sh([NPM, "ci", "--no-audit", "--no-fund"], cwd=WEB, shell=SHELL)


def fetch():
    """Download the real NASA PSI tables (checksum-verified) into data/raw/."""
    sh([PY, str(ROOT / "scripts" / "fetch_psi.py"), *sys.argv[2:]])


def ingest(step: str | None = None):
    sh([PY, "-m", "backend.ingest", step or (sys.argv[2] if len(sys.argv) > 2 else "all")])


def _web_stale() -> bool:
    built = WEB / "dist" / "index.html"
    if not built.exists():
        return True
    newest = max((p.stat().st_mtime for d in ("src", "public") if (WEB / d).exists()
                  for p in (WEB / d).rglob("*") if p.is_file()), default=0)
    newest = max([newest] + [(WEB / f).stat().st_mtime for f in ("index.html", "package.json", "vite.config.ts") if (WEB / f).exists()])
    return newest > built.stat().st_mtime


def build():
    if not WEB.exists():
        return
    if not (WEB / "node_modules").exists():
        sh([NPM, "ci", "--no-audit", "--no-fund"], cwd=WEB, shell=SHELL)
    sh([NPM, "run", "build"], cwd=WEB, shell=SHELL)


def _ensure_ready():
    if not _python_deps_ok():
        sh([PY, "-m", "pip", "install", "-r", "requirements.txt"])
    sys.path.insert(0, str(ROOT))
    from backend.ingest_cli import outputs_present
    if not outputs_present():
        ingest("all")
    if WEB.exists() and _web_stale():
        build()


def start():
    """Production mode: one process serves the built web app and the API on one port."""
    _ensure_ready()
    print(f"\n  Freefall Atlas → http://localhost:{PORT}   (API docs at /docs)\n")
    sh([PY, "-m", "uvicorn", "backend.api.main:app", "--host", os.environ.get("HOST", "127.0.0.1"), "--port", PORT,
        "--log-level", "warning"])


def api():
    sh([PY, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", PORT, "--reload", "--reload-dir", "backend"])


def dev():
    _ensure_ready()
    procs = [subprocess.Popen([PY, "-m", "uvicorn", "backend.api.main:app", "--host", "127.0.0.1", "--port", PORT, "--reload",
                               "--reload-dir", "backend"], cwd=ROOT, env=ENV)]
    if WEB.exists():
        procs.append(subprocess.Popen([NPM, "run", "dev"], cwd=WEB, env=ENV, shell=SHELL))
    print(f"\n  Freefall Atlas (dev) → http://localhost:5173   (API http://127.0.0.1:{PORT}/docs)\n")
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


def e2e():
    if not WEB.exists():
        print("no web app yet — skipping browser smoke test")
        return
    _ensure_ready()
    sh([NPM, "run", "e2e"], cwd=WEB, shell=SHELL)


def test():
    sh([PY, "-m", "pytest", "backend/tests", "-q"])
    if WEB.exists():
        if not (WEB / "node_modules").exists():
            sh([NPM, "ci", "--no-audit", "--no-fund"], cwd=WEB, shell=SHELL)
        sh([NPM, "test"], cwd=WEB, shell=SHELL)          # vitest: the browser model matches the server's
    e2e()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    fns = {"setup": setup, "fetch": fetch, "ingest": ingest, "build": build, "start": start, "dev": dev, "api": api,
           "test": test, "e2e": e2e}
    if cmd in fns:
        fns[cmd]()
    else:
        print(__doc__)
