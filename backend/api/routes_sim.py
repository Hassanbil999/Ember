"""SPEC §9 simulator routes."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..sim import service

router = APIRouter(prefix="/api", tags=["simulator"])


class SimReq(BaseModel):
    g: float = Field(0.166, ge=0, le=1.2, description="gravity, Earth g")
    o2: float = Field(34, ge=0, le=100, description="oxygen, % by volume")
    psi: float = Field(8.2, gt=0.5, le=30, description="total pressure, psi")
    u: float = Field(10, ge=0, le=100, description="forced airflow, cm/s")
    material: Literal["fabric", "pmma"] = "fabric"


@router.post("/simulate")
def simulate(body: SimReq):
    """Model result, time series (t[], I[], x_mm[], t_out, t_end, D), coverage message, 3 nearest test points
    and the model parameters used. Illustrative reduced-order model (SPEC §8)."""
    return service.run(body.g, body.o2, body.psi, body.u, body.material)


@router.get("/flammability-map")
def flammability_map(g: float = Query(0.166, ge=0, le=1.2), o2: float = Query(34, ge=0, le=100),
                     psi: float = Query(8.2, gt=0.5, le=30), u: float = Query(10, ge=0, le=100),
                     material: Literal["fabric", "pmma"] = "fabric"):
    """Flame-limit curve (oxygen limit against airflow) for the settings, the measured points for this
    gravity and material, and where the settings sit."""
    return service.flammability_map(g, o2, psi, u, material)


@router.get("/outside/zarm")
def outside_zarm():
    """Evidence from outside NASA, kept apart: ZARM drop-tower flame-spread rates over thin acrylic (backend/external.py).
    Shown next to the illustrative simulator for acrylic; never used to fit it."""
    from .. import external
    src = external.sources().get("zarm_barriers") or {}
    return {"label": src.get("label"), "material": src.get("material"), "doi": src.get("doi"), "url": src.get("url"),
            "citation": src.get("citation"), "license": src.get("license"), "limits": src.get("limits", []),
            "points": external.zarm_spread()}
