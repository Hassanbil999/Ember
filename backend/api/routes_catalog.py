"""SPEC §9 catalog routes: presets, investigations, resources, test points, model parameters."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ..catalog.query import catalog, public

router = APIRouter(prefix="/api", tags=["catalog"])

CRED_MIN = {"any", "verified", "medium", "high"}


def multi(request: Request, name: str) -> list[str]:
    """`types=a&types=b`, `types[]=a` and `types=a,b` all mean the same list."""
    vals = request.query_params.getlist(name) + request.query_params.getlist(f"{name}[]")
    return [p.strip() for v in vals for p in v.split(",") if p.strip()]


def _float(request: Request, name: str, default: float) -> float:
    v = request.query_params.get(name)
    try:
        return float(v) if v not in (None, "") else default
    except ValueError:
        raise HTTPException(422, f"{name} must be a number")


def filters_from(request: Request) -> dict:
    cm = request.query_params.get("cred_min", "any")
    if cm not in CRED_MIN:
        raise HTTPException(422, f"cred_min must be one of {sorted(CRED_MIN)}")
    return {"types": multi(request, "types"), "inv": multi(request, "inv"), "purpose": multi(request, "purpose"),
            "fuel": multi(request, "fuel"), "env": multi(request, "env"), "cred_min": cm,
            "q": (request.query_params.get("q") or "").strip().lower()}


def sim_from(request: Request) -> dict:
    mat = request.query_params.get("material", "fabric")
    return {"g": _float(request, "g", 0.166), "o2": _float(request, "o2", 34), "psi": _float(request, "psi", 8.2),
            "u": _float(request, "u", 10), "material": mat if mat in ("fabric", "pmma") else "fabric"}


@router.get("/presets")
def presets():
    """Environment presets: label, gravity (g), oxygen (%), pressure (psi), airflow u (cm/s), environment, note."""
    return catalog().presets


@router.get("/investigations")
def investigations():
    return catalog().investigations


@router.get("/resources")
def resources(request: Request):
    """Filtered, sorted resources with credibility and facet counts per type.

    Query: q, types[], inv[], purpose[], fuel[], env[], cred_min (any|verified|medium|high),
    sort (fit:<preset>|cred|near|new), g, o2, psi, u, material, page, page_size."""
    sort = request.query_params.get("sort", "fit:moon")
    if not (sort.startswith("fit:") or sort in ("cred", "near", "new")):
        raise HTTPException(422, "sort must be fit:<preset>, cred, near or new")
    page = max(1, int(_float(request, "page", 1)))
    size = min(200, max(1, int(_float(request, "page_size", 50))))
    return catalog().query(filters_from(request), sort, sim_from(request), page, size)


@router.get("/resources/{rid}")
def resource(rid: str, points_limit: int = 25):
    d = catalog().detail(rid, limit=max(0, min(points_limit, 2000)))
    if d is None:
        raise HTTPException(404, f"No resource {rid}")
    return d


@router.get("/test-points")
def test_points(request: Request):
    """Filter by investigation, material, verified, simulatable, code, and O₂ / pressure / flow / gravity ranges."""
    c = catalog()
    inv, mats, codes = multi(request, "investigation") or multi(request, "inv"), multi(request, "material"), multi(request, "code")
    q = request.query_params
    pts = c.points.values() if not codes else [c.points[x] for x in codes if x in c.points]
    out = []
    for p in pts:
        if inv and p.get("investigation") not in inv or mats and p.get("material") not in mats:
            continue
        if q.get("verified") in ("true", "false") and p["verified"] != (q["verified"] == "true"):
            continue
        if q.get("simulatable") in ("true", "false") and p["simulatable"] != (q["simulatable"] == "true"):
            continue
        ok = True
        for var, lo_k, hi_k in (("o2_pct", "o2_min", "o2_max"), ("pressure_kpa", "kpa_min", "kpa_max"),
                                ("flow_cm_s", "flow_min", "flow_max"), ("gravity_g", "g_min", "g_max")):
            v = p.get(var)
            if (q.get(lo_k) or q.get(hi_k)) and v is None:
                ok = False
            elif q.get(lo_k) and v < float(q[lo_k]) or q.get(hi_k) and v > float(q[hi_k]):
                ok = False
        if ok:
            out.append(p)
    page = max(1, int(_float(request, "page", 1)))
    size = min(2000, max(1, int(_float(request, "page_size", 200))))
    return {"items": out[(page - 1) * size:page * size], "total": len(out), "page": page, "page_size": size}


@router.get("/model-params")
def model_params():
    """Parameters the simulator uses per material, and whether they are §8.1 defaults or fitted (§8.4)."""
    c = catalog()
    return {"params": c.params, "meta": c.params_meta}


__all__ = ["router", "public"]
