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
