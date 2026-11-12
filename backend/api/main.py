"""FastAPI app. Run: uvicorn backend.api.main:app --port 8000"""
from __future__ import annotations

import csv
import io
import json
import time
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd
import pymupdf as fitz
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel

from .. import atmosphere, explore as explore_mod, insights as insights_mod, labgrid, record, topics
from ..answer.engine import answer
from ..atlas import tests_near
from ..core import config
from ..core.config import ARTIFACTS, ROOT
from ..core.store import get_store
from ..models import surrogate
from ..search.index import search
from ..search.query_parser import parse
from ..vision import pipeline as vision
from ..vision.frames import frame_paths, read_frame
from . import views

app = FastAPI(title="Freefall Atlas API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=2000)


@app.middleware("http")
async def timing(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
    return resp


@app.on_event("startup")
def _warm():
    """Compute the first screens' payloads before anyone asks, so the first click is as fast as the tenth."""
    import threading

    def work():
        try:
            _meta()
            api_explore()
            api_insights()
            for tid in topics.TOPICS:
                api_topic(tid)
                for m in topics.topic(tid)["materials"]:
                    api_topic(tid, m["material"])
            for g in (0.0, 0.165, 0.38, 1.0):
                api_lab_grid("solid", "PMMA", g, "N2")
        except Exception as e:                      # warming is an optimisation, never a reason to fail to start
            print("warm-up skipped:", e)
    threading.Thread(target=work, daemon=True).start()


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


@lru_cache(maxsize=1)
def _meta():
    st = get_store()
    mc = config.models_cfg()
    cards = {}
    for mid in mc["models"]:
        p = surrogate.MODEL_DIR / f"{mid}.card.json"
        if p.exists():
            cards[mid] = json.loads(p.read_text(encoding="utf-8"))
    cats = {c: sorted(st.usable_tests()[c].dropna().unique().tolist()) for c in ["fuel", "material", "diluent"]}
    return {
        "demo": bool(st.tests["demo"].any()),
        # which loaded tables are real and which are the synthetic stand-in, so every screen can say so precisely
        "loaded": {"real": [config.datasets()[d]["title"] for d in sorted(st.tests.loc[~st.tests["demo"], "dataset"].unique())],
                   "demo": [config.datasets()[d]["title"] for d in sorted(st.tests.loc[st.tests["demo"], "dataset"].unique())]},
        "counts": {"investigations": len(st.investigations), "tests": int((~st.tests.excluded).sum()),
                   "documents": len(st.documents), "chunks": len(st.chunks), "media": len(st.media)},
        "variables": config.variables(), "glossary": st.glossary,
        "concepts": json.loads(st.concepts.to_json(orient="records")),
        "presets": config.presets(), "models": cards, "categories": cats,
        "datasets": {k: {"title": v["title"], "demo": v.get("demo", False), "adapter": v["adapter"]}
                     for k, v in config.datasets().items()},
    }


@app.get("/api/meta")
def meta():
    return J(_meta())


# ------------------------------------------------------------------ atlas + search
@app.get("/api/atlas")
def get_atlas():
    return J(views.atlas())


@app.get("/api/navigate")
def navigate(q: str, k: int = 12):
    p = parse(q)
    sr = search(q, k=k)
    res = sr["results"]
    best = None
    if p.investigations:
        best = f"inv:{p.investigations[0]}"
    elif res:
        best = res[0]["node"]
    near = tests_near(get_store().tests, p.conditions, p.categories, k=8) if p.conditions else []
    paths = views.next_paths(best, p.as_dict()) if best else []
    if p.conditions and best and not best.startswith("ds:"):
        paths = [c for c in paths if not c["label"].startswith("tests near")]
        bn = views.node(best) or {}
        ds = (bn.get("datasets") or [None])[0] or             ("bass2_demo" if ("material" in p.categories or "flow_cm_s" in p.conditions) else "flex")
        paths.insert(0, {"label": "tests near " + ", ".join(c["text"] for c in p.chips if c["var"] in p.conditions),
                         "kind": "node", "node": f"ds:{ds}", "conditions": p.conditions})
    if p.question:
        paths.insert(0, {"label": "answer with sources", "kind": "answer", "q": q})
    return J({"query": q, "parsed": p.as_dict(), "best": best, "results": res, "tests_near": near,
              "paths": paths[:7], "ms": sr["ms"]})


@app.get("/api/search")
def api_search(q: str, k: int = 20, types: str | None = None, investigation: str | None = None):
    return J(search(q, k=k, types=types.split(",") if types else None, investigation=investigation))


@app.get("/api/answer")
def api_answer(q: str, role: str = "researcher"):
    return J(answer(q, role))


@app.get("/api/node/{nid:path}")
def api_node(nid: str, role: str = "researcher"):
    def build():
        out = views.focus_view(nid, role)
        return None if "error" in out else out
    return cached(("node", nid, role), build)


# ------------------------------------------------------------------ home topics, explore, insights
@app.get("/api/topic/{tid}")
def api_topic(tid: str, material: str | None = None):
    return cached(("topic", tid, material), lambda: topics.topic(tid, material))


@app.get("/api/atmosphere")
def api_atmosphere():
    return J(atmosphere.payload())


@app.get("/api/explore")
def api_explore():
    return cached(("explore",), explore_mod.explore)


@app.get("/api/insights")
def api_insights():
    return cached(("insights",), insights_mod.insights)


@app.get("/api/lab/items")
def api_lab_items():
    return J(labgrid.items())


@app.get("/api/lab/grid")
def api_lab_grid(mode: str = "solid", item: str = "PMMA", gravity: float = 0.0, diluent: str = "N2"):
    if mode not in labgrid.AXES:
        raise HTTPException(404, "unknown mode")
    return cached(("grid", mode, item, round(gravity, 3), diluent), lambda: labgrid.grid(mode, item, round(gravity, 3), diluent))


@app.get("/api/groups/{dataset}")
def api_groups(dataset: str, mode: str = "regime"):
    from ..atlas import group_tests
    return J(group_tests(get_store().tests.reset_index(drop=True), dataset, mode))


@app.get("/api/relationships/{dataset}")
def api_rel(dataset: str):
    rel = json.loads((ARTIFACTS / "relationships.json").read_text(encoding="utf-8"))
    if dataset not in rel:
        raise HTTPException(404)
    return J(rel[dataset])


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


# ------------------------------------------------------------------ models / scenario lab
class Scenario(BaseModel):
    scenario: dict
    mode: str = "droplet"


@app.get("/api/models")
def api_models():
    return J(_meta()["models"])


@app.post("/api/scenario")
def api_scenario(body: Scenario):
    sc = body.scenario
    st = get_store()
    if body.mode == "droplet":
        burn = surrogate.predict("droplet_burn", sc)
        rate = surrogate.predict("droplet_k", sc)
        rep = surrogate.replay(sc)
    else:
        burn = surrogate.predict("solid_burn", sc)
        rate = surrogate.predict("solid_spread", sc)
        rep = None
    nearest_ids = [n["test_id"] for n in burn["nearest"]]
    rows = json.loads(st.tests.loc[nearest_ids].drop(columns=["flags"]).to_json(orient="records"))
    for r, n in zip(rows, burn["nearest"]):
        r["distance"] = n["distance"]
    # morph: nearest test that has media, within configured distance
    morph = {"mode": "model", "reason": "no real test with footage within range"}
    if body.mode == "droplet":
        b = surrogate.load("droplet_burn")
        x = b["enc"].transform(pd.DataFrame([{f: sc.get(f) for f in b["card"]["features"]}]).fillna(
            {f: b["enc"].mean.get(f, 0) for f in b["enc"].numeric}))[0]
        maxd = config.models_cfg()["applicability"].get("morph_max_distance", 1.5)
        cands = []
        for tid in vision.media_by_test():
            if tid in b["ids"]:
                i = b["ids"].index(tid)
                cands.append((float(np.sqrt(((b["X"][i] - x) ** 2).sum())), tid))
        cands.sort()
        footage = [{"test_id": t, "distance": round(d, 3),
                    "kind": (vision.media_by_test()[t].get("backlit") or {}).get("kind", "footage"),
                    "row": json.loads(st.tests.loc[[t]].drop(columns=["flags"]).to_json(orient="records"))[0]}
                   for d, t in cands[:4]]
        if cands and cands[0][0] <= maxd:
            morph = {"mode": "real", "test_id": cands[0][1], "distance": round(cands[0][0], 3), "max_distance": maxd}
        else:
            morph = {"mode": "model", "nearest_distance": round(cands[0][0], 3) if cands else None, "max_distance": maxd}
    else:
        footage = []
    return J({"burn": burn, "rate": rate, "replay": rep, "nearest_tests": rows, "morph": morph, "footage": footage})


class AdvisorReq(BaseModel):
    model: str
    target: str | None = None
    box: dict | None = None
    base: dict | None = None


@app.post("/api/advisor")
def api_advisor(body: AdvisorReq):
    box = body.box
    if body.target:
        t = next(t for t in config.presets()["targets"] if t["id"] == body.target)
        box = {"o2_frac": t["o2_frac"], "pressure_kpa": t["pressure_kpa"]}
    return J(surrogate.advisor(body.model, box or {}, base=body.base))


@app.get("/api/gapmap")
def api_gap():
    st = get_store()
    t = st.usable_tests()
    pts = t[["test_id", "dataset", "o2_frac", "pressure_kpa", "gravity_g", "burned"]].dropna(subset=["o2_frac", "pressure_kpa"])
    return J({"points": pts.to_dict("records"), "targets": config.presets()["targets"],
              "note": "No partial-gravity tests exist; target environments at 0.165 g / 0.38 g are untested by construction."})


# ------------------------------------------------------------------ refinery
@app.get("/api/refinery")
def api_refinery():
    return J(json.loads((ARTIFACTS / "refinery.json").read_text(encoding="utf-8")))


# ------------------------------------------------------------------ vision
@app.get("/api/vision/tests")
def api_vision_tests():
    out = []
    st = get_store()
    for tid, views_ in vision.media_by_test().items():
        r = vision.load_result(tid)
        row = json.loads(st.tests.loc[[tid]].drop(columns=["flags"]).to_json(orient="records"))[0] if tid in st.tests.index else {}
        out.append({"test_id": tid, "views": list(views_), "kind": next(iter(views_.values())).get("kind", "footage"),
                    "processed": bool(r), "fit": r["derived"]["fit"] if r else None,
                    "validation": r["validation"] if r else None, "row": row})
    summ = ARTIFACTS / "vision" / "validation_summary.json"
    return J({"tests": out, "summary": json.loads(summ.read_text(encoding="utf-8")) if summ.exists() else None})


@app.get("/api/vision/{test_id}")
def api_vision(test_id: str):
    r = vision.load_result(test_id)
    if not r:
        raise HTTPException(404, "not processed")
    return J(r)


@lru_cache(maxsize=2048)
def _frame_png(test_id: str, view: str, i: int) -> bytes:
    import cv2
    m = vision.media_by_test()[test_id][view]
    paths = frame_paths(m)
    img = read_frame(paths[min(i, len(paths) - 1)], color=True)
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes()


@app.get("/api/vision/{test_id}/frame/{i}.png")
def api_frame(test_id: str, i: int, view: str = "backlit"):
    if test_id not in vision.media_by_test() or view not in vision.media_by_test()[test_id]:
        raise HTTPException(404)
    return Response(_frame_png(test_id, view, i), media_type="image/png", headers={"Cache-Control": "max-age=86400"})


class Rerun(BaseModel):
    params: dict


@app.post("/api/vision/{test_id}/rerun")
def api_rerun(test_id: str, body: Rerun):
    return {"job": vision.start_job(test_id, body.params)}


@app.get("/api/vision/job/{jid}")
def api_job(jid: str):
    j = vision.JOBS.get(jid)
    if not j:
        raise HTTPException(404)
    if j["status"] == "done":
        get_store().reload()
    return j


# ------------------------------------------------------------------ exports
class CsvReq(BaseModel):
    ids: list[str]
    columns: list[str] | None = None
    title: str = "Freefall Atlas export"


@app.post("/api/export/csv")
def api_export_csv(body: CsvReq):
    st = get_store()
    t = st.tests.loc[[i for i in body.ids if i in st.tests.index]]
    cols = body.columns or ["test_id", "dataset", "investigation_id", "campaign", "o2_frac", "pressure_kpa", "o2_pp_kpa",
                            "flow_cm_s", "d0_mm", "thickness_mm", "gravity_g", "fuel", "material", "diluent", "burned",
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
    for inv_id in body.investigations:
        if inv_id in st.investigations.index:
            inv = st.investigations.loc[inv_id]
            text.append(f"{inv.id}: {inv['name']}. NASA Physical Sciences Informatics (PSI). "
                        f"{'DOI ' + inv.doi if inv.doi else 'DOI: to be filled from PSI'}. https://psi.nasa.gov")
            key = inv.id.replace("-", "").replace(" ", "")
            bib.append(f"@misc{{{key},\n  title = {{{inv['name']} ({inv.id})}},\n  howpublished = {{NASA Physical Sciences "
                       f"Informatics}},\n  url = {{https://psi.nasa.gov}},\n  note = {{Accessed {date.today().isoformat()}}}\n}}")
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
        text.append(f"{cfg['title']}. Rows: {', '.join(ids[:30])}{' …' if len(ids) > 30 else ''}. "
                    f"License: {cfg.get('license')}. {'DOI ' + cfg['doi'] if cfg.get('doi') else ''}".strip())
        bib.append(f"@misc{{{ds},\n  title = {{{cfg['title']}}},\n  year = {{{year}}},\n  note = {{{cfg.get('license')}; "
                   f"rows {', '.join(ids[:30])}}}\n}}")
    return J({"text": "\n".join(text), "bibtex": "\n\n".join(bib)})


@app.post("/api/admin/reload")
def admin_reload():
    get_store().reload()
    views.atlas.cache_clear()
    _meta.cache_clear()
    surrogate.clear_cache()
    _json_cache.clear()
    for fn in (topics.topic, explore_mod.explore, insights_mod.insights, labgrid.grid, record._raw_table):
        fn.cache_clear()
    from ..search.index import reload
    reload()
    return {"ok": True}


@app.get("/api/envelope")
def api_envelope(model: str, x: str, y: str, fixed: str = "{}", nx: int = 36, ny: int = 28, logx: bool = False):
    """Classifier probability on an x–y grid (other features fixed): burn / extinguish regions
    with the 0.25–0.75 band as uncertainty."""
    b = surrogate.load(model)
    card = b["card"]
    fx = json.loads(fixed)
    xr, yr = card["ranges"][x], card["ranges"][y]
    xs = np.geomspace(max(xr[0], 0.3), xr[1], nx) if logx else np.linspace(xr[0], xr[1], nx)
    ys = np.linspace(yr[0], yr[1], ny)
    base = {f: fx.get(f, b["enc"].mean.get(f) if f in b["enc"].numeric else b["enc"].cats[f][0]) for f in card["features"]}
    rows = [{**base, x: float(a), y: float(c)} for c in ys for a in xs]
    df = pd.DataFrame(rows)[card["features"]]
    p = b["model"].predict_proba(b["enc"].transform(df))[:, 1]
    return J({"x": x, "y": y, "xs": xs.tolist(), "ys": ys.tolist(), "p": p.reshape(ny, nx).round(3).tolist(),
              "fixed": base, "model": model, "label": card["label"]})
