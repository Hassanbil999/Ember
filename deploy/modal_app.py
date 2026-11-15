"""Deploy Freefall Atlas on Modal (modal.com) from the repo's own Dockerfile.

    pip install modal
    modal setup                         # once: signs this computer in through the browser
    modal deploy deploy/modal_app.py    # from the repo root; prints the public URL

The image is the same one as `docker build .`: one process (FastAPI) serves the built web app and the API
on port 8000, with the data loaded and the fire-check models trained at build time.

AI (summary and Ask) uses the Modal secret "freefall-ai", created in the Modal dashboard (Secrets → Custom) with
LLM_API_KEY, LLM_BASE_URL and LLM_MODEL (a free OpenAI-compatible tier such as Groq; see .env.example). The key
lives only in Modal, never in the repo. Without the secret, remove `secrets=` below: the app then falls back to
templates and NASA passages.
It scales to zero when nobody is using it, so idle time costs nothing; the first visit after a quiet
spell waits while it starts.
"""
import subprocess
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]

image = modal.Image.from_dockerfile(ROOT / "Dockerfile", context_dir=ROOT)
app = modal.App("freefall-atlas")


# Lean on purpose: the free Starter credit is small, and a container only costs while it is awake.
# 1 CPU and 1 GiB; it sleeps 3 minutes after the last visitor.
@app.function(image=image, cpu=1.0, memory=1024, timeout=3600, scaledown_window=180,
              secrets=[modal.Secret.from_name("freefall-ai")])
@modal.concurrent(max_inputs=50)
@modal.web_server(port=8000, startup_timeout=240)
def web():
    # the Dockerfile's CMD, run from its working directory
    subprocess.Popen("python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --log-level warning",
                     shell=True, cwd="/app")
