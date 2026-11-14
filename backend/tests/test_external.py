"""Evidence from outside NASA: read from its pinned file and never mixed into the NASA data."""
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


def test_card_says_not_nasa_and_computes_its_ratio_from_the_file():
    o = external.spread_card(0.30, "Moon base")
    assert o and o["doi"].startswith("10.5281/zenodo.") and "Not NASA data" in o["summary"]
    assert any("not orbit" in l for l in o["limits"])
    pts = external.zarm_spread()
    earth = [p["spread_mm_s"] for p in pts if p["o2_frac"] < 0.22]
    assert f"{pts[-1]['spread_mm_s'] / (sum(earth) / len(earth)):.1f}×" in o["finding"]


def test_outside_rows_never_enter_the_nasa_store():
    t = get_store().tests
    assert not t.dataset.str.contains("zarm|external", case=False).any()
