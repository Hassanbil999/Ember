"""Real NASA PSI tables: files are byte-identical to PSI, and the gas-flame adapter reads them faithfully."""
from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from backend.adapters import REGISTRY
from backend.adapters.psi_gas_flames import _yyddd
from backend.core import config
from backend.core.config import RAW
from backend.core.validate import validate

MANIFEST = json.loads((RAW / "psi_manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("ds_id", sorted(MANIFEST))
def test_raw_file_matches_psi_checksum(ds_id):
    """Catches line-ending conversion or hand edits: the file must be exactly what PSI served."""
    m = MANIFEST[ds_id]
    data = (RAW.parents[1] / m["path"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == m["sha256"], f"{m['path']} differs from the PSI file"


def _load(ds_id):
    cfg = config.datasets()[ds_id]
    res = REGISTRY[cfg["adapter"]](ds_id, cfg)
    df, _ = validate(res.tests, ds_id)
    return cfg, res, df


def _raw(ds_id):
    cfg = config.datasets()[ds_id]
    raw = pd.read_csv(RAW / ds_id / cfg["files"][0], dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw.columns = [c.strip() for c in raw.columns]
    return raw[raw["Test"].str.strip() != ""]


def test_cfig_every_row_loaded_with_unique_ids():
    _, _, df = _load("cfig_normal")
    assert len(df) == len(_raw("cfig_normal")) == 179
    assert df.test_id.is_unique and df.test_id.str.startswith("CFIG-").all()
    assert not df.excluded.any()


def test_cfig_outcome_comes_only_from_se_ft_column():
    _, _, df = _load("cfig_normal")
    raw = _raw("cfig_normal")
    end = raw["Self-ext or flow term"].str.strip().str.upper().values
    b = df["burned"].values
    assert all(x == 1 for x, e in zip(b, end) if e == "FT")
    assert all(x == 0 for x, e in zip(b, end) if e == "SE")
    assert all(pd.isna(x) for x, e in zip(b, end) if e not in ("FT", "SE")), "no hot ignition must not become an outcome"


def test_cfig_values_converted_and_traced():
    _, res, df = _load("cfig_normal")
    r = df.set_index("test_id").loc["CFIG-21088D1"]
    assert r.o2_frac == pytest.approx(0.382905163)
    assert r.pressure_kpa == pytest.approx(94.43956)            # 0.9443956 bar
    assert r.fuel_flow_mg_s == 1.0 and r.burned == 1
    assert r.mission_date == "2021-03-29" and r.campaign == "Day 1"
    p = [x for x in res.provenance if x["test_id"] == "CFIG-21088D1"]
    by = {x["variable"]: x for x in p}
    assert by["pressure_kpa"]["raw_value"] == "0.9443956" and by["pressure_kpa"]["column"] == "approx p (bar)"
    assert by["burned"]["column"] == "Self-ext or flow term"
    for v in ("mission_date", "campaign", "test_end"):
        assert by[v]["steps"][0]["op"] == "derive" and by[v]["raw_value"] is None


def test_flame_design_claims_no_outcome():
    _, _, df = _load("flame_design_normal")
    assert len(df) == 207 and df.test_id.is_unique
    assert "burned" not in df.columns or df["burned"].isna().all()
    ramped = _raw("flame_design_normal")["mfuel (mg/s)"].str.upper().str.startswith("RAMP").values
    assert df["fuel_flow_mg_s"].isna().values[ramped].all(), "a ramped flow is not a single value"


def test_yyddd_dates():
    assert _yyddd("21088A1") == "2021-03-29"
    assert _yyddd("19115 B2") == "2019-04-25"
    assert _yyddd("A1") == "" and _yyddd("21999") == ""


def test_new_tables_are_real_and_in_the_store():
    from backend.core.store import get_store
    t = get_store().tests
    for ds in ("cfig_normal", "flame_design_normal"):
        assert not config.datasets()[ds]["demo"]
        assert (t.dataset == ds).sum() > 100 and not t.loc[t.dataset == ds, "demo"].any()


def test_gas_flame_question_is_answered_from_real_cfig_data():
    from backend.answer.engine import answer
    a = answer("Does a gas flame keep burning at 35% oxygen?")
    assert a["key"] and all(s["dataset"] == "cfig_normal" for s in a["key"])
    assert "still burning when the fuel flow was stopped" in a["key"][0]["text"]
    assert not a["dropped"], "every sentence must pass the verifier"
    assert [d["demo"] for d in a["data"]] == [False], "the evidence must be the real table only"
    assert a["chart"]["dataset"] == "cfig_normal"


# ------------------------------------------------------------------ solids (BASS-II, BASS, SAFFIRE)
def test_bass2_rows_and_no_invented_outcome():
    cfg, res, df = _load("bass2")
    assert len(df) == 129 and df.test_id.is_unique and not df.excluded.any()
    assert "burned" not in df.columns or df["burned"].isna().all(), "BASS-II has no burned/went-out column"
    assert df.o2_frac.min() == pytest.approx(0.136) and df.o2_frac.max() == pytest.approx(0.222)
    ends = df.test_end.value_counts().to_dict()
    assert ends["Flame went out when the airflow was lowered"] == 17 and ends["Flame blew off when the airflow was raised"] == 7


def test_bass2_reads_text_and_says_so():
    _, res, df = _load("bass2")
    r = df.set_index("test_id").loc["BASS2-O4"]
    assert r.material == "PMMA" and r.sample_shape == "rod" and r.diameter_mm == pytest.approx(9.525)   # 3/8 inch
    assert r.o2_frac == pytest.approx(0.148) and r.mission_date == "2014-07-08"
    by = {p["variable"]: p for p in res.provenance if p["test_id"] == "BASS2-O4"}
    assert "every rod sample that is named" in by["material"]["steps"][0]["detail"]   # inferred, and the panel says why
    assert by["test_end"]["raw_value"].startswith("Fan display: 5 0.7")
    assert df.set_index("test_id").loc["BASS2-B1"].thickness_mm == pytest.approx(0.1)  # "100 micron"


def test_saffire2_flight_and_ground_rows():
    _, _, df = _load("saffire2")
    d = df.set_index("test_id")
    assert len(df) == 18 and (df.gravity_g == 0).sum() == 9 and (df.gravity_g == 1).sum() == 9
    for s in ("2-1", "2-2", "2-3", "2-4"):                       # silicone: no spread in microgravity
        assert d.loc[f"SAF2-{s}-UG", "material"] == "Silicone" and d.loc[f"SAF2-{s}-UG", "burned"] == 0
    assert d.loc["SAF2-2-1-1G", "burned"] == 1                    # ... while the same sample burned at 1g
    assert d.loc["SAF2-2-5-UG", "burned"] == 1 and d.loc["SAF2-2-5-UG", "spread_rate_mm_s"] == pytest.approx(2.1)
    assert pd.isna(d.loc["SAF2-2-7-UG", "burned"]) and "Nomex was not ignited" in d.loc["SAF2-2-7-UG", "test_end"]
    assert pd.isna(d.loc["SAF2-2-9-UG", "burned"]) and "anchored at the base" in d.loc["SAF2-2-9-UG", "test_end"]
    assert pd.isna(d.loc["SAF2-2-1-1G", "o2_frac"]), "no oxygen level is given for the ground tests"
    assert d.loc["SAF2-2-6-UG", "material"] == "Cotton-fiberglass fabric (SIBAL)"     # blank cell, row above


def test_bass_run_list_flags_impossible_dates():
    _, res, df = _load("bass")
    d = df.set_index("test_id")
    assert len(df) == 122 and df.test_id.is_unique
    assert pd.isna(d.loc["BASS-104-50", "mission_date"])
    why = next(p for p in res.provenance if p["test_id"] == "BASS-104-50" and p["variable"] == "mission_date")
    assert "2103" in why["steps"][0]["detail"] and "not corrected" in why["steps"][0]["detail"]
    soot = df[df.test_end.fillna("").str.startswith("Soot")]
    assert len(soot) == 1 and soot.material.isna().all()


def test_no_real_solid_test_reaches_moon_base_oxygen():
    """The fact the Moon-base answer rests on: real solid tests stop at 22.2 % O2."""
    from backend.core.store import get_store
    t = get_store().tests
    solids = t[t.dataset.isin(["bass2", "bass", "saffire1", "saffire2", "saffire3"])]
    assert solids.o2_frac.max() == pytest.approx(0.222)
