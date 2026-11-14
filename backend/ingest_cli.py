"""`python -m backend.ingest <step>`: every step is idempotent.

    canonical  the team's existing cleaning pipeline (backend/ingest.py), unchanged: raw PSI tables and
               PDFs → validated canonical tables in data/processed/. Its outputs are gitignored, so a
               clean checkout runs it once; it never edits data/raw/.
    all        every step in order (the default).
"""
from __future__ import annotations

import sys
import time

from .core.config import PROCESSED

STEPS = ["canonical"]
OUTPUTS = ["tests.parquet", "chunks.parquet"]          # what `run.py start` needs before it can serve


def outputs_present() -> bool:
    return all((PROCESSED / f).exists() for f in OUTPUTS)


def run_step(step: str) -> dict:
    if step == "canonical":
        from .ingest import run
        return run()
    raise SystemExit(f"unknown step {step!r}; choose from {', '.join(STEPS + ['all'])}")


def main(argv: list[str] | None = None) -> None:
    for _s in (sys.stdout, sys.stderr):        # Windows consoles default to cp1252 and choke on "→"
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    step = args[0] if args else "all"
    t0 = time.time()
    for s in (STEPS if step == "all" else [step]):
        run_step(s)
    print(f"ingest {step}: done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
