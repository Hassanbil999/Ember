"""FastAPI app. Run: uvicorn backend.api.main:app --port 8000

Routes kept from the old site (see docs/AUDIT.md §3): health, test records and raw source rows,
document pages and chunks, search, CSV/citation export, admin reload. The SPEC §9 routes are added
in backend/api/routes_*.py.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from contextlib import asynccontextmanager
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import pymupdf as fitz
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from .. import record
from .auth import require_admin
from ..core import config
from ..core.config import ROOT
from ..core.store import get_store
from ..search.index import search

@asynccontextmanager
async def lifespan(_app):
    """Build the catalog read model in the background at startup, so the first request is fast (SPEC §12)."""
    import threading

    def warm():
        try:
            from ..catalog.query import catalog
            catalog()
        except Exception as e:                      # warming is an optimisation, never a reason to fail to start
            print("warm-up skipped:", e)
    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="Freefall Atlas API", version="1.0.0", lifespan=lifespan,
              description="NASA microgravity combustion data (PSI) for spacecraft and habitat fire safety. SPEC §9.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=2000)


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
    return resp

def _clean(o):
    """JSON-safe: NaN → None, numpy → python."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) or np.isinf(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if o is pd.NA:
        return None
    return o


def J(o):
    return JSONResponse(_clean(o))


_json_cache: dict[tuple, bytes] = {}


def cached(key: tuple, fn):
    """Serialize a computed view once and serve the same bytes afterwards (cleared by /api/admin/reload).
    Measured: cleaning + encoding the simulator grid cost 150 ms per request before this."""
    if key not in _json_cache:
        out = fn()
        if out is None:
            raise HTTPException(404)
        _json_cache[key] = json.dumps(_clean(out), ensure_ascii=False).encode("utf-8")
    return Response(_json_cache[key], media_type="application/json")


# ------------------------------------------------------------------ meta
@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/search")
def api_search(q: str, k: int = 20, types: str | None = None, investigation: str | None = None):
    return J(search(q, k=k, types=types.split(",") if types else None, investigation=investigation))


# ------------------------------------------------------------------ data + provenance
@app.get("/api/tests")
def api_tests(dataset: str | None = None, ids: str | None = None, include_excluded: bool = False):
    st = get_store()
    t = st.tests if include_excluded else st.usable_tests()
    if dataset:
        t = t[t.dataset == dataset]
    if ids:
        t = t[t.test_id.isin(ids.split(","))]
    rows = json.loads(t.to_json(orient="records"))
    for r in rows:
        r["outcome"] = record.outcome_label(r.get("burned"))
        r["gravity"] = record.gravity_label(r.get("gravity_g"))
    return J(rows)


@app.get("/api/test/{test_id}")
def api_test(test_id: str):
    """Readable record of one test: each value with status, plain label, source and technical trail."""
    return cached(("test", test_id), lambda: record.test_record(test_id))


@app.get("/api/source/{dataset}/row/{row}")
def api_source_row(dataset: str, row: int):
    if dataset not in config.datasets() or config.datasets()[dataset]["adapter"] == "pdf_reports":
        raise HTTPException(404)
    return J(record.source_rows(dataset, row))


@app.get("/api/chunk/{cid:path}")
def api_chunk(cid: str):
    st = get_store()
    if cid not in st.chunks.index:
        raise HTTPException(404)
    ch = st.chunks.loc[cid]
    doc = st.documents.loc[ch.doc_id]
    return J({"chunk": json.loads(st.chunks.loc[[cid]].to_json(orient="records"))[0],
              "doc": json.loads(st.documents.loc[[ch.doc_id]].to_json(orient="records"))[0],
              "citation": doc.citation})


@lru_cache(maxsize=256)
def _render_page(doc_id: str, page: int, zoom: float) -> bytes:
    st = get_store()
    d = st.documents.loc[doc_id]
    pdf = fitz.open(ROOT / d.file)
    pix = pdf[page - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    return pix.tobytes("png")


@app.get("/api/doc/{doc_id}/page/{page}.png")
def api_page_png(doc_id: str, page: int, zoom: float = 1.6):
    if doc_id not in get_store().documents.index:
        raise HTTPException(404)
    return Response(_render_page(doc_id, page, zoom), media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/doc/{doc_id}/page/{page}/highlights")
def api_page_hl(doc_id: str, page: int, spans: str = Query("", description="||-separated exact spans")):
    st = get_store()
    d = st.documents.loc[doc_id]
    pdf = fitz.open(ROOT / d.file)
    pg = pdf[page - 1]
    W, H = pg.rect.width, pg.rect.height
    rects = []
    for span in [s for s in spans.split("||") if s.strip()]:
        # search phrase by phrase so line breaks don't defeat the match
        words = span.split()
        for i in range(0, len(words), 6):
            frag = " ".join(words[i:i + 6])
            for r in pg.search_for(frag):
                rects.append({"x": r.x0 / W, "y": r.y0 / H, "w": r.width / W, "h": r.height / H})
    return J({"page": page, "pages": pdf.page_count, "rects": rects, "title": d.title, "demo": bool(d.demo)})


@app.get("/api/doc/{doc_id}/file")
def api_doc_file(doc_id: str):
    d = get_store().documents.loc[doc_id]
    return FileResponse(ROOT / d.file, media_type="application/pdf")


# ------------------------------------------------------------------ export
class CsvReq(BaseModel):
    ids: list[str]
    columns: list[str] | None = None
    title: str = "Freefall Atlas export"


@app.post("/api/export/csv")
def api_export_csv(body: CsvReq):
    st = get_store()
    t = st.tests.loc[[i for i in body.ids if i in st.tests.index]]
    cols = body.columns or ["test_id", "dataset", "investigation_id", "campaign", "o2_frac", "pressure_kpa", "o2_pp_kpa",
                            "flow_cm_s", "flow_direction", "d0_mm", "thickness_mm", "diameter_mm", "fuel_flow_mg_s", "gravity_g",
                            "fuel", "material", "sample_shape", "diluent", "burned", "test_end",
                            "burn_rate_k_mm2_s", "extinction_d_mm", "spread_rate_mm_s"]
    cols = [c for c in cols if c in t.columns]
    buf = io.StringIO()
    vm = config.variables()
    buf.write(f"# {body.title}\n# exported {date.today().isoformat()} from Freefall Atlas\n")
    if t["demo"].any():
        buf.write("# WARNING: contains DEMO FIXTURE rows (synthetic) - not NASA results\n")
    buf.write("# units: " + "; ".join(f"{c}={vm.get(c, {}).get('unit', '')}" for c in cols if vm.get(c, {}).get("unit")) + "\n")
    buf.write("# provenance: source_file:row per test; full transformation steps via /api/test/<id>\n")
    srcs = st.provenance[st.provenance.test_id.isin(t.test_id) & (st.provenance.variable == "o2_frac")]
    smap = {r.test_id: f"{r.source_file}:{r.locator}" for _, r in srcs.iterrows()}
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols + ["source"])
    for _, r in t.iterrows():
        w.writerow([("" if pd.isna(r[c]) else r[c]) for c in cols] + [smap.get(r.test_id, "")])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


class CiteReq(BaseModel):
    tests: list[str] = []
    chunks: list[str] = []
    investigations: list[str] = []


@app.post("/api/export/citations")
def api_export_citations(body: CiteReq):
    st = get_store()
    text, bib = [], []
    year = date.today().year
    psi_page = "https://psi.nasa.gov/physci/repo/data/investigations/{}"      # where each verified DOI resolves
    all_dois = {a: d for r in st.investigations.itertuples() for a, d in (json.loads(r.dois) if r.dois else {}).items()}
    for inv_id in body.investigations:
        if inv_id in st.investigations.index:
            inv = st.investigations.loc[inv_id]
            dois = json.loads(inv.dois) if inv.dois else {}
            psi = json.loads(inv.psi_ids) if inv.psi_ids else []
            refs = "; ".join(f"{a}, doi:{dois[a]}" if a in dois else a for a in psi) or "no PSI study recorded"
            links = ", ".join(f"https://doi.org/{dois[a]}" for a in psi if a in dois) or "https://psi.nasa.gov"
            text.append(f"{inv.id}: {inv['name']}. NASA Physical Sciences Informatics (PSI). {refs}. {links}")
            key = inv.id.replace("-", "").replace(" ", "")
            first = next((a for a in psi if a in dois), None)
            where = (f"  doi = {{{dois[first]}}},\n  url = {{{psi_page.format(first)}}},\n" if first
                     else "  url = {https://psi.nasa.gov},\n")
            bib.append(f"@misc{{{key},\n  title = {{{inv['name']} ({inv.id})}},\n  howpublished = {{NASA Physical Sciences "
                       f"Informatics}},\n{where}  note = {{Accessed {date.today().isoformat()}}}\n}}")
    docs_seen = set()
    for cid in body.chunks:
        if cid not in st.chunks.index:
            continue
        ch = st.chunks.loc[cid]
        d = st.documents.loc[ch.doc_id]
        text.append(f"{d.citation} p. {ch.page}, {ch.section}. [anchor {cid}]" + (" (DEMO FIXTURE)" if d.demo else ""))
        if d.id not in docs_seen:
            docs_seen.add(d.id)
            bib.append(f"@misc{{{d.id.replace('-', '_')},\n  title = {{{d.title}}},\n  author = {{{d.authors}}},\n"
                       f"  year = {{{d.year}}},\n  note = {{{'Demo fixture, synthetic - not a NASA report' if d.demo else ''}}}\n}}")
    ds_seen = {}
    for tid in body.tests:
        if tid not in st.tests.index:
            continue
        r = st.tests.loc[tid]
        ds_seen.setdefault(r.dataset, []).append(tid)
    for ds, ids in ds_seen.items():
        cfg = config.datasets()[ds]
        acc = re.search(r"PSI-\d+", cfg.get("license") or "")
        doi = all_dois.get(acc.group(0)) if acc else None
        text.append(f"{cfg['title']}. Rows: {', '.join(ids[:30])}{' …' if len(ids) > 30 else ''}. "
                    f"License: {cfg.get('license')} {'doi:' + doi if doi else ''}".strip())
        bib.append(f"@misc{{{ds},\n  title = {{{cfg['title']}}},\n  year = {{{year}}},\n  note = {{{cfg.get('license')}; "
                   f"rows {', '.join(ids[:30])}}}\n}}")
    return J({"text": "\n".join(text), "bibtex": "\n\n".join(bib)})


@app.post("/api/admin/reload")
def admin_reload(x_admin_token: str | None = Header(default=None)):
    require_admin(x_admin_token)
    get_store().reload()
    _json_cache.clear()
    record._raw_table.cache_clear()
    from ..search.index import reload
    reload()
    return {"ok": True}


# ------------------------------------------------------------------ SPEC §9 routers
from .routes_ai import router as ai_router  # noqa: E402
from .routes_catalog import router as catalog_router  # noqa: E402
from .routes_export import router as export_router  # noqa: E402
from .routes_admin import router as admin_router  # noqa: E402
from .routes_sim import router as sim_router  # noqa: E402

app.include_router(catalog_router)
app.include_router(ai_router)
app.include_router(export_router)
app.include_router(sim_router)
app.include_router(admin_router)


# ------------------------------------------------------------------ the web app (keep this section last)
WEB_DIST = ROOT / "web" / "dist"


@app.get("/{path:path}", include_in_schema=False)
def web_app(path: str):
    """Serve the built React app (web/dist) on the same port as the API. Unknown paths get index.html,
    so client routes such as /admin/verify work; /api/* never reaches here unless it does not exist."""
    if path.startswith("api/"):
        raise HTTPException(404, "No such API route")
    if not (WEB_DIST / "index.html").exists():
        return PlainTextResponse("Freefall Atlas API is running. The web app is not built yet: run `python run.py build`.", status_code=503)
    f = (WEB_DIST / path).resolve()
    if path and f.is_file() and WEB_DIST.resolve() in f.parents:
        cache = "public, max-age=31536000, immutable" if "/assets/" in f.as_posix() else "no-cache"
        return FileResponse(f, headers={"Cache-Control": cache})
    return FileResponse(WEB_DIST / "index.html", headers={"Cache-Control": "no-cache"})
