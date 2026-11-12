"""Image Lab extractors on the programmatic test pattern (known diameters). Spec: within 2%."""
import numpy as np
import pytest

from backend.fixture import draw_backlit, draw_flame_view, pattern_series
from backend.vision.d2fit import detect_events, fit_d2
from backend.vision.extractors import BacklitDroplet, Flame

PX = 20.0


@pytest.mark.parametrize("d_mm", [0.8, 1.5, 2.4, 3.3, 4.6])
def test_backlit_diameter_within_2pct(d_mm):
    rng = np.random.default_rng(1)
    img = draw_backlit(d_mm * PX, rng=rng)
    m = BacklitDroplet().measure(img, PX)
    assert m["ok"]
    assert abs(m["droplet_diameter_mm"] - d_mm) / d_mm < 0.02
    assert m["circularity"] > 0.8 and 0 < m["confidence"] <= 1


def test_backlit_off_centre_and_roi():
    img = draw_backlit(2.0 * PX, center=(40, 50), rng=np.random.default_rng(2))
    ex = BacklitDroplet()
    ex.params = {**ex.params, "roi": [10, 15, 70, 70]}
    m = ex.measure(img, PX)
    assert abs(m["droplet_diameter_mm"] - 2.0) / 2.0 < 0.02
    assert abs(m["cx"] - 40) < 1.5 and abs(m["cy"] - 50) < 1.5


def test_no_droplet_reports_failure():
    img = np.full((128, 128), 220, np.uint8)
    assert not BacklitDroplet().measure(img, PX)["ok"]


def test_flame_view_lit_and_dark():
    lit = Flame().measure(draw_flame_view(80, 0.9), PX)
    assert lit["lit"] and abs(lit["flame_diameter_mm"] - 4.0) / 4.0 < 0.05
    dark = Flame().measure(draw_flame_view(80, 0.0), PX)
    assert not dark["lit"]


def test_d2_fit_recovers_K():
    K, d0 = 0.62, 3.0
    ts, d, on = pattern_series(d0, K, None, PX, 5.0)
    rng = np.random.default_rng(3)
    meas = []
    for di in d:
        m = BacklitDroplet().measure(draw_backlit(di * PX, rng=rng), PX)
        meas.append(m["droplet_diameter_mm"] if m["ok"] else np.nan)
    fit = fit_d2(ts, np.array(meas))
    assert fit["ok"] and abs(fit["K"] - K) / K < 0.02 and fit["r2"] > 0.99
    assert len(fit["residuals"]) == fit["n"]


def test_events_ignition_and_extinction():
    t = np.arange(20) / 5
    lit = [False] * 2 + [True] * 10 + [False] * 8
    ev = {e["type"]: e for e in detect_events(t, None, lit, None)}
    assert ev["ignition"]["frame"] == 2 and ev["extinction"]["frame"] == 12


def test_pipeline_agrees_with_published():
    import json
    from backend.core.config import ARTIFACTS
    summ = json.loads((ARTIFACTS / "vision" / "validation_summary.json").read_text(encoding="utf-8"))
    assert summ["n_comparisons"] >= 4
    assert summ["mean_abs_error_pct"] < 2.0
