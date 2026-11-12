"""Canonical data model (spec §5). Adapters emit these; everything downstream reads them."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Pillar = Literal["prevention", "detection", "suppression"]


class ProvenanceStep(BaseModel):
    op: str                      # e.g. "parse_unit", "convert", "derive", "map_category", "manual_correction"
    detail: str


class Provenance(BaseModel):
    source_file: str
    locator: str                 # "row 14", "page 3", "frames 10-80"
    raw_value: Optional[str] = None
    steps: list[ProvenanceStep] = Field(default_factory=list)


class Investigation(BaseModel):
    id: str
    name: str
    psi_id: Optional[str] = None
    doi: Optional[str] = None
    pillars: list[Pillar]
    hardware: str
    fuel_phase: str
    platform: str
    years: Optional[list[int]] = None
    objectives: str = ""
    license: str = "See PSI terms of use"
    source_urls: list[str] = Field(default_factory=lambda: ["https://psi.nasa.gov"])
    parent: Optional[str] = None
    datasets: list[str] = Field(default_factory=list)


class Variable(BaseModel):
    name: str
    label: str
    unit: Optional[str] = None
    kind: Literal["number", "category", "date", "bool"]
    role: Literal["condition", "outcome", "id", "meta"]
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    valid_range: Optional[list[float]] = None


class Test(BaseModel):
    id: str
    dataset: str
    investigation_id: str
    campaign: Optional[str] = None
    conditions: dict[str, Any]
    outcomes: dict[str, Any]
    flags: list[str] = Field(default_factory=list)
    excluded: bool = False
    image_derived: list[str] = Field(default_factory=list)
    demo: bool = False


class Document(BaseModel):
    id: str
    title: str
    file: str
    pages: int
    investigations: list[str] = Field(default_factory=list)
    demo: bool = False
    citation: str = ""


class Chunk(BaseModel):
    id: str                      # stable anchor: <doc>#p<page>-<section-slug>-<n>
    doc_id: str
    page: int
    section: str
    anchor: str
    text: str


class Citation(BaseModel):
    target_kind: Literal["row", "chunk", "measurement"]
    target_id: str
    span: Optional[str] = None
    field: Optional[str] = None
    page: Optional[int] = None
    reference: str = ""


class Concept(BaseModel):
    id: str
    name: str
    definition: str
    plain: str = ""
    investigations: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)


class Media(BaseModel):
    id: str
    test_id: str
    dataset: str
    view: Literal["backlit", "flame"]
    path: str
    format: str
    fps: float
    px_per_mm: float
    t0_s: float = 0.0
    kind: Literal["footage", "test_pattern"] = "footage"


class Measurement(BaseModel):
    media_id: str
    frame: int
    t_s: float
    quantity: str
    value: float
    confidence: float
    extractor: str
    version: str
    mask_ref: Optional[str] = None
