"""Image Lab pipeline: media → per-frame measurements → events → d² fit → validation →
image-derived variables in the canonical schema. Results are cached per test; jobs run in
a background thread with progress."""
from __future__ import annotations

import json
import threading
import time
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..core import config
from ..core.config import ARTIFACTS, PROCESSED
from .d2fit import detect_events, fit_d2
from .extractors import EXTRACTORS
from .frames import frame_paths, read_frame

VDIR = ARTIFACTS / "vision"
VDIR.mkdir(parents=True, exist_ok=True)
OVERRIDES = VDIR / "overrides.json"
JOBS: dict[str, dict] = {}


def media_by_test() -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    include_demo = config.load_yaml("profile.yaml").get("include_demo", True)
    for m in config.media_cfg().get("media", []) or []:
        if m.get("kind") == "test_pattern" and not include_demo:
            continue
        out.setdefault(m["test_id"], {})[m["view"]] = m
    return out


def overrides() -> dict:
    return json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}


def process_test(test_id: str, params: dict | None = None, progress=None) -> dict:
    """Run extractors over all frames of a test's media. `params` = {"backlit": {...}, "flame": {...},
    "window": [t0, t1]} — manual corrections, recorded in provenance."""
    views = media_by_test().get(test_id, {})
    if not views:
        raise KeyError(f"no media for test {test_id}")
    ov = overrides().get(test_id, {})
    if params:
        ov = {**ov, **params, "_when": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        allov = overrides()
        allov[test_id] = ov
        OVERRIDES.write_text(json.dumps(allov, indent=1), encoding="utf-8")
    result = {"test_id": test_id, "views": {}, "frames": [], "kind": None}
    per_view = {}
    total = sum(len(frame_paths(m)) for m in views.values())
    done = 0
    for view, m in views.items():
        ex = EXTRACTORS[view]()
        ex.params = {**ex.params, **(ov.get(view) or {})}
        paths = frame_paths(m)
        rows = []
        for i, p in enumerate(paths):
            img = read_frame(p, color=(view == "flame"))
            r = ex.measure(img, m["px_per_mm"])
            r["frame"] = i
            r["t"] = m.get("t0_s", 0) + i / m["fps"]
            rows.append(r)
            done += 1
            if progress and done % 10 == 0:
                progress(done / max(total, 1))
        per_view[view] = rows
        result["views"][view] = {"media_id": m["id"], "extractor": ex.name, "version": ex.version, "params": ex.params,
                                 "n_frames": len(paths), "fps": m["fps"], "px_per_mm": m["px_per_mm"],
                                 "path": m["path"], "format": m["format"], "kind": m.get("kind", "footage"),
                                 "size": list(read_frame(paths[0]).shape[:2]) if paths else None}
        result["kind"] = m.get("kind", "footage")
    n = max(len(v) for v in per_view.values())
    t = np.array([(per_view.get("backlit") or per_view.get("flame"))[i]["t"] for i in range(n)])
    dd = np.array([r.get("droplet_diameter_mm", np.nan) if r.get("ok") else np.nan for r in per_view.get("backlit", [])] or [np.nan] * n)
    lit = [bool(r.get("lit")) for r in per_view.get("flame", [])] or None
    fint = [r.get("peak_intensity", 0) for r in per_view.get("flame", [])] or None
    events = detect_events(t, dd if "backlit" in per_view else None, lit, fint)
    # a flame that goes out when no droplet is left is burnout, not extinction
    if "backlit" in per_view and np.isfinite(dd).any():
        d0v = dd[np.where(np.isfinite(dd))[0][0]]
        for e in events:
            if e["type"] == "extinction":
                di = dd[min(e["frame"], len(dd) - 1)]
                if not np.isfinite(di) or di < 0.2 * d0v:
                    e["type"] = "burnout"
                    e["detail"] = "flame went out with no droplet left (burned to completion)"
    ign = next((e["t"] for e in events if e["type"] == "ignition"), t[0])
    ext = next((e["t"] for e in events if e["type"] == "extinction"), None)
    burnout = next((e["t"] for e in events if e["type"] == "burnout"), None)
    end = ext if ext is not None else burnout if burnout is not None else float(t[np.where(np.isfinite(dd))[0][-1]]) if np.isfinite(dd).any() else t[-1]
    if ov.get("window"):
        window = tuple(ov["window"])
    else:
        span = end - ign
        window = (ign + 0.1 * span, end - 0.1 * span)
    fit = fit_d2(t, dd, window) if "backlit" in per_view else {"ok": False}
    for i in range(n):
        b = per_view.get("backlit", [{}] * n)[i] if i < len(per_view.get("backlit", [])) else {}
        f = per_view.get("flame", [{}] * n)[i] if i < len(per_view.get("flame", [])) else {}
        fr = {"frame": i, "t": float(t[i]), "droplet": b if b.get("ok") else None, "flame": f if f else None}
        if b.get("ok") and f.get("lit"):
            fr["standoff_ratio"] = f["flame_diameter_mm"] / b["droplet_diameter_mm"]
        fr["state"] = ("burning" if f.get("lit") else
                       ("extinguished" if ext is not None and t[i] >= ext else "not ignited" if t[i] < ign else "burned out"))
        if any(e["type"] == "disruption" and e["frame"] == i for e in events):
            fr["state"] = "disrupted"
        result["frames"].append(fr)
    so = [fr["standoff_ratio"] for fr in result["frames"] if fr.get("standoff_ratio")]
    derived = {"fit": fit, "events": events,
               "d0_mm": float(dd[np.where(np.isfinite(dd))[0][0]]) if np.isfinite(dd).any() else None,
               "extinction_d_mm": float(dd[np.searchsorted(t, ext)]) if ext is not None and np.isfinite(dd).any() else None,
               "standoff_ratio_median": float(np.median(so)) if so else None,
               "curve": [{"t": float(a), "d": None if not np.isfinite(b) else float(b),
                          "d2": None if not np.isfinite(b) else float(b * b)} for a, b in zip(t, dd)]}
    result["derived"] = derived
    result["overrides"] = ov
    result["validation"] = validate_test(test_id, derived)
    result["processed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (VDIR / f"{test_id}.json").write_text(json.dumps(result, default=float), encoding="utf-8")
    if progress:
        progress(1.0)
    return result


def validate_test(test_id: str, derived: dict) -> dict:
    pub_all = json.loads((ARTIFACTS / "published_values.json").read_text(encoding="utf-8"))
    pub = {}
    for ds in pub_all.values():
        pub.update(ds.get(test_id, {}) if isinstance(ds, dict) else {})
    rows = []
    pairs = [("burn_rate_k_mm2_s", derived["fit"].get("K") if derived["fit"].get("ok") else None),
             ("d0_mm", derived.get("d0_mm")), ("extinction_d_mm", derived.get("extinction_d_mm"))]
    for var, ext in pairs:
        p = pub.get(var)
        if p is None or ext is None:
            continue
        err = (ext - p) / p * 100
        rows.append({"variable": var, "extracted": ext, "published": p, "error_pct": err, "agree": abs(err) <= 5})
    return {"rows": rows, "source": "adapter-published values (demo table)", "all_agree": all(r["agree"] for r in rows) if rows else None}


def load_result(test_id: str) -> dict | None:
    p = VDIR / f"{test_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def write_canonical() -> dict:
    """Push image-derived values into the canonical tables with provenance."""
    tests = pd.read_parquet(PROCESSED / "tests.parquet")
    prov = pd.read_parquet(PROCESSED / "provenance.parquet")
    prov = prov[~prov["variable"].astype(str).str.startswith("img_")]
    meas, newprov = [], []
    for c in ["img_burn_rate_k_mm2_s", "img_d0_mm", "img_extinction_d_mm"]:
        tests[c] = np.nan
    tests["image_derived"] = "[]"
    summary = []
    known = set(tests.test_id)
    for test_id in media_by_test():
        r = load_result(test_id)
        if not r or test_id not in known:
            continue
        bl = r["views"].get("backlit", {})
        for fr in r["frames"]:
            if fr.get("droplet"):
                meas.append({"media_id": bl.get("media_id"), "frame": fr["frame"], "t_s": fr["t"],
                             "quantity": "droplet_diameter_mm", "value": fr["droplet"]["droplet_diameter_mm"],
                             "confidence": fr["droplet"]["confidence"], "extractor": bl.get("extractor"),
                             "version": bl.get("version"), "mask_ref": f"vision/{test_id}.json#frame={fr['frame']}"})
            if fr.get("flame") and fr["flame"].get("lit"):
                fv = r["views"]["flame"]
                meas.append({"media_id": fv["media_id"], "frame": fr["frame"], "t_s": fr["t"],
                             "quantity": "flame_diameter_mm", "value": fr["flame"]["flame_diameter_mm"],
                             "confidence": fr["flame"]["confidence"], "extractor": fv["extractor"],
                             "version": fv["version"], "mask_ref": f"vision/{test_id}.json#frame={fr['frame']}"})
        d = r["derived"]
        idx = tests.index[tests.test_id == test_id]
        if not len(idx):
            continue
        vals = {"img_burn_rate_k_mm2_s": d["fit"].get("K") if d["fit"].get("ok") else None,
                "img_d0_mm": d.get("d0_mm"), "img_extinction_d_mm": d.get("extinction_d_mm")}
        derived_list = []
        for var, v in vals.items():
            if v is None:
                continue
            tests.loc[idx, var] = v
            derived_list.append(var)
            w = d["fit"].get("window") or [None, None]
            steps = [{"op": "extract", "detail": f"{bl.get('extractor')} v{bl.get('version')} params={json.dumps(bl.get('params'))}"}]
            if var == "img_burn_rate_k_mm2_s":
                steps.append({"op": "fit", "detail": f"d² law fit, window {w[0]:.2f}–{w[1]:.2f} s, n={d['fit']['n']}, R²={d['fit']['r2']:.4f}"})
            if r.get("overrides"):
                steps.append({"op": "manual_correction", "detail": json.dumps(r["overrides"])})
            newprov.append({"dataset": tests.loc[idx[0], "dataset"], "test_id": test_id, "variable": var,
                            "source_file": f"data/raw/{bl.get('path')}", "locator": f"frames 0–{bl.get('n_frames', 0) - 1}",
                            "column": None, "raw_value": None, "steps": json.dumps(steps)})
        tests.loc[idx, "image_derived"] = json.dumps(derived_list)
        summary.append({"test_id": test_id, "kind": r["kind"], **{k: v for k, v in vals.items()},
                        "validation": r["validation"]})
    tests.to_parquet(PROCESSED / "tests.parquet", index=False)
    pd.concat([prov, pd.DataFrame(newprov)], ignore_index=True).to_parquet(PROCESSED / "provenance.parquet", index=False)
    pd.DataFrame(meas).to_parquet(PROCESSED / "measurements.parquet", index=False)
    errs = [abs(v["error_pct"]) for s in summary for v in s["validation"]["rows"]]
    agg = {"tests": summary, "mean_abs_error_pct": float(np.mean(errs)) if errs else None,
           "n_comparisons": len(errs), "all_test_patterns": all(s["kind"] == "test_pattern" for s in summary)}
    (VDIR / "validation_summary.json").write_text(json.dumps(agg, default=float, indent=1), encoding="utf-8")
    return agg


def run_all() -> dict:
    for test_id in media_by_test():
        t0 = time.time()
        r = process_test(test_id)
        fit = r["derived"]["fit"]
        print(f"vision {test_id}: {len(r['frames'])} frames, K={fit.get('K', float('nan')):.4f} R²={fit.get('r2', 0):.4f} "
              f"({time.time() - t0:.1f}s) validation={[(v['variable'], round(v['error_pct'], 2)) for v in r['validation']['rows']]}")
    return write_canonical()


def start_job(test_id: str, params: dict | None) -> str:
    jid = uuid.uuid4().hex[:10]
    JOBS[jid] = {"id": jid, "test_id": test_id, "status": "running", "progress": 0.0, "started": time.time()}

    def work():
        try:
            process_test(test_id, params, progress=lambda p: JOBS[jid].update(progress=round(p, 3)))
            write_canonical()
            JOBS[jid].update(status="done", progress=1.0)
        except Exception as e:  # surfaced to the UI
            JOBS[jid].update(status="error", error=str(e))
    threading.Thread(target=work, daemon=True).start()
    return jid
