"""Evidence from outside NASA: read from its pinned file, labelled, and never mixed into the NASA data."""
from __future__ import annotations

import hashlib

import pandas as pd

from backend import external
from backend.core.store import get_store
from scripts.fetch_psi import DOCUMENTS

ROOT = external.ROOT


def test_zarm_file_matches_pinned_checksum():
    pinned = {name: sha for folder, name, sha, _ in DOCUMENTS if folder == "external"}
    src = external.sources()["zarm_barriers"]
    data = (ROOT / src["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == pinned["zarm_metal_barriers_index.csv"]


def test_points_are_the_files_continuous_strips_with_a_rate():
    """Every value shown is a value in the file: no barrier samples, nothing typed by hand."""
    raw = pd.read_csv(ROOT / external.sources()["zarm_barriers"]["file"])
    full = raw[raw["Gaps [Sequence]"].isna() & raw["Propagation Rate [mm/s]"].notna()]
    pts = external.zarm_spread()
    assert len(pts) == len(full) >= 3
    for p in pts:
        row = full[full["Experiment [ID]"].astype(str) == p["id"]].iloc[0]
        assert p["spread_mm_s"] == row["Propagation Rate [mm/s]"]
        assert p["o2_frac"] == row["Oxygen [mole/mole]"]
        assert p["pressure_kpa"] == row["Pressure [kPa]"]


# The Moon-base and ISS card tests went with the old answer screens (backend/topics.py), removed in the rebuild.


def test_outside_rows_never_enter_the_nasa_store():
    t = get_store().tests
    assert not t.dataset.str.contains("zarm|external", case=False).any()
    assert "external" not in set(t.dataset)
