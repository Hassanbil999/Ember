"""Fire check: the rules that make its numbers trustworthy."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.predict import report, service
from backend.predict.problems import PSI, gas_fuel_parts

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
    return r, {"problem": "droplet", "fuel": r.fuel, "o2_pct": r.o2_frac * 100, "psi": r.pressure_kpa / PSI, "d0_mm": r.d0_mm, "diluent": "N2"}


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
    res = service.check({"problem": "droplet", "fuel": "n-heptane", "o2_pct": 19, "psi": 14.7, "d0_mm": 3, "diluent": "N2"})
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
    for s in ("Nearest NASA tests", "Model and validation", "Limits", "IBM+Plex+Sans", "Barlow+Condensed", "PSI-159"):
        assert s in body


def test_report_escapes_what_it_prints():
    res = service.check(_real("gas")[1])
    res["inputs"][0]["value"] = "<script>alert(1)</script>"
    html = report.render(res, datetime.now(timezone.utc))
    assert "<script>alert(1)</script>" not in html and "&lt;script&gt;" in html


# ------------------------------------------------------------------ oxygen line and next tests
MOON_PROPANE = {"problem": "gas", "fuel": "propane", "o2_pct": 34, "psi": 8.2, "fuel_flow": 1.0}
ISS_METHANOL = {"problem": "droplet", "fuel": "methanol", "o2_pct": 21, "psi": 14.7, "d0_mm": 3, "diluent": "N2"}


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
