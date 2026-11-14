"""`python -m backend.ingest <step>`: every step is idempotent.

    canonical  the team's existing cleaning pipeline (backend/ingest.py), unchanged: raw PSI tables and
               PDFs → validated canonical tables in data/processed/. Its outputs are gitignored, so a
               clean checkout runs it once; it never edits data/raw/.
    existing   map those tables onto the SPEC §5 model (backend/catalog/build.py): investigations,
               resources, test_points, resource_points, chunks. Reads only; never re-cleans.
    psi        register files from the public PSI bucket (`psi --discover` → confirm data/psi_map.csv → `psi --fetch`)
    ntrs       register NASA NTRS reports from the committed snapshot data/raw/ntrs/ (`ntrs --fetch` refreshes it)
    text       load page-anchored chunks of the NTRS PDFs from data/raw/ntrs/text/ (`text --fetch` builds them)
    seed       add data/seed.json rows only where no real row exists (backend/catalog/seed.py)
    curate     add AI-extracted points and apply reviewer decisions from data/curation/ (backend/catalog/curate.py)
    fit        fit the simulator's parameters to verified test points, or keep the defaults (backend/sim/fit.py)
    index      rebuild the search index with the §5 resources (used by `q` and by Ask)
    extract    Claude proposes test points from NASA passages → data/curation/ai_extracted.json (needs a key, costs
               credits; not part of `all`); review them on /admin/verify
    all        every offline step in order (the default): no network, no API key
"""
from __future__ import annotations

import sys
import time

from .core.config import PROCESSED

STEPS = ["canonical", "existing", "psi", "ntrs", "text", "seed", "curate", "fit", "index"]
OUTPUTS = ["tests.parquet", "atlas_resources.parquet", "atlas_test_points.parquet", "atlas_presets.parquet"]          # what `run.py start` needs before it can serve


def outputs_present() -> bool:
    return all((PROCESSED / f).exists() for f in OUTPUTS)


def run_step(step: str, flags: list[str] | None = None) -> dict:
    flags = flags or []
    if step == "canonical":
        from .ingest import run
        return run()
    if step == "existing":
        from .catalog.build import run
        return run()
    if step == "psi":
        from .catalog import psi_bucket
        if "--discover" in flags:
            return psi_bucket.discover()
        if "--fetch" in flags:
            psi_bucket.fetch()
        return psi_bucket.run()
    if step == "ntrs":
        from .catalog import ntrs
        if "--fetch" in flags:
            ntrs.fetch()
        return ntrs.run()
    if step == "text":
        from .catalog import text
        if "--fetch" in flags:
            text.fetch()
        return text.run()
    if step == "seed":
        from .catalog.seed import run
        return run()
    if step == "curate":
        from .catalog.curate import run
        return run()
    if step == "extract":
        from .ai.extract import run
        return run()
    if step == "fit":
        from .sim.fit import run
        return run()
    if step == "index":
        from .search.index import build_index
        return build_index()
    raise SystemExit(f"unknown step {step!r}; choose from {', '.join(STEPS + ['extract', 'all'])}")


def main(argv: list[str] | None = None) -> None:
    for _s in (sys.stdout, sys.stderr):        # Windows consoles default to cp1252 and choke on "→"
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:] if argv is None else argv
    step = args[0] if args else "all"
    t0 = time.time()
    for s in (STEPS if step == "all" else [step]):
        run_step(s, args[1:])
    print(f"ingest {step}: done in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
