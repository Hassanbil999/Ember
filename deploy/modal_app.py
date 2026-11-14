"""Deploy Freefall Atlas on Modal (modal.com) from the repo's own Dockerfile.

    pip install modal
    modal setup                         # once: signs this computer in through the browser
    modal deploy deploy/modal_app.py    # from the repo root; prints the public URL

The container is the same one as `docker build .`: Next.js on port 7860 in front of the FastAPI API.
It scales to zero when nobody is using it, so idle time costs nothing; the first visit after a quiet
spell waits while it starts (about half a minute).
"""
import subprocess
from pathlib import Path

import modal

ROOT = Path(__file__).resolve().parents[1]

image = modal.Image.from_dockerfile(ROOT / "Dockerfile", context_dir=ROOT)
app = modal.App("freefall-atlas")


@app.function(image=image, cpu=2.0, memory=2048, timeout=3600, scaledown_window=600)
@modal.concurrent(max_inputs=50)
@modal.web_server(port=7860, startup_timeout=240)
def web():
    # start.sh starts the API, waits until it answers, then serves the site on $PORT (7860 in the image)
    subprocess.Popen(["/start.sh"])
