"""Evidence from outside NASA, read straight from its pinned source file (config/external.yaml).

Kept apart from the NASA PSI tests on purpose: nothing here enters the test store, trains a model or
changes an evidence grade. The topic screens show it in its own labelled card.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "external.yaml"


@lru_cache(maxsize=1)
def sources() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=1)
def zarm_spread() -> list[dict]:
    """ZARM drop-tower tests on continuous thin PMMA strips that report a measured flame-spread rate.

    Rows with metal barriers (a `Gaps` sequence) report no single spread rate and are left out.
    Units as published: oxygen mole fraction, pressure kPa, flow and spread mm/s.
    """
    src = sources().get("zarm_barriers")
    if not src or not (ROOT / src["file"]).exists():
        return []
    df = pd.read_csv(ROOT / src["file"])
    full = df[df["Gaps [Sequence]"].isna() & df["Propagation Rate [mm/s]"].notna()]
    out = [{"id": str(int(r["Experiment [ID]"])), "date": r["Date [yyyy-mm-dd]"],
            "o2_frac": float(r["Oxygen [mole/mole]"]), "pressure_kpa": float(r["Pressure [kPa]"]),
            "flow_mm_s": float(r["Flow Velocity [mm/s]"]), "thickness_mm": float(r["Thickness [mm]"]),
            "spread_mm_s": float(r["Propagation Rate [mm/s]"]), "spread_std": float(r["Propagation Rate (std.) [mm/s]"])}
           for _, r in full.iterrows()]
    return sorted(out, key=lambda p: p["o2_frac"])


def spread_card(o2_target: float, place: str) -> dict | None:
    """The 'outside NASA' card for a place whose planned oxygen is above every NASA solid test in orbit."""
    pts = zarm_spread()
    earth = [p for p in pts if p["o2_frac"] < 0.22]
    if len(pts) < 3 or not earth:
        return None
    src = sources()["zarm_barriers"]
    hi = pts[-1]
    base = sum(p["spread_mm_s"] for p in earth) / len(earth)
    ratio = hi["spread_mm_s"] / base
    near = min(pts, key=lambda p: abs(p["o2_frac"] - o2_target))
    e_o2 = sorted({f"{p['o2_frac'] * 100:.1f}" for p in earth})
    finding = (f"In a German drop tower, flame spread over thin acrylic at {hi['o2_frac'] * 100:.1f}% oxygen and "
               f"{hi['pressure_kpa']:.0f} kPa was {ratio:.1f}× as fast as in Earth-like air "
               f"({' and '.join(e_o2)}% oxygen at about {min(p['pressure_kpa'] for p in earth):.0f}–"
               f"{max(p['pressure_kpa'] for p in earth):.0f} kPa): {hi['spread_mm_s']:.2f} against {base:.2f} mm/s on average.")
    return {"label": src["label"], "finding": finding,
            "summary": (f"Not NASA data. The closest test to {place} air ({o2_target * 100:.0f}% oxygen) ran at "
                        f"{near['o2_frac'] * 100:.1f}% oxygen and {near['pressure_kpa']:.0f} kPa."),
            "points": pts, "near_id": near["id"], "ratio": round(ratio, 2),
            "material": src["material"], "limits": src["limits"], "license": src["license"],
            "funding": src["funding"], "citation": src["citation"],
            "doi": src["doi"], "url": src["url"], "paper_doi": src["paper_doi"]}
