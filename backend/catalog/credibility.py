"""SPEC §7: S = 100 (0.4 P + 0.3 R + 0.3 T). High ≥ 85, Medium 65–85, Low < 65; placeholders are Unverified."""
from __future__ import annotations

import math

# Default factors assigned by ingestion rules (§7 table; README Decision C for PSI data review).
PSI_DATA = {"publisher": 1.0, "review": 0.8, "trace": 1.0}
NASA_DOCUMENT = {"publisher": 0.85, "review": 0.8, "trace": 0.8}


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def score(status: str | None, url: str | None, p, r, t) -> dict:
    """Score, label, 1–5 meter level, factors and a one-line explanation for one resource."""
    p, r, t = _f(p), _f(r), _f(t)
    if status == "placeholder" or not url or None in (p, r, t):
        why = "Placeholder: no source link yet." if status == "placeholder" or not url else "Credibility factors not assigned yet."
        return {"score": None, "label": "Unverified", "level": 0, "factors": None, "explanation": why}
    s = round(100 * (0.4 * p + 0.3 * r + 0.3 * t))
    label = "High" if s >= 85 else "Medium" if s >= 65 else "Low"
    factors = {"publisher": round(p * 100), "review": round(r * 100), "trace": round(t * 100)}
    return {"score": s, "label": label, "level": max(1, round(s / 20)), "factors": factors,
            "explanation": f"Publisher {factors['publisher']} · Review {factors['review']} · Traceability {factors['trace']}"}
