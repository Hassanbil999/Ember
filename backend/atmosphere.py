"""The atmosphere trade: breathing and spacewalk physiology that a cabin atmosphere must satisfy,
to be laid over the flammability evidence.

Nothing here is learned from the combustion data. Every constant and formula is taken from two NASA
Office of the Chief Health & Medical Officer technical briefs (listed in SOURCES) and is returned with
its source so the screen can cite it. The pre-breathe figure is a first-order estimate from the
tissue-ratio model those briefs describe, not a validated protocol.
"""
from __future__ import annotations

import math

PSI_KPA = 6.894757
MMHG_KPA = 0.1333224

SOURCES = [
    {"id": "tb003", "title": "NASA OCHMO-TB-003, Habitable Atmosphere (derived from NASA-STD-3001 Vol. 2 Rev D)",
     "url": "https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-003-habitable-atmosphere.pdf"},
    {"id": "tb037", "title": "NASA OCHMO-TB-037, Decompression Sickness (DCS) Risk Mitigation",
     "url": "https://www.nasa.gov/sites/default/files/atoms/files/dcs_technical_brief_ochmo.pdf"},
    {"id": "ntrs2022", "title": "NASA NTRS 20220009536, exploration atmosphere (8.2 psia, 34 % O₂) and pre-breathe validation",
     "url": "https://ntrs.nasa.gov/citations/20220009536"},
]

C = {
    # breathing: inspired oxygen partial pressure PIO2 = (cabin pressure − water vapour) × oxygen fraction   [tb003]
    "water_vapour_mmhg": 47.0,
    "pio2_normal_mmhg": 149.0,        # sea-level equivalent ("normoxia")
    "pio2_floor_mmhg": 127.0,         # lowest PIO2 NASA accepts for exploration missions, with monitoring
    "max_o2_frac": 0.70,              # at least 30 % of the atmosphere must be an inert gas
    # spacewalks: tissue ratio R = nitrogen in the body / suit pressure                                        [tb037]
    "suit_psi": 4.3,
    "r_accept": 1.65,                 # historically accepted R for the 4.3 psi suit
    "half_life_min": 360.0,           # tissue half-life used for nitrogen wash-out on pure oxygen
    # fire: NASA's own design line for materials                                                               [tb037]
    "o2_flammability_line": 0.30,
}

REFERENCES = [
    {"id": "iss", "label": "ISS today", "pressure_psi": 14.7, "o2_frac": 0.21, "source": "tb003"},
    {"id": "campout", "label": "Airlock campout", "pressure_psi": 10.2, "o2_frac": 0.265, "source": "tb037"},
    {"id": "exploration", "label": "Planned Moon/Mars habitat", "pressure_psi": 8.2, "o2_frac": 0.34, "source": "ntrs2022"},
]


def pio2_mmhg(pressure_kpa: float, o2_frac: float) -> float:
    """Inspired oxygen partial pressure, mmHg."""
    return (pressure_kpa / MMHG_KPA - C["water_vapour_mmhg"]) * o2_frac


def breathing(pressure_kpa: float, o2_frac: float) -> dict:
    p = pio2_mmhg(pressure_kpa, o2_frac)
    if o2_frac > C["max_o2_frac"]:
        status, text = "too_rich", "More than 70 % oxygen: NASA requires at least 30 % inert gas"
    elif p < C["pio2_floor_mmhg"]:
        status, text = "too_low", "Too little oxygen to breathe safely"
    elif p < C["pio2_normal_mmhg"]:
        status, text = "mild", "Breathable, mildly low: accepted for exploration with health monitoring"
    else:
        status, text = "normal", "Breathable, at or above sea-level oxygen"
    return {"pio2_mmhg": round(p, 1), "status": status, "text": text}


def prebreathe(pressure_kpa: float, o2_frac: float) -> dict:
    """Tissue ratio before a spacewalk and the pure-oxygen pre-breathe time that brings it to the accepted value.

    Assumes the body is in equilibrium with the cabin's nitrogen and washes out with one 360-minute half-life.
    """
    ppn2_psi = pressure_kpa / PSI_KPA * (1.0 - o2_frac)
    r0 = ppn2_psi / C["suit_psi"]
    minutes = 0.0 if r0 <= C["r_accept"] else C["half_life_min"] / math.log(2) * math.log(r0 / C["r_accept"])
    return {"ppn2_psi": round(ppn2_psi, 2), "r0": round(r0, 2), "minutes": round(minutes)}


def payload() -> dict:
    refs = []
    for r in REFERENCES:
        kpa = r["pressure_psi"] * PSI_KPA
        refs.append({**r, "pressure_kpa": round(kpa, 1), "breathing": breathing(kpa, r["o2_frac"]),
                     "prebreathe": prebreathe(kpa, r["o2_frac"])})
    return {"constants": C, "references": refs, "sources": SOURCES,
            "caveats": [
                "Breathing limits and the tissue-ratio model come from NASA medical technical briefs, not from the combustion data.",
                "The pre-breathe time is a first-order estimate (one 360-minute tissue half-life, body in equilibrium with the cabin). "
                "NASA validates real protocols in chamber tests and is still testing pre-breathe from the 8.2 psi / 34 % oxygen atmosphere.",
                "The fire layer is the same data-driven model as the simulator, with the same limits.",
            ]}
