"""SPEC §9 AI routes. Summary falls back to a template with no API key (SPEC §11)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..ai.summary import summarize

router = APIRouter(prefix="/api/ai", tags=["ai"])


class SummaryReq(BaseModel):
    q: str = ""
    types: list[str] = Field(default_factory=list)
    inv: list[str] = Field(default_factory=list)
    purpose: list[str] = Field(default_factory=list)
    fuel: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    cred_min: str = "any"
    sort: str = "fit:moon"
    g: float = 0.166
    o2: float = 34
    psi: float = 8.2
    u: float = 10
    material: str = "fabric"


@router.post("/summary")
def summary(body: SummaryReq):
    if body.cred_min not in ("any", "verified", "medium", "high"):
        raise HTTPException(422, "cred_min must be any, verified, medium or high")
    f = {"types": body.types, "inv": body.inv, "purpose": body.purpose, "fuel": body.fuel, "env": body.env,
         "cred_min": body.cred_min, "q": body.q.strip().lower()}
    sim = {"g": body.g, "o2": body.o2, "psi": body.psi, "u": body.u, "material": body.material if body.material in ("fabric", "pmma") else "fabric"}
    return summarize(f, body.sort, sim)
