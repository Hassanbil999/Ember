"""Read side of the §5 tables: what the §9 API returns. Filtering, facets and sorting follow the prototype's
passes(), fit() and nearOf() exactly, moved to the server."""
from __future__ import annotations

import json
import math
from functools import lru_cache

import pandas as pd

from ..core.store import get_store
from ..sim.model import DEFAULTS, rec_dist
from .credibility import score
from .groups import simulatable

TYPES = ["data", "paper", "report", "slides", "video", "image", "news"]
GOAL_WEIGHT = {"prevent": 1.0, "suppress": 0.85, "detect": 0.85, "basics": 0.45}
OUTCOME_TEXT = {"burned": "burned", "went_out": "went out", "cool_flame": "cool flame", "flame": "flame", "measured": "measured"}


def _v(x):
    if x is None or x is pd.NA:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if hasattr(x, "item"):
        x = x.item()
    return x


def _j(x, default):
    x = _v(x)
    if x is None:
        return default
    return json.loads(x) if isinstance(x, str) else x


def point_payload(r: dict) -> dict:
    p = {k: _v(v) for k, v in r.items()}
    p["extra"] = _j(r.get("extra"), {})
    p["verified"] = bool(p.get("verified"))
    p["outcome_text"] = OUTCOME_TEXT.get(p.get("outcome"), p.get("outcome"))
    p["simulatable"] = simulatable(p.get("material"), p.get("o2_pct"), p.get("outcome"))
    p["placeholder"] = p.get("origin") == "seed"
    return p


class Catalog:
    """Parsed, indexed view of the §5 tables. Rebuilt when the store reloads."""

    def __init__(self):
        st = get_store()
        a = st.atlas
        self.presets = [{k: _v(v) for k, v in r.items()} for r in a["presets"].to_dict("records")]
        self.preset_by_key = {p["key"]: p for p in self.presets}
        self.params = {m: dict(v) for m, v in DEFAULTS.items()}
        self.params_meta = {m: {"n_points": 0, "rmse": None, "fitted_at": None, "source": "defaults (SPEC §8.1)"} for m in DEFAULTS}
        for r in a["model_params"].to_dict("records"):
            self.params[r["material"]] = {k: float(r[k]) for k in ("xmin", "ustar", "kl", "kh", "c", "pexp")}
            self.params_meta[r["material"]] = {"n_points": int(_v(r.get("n_points")) or 0), "rmse": _v(r.get("rmse")),
                                               "fitted_at": _v(r.get("fitted_at")), "source": _v(r.get("source"))}
        self.investigations = []
        for r in a["investigations"].to_dict("records"):
            self.investigations.append({
                "slug": r["slug"], "name": r["name"], "full_name": _v(r["full_name"]), "purposes": _j(r["purposes"], []),
                "fuels": _j(r["fuels"], []), "envs": _j(r["envs"], []), "hardware": _v(r["hardware"]), "summary": _v(r["summary"]),
                "psi_url": _v(r["psi_url"]), "members": _j(r["members"], []), "origin": r["origin"]})
        self.inv = {i["slug"]: i for i in self.investigations}
        self.points = {r["code"]: point_payload(r) for r in a["test_points"].to_dict("records")}
        self.sim_points = [p for p in self.points.values() if p["simulatable"]]
        links = a["resource_points"]
        by_res: dict[str, list[str]] = {}
        for rid, code in zip(links.resource_id, links.code):
            by_res.setdefault(rid, []).append(code)
        self.resources = []
        for r in a["resources"].to_dict("records"):
            invs = [i for i in _j(r.get("investigations"), []) if i] or ([r["investigation"]] if _v(r.get("investigation")) else [])
            codes = by_res.get(r["id"], [])
            pts = [self.points[c] for c in codes if c in self.points]
            sim = [p for p in pts if p["simulatable"]]
            envs = _j(r.get("envs_override"), None) or list(dict.fromkeys(e for i in invs for e in self.inv.get(i, {}).get("envs", [])))
            item = {k: _v(r.get(k)) for k in ("id", "type", "title", "publisher", "year", "format", "url", "description", "status",
                                               "investigation", "investigation_detail", "origin", "doi", "psi_id", "dataset", "doc_id")}
            if item["year"] is not None:
                item["year"] = int(item["year"])
            item.update({
                "investigations": invs, "envs": envs, "points_count": len(pts), "sim_point": sim[0]["code"] if sim else None,
                "credibility": score(item["status"], item["url"], r.get("cred_publisher"), r.get("cred_review"), r.get("cred_trace")),
                "placeholder": item["status"] == "placeholder",
            })
            item["_codes"] = codes
            item["_o2"] = [p["o2_pct"] for p in pts if p.get("o2_pct") is not None]
            item["_sim"] = sim
            inv_names = " ".join(self.inv[i]["name"] for i in invs if i in self.inv)
            labels = " ".join(dict.fromkeys(p.get("sample_desc") or "" for p in pts))
            item["_hay"] = " ".join(str(x or "") for x in (item["title"], item["publisher"], inv_names, item["description"],
                                                           item["investigation_detail"], labels)).lower()
            self.resources.append(item)
        self.res = {r["id"]: r for r in self.resources}

    # ---------------------------------------------------------------- resources
    def _tags(self, r: dict, key: str) -> list[str]:
        return list(dict.fromkeys(t for i in r["investigations"] for t in self.inv.get(i, {}).get(key, [])))

    def passes(self, r: dict, f: dict, skip_type: bool = False) -> bool:
        if not skip_type and f["types"] and r["type"] not in f["types"]:
            return False
        if f["inv"] and not set(r["investigations"]) & set(f["inv"]):
            return False
        if f["purpose"] and not set(self._tags(r, "purposes")) & set(f["purpose"]):
            return False
        if f["fuel"] and not set(self._tags(r, "fuels")) & set(f["fuel"]):
            return False
        if f["env"] and not set(r["envs"]) & set(f["env"]):
            return False
        s = r["credibility"]["score"]
        cm = f["cred_min"]
        if cm == "verified" and s is None or cm == "medium" and not (s is not None and s >= 65) or cm == "high" and not (s is not None and s >= 85):
            return False
        if f["q"] and f["q"] not in r["_hay"]:
            return False
        return True

    def fit(self, r: dict, preset: dict) -> float:
        goal = max([GOAL_WEIGHT.get(p, 0.45) for p in self._tags(r, "purposes")] or [0.45])
        env = 1.0 if preset["env"] in r["envs"] else 0.4
        o = [math.exp(-abs(v - preset["o2"]) / 12) for v in r["_o2"]]
        c = r["credibility"]["score"]
        return 0.35 * goal + 0.25 * env + 0.15 * (max(o) if o else 0.4) + 0.25 * (0.3 if c is None else c / 100)

    def near(self, r: dict, sim: dict) -> float:
        return min([rec_dist(p, sim["g"], sim["o2"], sim["psi"], sim["u"], sim["material"]) for p in r["_sim"]] or [math.inf])

    def query(self, f: dict, sort: str, sim: dict, page: int, page_size: int) -> dict:
        items = [r for r in self.resources if self.passes(r, f)]
        preset = self.preset_by_key.get(sort[4:] if sort.startswith("fit:") else "moon") or (self.presets[0] if self.presets else None)
        if sort.startswith("fit:") and preset:
            items.sort(key=lambda r: -self.fit(r, preset))
        elif sort == "cred":
            items.sort(key=lambda r: -(r["credibility"]["score"] if r["credibility"]["score"] is not None else -1))
        elif sort == "near":
            items.sort(key=lambda r: self.near(r, sim))
        else:
            items.sort(key=lambda r: -(r["year"] or 0))
        facets = {t: sum(1 for r in self.resources if r["type"] == t and self.passes(r, f, skip_type=True)) for t in TYPES}
        total = len(items)
        lo = (page - 1) * page_size
        out = []
        for r in items[lo:lo + page_size]:
            o = public(r)
            if sort.startswith("fit:") and preset:
                o["fit"] = round(self.fit(r, preset), 4)
            if sort == "near":
                d = self.near(r, sim)
                o["near"] = None if math.isinf(d) else round(d, 3)
            out.append(o)
        return {"items": out, "total": total, "page": page, "page_size": page_size, "facets": {"types": facets},
                "counts": {"high": sum(1 for r in items if r["credibility"]["label"] == "High"),
                           "unverified": sum(1 for r in items if r["credibility"]["score"] is None)},
                "preset": preset["key"] if preset else None}

    def detail(self, rid: str, limit: int = 25) -> dict | None:
        r = self.res.get(rid)
        if r is None:
            return None
        pts = [self.points[c] for c in r["_codes"] if c in self.points]
        pts.sort(key=lambda p: not p["simulatable"])      # simulatable tests first (stable: source-table order after)
        out = public(r)
        out["test_points"] = pts[:limit]
        out["points_total"] = len(pts)
        out["investigation_names"] = [self.inv[i]["name"] for i in r["investigations"] if i in self.inv]
        out["credibility_formula"] = "Score = 0.4 × publisher + 0.3 × review + 0.3 × traceability"
        return out


def public(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


_cache: dict = {}


def catalog() -> Catalog:
    v = get_store().version
    if _cache.get("v") != v:
        _cache["cat"] = Catalog()
        _cache["v"] = v
    return _cache["cat"]
