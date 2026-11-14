"""The two questions the NASA tables can answer with a measured outcome.

gas      CFI-G (PSI-159, normal flames): a gaseous fuel jet burning in microgravity, like a small leak on fire.
         Outcome: the flame stayed lit (1) or went out on its own (0).
droplet  FLEX (PSI-69): one drop of liquid fuel on fibres, lit in microgravity.
         Outcome: burned the drop to the end (1) or the flame died with fuel left (0).
         Also measured: burning-rate constant K (mm²/s) and, when the flame died early, the drop size then.

Fuel is described by what it is made of, not by a label: carbon number and the fuel's share of the jet
(CFI-G burns ethane, propane and butane, some diluted to 30 % or 50 % in nitrogen). That lets an engineer
enter a mix the tests used without a separate category per label, and keeps "same fuel" well defined.
Rows missing an input or the outcome are left out of that model; nothing is filled in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..core.store import get_store

PSI = 6.894757

GAS_FUELS = {"ethane": 2, "propane": 3, "butane": 4}
DROPLET_FUELS = {"n-heptane": "heptane", "methanol": "methanol"}
DATASETS = {"gas": "cfig_normal", "droplet": "flex"}          # the one table each question learns from


def gas_fuel_parts(label: str) -> tuple[str, int, float] | None:
    """'30% butane' -> ('butane', 4, 0.30); 'ethane' -> ('ethane', 2, 1.0)."""
    m = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)\s*%\s*)?([a-z-]+)\s*", str(label).lower())
    if not m or m.group(2) not in GAS_FUELS:
        return None
    return m.group(2), GAS_FUELS[m.group(2)], (float(m.group(1)) / 100 if m.group(1) else 1.0)


@dataclass
class Problem:
    key: str
    label: str
    question: str
    investigation: str
    psi_id: str
    target: str
    outcome_yes: str
    outcome_no: str
    will: str
    features: list[str]
    feature_labels: dict[str, str]
    units: dict[str, str]
    regressions: dict[str, dict] = field(default_factory=dict)

    def frame(self, target: str | None = None) -> pd.DataFrame:
        return FRAMES[self.key](target or self.target)


def _gas_frame(target: str) -> pd.DataFrame:
    t = get_store().usable_tests(DATASETS["gas"]).copy()
    parts = t.fuel.map(gas_fuel_parts)
    t = t[parts.notna()].copy()
    parts = parts[parts.notna()]
    t["fuel_name"] = [p[0] for p in parts]
    t["carbon_n"] = [float(p[1]) for p in parts]
    t["fuel_share"] = [p[2] for p in parts]
    t["o2_pct"] = t.o2_frac * 100
    t["psi"] = t.pressure_kpa / PSI
    t["fuel_flow"] = t.fuel_flow_mg_s
    t = t.dropna(subset=[target, "o2_pct", "psi", "fuel_flow"])
    return t


def _droplet_frame(target: str) -> pd.DataFrame:
    t = get_store().usable_tests(DATASETS["droplet"]).copy()
    t = t[t.fuel.isin(DROPLET_FUELS)].copy()
    t["fuel_name"] = t.fuel.map(DROPLET_FUELS)
    t["heptane"] = (t.fuel_name == "heptane").astype(float)
    t["o2_pct"] = t.o2_frac * 100
    t["psi"] = t.pressure_kpa / PSI
    t["co2_pct"] = t.co2_frac.fillna(0) * 100
    t["he_pct"] = t.he_frac.fillna(0) * 100
    t = t.dropna(subset=[target, "o2_pct", "psi", "d0_mm"])
    return t


FRAMES = {"gas": _gas_frame, "droplet": _droplet_frame}

PROBLEMS: dict[str, Problem] = {
    "gas": Problem(
        key="gas", label="Gas leak flame", question="Does a gas-jet flame stay lit?",
        investigation="CFI-G", psi_id="PSI-159", target="burned",
        outcome_yes="stayed lit", outcome_no="went out on its own", will="stays lit",
        features=["o2_pct", "psi", "fuel_flow", "carbon_n", "fuel_share"],
        feature_labels={"o2_pct": "Oxygen", "psi": "Pressure", "fuel_flow": "Fuel flow (leak size)",
                        "carbon_n": "Fuel (carbon atoms)", "fuel_share": "Fuel share of the jet"},
        units={"o2_pct": "%", "psi": "psi", "fuel_flow": "mg/s", "carbon_n": "", "fuel_share": ""},
        regressions={
            "burn_time_s": {"label": "Time until the flame went out", "unit": "s", "only_when": {"burned": 0},
                            "meaning": "only for flames that go out on their own; a flame that stays lit burns until the test is stopped"},
        },
    ),
    "droplet": Problem(
        key="droplet", label="Liquid fuel droplet", question="Does a burning fuel drop burn to the end?",
        investigation="FLEX", psi_id="PSI-69", target="burned",
        outcome_yes="burned to the end", outcome_no="flame died with fuel left", will="burns to the end",
        features=["o2_pct", "psi", "d0_mm", "heptane", "co2_pct", "he_pct"],
        feature_labels={"o2_pct": "Oxygen", "psi": "Pressure", "d0_mm": "Drop size", "heptane": "Fuel",
                        "co2_pct": "CO₂ in the air", "he_pct": "Helium in the air"},
        units={"o2_pct": "%", "psi": "psi", "d0_mm": "mm", "heptane": "", "co2_pct": "%", "he_pct": "%"},
        regressions={
            "burn_rate_k_mm2_s": {"label": "Burning-rate constant K", "unit": "mm²/s",
                                  "meaning": "how fast the drop is consumed (diameter² falls by K each second)"},
            "extinction_d_mm": {"label": "Drop size when the flame died", "unit": "mm", "only_when": {"burned": 0},
                                "meaning": "only meaningful when the flame dies early"},
            "burn_time_s": {"label": "Burn time", "unit": "s",
                            "meaning": "from ignition until the flame went out or the drop was used up"},
        },
    ),
}


def features_from(problem: Problem, inp: dict) -> np.ndarray:
    """One request (engineer's units) -> the model's feature row."""
    if problem.key == "gas":
        parts = gas_fuel_parts(inp["fuel"])
        if parts is None:
            raise ValueError(f"Unknown gas fuel {inp['fuel']!r}; choose ethane, propane or butane.")
        share = float(inp.get("fuel_share", parts[2]))
        row = {"o2_pct": inp["o2_pct"], "psi": inp["psi"], "fuel_flow": inp["fuel_flow"], "carbon_n": float(parts[1]), "fuel_share": share}
    else:
        fuel = DROPLET_FUELS.get(inp["fuel"], inp["fuel"])
        if fuel not in DROPLET_FUELS.values():
            raise ValueError(f"Unknown droplet fuel {inp['fuel']!r}; choose n-heptane or methanol.")
        # the rest of the air: CO₂ and helium shares as NASA mixed them; nitrogen makes up the remainder
        co2, he = float(inp.get("co2_pct") or 0.0), float(inp.get("he_pct") or 0.0)
        if co2 < 0 or he < 0 or float(inp["o2_pct"]) + co2 + he > 100.0 + 1e-6:
            raise ValueError("Oxygen, CO₂ and helium together cannot exceed 100 %.")
        row = {"o2_pct": inp["o2_pct"], "psi": inp["psi"], "d0_mm": inp["d0_mm"], "heptane": 1.0 if fuel == "heptane" else 0.0,
               "co2_pct": co2, "he_pct": he}
    return np.array([[float(row[f]) for f in problem.features]])
