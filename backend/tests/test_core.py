"""Adapters, normalization, validation."""
import pandas as pd
import pytest

from backend.core.units import header_unit, normalize, parse_number_unit
from backend.core.validate import validate


@pytest.mark.parametrize("raw,unit,expected", [
    ("14.7 psi", None, 101.35),
    ("1 atm", None, 101.325),
    ("101.3 kPa", None, 101.3),
    ("1.013 bar", None, 101.3),
    (760, "torr", 101.32),
])
def test_pressure_units(raw, unit, expected):
    v, steps = normalize("pressure_kpa", raw, unit)
    assert v == pytest.approx(expected, rel=2e-3)


@pytest.mark.parametrize("raw,expected", [("21%", 0.21), ("0.21", 0.21), ("21", 0.21), ("30 %", 0.30), (0.3, 0.3)])
def test_oxygen_fraction(raw, expected):
    v, _ = normalize("o2_frac", raw)
    assert v == pytest.approx(expected)


def test_length_speed_time():
    assert normalize("d0_mm", "0.3 cm")[0] == pytest.approx(3.0)
    assert normalize("flow_cm_s", 50, "mm/s")[0] == pytest.approx(5.0)
    assert normalize("flow_cm_s", "0.1 m/s")[0] == pytest.approx(10.0)


def test_steps_are_recorded():
    _, steps = normalize("pressure_kpa", "14.7 psi")
    assert any(s["op"] == "convert" and "psi" in s["detail"] for s in steps)


def test_blank_and_header_unit():
    assert parse_number_unit("") == (None, None)
    assert parse_number_unit(float("nan")) == (None, None)
    assert header_unit("Thickness [mm]") == "mm"
    assert header_unit("D0 (mm)") == "mm"


def test_validation_flags_never_fixes():
    df = pd.DataFrame([
        {"test_id": "A", "pressure_kpa": None, "o2_frac": 0.21, "burned": 1, "_row": 2,
         "invalid": {"pressure_kpa": "Total pressure must be greater than zero."}},
        {"test_id": "B", "pressure_kpa": 101.0, "o2_frac": 0.21, "burned": None, "_row": 3, "invalid": {}},
        {"test_id": "B", "pressure_kpa": 101.0, "o2_frac": 0.21, "burned": 1, "_row": 4, "invalid": {}},
        {"test_id": "C", "pressure_kpa": 101.0, "o2_frac": 0.21, "burned": 0, "spread_rate_mm_s": 2.0, "_row": 5, "invalid": {}},
    ])
    out, log = validate(df, "t")
    assert out.loc[0, "excluded"] and "impossible_value" in out.loc[0, "flags"]
    assert pd.isna(out.loc[0, "pressure_kpa"])        # flagged value is never replaced by a number
    assert "missing_outcome" in out.loc[1, "flags"] and not out.loc[1, "excluded"]
    assert out.loc[2, "excluded"] and "duplicate" in out.loc[2, "flags"]
    assert "rate_without_burn" in out.loc[3, "flags"]
    assert all(e["reason"] for e in log)


def test_adapters_produce_canonical_rows():
    from backend.adapters import REGISTRY
    from backend.core import config
    ds = config.datasets()
    flex = REGISTRY["flex_droplets"]("flex_demo", ds["flex_demo"])
    t = flex.tests
    assert {"o2_frac", "pressure_kpa", "o2_pp_kpa", "d0_mm", "burned", "gravity_g"} <= set(t.columns)
    assert t["o2_frac"].dropna().between(0, 1).all()
    good = t[t["pressure_kpa"].notna()]
    assert len(good) == len(t) - 1                            # the impossible "0 atm" row is flagged, not converted
    assert good["pressure_kpa"].between(40, 320).all()        # all units converted to kPa
    assert (good["o2_pp_kpa"] - good["o2_frac"] * good["pressure_kpa"]).abs().max() < 1e-9
    assert len(flex.provenance) > len(t) * 5
    bass = REGISTRY["bass2_solids"]("bass2_demo", ds["bass2_demo"])
    b = bass.tests
    assert set(b["gravity_g"].dropna().unique()) <= {0.0, 1.0}
    assert b["flow_cm_s"].max() < 100                         # mm/s → cm/s
    assert b["investigation_id"].eq("BASS-II").all()
