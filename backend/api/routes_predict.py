"""Fire check routes: estimate from NASA's outcome-labelled tests, and the engineering report."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..predict import report, service

router = APIRouter(prefix="/api/fire-check", tags=["fire check"])


class CheckReq(BaseModel):
    problem: Literal["gas", "droplet"]
    fuel: str = Field(..., max_length=40)
    o2_pct: float = Field(..., ge=0, le=100, description="oxygen, % by volume")
    psi: float = Field(..., gt=0, le=100, description="total pressure, psi")
    gravity_g: float = Field(0.0, ge=0, le=1.5)
    fuel_flow: Optional[float] = Field(None, ge=0, le=100, description="gas: fuel flow, mg/s")
    d0_mm: Optional[float] = Field(None, gt=0, le=20, description="droplet: starting drop size, mm")
    co2_pct: float = Field(0.0, ge=0, le=100, description="droplet: CO₂ share of the air, %")
    he_pct: float = Field(0.0, ge=0, le=100, description="droplet: helium share of the air, %")


def _run(body: CheckReq) -> dict:
    if not service.available():
        raise HTTPException(503, "The fire-check models are not trained yet (python -m backend.ingest predict).")
    req = body.model_dump()
    if body.problem == "gas" and body.fuel_flow is None:
        raise HTTPException(422, "A gas check needs fuel_flow (mg/s).")
    if body.problem == "droplet" and body.d0_mm is None:
        raise HTTPException(422, "A droplet check needs d0_mm (mm).")
    try:
        res = service.check(req)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    res["verdict"] = report.verdict(res)
    return res


@router.get("/meta")
def meta():
    if not service.available():
        raise HTTPException(503, "The fire-check models are not trained yet (python -m backend.ingest predict).")
    return service.meta()


@router.get("/pipeline")
def pipeline_view():
    """Statistics page: cleaning counts, unsupervised clusters of the test conditions, and the Gaussian process's
    chance map (empty where the fire check would say untested), per question."""
    if not service.available():
        raise HTTPException(503, "The fire-check models are not trained yet (python -m backend.ingest predict).")
    from ..predict import pipeline
    return pipeline.build()


@router.get("/map")
def fire_map():
    """Fire map: every NASA test with a recorded ending by oxygen, pressure and fuel, plus where new tests are needed
    (the models' next tests per fuel, and the crew air with its zone per fuel)."""
    if not service.available():
        raise HTTPException(503, "The fire-check models are not trained yet (python -m backend.ingest predict).")
    from ..predict import firemap
    return firemap.build()


@router.post("")
def check(body: CheckReq):
    return _run(body)


@router.post("/report", response_class=HTMLResponse)
def report_file(body: CheckReq):
    res = _run(body)
    stamp = datetime.now(timezone.utc)
    html = report.render(res, stamp)
    name = f"fire-check-{body.problem}-{stamp:%Y%m%d-%H%M%S}.html"
    return HTMLResponse(html, headers={"Content-Disposition": f'attachment; filename="{name}"'})
