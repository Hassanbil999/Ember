"""M5: filling data gaps — curation and /admin/verify, NTRS, the PSI bucket, PDF text, AI extraction.
No test touches the network or the real API; tests that change the review files restore the tables after."""
from __future__ import annotations

import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.ai import extract, llm
from backend.catalog import curate, ntrs, psi_bucket, text
from backend.catalog.build import read
from backend.core.config import PROCESSED
from backend.core.store import get_store


@pytest.fixture()
def review(monkeypatch, tmp_path):
    """Point the review files at a temp dir; rebuild the tables from the real (tracked) files afterwards."""
    real_dec, real_ai = curate.DECISIONS, curate.AI_FILE
    monkeypatch.setattr(curate, "DECISIONS", tmp_path / "verifications.json")
    monkeypatch.setattr(curate, "AI_FILE", tmp_path / "ai_extracted.json")
    monkeypatch.setattr(extract, "AI_FILE", tmp_path / "ai_extracted.json")
    monkeypatch.setenv("ADMIN_TOKEN", "test-token")
    from backend.api.main import app
    yield TestClient(app)
    monkeypatch.setattr(curate, "DECISIONS", real_dec)
    monkeypatch.setattr(curate, "AI_FILE", real_ai)
    from backend.ingest_cli import run_step
    for step in ("existing", "psi", "ntrs", "text", "seed", "curate", "fit"):     # rebuild the §5 tables from scratch
        run_step(step)
    get_store().reload()


H = {"X-Admin-Token": "test-token"}


# ------------------------------------------------------------------ admin auth
def test_admin_is_off_without_a_token_and_needs_the_right_one(monkeypatch):
    from backend.api.main import app
    c = TestClient(app)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert c.get("/api/admin/queue").status_code == 403
    monkeypatch.setenv("ADMIN_TOKEN", "change-me")
    assert c.get("/api/admin/queue", headers={"X-Admin-Token": "change-me"}).status_code == 403
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert c.get("/api/admin/queue", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert c.post("/api/admin/reload").status_code == 401


def test_queue_lists_unverified_points_with_their_sources(review):
    q = review.get("/api/admin/queue", headers=H).json()
    assert q["counts"]["seed"] == 12 and q["counts"]["psi"] == 110
    first = q["items"][0]
    assert first["origin"] == "seed" and not first["verified"]
    assert any(i["source_quote"] for i in q["items"] if i["origin"] == "psi")


# ------------------------------------------------------------------ decisions
def test_verifying_four_points_fits_the_model(review):
    for code in ("BASS2-01", "BASS2-02", "BASS2-G1", "BASS2-G2"):
        r = review.post(f"/api/admin/test-points/{code}/verify", headers=H, json={"by": "tester"})
        assert r.status_code == 200 and r.json()["point"]["verified"] and r.json()["point"]["verified_by"] == "tester"
    meta = review.get("/api/model-params").json()["meta"]["pmma"]
    assert meta["n_points"] == 4 and meta["source"].startswith("fitted")
    assert json.loads(curate.DECISIONS.read_text())[0]["action"] == "verify"


def test_nasa_rows_cannot_be_edited_or_rejected(review):
    r = review.post("/api/admin/test-points/SAF2-2-5-UG/edit", headers=H, json={"fields": {"o2_pct": 21}})
    assert r.status_code == 422 and "published" in r.json()["detail"]
    assert review.post("/api/admin/test-points/SAF2-2-5-UG/reject", headers=H, json={}).status_code == 422
    assert review.post("/api/admin/test-points/SAF2-2-5-UG/verify", headers=H, json={"by": "x"}).json()["point"]["verified"]


def test_edit_clears_verification_and_reject_removes(review):
    review.post("/api/admin/test-points/SAF1-C/verify", headers=H, json={"by": "a"})
    e = review.post("/api/admin/test-points/SAF1-C/edit", headers=H, json={"by": "b", "fields": {"spread_mm_s": 1.7}}).json()
    assert e["point"]["spread_mm_s"] == 1.7 and not e["point"]["verified"] and "Edited by b" in e["point"]["unverified_reason"]
    assert review.post("/api/admin/test-points/SAF3-C/edit", headers=H, json={"fields": {"o2_pct": 400}}).status_code == 422
    review.post("/api/admin/test-points/FLEX-01/reject", headers=H, json={"by": "c"})
    assert "FLEX-01" not in set(read("atlas_test_points").code)


def test_ai_points_load_unverified_and_never_overwrite(review):
    curate.AI_FILE.write_text(json.dumps([
        {"code": "AI-TEST-P2-1", "source_resource_id": "ntrs-20150008961", "investigation": "bass", "material": "pmma",
         "o2_pct": 21.0, "outcome": "burned", "source_page": "p. 2", "source_quote": "21% oxygen", "extraction": "ai"},
        {"code": "BASS2-01", "source_resource_id": "p-link", "material": "pmma", "o2_pct": 99, "outcome": "burned"},
    ]))
    curate.run()
    pts = read("atlas_test_points").set_index("code")
    assert pts.loc["AI-TEST-P2-1", "extraction"] == "ai" and not pts.loc["AI-TEST-P2-1", "verified"]
    assert pts.loc["BASS2-01", "o2_pct"] == 17.0, "an AI row never overwrites an existing code"


# ------------------------------------------------------------------ NTRS
def test_ntrs_records_are_real_resources_that_replace_seed_copies():
    res = read("atlas_resources").set_index("id")
    n = res[res.origin == "ntrs"]
    assert len(n) >= 30 and n.url.str.startswith("https://ntrs.nasa.gov/citations/").all()
    assert "ntrs-20210011385" in res.index and "r-bass2" not in res.index        # BASS-II summary report: real wins
    tm = res.loc["ntrs-20210011385"]
    assert tm["type"] == "report" and tm["cred_publisher"] == 0.85


def test_ntrs_mapping_rules():
    snap = {"records": [
        {"id": "1", "title": "A", "stiType": "JOURNAL_ARTICLE", "investigations": ["FLEX"], "date": "2015-01-01",
         "downloadsAvailable": True, "onlyAbstract": False, "authors": ["X", "Y"], "publications": ["Combust. Flame"], "abstract": "a"},
        {"id": "2", "title": "B", "stiType": "PRESENTATION", "investigations": ["BASS-II"], "date": None,
         "downloadsAvailable": False, "onlyAbstract": True, "authors": [], "abstract": ""}]}
    df = ntrs.resources_from(snap).set_index("id")
    assert df.loc["ntrs-1", "type"] == "paper" and df.loc["ntrs-1", "cred_review"] == 1.0 and df.loc["ntrs-1", "investigation"] == "flex"
    assert df.loc["ntrs-2", "type"] == "slides" and df.loc["ntrs-2", "cred_trace"] == 0.6 and df.loc["ntrs-2", "format"] == "Abstract"


def test_ntrs_relevance_needs_the_investigation_named():
    inv = {"id": "FLEX", "name": "Flame Extinguishment Experiment"}
    assert ntrs._mentions({"title": "FLEX droplet results", "abstract": ""}, inv)
    assert not ntrs._mentions({"title": "A flexible sensor", "abstract": "FLEXIBLE"}, inv)


# ------------------------------------------------------------------ PSI bucket
def test_discover_writes_a_map_for_a_person_to_confirm(monkeypatch, tmp_path):
    pages = {
        "": '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><CommonPrefixes><Prefix>BASS-II/</Prefix></CommonPrefixes>'
            '<CommonPrefixes><Prefix>pk4/</Prefix></CommonPrefixes></ListBucketResult>',
        "BASS-II/": '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Contents><Key>BASS-II/run1.csv</Key><Size>10</Size></Contents></ListBucketResult>',
        "pk4/": '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"></ListBucketResult>',
    }
    monkeypatch.setattr(psi_bucket, "MAP", tmp_path / "psi_map.csv")
    psi_bucket.discover(get=lambda params: pages[params["prefix"]])
    rows = pd.read_csv(tmp_path / "psi_map.csv", dtype=str).fillna("").set_index("prefix")
    assert rows.loc["BASS-II/", "candidate_slug"] == "bass" and rows.loc["BASS-II/", "confirmed"] == ""
    assert rows.loc["pk4/", "candidate_investigation"] == ""
    assert psi_bucket.confirmed() == [], "nothing is registered until a person confirms"


def test_bucket_files_map_to_resource_types():
    snap = {"prefixes": [{"prefix": "BASS-II/", "slug": "bass", "investigation": "BASS-II", "files": [
        {"key": "BASS-II/a.csv", "size": 1}, {"key": "BASS-II/b.mp4", "size": 1}, {"key": "BASS-II/c.pdf", "size": 1},
        {"key": "BASS-II/d.pptx", "size": 1}, {"key": "BASS-II/e.tif", "size": 1}, {"key": "BASS-II/f.zip", "size": 1}]}]}
    df = psi_bucket.resources_from(snap)
    assert list(df.type) == ["data", "video", "report", "slides", "image"] and (df.publisher == "NASA PSI").all()
    assert df.loc[df.type == "data", "cred_trace"].iloc[0] == 1.0 and df.s3_key.notna().all()


def test_the_real_bucket_has_no_combustion_prefix_confirmed():
    assert psi_bucket.MAP.exists() and psi_bucket.confirmed() == []


# ------------------------------------------------------------------ text
def test_chunks_stay_on_one_page_and_are_sized():
    page = ("Intro paragraph. " * 30 + "\n\n") * 12
    ch = text.chunk_page(page)
    assert len(ch) >= 2 and all(len(c) <= text.CHUNK_CHARS + 600 for c in ch)


def test_ntrs_passages_are_loaded_and_retrievable():
    ch = read("atlas_chunks")
    assert (ch.resource_id.str.startswith("ntrs-")).sum() > 300
    from backend.ai.ask import retrieve
    got = retrieve("How fast did flames spread over PMMA rods in concurrent flow?")
    assert any(p["resource_id"].startswith("ntrs-") and p["page"] for p in got)


# ------------------------------------------------------------------ AI extraction
PAGE = "Tests were run at 21% oxygen with a 10 cm/s concurrent flow; the PMMA rod burned and the flame spread at 1.2 mm/s."


def test_validate_keeps_only_quoted_in_range_rows():
    ok = {"o2_pct": 21, "flow_cm_s": 10, "spread_mm_s": 1.2, "pressure_kpa": None, "gravity_g": 0,
          "source_quote": "21% oxygen with a 10 cm/s concurrent flow; the PMMA rod burned and the flame spread at 1.2 mm/s"}
    assert extract.validate(ok, PAGE) is None
    assert "not found" in extract.validate({**ok, "source_quote": "25% oxygen"}, PAGE)
    assert "not in the quote" in extract.validate({**ok, "o2_pct": 25}, PAGE)
    assert "outside" in extract.validate({**ok, "flow_cm_s": 500}, PAGE)


def test_extract_writes_unverified_ai_rows(review, monkeypatch):
    monkeypatch.setattr(extract, "candidate_passages", lambda chunks, limit=40: [
        {"id": "ntrs-20150008961#p2-0", "resource_id": "ntrs-20150008961", "page": 2, "text": PAGE}])
    good = {"material": "pmma", "sample_desc": "PMMA rod", "gravity_g": 0, "o2_pct": 21, "pressure_kpa": None, "flow_cm_s": 10,
            "spread_mm_s": 1.2, "flow_direction": "concurrent", "outcome": "burned",
            "source_quote": "21% oxygen with a 10 cm/s concurrent flow; the PMMA rod burned and the flame spread at 1.2 mm/s"}
    bad = {**good, "o2_pct": 35, "source_quote": "35% oxygen"}
    calls = []

    def fake(system, user, max_tokens, schema):
        calls.append(schema)
        return llm.Completion(json.dumps({"points": [good, bad]}), "claude-sonnet-5-5")
    out = extract.run(complete=fake)
    assert out["kept"] == 1 and len(out["dropped"]) == 1 and calls[0]["required"] == ["points"]
    rows = json.loads(extract.AI_FILE.read_text())
    assert rows[0]["extraction"] == "ai" and rows[0]["verified"] is False and rows[0]["source_page"] == "p. 2"
    curate.run()
    p = read("atlas_test_points").set_index("code").loc[rows[0]["code"]]
    assert p["origin"] == "ai" and not p["verified"]


def test_extract_skips_without_a_key(monkeypatch):
    monkeypatch.setattr(llm, "enabled", lambda: False)
    assert extract.run() == {"skipped": True}


def test_structured_output_request_shape(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    seen = {}

    class M:
        def create(self, **kw):
            seen.update(kw)
            return SimpleNamespace(stop_reason="end_turn", model=kw["model"], content=[SimpleNamespace(type="text", text='{"points": []}')])
    monkeypatch.setattr(llm, "_client", SimpleNamespace(beta=SimpleNamespace(messages=M()), messages=M()))
    llm.complete("s", "u", 100, schema=extract.SCHEMA)
    assert seen["output_config"]["format"] == {"type": "json_schema", "schema": extract.SCHEMA} and seen["output_config"]["effort"] == "low"


def test_processed_tables_exist():
    assert (PROCESSED / "atlas_chunks.parquet").exists()
