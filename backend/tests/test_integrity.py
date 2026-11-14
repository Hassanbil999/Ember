"""Data integrity: impossible values are flagged before conversion, never derived from, never shown as normal."""
import re

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.core.store import get_store
from backend.core.units import is_flagged, normalize
from backend.record import gravity_label, test_record as build_record


@pytest.fixture(scope="module")
def st():
    return get_store()


@pytest.fixture(scope="module")
def api():
    from backend.api.main import app
    return TestClient(app)


# ---------------------------------------------------------------- validate before convert
@pytest.mark.parametrize("var,raw,unit", [
    ("pressure_kpa", "0 atm", None), ("pressure_kpa", "0", "psi"), ("pressure_kpa", "-3 kPa", None), ("pressure_kpa", 0, "kPa"),
    ("o2_frac", "130%", None), ("o2_frac", "-0.2", None), ("o2_frac", "140", None),
    ("d0_mm", "0 cm", None), ("flow_cm_s", "-4 mm/s", None), ("burn_rate_k_mm2_s", "-0.5", "mm^2/s"),
])
def test_impossible_raw_values_are_flagged_not_converted(var, raw, unit):
    value, steps = normalize(var, raw, unit)
    assert value is None
    assert is_flagged(steps)
    assert not any(s["op"] == "convert" for s in steps), "an impossible value must never be converted"


def test_unknown_unit_is_flagged_not_kept():
    value, steps = normalize("pressure_kpa", "14.7 furlongs")
    assert value is None and is_flagged(steps)


def test_valid_values_still_convert():
    value, steps = normalize("pressure_kpa", "1 atm")
    assert value == pytest.approx(101.325) and not is_flagged(steps)
    assert normalize("o2_frac", "0")[0] == 0.0            # zero oxygen is possible; zero pressure is not
    assert normalize("flow_cm_s", "0 cm/s")[0] == 0.0


def test_flagged_input_blocks_the_derived_value():
    from backend.adapters.base import tabular_to_canonical
    from backend.core import config
    raw = pd.DataFrame([{"Test ID": "T1", "O2": "0.30", "Pressure": "0 atm", "Outcome": "burned"},
                        {"Test ID": "T2", "O2": "0.30", "Pressure": "1 atm", "Outcome": "burned"}])
    cfg = {**config.datasets()["flex_demo"], "constants": {}}
    res = tabular_to_canonical(raw, "flex_demo", cfg, "unit-test.csv")
    bad, good = res.tests.iloc[0], res.tests.iloc[1]
    assert bad["pressure_kpa"] is None or pd.isna(bad["pressure_kpa"])
    assert bad["o2_pp_kpa"] is None or pd.isna(bad["o2_pp_kpa"])
    assert set(bad["invalid"]) == {"pressure_kpa", "o2_pp_kpa"}
    assert bad["invalid"]["o2_pp_kpa"].startswith("Not computed: input flagged")
    assert good["o2_pp_kpa"] == pytest.approx(0.30 * 101.325) and not good["invalid"]
    prov = [p for p in res.provenance if p["test_id"] == "T1" and p["variable"] == "o2_pp_kpa"]
    assert prov and prov[0]["steps"][0]["op"] == "not_computed"


def test_dataset_rows_with_impossible_values(st):
    bad = st.tests[st.tests["invalid"].map(bool)]
    assert "FLEX-114" in set(bad.index)                  # "0" pressure in the real FLEX table
    for tid, r in bad.iterrows():
        assert r["excluded"], f"{tid} must be excluded from charts and models"
        assert "impossible_value" in r["flags"]
        for var in r["invalid"]:
            assert pd.isna(r[var]), f"{tid}.{var} is flagged but still holds a number"
    assert not (st.usable_tests()["pressure_kpa"] <= 0).any()


# ---------------------------------------------------------------- nothing flagged renders as a normal value
def test_no_flagged_value_is_displayed_anywhere(st):
    """Every record of every test: flagged fields carry no value, only a reason."""
    for tid in st.tests.index:
        rec = build_record(tid)
        invalid = st.tests.at[tid, "invalid"]
        by_var = {f["var"]: f for f in rec["fields"]}
        for var in invalid:
            f = by_var[var]
            assert f["status"] == "flagged" and f["value"] is None and f["note"], (tid, var)
        for f in rec["fields"]:
            if f["status"] == "flagged":
                assert f["value"] is None
            if f["value"] is None:
                assert f["note"], f"{tid}.{f['var']}: a blank must say why"
            assert f["status"] in {"measured", "derived", "assumed", "flagged", "image", "blank"}


def test_impossible_pressure_record(st):
    """FLEX-114: the real PSI-69 table gives an ambient pressure of 0 mmHg for this test."""
    rec = build_record("FLEX-114")
    f = {x["var"]: x for x in rec["fields"]}
    assert rec["excluded"]
    assert f["pressure_kpa"]["status"] == "flagged" and "0 mmHg" in f["pressure_kpa"]["note"]
    assert f["o2_pp_kpa"]["status"] == "flagged" and f["o2_pp_kpa"]["note"].startswith("Not computed: input flagged")
    assert f["gravity_g"]["value"] == "Microgravity (ISS)" and f["gravity_g"]["status"] == "assumed"
    assert f["flow_cm_s"]["status"] == "assumed"
    assert f["burned"]["value"] == "Extinguished"
    assert f["burn_rate_k_mm2_s"]["status"] == "measured"      # droplets report a rate before extinction; it is kept
    assert f["campaign"]["status"] == "derived" and f["diluent"]["status"] == "derived"
    shown = " ".join(str(x["value"]) for x in rec["fields"] if x["value"])
    assert "0 kPa" not in shown and not re.search(r"\b0 g", shown)


def test_gravity_is_always_a_regime_name(st):
    assert gravity_label(0.0) == "Microgravity (ISS)" and gravity_label(1.0) == "Earth 1g"
    assert "Moon" in gravity_label(0.165) and "Mars" in gravity_label(0.38)
    for tid in list(st.tests.index)[:60]:
        for f in build_record(tid)["fields"]:
            if f["var"] == "gravity_g" and f["value"]:
                assert not re.match(r"^[\d.]+", f["value"]), "gravity must not be shown as a bare number"
            if f["var"] == "burned" and f["value"]:
                assert f["value"] in {"Burned", "Extinguished"}


def test_source_row_is_the_raw_file(api):
    r = api.get("/api/source/flex/row/115").json()
    hit = next(x for x in r["rows"] if x["n"] == 115)
    assert hit["cells"][0] == "114" and hit["cells"][r["columns"].index("Ambient pressure; mmHg")] == "0"


# ---------------------------------------------------------------- API payloads behind the new screens
def test_api_never_returns_a_flagged_number(api, st):
    rows = api.get("/api/tests?include_excluded=true").json()
    for r in rows:
        for var in r["invalid"]:
            assert r[var] is None
        assert r["outcome"] in {"Burned", "Extinguished", None}
        assert r["gravity"] is None or not r["gravity"][0].isdigit()












# ---------------------------------------------------------------- the real FLEX table (NASA PSI-69)
def test_real_flex_table_is_loaded_as_published(st):
    t = st.tests[st.tests.dataset == "flex"]
    assert len(t) == 274 and not t["demo"].any()
    assert set(t.fuel.dropna().unique()) == {"methanol", "n-heptane"}
    first = t.loc["FLEX-001"]
    assert first.pressure_kpa == pytest.approx(757.7 * 0.133322, rel=1e-4)      # mmHg → kPa
    assert first.o2_frac == 0.21 and first.d0_mm == 1.69 and first.burn_rate_k_mm2_s == 0.52
    assert first.test_end == "Disruption" and pd.isna(first.burned)           # disruption decides nothing about burning
    assert t.loc["FLEX-002"].burned == 0 and t.loc["FLEX-020"].burned == 1     # Extinction / Completion
    assert not st.tests[st.tests.dataset == "flex_demo"].shape[0], "the synthetic droplet set must not be mixed in"


def test_disruption_is_explained_not_blank(st):
    f = {x["var"]: x for x in build_record("FLEX-001")["fields"]}
    assert f["test_end"]["value"] == "Disruption"
    assert f["burned"]["value"] is None and "broke apart" in f["burned"]["note"]


# ---------------------------------------------------------------- atmosphere trade physiology (NASA OCHMO briefs)














