"""Synonym- and unit-aware query parsing.

"30 percent oxygen", "0.3 O2", "30% O₂", "10 psi", "70 kPa", "moon base", "helium",
"microgravity" → structured conditions + human-readable chips + residual keywords.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.units import PRESSURE, SPEED

INVESTIGATIONS = ["BASS-II", "BASS", "Saffire-III", "Saffire-II", "Saffire-I", "SAME-R", "SAME", "FLEX-2", "FLEX",
                  "CFI-G", "CFI", "ACME", "E-FIELD Flames", "SPICE", "SLICE", "DAFT-2", "DAFT"]
DILUENTS = {"helium": "He", "he": "He", "nitrogen": "N2", "n2": "N2", "co2": "CO2", "carbon dioxide": "CO2"}
FUELS = {"heptane": "n-heptane", "n-heptane": "n-heptane", "methanol": "methanol", "decane": "n-decane",
         "n-decane": "n-decane", "ethanol": "ethanol"}
MATERIALS = {"pmma": "PMMA", "acrylic": "PMMA", "cotton": "Cotton-fiberglass fabric", "sibal": "Cotton-fiberglass fabric",
             "fiberglass": "Cotton-fiberglass fabric", "nomex": "Nomex-like fabric", "acetal": "Acetal", "delrin": "Acetal"}
PILLARS = {"prevention": "prevention", "prevent": "prevention", "flammability": "prevention", "detection": "detection",
           "detect": "detection", "smoke": "detection", "sensor": "detection", "suppression": "suppression",
           "suppress": "suppression", "extinguish": "suppression", "extinguishment": "suppression"}
ENVIRONMENTS = {
    "moon base": {"o2_frac": 0.30, "pressure_kpa": 70.3, "gravity_g": 0.165},
    "lunar base": {"o2_frac": 0.30, "pressure_kpa": 70.3, "gravity_g": 0.165},
    "rover": {"o2_frac": 0.34, "pressure_kpa": 56.5, "gravity_g": 0.165},
    "spacesuit": {"o2_frac": 1.0, "pressure_kpa": 29.6, "gravity_g": 0.0},
    "iss cabin": {"o2_frac": 0.21, "pressure_kpa": 101.3, "gravity_g": 0.0},
    "mars": {"gravity_g": 0.38},
    "martian": {"gravity_g": 0.38},
    "lunar": {"gravity_g": 0.165},
    "moon": {"gravity_g": 0.165},
}

NUM = r"(\d+(?:\.\d+)?|\.\d+)"
O2W = r"(?:o2|o₂|oxygen|ox)"


@dataclass
class Parsed:
    raw: str
    conditions: dict = field(default_factory=dict)      # numeric canonical values
    categories: dict = field(default_factory=dict)      # diluent/fuel/material
    investigations: list = field(default_factory=list)
    pillar: str | None = None
    environment: str | None = None
    partial_gravity: bool = False
    chips: list = field(default_factory=list)
    residual: str = ""
    question: bool = False

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items()}


def _chip(p: Parsed, var: str, text: str):
    p.chips.append({"var": var, "text": text})


def parse(q: str) -> Parsed:
    p = Parsed(raw=q)
    s = " " + q.lower().replace("₂", "2").replace("–", "-") + " "
    consumed: list[tuple[int, int]] = []

    def take(m):
        consumed.append(m.span())

    for m in re.finditer(rf"{NUM}\s*(?:%|percent|per cent|pct)\s*{O2W}?", s):
        v = float(m.group(1)) / 100
        if 0 < v <= 1:
            p.conditions["o2_frac"] = v
            _chip(p, "o2_frac", f"O₂ {v * 100:.3g}%")
            take(m)
    if "o2_frac" not in p.conditions:
        for m in re.finditer(rf"(?<![\d.]){NUM}\s*(?:mole fraction\s*)?{O2W}\b|{O2W}\s*(?:of|=|at|:)?\s*{NUM}(?!\s*(?:psi|kpa|atm|bar|mm|cm))", s):
            raw = m.group(1) or m.group(2)
            v = float(raw)
            v = v / 100 if v > 1 else v
            if 0 < v <= 1:
                p.conditions["o2_frac"] = v
                _chip(p, "o2_frac", f"O₂ {v * 100:.3g}%")
                take(m)
                break
    for m in re.finditer(rf"{NUM}\s*(psia|psi|kpa|atm|bar|mbar|torr)\b", s):
        v = float(m.group(1)) * PRESSURE[m.group(2)]
        p.conditions["pressure_kpa"] = v
        unit = m.group(2)
        _chip(p, "pressure_kpa", f"P {v:.3g} kPa" + ("" if unit == "kpa" else f" ({m.group(1)} {unit})"))
        take(m)
    for m in re.finditer(rf"{NUM}\s*(cm/s|mm/s|m/s)\b", s):
        v = float(m.group(1)) * SPEED[m.group(2)]
        p.conditions["flow_cm_s"] = v
        _chip(p, "flow_cm_s", f"flow {v:.3g} cm/s")
        take(m)
    for m in re.finditer(rf"{NUM}\s*mm\b(?!/)", s):
        p.conditions["d0_mm"] = float(m.group(1))
        _chip(p, "d0_mm", f"d₀ {float(m.group(1)):.3g} mm")
        take(m)

    if re.search(r"\b(micro-?gravity|μg|µg|ug|0g|zero[- ]g|weightless)", s):
        p.conditions["gravity_g"] = 0.0
        _chip(p, "gravity_g", "microgravity")
    elif re.search(r"\b(1g|1 g|normal gravity|earth gravity|on earth|ground)\b", s):
        p.conditions["gravity_g"] = 1.0
        _chip(p, "gravity_g", "1g")
    if re.search(r"partial[- ]gravity|lunar gravity|martian gravity|0\.16|0\.38", s):
        p.partial_gravity = True

    for name, env in ENVIRONMENTS.items():
        if re.search(rf"\b{name}\b", s):
            p.environment = name
            for k, v in env.items():
                p.conditions.setdefault(k, v)
            if env.get("gravity_g", 0) not in (0.0, 1.0):
                p.partial_gravity = True
            _chip(p, "environment", name)
            break

    for word, val in DILUENTS.items():
        if re.search(rf"\b{re.escape(word)}\b", s):
            p.categories["diluent"] = val
            _chip(p, "diluent", f"diluent {val}")
            break
    for word, val in FUELS.items():
        if re.search(rf"\b{re.escape(word)}\b", s):
            p.categories["fuel"] = val
            _chip(p, "fuel", val)
            break
    for word, val in MATERIALS.items():
        if re.search(rf"\b{re.escape(word)}\b", s):
            p.categories["material"] = val
            _chip(p, "material", val)
            break
    for inv in INVESTIGATIONS:
        if re.search(rf"(?<![\w-]){re.escape(inv.lower())}(?![\w-])", s):
            if not any(inv in x for x in p.investigations):
                p.investigations.append(inv)
    for word, pil in PILLARS.items():
        if re.search(rf"\b{word}\b", s):
            p.pillar = pil
            break

    res = list(s)
    for a, b in consumed:
        for i in range(a, b):
            res[i] = " "
    p.residual = re.sub(r"\s+", " ", "".join(res)).strip()
    p.question = bool(re.match(r"^\s*(what|how|why|which|does|do|is|are|can|when|where|compare)\b", s)) or "?" in q
    return p
