"""d² law fit and event detection."""
from __future__ import annotations

import numpy as np


def fit_d2(t: np.ndarray, d: np.ndarray, window: tuple[float, float] | None = None) -> dict:
    """Linear fit of d² = d₀² − K·t inside a window. Default window: the quasi-steady part,
    skipping the first 10% (ignition transient) and the last 10% (near burnout/extinction)."""
    t = np.asarray(t, float)
    d2 = np.asarray(d, float) ** 2
    ok = np.isfinite(d2)
    t, d2 = t[ok], d2[ok]
    if len(t) < 4:
        return {"ok": False, "reason": "fewer than 4 points"}
    if window is None:
        span = t[-1] - t[0]
        window = (t[0] + 0.1 * span, t[-1] - 0.1 * span)
    w = (t >= window[0]) & (t <= window[1])
    if w.sum() < 4:
        return {"ok": False, "reason": "fewer than 4 points in window"}
    slope, icpt = np.polyfit(t[w], d2[w], 1)
    pred = slope * t[w] + icpt
    ss_res = float(((d2[w] - pred) ** 2).sum())
    ss_tot = float(((d2[w] - d2[w].mean()) ** 2).sum()) or 1e-12
    resid = (d2[w] - pred)
    n = int(w.sum())
    se = np.sqrt(ss_res / max(n - 2, 1) / (((t[w] - t[w].mean()) ** 2).sum() or 1e-12))
    return {"ok": True, "K": float(-slope), "K_se": float(se), "d0_fit_mm": float(np.sqrt(max(icpt, 0))),
            "r2": 1 - ss_res / ss_tot, "window": [float(window[0]), float(window[1])], "n": n,
            "residuals": [{"t": float(a), "r": float(b)} for a, b in zip(t[w], resid)]}


def detect_events(t, droplet_d, flame_lit, flame_int, floor_frames: int = 3) -> list[dict]:
    ev = []
    t = np.asarray(t, float)
    lit = np.asarray(flame_lit, bool) if flame_lit is not None else None
    if lit is not None and lit.any():
        i0 = int(np.argmax(lit))
        ev.append({"type": "ignition", "frame": i0, "t": float(t[i0]),
                   "detail": "first frame with flame luminosity above the floor"})
        run = 0
        for i in range(i0, len(lit)):
            run = run + 1 if not lit[i] else 0
            if run >= floor_frames:
                j = i - floor_frames + 1
                ev.append({"type": "extinction", "frame": j, "t": float(t[j]),
                           "detail": f"flame intensity below floor for ≥{floor_frames} frames"})
                break
    d = np.asarray(droplet_d, float) if droplet_d is not None else None
    if d is not None and np.isfinite(d).sum() > 5:
        dd = np.diff(d)
        good = np.isfinite(dd)
        if good.sum() > 4:
            sd = np.nanstd(dd) or 1e-9
            med = np.nanmedian(dd)
            jumps = np.where(np.abs(dd - med) > 6 * sd + 0.05)[0]
            if len(jumps):
                ev.append({"type": "disruption", "frame": int(jumps[0] + 1), "t": float(t[jumps[0] + 1]),
                           "detail": "sudden change in droplet diameter"})
        # end of burn: diameter stops shrinking
        tail = np.where(np.abs(dd) < 1e-3)[0] if good.any() else []
        if len(tail):
            stop = int(tail[0] + 1)
            if stop > len(d) * 0.3:
                ev.append({"type": "end_of_burn", "frame": stop, "t": float(t[stop]),
                           "detail": "droplet diameter stopped changing"})
    return ev
