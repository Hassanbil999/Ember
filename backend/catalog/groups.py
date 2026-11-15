"""Investigation groups (Decision A) and the rules that map real values onto the §5 vocabulary.

The prototype and the seed group investigations (`bass` = BASS + BASS-II). The real catalog
(config/investigations.yaml) has one row per PSI investigation. Each group lists its real members;
test points and data resources keep the exact PSI investigation name in `investigation_detail`.
"""
from __future__ import annotations

# slug → real investigation ids in config/investigations.yaml (order = display order)
GROUPS: dict[str, list[str]] = {
    "bass": ["BASS", "BASS-II"],
    "saffire": ["Saffire-I", "Saffire-II", "Saffire-III"],
    "same": ["SAME", "SAME-R"],
    "flex": ["FLEX", "FLEX-2"],
    "cfi": ["CFI"],
    "acme": ["ACME", "CFI-G", "E-FIELD Flames"],
    "spice": ["SPICE", "SLICE"],
    "daft": ["DAFT", "DAFT-2"],
}
MEMBER_TO_GROUP = {m: g for g, ms in GROUPS.items() for m in ms}

PILLAR_TO_PURPOSE = {"prevention": "prevent", "detection": "detect", "suppression": "suppress"}
# fuel_phase in investigations.yaml → §5 fuels. "smoke" and "dust" are not fuels: left for the seed to fill.
FUEL_PHASE_TO_FUEL = {"solid": "solid", "liquid droplet": "liquid", "gas": "gas"}

DROPLET_SETS = {"flex", "cfi"}
GAS_SETS = {"cfig_normal", "cfig_inverse", "flame_design_normal", "acme_bre", "efield", "spice"}
SOLID_SETS = {"bass", "bass2", "saffire1", "saffire2", "saffire3"}


def material_of(dataset: str, material_text) -> str:
    """§5 material class. Never inferred beyond what the source names."""
    if dataset in DROPLET_SETS:
        return "droplet"
    if dataset in GAS_SETS:
        return "gas"
    if dataset in SOLID_SETS and isinstance(material_text, str):
        t = material_text.strip().lower()
        if "sibal" in t or "cotton-fiberglass" in t:
            return "fabric"
        if t == "pmma":
            return "pmma"
    return "other"


def outcome_of(burned) -> str:
    """burned 1 → burned, 0 → went_out; anything the table does not state → measured (conditions only)."""
    if burned is None or burned != burned:          # None or NaN
        return "measured"
    return "burned" if float(burned) >= 0.5 else "went_out"


SIM_MATERIALS = ("fabric", "pmma")
SIM_OUTCOMES = ("burned", "went_out")


def simulatable(material: str, o2_pct, outcome: str) -> bool:
    """A point the solid-fuel simulator can load and compare against (§8.3)."""
    return material in SIM_MATERIALS and o2_pct is not None and o2_pct == o2_pct and outcome in SIM_OUTCOMES
