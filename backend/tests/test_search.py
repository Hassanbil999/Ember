"""Search quality on a small labeled query set, query parsing, latency, API smoke."""
import time

import pytest
from fastapi.testclient import TestClient

from backend.search.index import search
from backend.search.query_parser import parse

# query → item ids that must appear in the top-k
LABELED = [
    ("smoke detection", ["inv:SAME", "concept:smoke-detection"], 5),
    ("dust aerosol background", ["inv:DAFT"], 6),
    ("droplet extinction in helium", ["concept:inert-diluents"], 5),
    ("d2 law burning rate", ["concept:d2-law"], 3),
    ("moon base atmosphere", ["concept:exploration-atmosphere"], 3),
    ("partial gravity", ["concept:partial-gravity-gap"], 3),
    ("BASS-II", ["inv:BASS-II"], 2),
    ("cool flames", ["concept:cool-flames"], 3),
    ("soot smoke point co-flow", ["inv:SPICE"], 5),
    ("flame spread over solids in ventilation flow", ["concept:flame-spread"], 6),
    ("85% oxygen gaseous flames", ["inv:CFI-G"], 5),
    ("electric field flames", ["inv:E-FIELD Flames"], 3),
]


@pytest.mark.parametrize("q,expected,k", LABELED)
def test_labeled_queries(q, expected, k):
    ids = [r["id"] for r in search(q, k=k)["results"]]
    for e in expected:
        assert e in ids, f"{e} not in top-{k} for '{q}': {ids}"


def test_mean_reciprocal_rank():
    rr = []
    for q, expected, _ in LABELED:
        ids = [r["id"] for r in search(q, k=20)["results"]]
        rr.append(max((1 / (ids.index(e) + 1) for e in expected if e in ids), default=0))
    assert sum(rr) / len(rr) > 0.6


@pytest.mark.parametrize("q,var,val", [
    ("30 percent oxygen", "o2_frac", 0.30), ("0.3 O2", "o2_frac", 0.30), ("30% O₂", "o2_frac", 0.30),
    ("10 psi", "pressure_kpa", 68.95), ("70 kPa", "pressure_kpa", 70.0), ("1 atm", "pressure_kpa", 101.325),
    ("10 cm/s flow", "flow_cm_s", 10.0), ("3 mm droplet", "d0_mm", 3.0),
])
def test_unit_aware_parsing(q, var, val):
    assert parse(q).conditions[var] == pytest.approx(val, rel=1e-3)


def test_environment_and_categories():
    p = parse("Does PMMA burn at moon base conditions in helium?")
    assert p.environment == "moon base" and p.partial_gravity and p.question
    assert p.categories == {"material": "PMMA", "diluent": "He"}


def test_search_is_fast():
    search("warm-up")
    t0 = time.perf_counter()
    for q in ["smoke", "30% oxygen flammability", "droplet extinction", "BASS-II flow"]:
        search(q)
    assert (time.perf_counter() - t0) / 4 < 0.15


def test_api_smoke():
    from backend.api.main import app
    c = TestClient(app)
    for url in ["/api/meta", "/api/atlas", "/api/navigate?q=moon%20base", "/api/node/inv:FLEX", "/api/refinery",
                "/api/vision/tests", "/api/gapmap", "/api/answer?q=smoke%20detection"]:
        r = c.get(url)
        assert r.status_code == 200, url
        assert int(float(r.headers["server-timing"].split("dur=")[1])) < 1500
    t0 = time.perf_counter()
    r = c.get("/api/navigate?q=tests%20near%2030%25%20oxygen")
    assert r.status_code == 200 and (time.perf_counter() - t0) < 0.15
    r = c.post("/api/scenario", json={"mode": "droplet", "scenario": {"o2_frac": 0.21, "pressure_kpa": 101.3, "d0_mm": 3, "co2_frac": 0, "he_frac": 0, "fuel": "n-heptane", "gravity_g": 0}})
    assert r.status_code == 200 and r.json()["burn"]["domain"]["status"] == "inside"
    csv = c.post("/api/export/csv", json={"ids": ["BASS2-O4", "SAF2-2-1-UG"]}).text
    assert "DEMO FIXTURE" not in csv and "source" in csv.splitlines()[4]
    assert "PSI-25_Experimental table_BASS-II.csv:row" in csv and "Did not spread" in csv
