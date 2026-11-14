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


@pytest.mark.parametrize("tid", ["moon-base", "iss-cabin", "microgravity", "untested"])
def test_topics_separate_measured_inferred_untested(api, tid):
    t = api.get(f"/api/topic/{tid}").json()
    assert t["finding"] and t["grade"]["label"] and t["visual"]["kind"]
    for k in ("measured", "inferred", "untested"):
        assert t[k]["summary"] and isinstance(t[k]["items"], list)
    assert t["untested"]["items"], "every answer states what was never tested"
    assert t["sources"], "every answer cites a source passage"
    assert t["demo"] is False, "no synthetic test data is loaded any more"


def test_moon_base_answer_for_one_material(api):
    t = api.get("/api/topic/moon-base", params={"material": "PMMA"}).json()
    assert t["material"] == "PMMA" and "PMMA" in t["finding"] and "22.2%" in t["finding"]
    assert t["grade"]["label"] == "Not tested"               # no PMMA test at Moon-base oxygen, no test at lunar gravity
    assert any("Moon gravity" in i["text"] for i in t["untested"]["items"])
    assert all(m["verdict"].startswith("tested only at") for m in t["materials"]), "no real solid test reaches 30 % O2"


def test_moon_base_answer_uses_only_real_data(api):
    t = api.get("/api/topic/moon-base").json()
    assert "No solid material has ever been burned in orbit" in t["finding"]
    pts = t["visual"]["points"]
    assert pts and {p["dataset"] for p in pts} <= {"flex", "cfig_normal"}
    assert t["visual"]["band"]["o2_frac"][1] == pytest.approx(0.222)


def test_explore_and_insights_payloads(api):
    e = api.get("/api/explore").json()
    ids = {i["id"] for i in e["investigations"]}
    for g in e["groupings"].values():
        assert all(m in ids for grp in g for m in grp["members"])
    assert all(len(v) <= 4 for v in e["links"].values()), "only the strongest few relationships are sent"
    ins = api.get("/api/insights").json()["insights"]
    assert 5 <= len(ins) <= 8
    for i in ins:
        assert i["sentence"].endswith(".") and i["visual"]["kind"] and i["source"] and i["studio"]


def test_lab_grid_shape_and_domain(api):
    g = api.get("/api/lab/grid", params={"mode": "gas", "item": "30% butane"}).json()
    assert g["source"] == "real CFI-G gas-flame" and g["rate_label"] is None
    n = 1
    for a in g["axes"]:
        n *= len(a["values"])
    assert len(g["p"]) == len(g["rate"]) == len(g["dist"]) == n
    assert all(0 <= p <= 1 for p in g["p"])
    assert g["cv"]["accuracy"] > g["cv"]["baseline"], "the model is reported against its baseline"
    assert max(g["dist"]) > g["edge"], "the grid reaches beyond the tested range and says so"


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
def test_breathing_limits_match_the_nasa_briefs():
    from backend.atmosphere import breathing, pio2_mmhg
    assert pio2_mmhg(101.325, 0.21) == pytest.approx(149.7, abs=0.3)            # the brief's own worked example
    assert breathing(101.325, 0.21)["status"] == "normal"
    assert breathing(8.2 * 6.894757, 0.34)["status"] == "mild"                  # exploration atmosphere: just above the floor
    assert pio2_mmhg(8.2 * 6.894757, 0.34) == pytest.approx(128, abs=1.5)
    assert breathing(8.2 * 6.894757, 0.25)["status"] == "too_low"
    assert breathing(30.0, 0.9)["status"] == "too_rich"


def test_prebreathe_estimate_reproduces_known_protocols():
    from backend.atmosphere import prebreathe
    iss = prebreathe(14.7 * 6.894757, 0.21)
    assert iss["r0"] == pytest.approx(2.70, abs=0.02)
    assert 3.5 * 60 < iss["minutes"] < 4.6 * 60          # NASA's in-suit protocol from 14.7 psi is 4 hours
    assert prebreathe(8.2 * 6.894757, 0.34)["minutes"] == 0   # the reason the exploration atmosphere was chosen
    camp = prebreathe(10.2 * 6.894757, 0.265)
    assert 0 < camp["minutes"] < 90                       # the 10.2 psi campout leaves a short in-suit pre-breathe


def test_atmosphere_payload_cites_its_sources(api):
    a = api.get("/api/atmosphere").json()
    assert {r["id"] for r in a["references"]} == {"iss", "campout", "exploration"}
    assert all(s["url"].startswith("https://") and "nasa.gov" in s["url"] for s in a["sources"])
    assert a["constants"]["pio2_floor_mmhg"] == 127 and a["constants"]["r_accept"] == 1.65 and a["caveats"]


def test_every_place_ranks_every_investigation_with_reasons():
    from backend import relevance
    for p in relevance.places():
        d = relevance.rank(p["id"])
        scores = [r["score"] for r in d["rows"]]
        assert scores == sorted(scores, reverse=True) and len(d["rows"]) >= 15
        for r in d["rows"]:
            assert set(r["parts"]) == {"burns", "air", "gravity", "evidence"}
            assert all(0 <= part["score"] <= 3 and part["why"].endswith(".") for part in r["parts"].values())
            assert r["score"] == sum(part["score"] for part in r["parts"].values())


def test_partial_gravity_never_scores_as_tested():
    from backend import relevance
    for pid in ("moon_base", "rover", "mars"):
        d = relevance.rank(pid)
        assert not d["gravity_tested"]
        assert all(r["parts"]["gravity"]["score"] <= 2 for r in d["rows"])
        assert any("partial-gravity" in g["text"] for g in d["gaps"])
    assert all(r["parts"]["gravity"]["score"] == 3 for r in relevance.rank("iss")["rows"])


def test_demo_rows_never_count_as_real_evidence_in_the_ranking():
    """Full marks for evidence need real rows; demo-only rows score 1 and are marked; no rows score 0."""
    from backend import relevance
    from backend.core.store import get_store
    t = get_store().usable_tests()
    for r in relevance.rank("iss")["rows"]:
        mine = t[t.investigation_id == r["label"]]
        real = int((~mine.demo.astype(bool)).sum())
        ev = r["parts"]["evidence"]
        assert ev["score"] == (3 if real else 1 if len(mine) else 0)
        assert bool(ev.get("demo")) == (len(mine) > 0 and real == 0)
    assert next(r for r in relevance.rank("iss")["rows"] if r["label"] == "FLEX")["parts"]["evidence"]["score"] == 3
    rows = relevance.rank("iss")["rows"]
    assert not any(r["parts"]["evidence"].get("demo") for r in rows), "no demo rows are loaded any more"
    for label in ("BASS-II", "FLEX", "CFI-G", "Saffire-II"):       # real PSI tables now: full evidence score
        assert next(r for r in rows if r["label"] == label)["parts"]["evidence"]["score"] == 3, label


def test_missing_pressure_is_never_reported_as_a_mismatch():
    """A table with no pressure column is matched on oxygen only and says so; with neither value it is 'not known'."""
    from backend import relevance
    from backend.core.store import get_store
    t = get_store().usable_tests()
    for r in relevance.rank("iss")["rows"]:
        mine = t[t.investigation_id == r["label"]]
        air = r["parts"]["air"]
        if len(mine) and mine.pressure_kpa.isna().all():
            if mine.o2_frac.notna().any():
                assert air.get("o2_only") and air["score"] <= 2 and "oxygen only" in air["why"]
            else:
                assert air.get("unknown") and "neither" in air["why"]


def test_solids_are_matched_on_oxygen_alone_in_the_ranking():
    """BASS-II records no pressure: its air match must say so, never claim 0 tests in a place's air by pressure."""
    from backend import relevance
    iss = next(r for r in relevance.rank("iss")["rows"] if r["label"] == "BASS-II")["parts"]["air"]
    assert iss["score"] >= 1 and "records no pressure" in iss["why"]
    moon = next(r for r in relevance.rank("moon_base")["rows"] if r["label"] == "BASS-II")["parts"]["air"]
    assert moon["score"] == 0 and "22.2%" in moon["why"]
