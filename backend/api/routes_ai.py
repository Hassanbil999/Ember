"""SPEC §9 AI routes. Summary falls back to a template with no API key (SPEC §11)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..ai import llm
from ..ai.ask import ask as ask_atlas, retrieve
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


class AskReq(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    filters: dict | None = None


@router.post("/ask")
def ask(body: AskReq):
    """Answer grounded in retrieved NASA passages, each sentence citing [resource_id p.N]. If retrieval finds
    nothing relevant: "The data here doesn't cover that." With no API key: 503, with the relevant passages."""
    try:
        return ask_atlas(body.question)
    except llm.AIUnavailable as e:
        passages = [{k: p[k] for k in ("resource_id", "page", "title", "section")} | {"excerpt": p["text"][:400]}
                    for p in retrieve(body.question)]
        return JSONResponse(status_code=503, content={"detail": str(e), "passages": passages})


@router.get("/status")
def status():
    """Whether AI features are on, and which model they use."""
    return {"enabled": llm.enabled(), "model": llm.model_name() if llm.enabled() else None,
            "fallback": "Summaries use a template and Ask returns the relevant passages when no key is set."}
