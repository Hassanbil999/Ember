"""Atlas: the corpus as a graph with precomputed layouts per lens, auto-grouping of tests,
relationship statistics, nearest-test lookup and next-path generation."""
from __future__ import annotations

import json
import zlib
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
from sklearn.tree import DecisionTreeClassifier

from .core import config
from .core.config import ARTIFACTS, PROCESSED

W, H = 1700, 1040
NUMERIC = ["o2_frac", "pressure_kpa", "o2_pp_kpa", "flow_cm_s", "d0_mm", "thickness_mm", "gravity_g"]
OUTCOMES = ["burned", "burn_rate_k_mm2_s", "extinction_d_mm", "spread_rate_mm_s"]
PILLAR_ORDER = ["prevention", "detection", "suppression"]


def _fmt_var(var: str, v: float) -> str:
    meta = config.variables().get(var, {})
    scale = meta.get("display_scale", 1)
    unit = meta.get("display_unit", meta.get("unit", ""))
    return f"{v * scale:.3g}{'' if unit == '%' else ' '}{unit}".strip()


# ------------------------------------------------------------------ auto-grouping
def group_tests(tests: pd.DataFrame, dataset: str, mode: str = "regime", max_groups: int = 6) -> list[dict]:
    """Group a dataset's tests into labeled clusters.

    regime  – shallow decision tree on the outcome: each leaf is a group labeled by the
              conditions that define it (e.g. "O₂ ≥ 18.6% · P < 86 kPa").
    campaign – by test campaign (time).
    """
    t = tests[(tests.dataset == dataset) & (~tests.excluded)].copy()
    if t.empty:
        return []
    if mode == "campaign":
        groups = []
        for camp, g in t.groupby("campaign"):
            groups.append(_group_summary(g, f"Campaign {camp}", [f"campaign = {camp}"], dataset, f"{dataset}:c:{camp}"))
        return groups
    feats = [c for c in NUMERIC if t[c].notna().mean() > 0.9 and t[c].nunique() > 1]
    cats = [c for c in ["diluent", "fuel", "material"] if t[c].notna().mean() > 0.9 and t[c].nunique() > 1]
    X = t[feats].copy()
    for c in cats:
        for val in sorted(t[c].dropna().unique()):
            X[f"{c}={val}"] = (t[c] == val).astype(float)
    X = X.fillna(X.median(numeric_only=True))
    y = t["burned"]
    labeled = y.notna()
    tree = DecisionTreeClassifier(max_leaf_nodes=max_groups, min_samples_leaf=max(8, len(t) // 20), random_state=0)
    tree.fit(X[labeled], y[labeled].astype(int))
    leaves = tree.apply(X)
    tr = tree.tree_
    # rule path per leaf
    paths: dict[int, list] = {}

    def walk(node, conds):
        if tr.children_left[node] == -1:
            paths[node] = conds
            return
        f = X.columns[tr.feature[node]]
        th = tr.threshold[node]
        walk(tr.children_left[node], conds + [(f, "<", th)])
        walk(tr.children_right[node], conds + [(f, "≥", th)])
    walk(0, [])
    groups = []
    for leaf, conds in paths.items():
        g = t[leaves == leaf]
        if g.empty:
            continue
        # merge redundant bounds into readable ranges
        lo, hi, catlab = {}, {}, []
        for f, op, th in conds:
            if "=" in f:
                var, val = f.split("=", 1)
                catlab.append(f"{val}" if op == "≥" else f"not {val}")
            elif op == "<":
                hi[f] = min(hi.get(f, math.inf), th)
            else:
                lo[f] = max(lo.get(f, -math.inf), th)
        parts = []
        for f in dict.fromkeys(list(lo) + list(hi)):
            short = config.variables().get(f, {}).get("short", f)
            if f in lo and f in hi:
                parts.append(f"{short} {_fmt_var(f, lo[f])}–{_fmt_var(f, hi[f])}")
            elif f in lo:
                parts.append(f"{short} ≥ {_fmt_var(f, lo[f])}")
            else:
                parts.append(f"{short} < {_fmt_var(f, hi[f])}")
        parts += catlab
        label = " · ".join(parts) if parts else "All tests"
        groups.append(_group_summary(g, label, parts, dataset, f"{dataset}:r:{leaf}"))
    groups.sort(key=lambda g: -g["burn_share"] if g["burn_share"] is not None else 0)
    return groups


def _group_summary(g: pd.DataFrame, label: str, conditions: list[str], dataset: str, gid: str) -> dict:
    b = g["burned"].dropna()
    rate_col = "burn_rate_k_mm2_s" if g["burn_rate_k_mm2_s"].notna().any() else "spread_rate_mm_s"
    rates = g[rate_col].dropna()
    ranges = {}
    for v in NUMERIC:
        col = g[v].dropna()
        if len(col) and col.nunique() > 0:
            ranges[v] = [float(col.min()), float(col.max())]
    return {"id": f"cluster:{gid}", "dataset": dataset, "label": label, "conditions": conditions, "n": int(len(g)),
            "burn_share": float(b.mean()) if len(b) else None, "n_outcome": int(len(b)),
            "rate_var": rate_col, "rate_median": float(rates.median()) if len(rates) else None,
            "ranges": ranges, "test_ids": g["test_id"].tolist()}


# ------------------------------------------------------------------ relationships
def relationships(tests: pd.DataFrame, dataset: str) -> dict:
    t = tests[(tests.dataset == dataset) & (~tests.excluded)]
    vars_ = [c for c in NUMERIC + OUTCOMES if t[c].notna().sum() >= 12 and t[c].nunique() > 1]
    n = len(vars_)
    rho = np.full((n, n), np.nan)
    mi = np.full((n, n), np.nan)
    cnt = np.zeros((n, n), dtype=int)
    for i, a in enumerate(vars_):
        for j, b in enumerate(vars_):
            sub = t[[a, b]].dropna()
            cnt[i, j] = len(sub)
            if len(sub) < 12:
                continue
            if i == j:
                rho[i, j] = 1.0
                continue
            r, _ = spearmanr(sub[a], sub[b])
            rho[i, j] = r
            if j > i:
                Xa = sub[[a]].values
                if b == "burned":
                    m = mutual_info_classif(Xa, sub[b].astype(int), random_state=0)[0]
                elif a == "burned":
                    m = mutual_info_classif(sub[[b]].values, sub[a].astype(int), random_state=0)[0]
                else:
                    m = mutual_info_regression(Xa, sub[b], random_state=0)[0]
                mi[i, j] = mi[j, i] = m
    # order by hierarchical clustering on |rho|
    order = list(range(n))
    if n > 2:
        D = 1 - np.nan_to_num(np.abs(rho), nan=0)
        np.fill_diagonal(D, 0)
        try:
            from scipy.cluster.hierarchy import leaves_list, linkage
            from scipy.spatial.distance import squareform
            order = leaves_list(linkage(squareform(D, checks=False), "average")).tolist()
        except Exception:
            pass
    return {"dataset": dataset, "vars": vars_, "spearman": np.round(rho, 3).tolist(), "mutual_info": np.round(mi, 3).tolist(),
            "n": cnt.tolist(), "order": order,
            "caveat": "Association, not causation. Fixture variables were sampled independently by design, so "
                      "condition–condition correlations are near zero; condition–outcome links reflect the data only."}


# ------------------------------------------------------------------ nearest tests
def tests_near(tests: pd.DataFrame, conditions: dict, categories: dict | None = None, k: int = 8,
               dataset: str | None = None) -> list[dict]:
    t = tests[~tests.excluded]
    if dataset:
        t = t[t.dataset == dataset]
    vars_ = [v for v in conditions if v in NUMERIC and v != "gravity_g"]
    if not vars_:
        return []
    sd = {v: (tests[v].std() or 1.0) for v in vars_}
    d = np.zeros(len(t))
    used = np.zeros(len(t))
    for v in vars_:
        col = t[v].values.astype(float)
        ok = ~np.isnan(col)
        d[ok] += ((col[ok] - conditions[v]) / sd[v]) ** 2
        used += ok
    d = np.sqrt(d / np.maximum(used, 1))
    d[used == 0] = np.inf
    for c, val in (categories or {}).items():
        if c in t.columns:
            d = d + np.where(t[c].values == val, 0, 0.75)
    order = np.argsort(d)[:k]
    out = []
    for i in order:
        if not np.isfinite(d[i]):
            continue
        r = t.iloc[i]
        out.append({"test_id": r.test_id, "dataset": r.dataset, "distance": round(float(d[i]), 3),
                    **{c: (None if pd.isna(r[c]) else (float(r[c]) if c in NUMERIC + OUTCOMES else str(r[c])))
                       for c in NUMERIC + OUTCOMES + ["fuel", "material", "diluent", "campaign"]}})
    return out


# ------------------------------------------------------------------ graph + layouts
def _relax(pos: dict, anchors: set, links: dict, sizes: dict, iters: int = 260, bounds=(W, H)) -> dict:
    ids = list(pos)
    P = np.array([pos[i] for i in ids], dtype=float)
    R = np.array([sizes.get(i, 10) + (16 if i.startswith("inv:") else 34) for i in ids], dtype=float)
    fixed = np.array([i in anchors for i in ids])
    idx = {i: k for k, i in enumerate(ids)}
    for it in range(iters):
        F = np.zeros_like(P)
        for i, nbrs in links.items():
            if i not in idx or fixed[idx[i]]:
                continue
            tgt = [P[idx[n]] for n in nbrs if n in idx]
            if tgt:
                F[idx[i]] += (np.mean(tgt, axis=0) - P[idx[i]]) * 0.08
        diff = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((diff ** 2).sum(-1)) + 1e-6
        minD = R[:, None] + R[None, :]
        push = np.clip(minD - dist, 0, None) / dist
        np.fill_diagonal(push, 0)
        F += (diff * push[..., None]).sum(1) * 0.5
        F[fixed] = 0
        P += F
        P[:, 0] = np.clip(P[:, 0], 40, bounds[0] - 40)
        P[:, 1] = np.clip(P[:, 1], 60, bounds[1] - 40)
    return {i: [round(float(P[k, 0]), 1), round(float(P[k, 1]), 1)] for k, i in enumerate(ids)}


def _grid_in(region, n):
    x0, y0, w, h = region
    cols = max(1, math.ceil(math.sqrt(n * w / max(h, 1))))
    rows = math.ceil(n / cols)
    out = []
    for k in range(n):
        c, r = k % cols, k // cols
        out.append([x0 + w * (c + 0.5) / cols, y0 + 60 + (h - 80) * (r + 0.5) / max(rows, 1)])
    return out


def build_atlas():
    tests = pd.read_parquet(PROCESSED / "tests.parquet")
    tests["flags"] = tests["flags"].map(json.loads)
    inv = pd.read_parquet(PROCESSED / "investigations.parquet")
    docs = pd.read_parquet(PROCESSED / "documents.parquet")
    concepts = pd.read_parquet(PROCESSED / "concepts.parquet")
    dscfg = config.datasets()

    nodes, edges = [], []
    links = defaultdict(set)

    def link(a, b, kind):
        edges.append({"source": a, "target": b, "kind": kind})
        links[a].add(b)
        links[b].add(a)

    inv_stats = {}
    for _, r in inv.iterrows():
        ds = json.loads(r.datasets)
        t = tests[tests.dataset.isin(ds) & ~tests.excluded & (tests.investigation_id == r.id)] if ds else tests.iloc[0:0]
        stats = {"n_tests": int(len(t))}
        for v in ["o2_frac", "pressure_kpa", "flow_cm_s", "gravity_g"]:
            col = t[v].dropna()
            if len(col):
                stats[v] = [float(col.min()), float(col.mean()), float(col.max())]
        inv_stats[r.id] = stats
        nodes.append({"id": f"inv:{r.id}", "type": "investigation", "label": r.id, "name": r["name"],
                      "pillars": json.loads(r.pillars), "hardware": r.hardware, "fuel_phase": r.fuel_phase,
                      "platform": r.platform, "years": json.loads(r.years), "parent": r.parent, "stats": stats,
                      "datasets": ds, "investigations": [r.id], "size": 16 + min(10, len(t) / 15)})
        if r.parent and isinstance(r.parent, str):
            link(f"inv:{r.id}", f"inv:{r.parent}", "part-of")

    for ds_id, cfg in dscfg.items():
        if cfg["adapter"] == "pdf_reports":
            continue
        t = tests[(tests.dataset == ds_id)]
        nodes.append({"id": f"ds:{ds_id}", "type": "dataset", "label": cfg["title"], "demo": cfg.get("demo", False),
                      "investigations": cfg.get("investigations", []), "n": int(len(t)),
                      "search_text": f"dataset table tests {' '.join(cfg['columns'].values())}", "size": 11})
        for i in cfg.get("investigations", []):
            link(f"ds:{ds_id}", f"inv:{i}", "data")
        for g in group_tests(tests, ds_id):
            nodes.append({"id": g["id"], "type": "cluster", "label": g["label"], "dataset": ds_id, "n": g["n"],
                          "burn_share": g["burn_share"], "investigations": cfg.get("investigations", []),
                          "demo": cfg.get("demo", False), "size": 5 + min(7, g["n"] / 6),
                          "search_text": f"tests group cluster {' '.join(g['conditions'])} {ds_id}"})
            link(g["id"], f"ds:{ds_id}", "contains")

    for _, d in docs.iterrows():
        invs = json.loads(d.investigations)
        nodes.append({"id": f"doc:{d.id}", "type": "document", "label": d.title, "pages": int(d.pages),
                      "demo": bool(d.demo), "investigations": invs, "size": 8})
        for i in invs[:6] if len(invs) > 6 else invs:
            link(f"doc:{d.id}", f"inv:{i}", "documents")

    for _, c in concepts.iterrows():
        invs = json.loads(c.investigations)
        nodes.append({"id": f"concept:{c.id}", "type": "concept", "label": c["name"], "plain": c.plain,
                      "investigations": invs, "size": 7})
        for i in invs:
            link(f"concept:{c.id}", f"inv:{i}", "concept")

    sizes = {n["id"]: n["size"] for n in nodes}
    inv_nodes = [n for n in nodes if n["type"] == "investigation"]

    # discovered structure: TF-IDF on investigation text + variable coverage
    texts = []
    for n in inv_nodes:
        r = inv.set_index("id").loc[n["label"]]
        cov = " ".join(f"var_{k}" for k in n["stats"] if k != "n_tests")
        texts.append(f"{r['name']} {r.objectives} {r.hardware} {r.fuel_phase} {cov}")
    tf = TfidfVectorizer(stop_words="english", sublinear_tf=True)
    X = tf.fit_transform(texts).toarray()
    k = min(5, len(inv_nodes))
    lab = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average").fit_predict(X)
    terms = np.array(tf.get_feature_names_out())
    disc_labels = {}
    for c in range(k):
        cen = X[lab == c].mean(0)
        top = [t for t in terms[np.argsort(-cen)] if not t.startswith("var_")][:3]
        disc_labels[c] = " · ".join(top)
    for n, c in zip(inv_nodes, lab):
        n["discovered"] = disc_labels[int(c)]

    def group_key(lens, n):
        if lens == "pillar":
            return n["pillars"][0]
        if lens == "fuel":
            return n["fuel_phase"]
        if lens == "hardware":
            return n["hardware"].split(" / ")[0]
        if lens == "gravity":
            g = n["stats"].get("gravity_g")
            if not g:
                return "microgravity (no table data)"
            return "microgravity + 1g reference" if g[2] >= 0.5 else "microgravity"
        if lens == "discovered":
            return n["discovered"]
        return "all"

    layouts = {}
    for lens in ["pillar", "fuel", "hardware", "gravity", "discovered"]:
        groups = defaultdict(list)
        for n in inv_nodes:
            groups[group_key(lens, n)].append(n)
        keys = list(groups)
        if lens == "pillar":
            keys = [p for p in PILLAR_ORDER if p in groups]
        if lens == "gravity":
            keys.append("partial gravity — no data in PSI")
        gw = (W - 120) / max(len(keys), 1)
        pos, frames = {}, []
        for gi, key in enumerate(keys):
            region = (60 + gi * gw, 60, gw - 30, H * 0.62)
            members = groups.get(key, [])
            if lens == "pillar":   # sub-group by fuel phase inside each pillar
                members = sorted(members, key=lambda n: (n["fuel_phase"], n["label"]))
            for n, p in zip(members, _grid_in(region, len(members))):
                pos[n["id"]] = p
            frames.append({"label": key, "x": region[0], "y": region[1], "w": region[2], "h": region[3],
                           "empty": len(members) == 0, "count": len(members)})
        layouts[lens] = {"frames": frames, "positions": pos, "axis": None}

    def axis_layout(var, lens, label):
        pos, have, nodata = {}, [], []
        for n in inv_nodes:
            (have if var in n["stats"] or (var == "years" and n["years"]) else nodata).append(n)
        if var == "years":
            vals = [n["years"][0] for n in have]
        else:
            vals = [n["stats"][var][1] for n in have]
        lo, hi = (min(vals), max(vals)) if vals else (0, 1)
        if hi - lo < 1e-9:
            lo, hi = lo - 1, hi + 1
        pad = (hi - lo) * 0.08
        lo, hi = lo - pad, hi + pad
        x0, x1 = 380, W - 80
        rng = {}
        for n, v in zip(have, vals):
            x = x0 + (v - lo) / (hi - lo) * (x1 - x0)
            pos[n["id"]] = [x, H * 0.33]
            if var != "years":
                a, _, b = n["stats"][var]
                rng[n["id"]] = [x0 + (a - lo) / (hi - lo) * (x1 - x0), x0 + (b - lo) / (hi - lo) * (x1 - x0)]
            else:
                y0, y1 = n["years"]
                rng[n["id"]] = [x0 + (y0 - lo) / (hi - lo) * (x1 - x0), x0 + (y1 - lo) / (hi - lo) * (x1 - x0)]
        # stack overlapping nodes vertically
        order = sorted(have, key=lambda n: pos[n["id"]][0])
        lanes: list[float] = []
        for n in order:
            x = pos[n["id"]][0]
            lane = next((li for li, last in enumerate(lanes) if x - last > 70), None)
            if lane is None:
                lanes.append(x)
                lane = len(lanes) - 1
            else:
                lanes[lane] = x
            pos[n["id"]][1] = 140 + lane * 62
        for n, p in zip(nodata, _grid_in((60, 60, 280, H * 0.62), len(nodata))):
            pos[n["id"]] = p
        meta = config.variables().get(var, {})
        scale = meta.get("display_scale", 1)
        ticks = []
        for v in np.linspace(lo + pad, hi - pad, 6):
            ticks.append({"x": x0 + (v - lo) / (hi - lo) * (x1 - x0),
                          "label": f"{v:.0f}" if var == "years" else f"{v * scale:.3g}"})
        unit = "" if var == "years" else meta.get("display_unit", meta.get("unit", ""))
        layouts[lens] = {"frames": [{"label": "no tabular data", "x": 60, "y": 60, "w": 280, "h": H * 0.62, "empty": False,
                                     "nodata": True, "count": len(nodata)}],
                         "positions": pos, "ranges": rng,
                         "axis": {"label": f"{label}" + (f" ({unit})" if unit else ""), "ticks": ticks, "y": H * 0.68}}

    axis_layout("o2_frac", "oxygen", "O₂ mole fraction — mean of tests, bar = tested range")
    axis_layout("pressure_kpa", "pressure", "Total pressure — mean of tests, bar = tested range")
    axis_layout("years", "time", "Operation period")

    for lens, lay in layouts.items():
        pos = dict(lay["positions"])
        anchors = set(pos)
        for n in nodes:
            if n["id"] in pos:
                continue
            nb = [pos[m] for m in links[n["id"]] if m in pos]
            if nb:
                c = np.mean(nb, axis=0)
                ang = (zlib.crc32(n["id"].encode()) % 360) / 180 * math.pi
                pos[n["id"]] = [c[0] + 85 * math.cos(ang), c[1] + 85 * math.sin(ang) + 30]
            else:
                pos[n["id"]] = [W / 2 + (zlib.crc32(n["id"].encode()) % 400) - 200, H * 0.82]
        # second pass for nodes linked only to non-anchors (clusters → dataset)
        for n in nodes:
            if n["type"] == "cluster":
                dpos = pos[f"ds:{n['dataset']}"]
                ang = (zlib.crc32(n["id"].encode()) % 360) / 180 * math.pi
                pos[n["id"]] = [dpos[0] + 60 * math.cos(ang), dpos[1] + 60 * math.sin(ang)]
        lay["positions"] = _relax(pos, anchors, links, sizes)

    atlas = {"nodes": nodes, "edges": edges, "layouts": layouts, "world": [W, H],
             "lenses": [{"id": "pillar", "label": "Pillar"}, {"id": "fuel", "label": "Fuel phase"},
                        {"id": "hardware", "label": "Hardware"}, {"id": "oxygen", "label": "Oxygen"},
                        {"id": "pressure", "label": "Pressure"}, {"id": "gravity", "label": "Gravity"},
                        {"id": "time", "label": "Time"}, {"id": "discovered", "label": "Discovered"},
                        {"id": "relationships", "label": "Relationships"}]}
    (ARTIFACTS / "atlas.json").write_text(json.dumps(atlas, ensure_ascii=False), encoding="utf-8")
    rel = {ds: relationships(tests, ds) for ds in dscfg if dscfg[ds]["adapter"] != "pdf_reports"}
    (ARTIFACTS / "relationships.json").write_text(json.dumps(rel), encoding="utf-8")
    print(f"atlas: {len(nodes)} nodes, {len(edges)} edges, {len(layouts)} layouts")
