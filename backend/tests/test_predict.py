"""Fire check: the rules that make its numbers trustworthy."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.predict import report, service
from backend.predict.problems import PROBLEMS, PSI, gas_fuel_parts

pytestmark = pytest.mark.skipif(not service.available(), reason="fire-check models not trained (python -m backend.ingest predict)")


@pytest.fixture(scope="module")
def client():
    from backend.api.main import app
    return TestClient(app)


def _real(problem: str):
    from backend.core.store import get_store
    t = get_store().usable_tests()
    if problem == "gas":
        r = t[(t.dataset == "cfig_normal") & t.burned.notna() & t.o2_frac.notna() & t.fuel_flow_mg_s.notna()].iloc[0]
        return r, {"problem": "gas", "fuel": r.fuel, "o2_pct": r.o2_frac * 100, "psi": r.pressure_kpa / PSI, "fuel_flow": r.fuel_flow_mg_s}
    r = t[(t.dataset == "flex") & t.burned.notna() & t.d0_mm.notna() & (t.diluent == "N2")].iloc[0]
    return r, {"problem": "droplet", "fuel": r.fuel, "o2_pct": r.o2_frac * 100, "psi": r.pressure_kpa / PSI, "d0_mm": r.d0_mm,
               "co2_pct": (r.co2_frac or 0) * 100, "he_pct": (r.he_frac or 0) * 100}


def test_fuel_labels_parse_into_what_the_fuel_is():
    assert gas_fuel_parts("30% butane") == ("butane", 4, 0.3)
    assert gas_fuel_parts("ethane") == ("ethane", 2, 1.0)
    assert gas_fuel_parts("kerosene") is None


@pytest.mark.parametrize("problem", ["gas", "droplet"])
def test_a_real_nasa_test_is_answered_by_the_tests(problem):
    row, req = _real(problem)
    res = service.check(req)
    assert res["zone"] == "tested"
    assert res["nearest"][0]["code"] == row.test_id and res["nearest"][0]["distance"] == 0
    assert res["tested"]["n"] >= 1


@pytest.mark.parametrize("change", [{"o2_pct": 60.0}, {"gravity_g": 0.166}, {"psi": 2.0}])
def test_no_number_outside_what_nasa_tested(change):
    _, req = _real("gas")
    res = service.check({**req, **change})
    assert res["zone"] == "untested" and res["estimate"] is None and res["quantities"] == []
    assert res["reasons"]
    assert res["nearest"], "the nearest real tests are still shown"


def test_models_are_used_only_if_they_beat_the_baseline_on_unseen_campaigns():
    for key in ("gas", "droplet"):
        card = json.loads((service.OUT / f"{key}.card.json").read_text(encoding="utf-8"))
        assert "GroupKFold by campaign" in card["validation"]
        base = card["comparison"][0]
        assert base["model"].startswith("baseline")
        if card["chosen"]:
            best = next(r for r in card["comparison"] if r["model"] == card["chosen"])
            assert best["brier"] < base["brier"] and best["log_loss"] < base["log_loss"]
        for rc in card["regressions"].values():
            if rc["chosen"]:
                best = next(r for r in rc["comparison"] if r["model"] == rc["chosen"])
                assert best["mae"] < rc["comparison"][0]["mae"]


def test_estimate_between_tests_has_a_range_and_drivers():
    res = service.check({"problem": "droplet", "fuel": "n-heptane", "o2_pct": 19, "psi": 14.7, "d0_mm": 3})
    assert res["zone"] in ("estimated", "tested")
    e = res["estimate"]
    assert 0 <= e["low"] <= e["high"] <= 1 and 0 <= e["probability"] <= 1
    assert {d["input"] for d in res["drivers"]} >= {"o2_pct", "d0_mm"}
    oxy = next(d for d in res["drivers"] if d["input"] == "o2_pct")
    size = next(d for d in res["drivers"] if d["input"] == "d0_mm")
    assert oxy["change_pts"] > 0 > size["change_pts"], "more oxygen helps, a bigger drop hurts (radiative extinction)"


def test_outside_reference_is_labelled_and_never_for_untested_fuels():
    _, req = _real("gas")
    ref = service.check({**req, "fuel": "propane"})["reference"]
    assert ref["values"] == {"N2": 11.5, "CO2": 14.5} and "Perry" in ref["source"]["label"]
    assert service.check(_real("droplet")[1])["reference"] is None


def test_api_and_report(client):
    _, req = _real("gas")
    r = client.post("/api/fire-check", json=req)
    assert r.status_code == 200 and r.json()["verdict"]
    assert client.get("/api/fire-check/meta").json()["gas"]["fuels"]
    assert client.post("/api/fire-check", json={**req, "fuel_flow": None}).status_code == 422
    assert client.post("/api/fire-check", json={**req, "fuel": "kerosene"}).status_code == 422
    rep = client.post("/api/fire-check/report", json=req)
    assert rep.status_code == 200 and "attachment" in rep.headers["content-disposition"]
    body = rep.text
    for s in ("Nearest NASA tests", "Model and validation", "Limits", "IBM+Plex+Sans", "IBM+Plex+Mono", "PSI-159"):
        assert s in body


def test_report_escapes_what_it_prints():
    res = service.check(_real("gas")[1])
    res["inputs"][0]["value"] = "<script>alert(1)</script>"
    html = report.render(res, datetime.now(timezone.utc))
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


@pytest.mark.parametrize("req", [
    {"problem": "gas", "fuel": "30% butane", "o2_pct": 38, "psi": 14.5, "fuel_flow": 1},
    {"problem": "droplet", "fuel": "n-heptane", "o2_pct": 13, "psi": 10.5, "d0_mm": 4},
])
def test_the_estimate_is_inside_the_range_shown_with_it(req):
    """These inputs once gave a full-data estimate just outside the range shown with it (e.g. 26 %, range 27–31 %)."""
    e = service.check(req)["estimate"]
    assert e and e["low"] <= e["probability"] <= e["high"]


def test_meta_gives_each_fuel_its_own_tested_range_and_the_tests_behind_it():
    m = service.meta()
    for key, pb in PROBLEMS.items():
        assert len(m[key]["points"]) == m[key]["card"]["n_tests"]
        assert {f["key"] for f in m[key]["features"]} == set(pb.features)
        for fuel, ranges in m[key]["ranges_by_fuel"].items():
            for f, (lo, hi) in ranges.items():
                plo, phi = m[key]["ranges"][f]
                assert plo <= lo <= hi <= phi, (key, fuel, f)
    # pure propane was only tested near sea-level pressure, though gas jets as a whole went down to ~7 psi
    assert m["gas"]["ranges_by_fuel"]["propane"]["psi"][0] > 13 > m["gas"]["ranges"]["psi"][0]


def test_model_cards_carry_the_roc_curve_behind_each_auc():
    """The Statistics page draws these lines; each must be the curve its reported AUC was computed from."""
    for key in PROBLEMS:
        card = service._bundle(key)["card"]
        for r in card["comparison"][1:]:
            roc = r["roc"]
            assert roc[0] == [0.0, 0.0] and roc[-1] == [1.0, 1.0]
            assert all(a[0] <= b[0] and a[1] <= b[1] for a, b in zip(roc, roc[1:]))
            area = sum((b[0] - a[0]) * (a[1] + b[1]) / 2 for a, b in zip(roc, roc[1:]))
            assert abs(area - r["auc"]) < 0.01, (key, r["model"], area, r["auc"])


def test_a_real_co2_mix_is_answered_not_always_untested():
    """NASA mixed 45–70 % CO₂ with nitrogen; the old input set CO₂ to everything but oxygen and was always untested."""
    from backend.core.store import get_store
    t = get_store().usable_tests("flex")
    r = t[(t.diluent == "CO2") & t.burned.notna() & t.d0_mm.notna()].iloc[0]
    res = service.check({"problem": "droplet", "fuel": r.fuel, "o2_pct": r.o2_frac * 100, "psi": r.pressure_kpa / PSI,
                         "d0_mm": r.d0_mm, "co2_pct": r.co2_frac * 100, "he_pct": 0})
    assert res["zone"] == "tested" and res["nearest"][0]["code"] == r.test_id
    with pytest.raises(ValueError):
        service.check({"problem": "droplet", "fuel": "n-heptane", "o2_pct": 40, "psi": 14.7, "d0_mm": 3, "co2_pct": 70})


def test_hints_are_per_fuel_and_airflow_is_explained():
    m = service.meta()
    assert m["gas"]["ranges_by_fuel"]["propane"]["psi"][0] > 13          # pure propane: tested near 1 atm only
    assert m["gas"]["ranges"]["psi"][0] < 8                               # all fuels together reach lower pressure
    assert "Airflow" in m["gas"]["not_in_data"] and "still air" in m["droplet"]["not_in_data"]


def test_untested_offers_the_nearest_tested_conditions():
    res = service.check({"problem": "gas", "fuel": "propane", "o2_pct": 34, "psi": 8.2, "fuel_flow": 1})
    assert res["zone"] == "untested" and res["suggestion"]
    s = res["suggestion"]
    again = service.check({"problem": "gas", "fuel": s["fuel"], "o2_pct": s["o2_pct"], "psi": s["psi"], "fuel_flow": s["fuel_flow"]})
    assert again["zone"] == "tested"
    assert service.check({"problem": "gas", "fuel": "propane", "o2_pct": 34, "psi": 14.7, "fuel_flow": 1, "gravity_g": 0.166})["suggestion"] is None


def test_burn_time_and_calibration_are_reported():
    res = service.check({"problem": "droplet", "fuel": "n-heptane", "o2_pct": 19, "psi": 14.7, "d0_mm": 3})
    assert any(q["label"] == "Burn time" and q["unit"] == "s" and q["low"] <= q["value"] <= q["high"] for q in res["quantities"])
    m = res["model"]
    assert 0 < m["skill"] < 1 and len(m["calibration"]) == 5 and "bootstrap" in m["range_method"]


def test_validation_errors_are_readable(client):
    r = client.post("/api/fire-check", json={"problem": "gas", "fuel": "propane", "o2_pct": 21, "psi": 0, "fuel_flow": 1})
    assert r.status_code == 422 and isinstance(r.json()["detail"], list)      # the web client turns this list into text


# ------------------------------------------------------------------ oxygen line and next tests
MOON_PROPANE = {"problem": "gas", "fuel": "propane", "o2_pct": 34, "psi": 8.2, "fuel_flow": 1.0}
ISS_METHANOL = {"problem": "droplet", "fuel": "methanol", "o2_pct": 21, "psi": 14.7, "d0_mm": 3}


def test_oxygen_line_shows_a_chance_only_where_a_single_check_would():
    res = service.check(ISS_METHANOL)
    ol = res["oxygen_line"]
    for p in ol["points"][::7]:
        single = service.check({**ISS_METHANOL, "o2_pct": p["o2_pct"]})
        assert p["zone"] == single["zone"]
        assert (p["p"] is None) == (single["zone"] == "untested")
        if p["p"] is not None:
            assert 0 <= p["low"] <= p["high"] <= 1, "the fold range is a real range"


def test_oxygen_line_crossing_sits_inside_the_estimated_stretch():
    L = service.check(ISS_METHANOL)["oxygen_line"]
    spans = L["estimated_spans"]
    assert L["line"]["o2_pct"] is not None
    assert any(a <= L["line"]["o2_pct"] <= b for a, b in spans)
    assert all(t["burned"] in (0, 1) for t in L["tests"]) and any(t["near_settings"] for t in L["tests"])


def test_untested_request_still_gets_next_tests_inside_the_hardware_range():
    res = service.check(MOON_PROPANE)
    assert res["zone"] == "untested" and res["estimate"] is None
    assert res["oxygen_line"]["line"] is None, "no line where nothing is estimated"
    nt = res["next_tests"]
    assert 1 <= len(nt) <= 3
    b = service._bundle("gas")
    feats = b["features"]
    for n in nt:
        for k, v in n["inputs"].items():
            col = b["X"][:, feats.index(k)]
            assert col.min() - 1e-6 <= v <= col.max() + 1e-6, f"{k} outside what the hardware has done"
        assert n["committee_low"] <= n["committee_high"] and n["nearest_distance"] > 0
    keys = list(nt[0]["inputs"])
    assert len({tuple(n["inputs"][k] for k in keys) for n in nt}) == len(nt), "three different experiments"


def test_report_has_the_line_and_the_next_tests(client):
    body = client.post("/api/fire-check/report", json=ISS_METHANOL).text
    assert "Where is the line?" in body and "<svg" in body and "50 % at" in body
    assert "Tests that would teach the model most" in body and "Query by committee" in body


def test_statistics_pipeline_cleaning_clusters_and_chance_map():
    """Statistics page: the funnel only shrinks and ends at the training set; every test is in one cluster; the
    Gaussian process map carries a number only where the fire check would give one."""
    from backend.predict import pipeline
    out = pipeline.build()
    for key in PROBLEMS:
        v, card = out[key], service._bundle(key)["card"]
        ns = [s["n"] for s in v["cleaning"]]
        assert ns == sorted(ns, reverse=True) and ns[-1] == card["n_tests"]
        c = v["clusters"]
        assert c["k"] in range(2, 7) and len(c["groups"]) == c["k"] and sum(g["n"] for g in c["groups"]) == card["n_tests"]
        assert {p["group"] for p in c["points"]} == set(range(1, c["k"] + 1)) and -1 <= c["ari_campaigns"] <= 1
        s = v["surface"]
        assert len(s["chance"]) == len(s["o2"]) * len(s["psi"])
        nums = [x for x in s["chance"] if x is not None]
        assert 0 < len(nums) < len(s["chance"]) and all(0 <= x <= 1 for x in nums)
        # spot-check one numbered cell against a real fire check at the same inputs
        i = s["chance"].index(nums[0])
        o2, psi = s["o2"][i % len(s["o2"])], s["psi"][i // len(s["o2"])]
        req = {"problem": key, "fuel": s["fuel"], "o2_pct": o2, "psi": psi}
        for h in s["held"]:
            req[{"Fuel flow (leak size)": "fuel_flow", "Drop size": "d0_mm", "CO₂ in the air": "co2_pct", "Helium in the air": "he_pct"}[h["label"]]] = h["value"]
        res = service.check(req)
        assert res["zone"] != "untested" and abs(res["estimate"]["probability"] - nums[0]) < 0.02
