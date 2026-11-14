"""`python -m backend.ingest <step>`: every step is idempotent.

    canonical  the team's existing cleaning pipeline (backend/ingest.py), unchanged: raw PSI tables and
               PDFs → validated canonical tables in data/processed/. Its outputs are gitignored, so a
               clean checkout runs it once; it never edits data/raw/.
    existing   map those tables onto the SPEC §5 model (backend/catalog/build.py): investigations,
               resources, test_points, resource_points, chunks. Reads only; never re-cleans.
    seed       add data/seed.json rows only where no real row exists (backend/catalog/seed.py)
    all        every step in order (the default).
"""
from __future__ import annotations

import sys
import time

from .core.config import PROCESSED

STEPS = ["canonical", "existing", "seed"]
OUTPUTS = ["tests.parquet", "atlas_resources.parquet", "atlas_test_points.parquet", "atlas_presets.parquet"]          # what `run.py start` needs before it can serve


def outputs_present() -> bool:
    return all((PROCESSED / f).exists() for f in OUTPUTS)


def run_step(step: str) -> dict:
    if step == "canonical":
        from .ingest import run
        return run()
    if step == "existing":
        from .catalog.build import run
        return run()
    if step == "seed":
        from .catalog.seed import run
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
