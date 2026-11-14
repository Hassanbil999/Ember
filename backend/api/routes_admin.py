"""Admin routes for /admin/verify (SPEC §6, §9). Every route needs the X-Admin-Token header."""
from __future__ import annotations

import threading

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..catalog import curate
from ..catalog.query import catalog
from ..core.store import get_store
from .auth import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])
_lock = threading.Lock()
ORDER = {"ai": 0, "seed": 1, "psi": 2}


class Decision(BaseModel):
    by: str = Field("", max_length=80, description="who checked it (name or initials)")
    note: str | None = Field(None, max_length=500)
    fields: dict | None = None


def _apply_and_reload() -> None:
    """Re-apply every decision, refit the model on the verified points, reload the read model."""
    from ..sim import fit
    curate.run()
    fit.run()
    get_store().reload()


@router.get("/queue")
def queue(x_admin_token: str | None = Header(default=None), origin: str | None = None, limit: int = 200):
    """Unverified test points, AI-extracted first, each with its source, page and verbatim quote."""
    require_admin(x_admin_token)
    c = catalog()
    pts = [p for p in c.points.values() if not p["verified"] and (origin is None or p["origin"] == origin)]
    pts.sort(key=lambda p: (ORDER.get(p["origin"], 3), not p["simulatable"], p["code"]))
    out = []
    for p in pts[:max(1, min(limit, 2000))]:
        src = c.res.get(p.get("source_resource_id") or "")
        out.append({**p, "source_title": src["title"] if src else None, "source_url": src["url"] if src else None})
    counts = {o: sum(1 for p in c.points.values() if not p["verified"] and p["origin"] == o) for o in ORDER}
    return {"items": out, "counts": counts, "decisions": len(curate.decisions())}


def _decide(code: str, action: str, body: Decision, token: str | None) -> dict:
    require_admin(token)
    with _lock:
        try:
            d = curate.record(code, action, body.by, body.fields, body.note)
        except curate.CurationError as e:
            raise HTTPException(422, str(e))
        _apply_and_reload()
    p = catalog().points.get(code)
    return {"decision": d, "point": p, "model_params": catalog().params_meta}


@router.post("/test-points/{code}/verify")
def verify(code: str, body: Decision, x_admin_token: str | None = Header(default=None)):
    """Mark a test point verified after checking it against its source quote and page."""
    return _decide(code, "verify", body, x_admin_token)


@router.post("/test-points/{code}/edit")
def edit(code: str, body: Decision, x_admin_token: str | None = Header(default=None)):
    """Correct an AI-extracted or seed point's values (it then needs verifying again)."""
    return _decide(code, "edit", body, x_admin_token)


@router.post("/test-points/{code}/reject")
def reject(code: str, body: Decision, x_admin_token: str | None = Header(default=None)):
    """Remove an AI-extracted or seed point that does not match its source."""
    return _decide(code, "reject", body, x_admin_token)
