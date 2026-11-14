"""SPEC §8.5 anchor tests (default parameters), the §8.4 fitter, the simulator routes, and the golden file
that keeps the browser's model copy (web/src/sim/model.ts) identical to the server's."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.sim import fit
from backend.sim.model import DEFAULTS, model, simulate

GOLDEN = Path(__file__).parent / "fixtures" / "model_golden.json"
FAB, PMMA = DEFAULTS["fabric"], DEFAULTS["pmma"]


@pytest.fixture(scope="module")
def api():
    from backend.api.main import app
    return TestClient(app)


# ------------------------------------------------------------------ §8.5 anchors (must pass with defaults)
def test_pmma_burns_at_17pct_in_microgravity_with_5cms():
    assert model(0, 17, 14.7, 5, PMMA).burns


def test_pmma_goes_out_at_21pct_with_half_cms_by_quenching():
    r = model(0, 21, 14.7, 0.5, PMMA)
    assert not r.burns and r.regime == "quench"


def test_pmma_in_normal_gravity_still_air_18_out_21_burns():
    assert not model(1, 18, 14.7, 0, PMMA).burns
    assert model(1, 21, 14.7, 0, PMMA).burns


def test_fabric_spread_matches_saffire_1():
    assert model(0, 21, 14.7, 20, FAB).spread == pytest.approx(1.8, abs=0.15)


def test_fabric_burns_in_lunar_rover_with_fan_off():
    r = model(0.166, 34, 8.2, 0, FAB)
    assert r.burns and r.ub > 10                       # gravity still feeds it about 12 cm/s


# ------------------------------------------------------------------ §8.2 time series
def test_time_series_burn_through_and_duration_rounding():
    s = simulate(0, 21, 14.7, 20, FAB)
    assert s["t_end"] is not None and s["t_out"] is None
    assert s["D"] % 5 == 0 and 10 <= s["D"] <= 240
    assert s["x_mm"][-1] == 100 and s["n"] == round(s["D"] / 0.05) + 1


def test_time_series_goes_out_after_the_igniter():
    s = simulate(0, 21, 14.7, 0.5, PMMA)
    assert s["D"] == 10 and s["t_out"] is not None and s["t_out"] > 1.5 and s["t_end"] is None


# ------------------------------------------------------------------ §8.4 fitting
def _synthetic(params: dict, n: int = 24) -> list[dict]:
    """Points generated from the model itself: test data for the fitter only, never loaded anywhere."""
    pts = []
    for i in range(n):
        g, o2, u = (0.0, 1.0)[i % 2], 15 + (i * 7) % 16, [0.5, 2, 5, 10, 20, 30][i % 6]
        r = model(g, o2, 14.7, u, params)
        if abs(r.margin) < 0.6:
            continue
        pts.append({"gravity_g": g, "o2_pct": o2, "pressure_kpa": 101.3, "flow_cm_s": u,
                    "outcome": "burned" if r.burns else "went_out", "spread_mm_s": round(r.spread, 3) if r.burns else None})
    return pts


def test_fitter_recovers_a_consistent_model():
    truth = {**FAB, "xmin": 16.5, "c": 0.4}
    pts = _synthetic(truth)
    params, rmse = fit.fit_material(pts, FAB)
    assert rmse < 0.05
    assert fit.residuals([params[n] for n in fit.NAMES], pts, 0.15).max() < 0.2


def test_fit_keeps_defaults_with_too_few_verified_points(api):
    meta = api.get("/api/model-params").json()["meta"]
    for mat in ("fabric", "pmma"):
        assert meta[mat]["n_points"] < fit.MIN_POINTS and meta[mat]["source"].startswith("defaults")


def test_fit_uses_only_verified_points_with_every_value():
    import pandas as pd
    pts = pd.DataFrame([
        {"material": "fabric", "verified": True, "outcome": "burned", "o2_pct": 21, "pressure_kpa": 101.3, "flow_cm_s": 20, "gravity_g": 0},
        {"material": "fabric", "verified": False, "outcome": "burned", "o2_pct": 21, "pressure_kpa": 101.3, "flow_cm_s": 20, "gravity_g": 0},
        {"material": "fabric", "verified": True, "outcome": "measured", "o2_pct": 21, "pressure_kpa": 101.3, "flow_cm_s": 20, "gravity_g": 0},
        {"material": "fabric", "verified": True, "outcome": "burned", "o2_pct": 21, "pressure_kpa": None, "flow_cm_s": 20, "gravity_g": 0},
    ])
    assert len(fit.usable(pts, "fabric")) == 1


# ------------------------------------------------------------------ routes
def test_simulate_route_returns_series_coverage_and_evidence(api):
    r = api.post("/api/simulate", json={"g": 0.166, "o2": 34, "psi": 8.2, "u": 0, "material": "fabric"}).json()
    assert r["result"]["burns"] and r["coverage"]["kind"] == "partial-g"
    assert len(r["t"]) == len(r["I"]) == len(r["x_mm"]) == r["n"]
    assert len(r["nearest"]) == 3 and r["nearest"][0]["distance"] <= r["nearest"][-1]["distance"]
    assert r["model_params"]["source"].startswith("defaults")


def test_simulate_coverage_extrapolation_and_inside(api):
    hi = api.post("/api/simulate", json={"g": 0, "o2": 34, "psi": 14.7, "u": 10, "material": "fabric"}).json()
    assert hi["coverage"]["kind"] == "o2" and "Extrapolated" in hi["coverage"]["text"]
    lo = api.post("/api/simulate", json={"g": 0, "o2": 21, "psi": 8.2, "u": 10, "material": "fabric"}).json()
    assert lo["coverage"]["kind"] == "pressure"
    ok = api.post("/api/simulate", json={"g": 0, "o2": 21, "psi": 14.7, "u": 10, "material": "fabric"}).json()
    assert ok["coverage"]["kind"] == "inside"


def test_simulate_rejects_out_of_range(api):
    assert api.post("/api/simulate", json={"g": 5}).status_code == 422
    assert api.post("/api/simulate", json={"material": "wood"}).status_code == 422


def test_flammability_map(api):
    m = api.get("/api/flammability-map", params={"g": 0, "o2": 17, "psi": 14.7, "u": 5, "material": "pmma"}).json()
    assert len(m["limit"]) == 81 and m["you"]["burns"]
    lims = [p["o2_limit"] for p in m["limit"]]
    assert min(lims) == pytest.approx(16.0, abs=0.05)            # X_min at u_eff = u*
    assert {p["code"] for p in m["points"]} >= {"BASS2-01", "BASS2-02"}
    assert api.get("/api/flammability-map", params={"g": 0.38}).json()["points"] == []


# ------------------------------------------------------------------ browser model parity
CASES = [(g, o2, psi, u, mat) for mat in ("fabric", "pmma") for g in (0, 0.166, 0.38, 1)
         for o2 in (15, 17, 21, 34, 45) for psi in (4, 8.2, 14.7) for u in (0, 0.5, 5, 20, 50)]


def golden_cases() -> list[dict]:
    out = []
    for g, o2, psi, u, mat in CASES:
        r = model(g, o2, psi, u, DEFAULTS[mat])
        s = simulate(g, o2, psi, u, DEFAULTS[mat])
        out.append({"in": {"g": g, "o2": o2, "p": psi, "u": u, "mat": mat},
                    "xlim": r.xlim, "spread": r.spread, "burns": r.burns, "regime": r.regime,
                    "D": s["D"], "t_out": s["t_out"], "t_end": s["t_end"], "x_last": s["x_mm"][-1]})
    return out


def test_golden_file_matches_the_server_model():
    """web/src/sim/model.test.ts checks the browser copy against the same file."""
    if not GOLDEN.exists():
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(golden_cases()), encoding="utf-8")
    saved = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = golden_cases()
    assert len(saved) == len(now) == 600
    for a, b in zip(saved, now):
        assert a["burns"] == b["burns"] and a["regime"] == b["regime"] and a["D"] == b["D"]
        assert math.isclose(a["xlim"], b["xlim"], rel_tol=1e-9) and math.isclose(a["spread"], b["spread"], rel_tol=1e-9, abs_tol=1e-12)
