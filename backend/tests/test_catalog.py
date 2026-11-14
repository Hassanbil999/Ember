"""SPEC §5 adapter layer, seed gap-filling, §7 credibility, §9 catalog routes and export (M1)."""
from __future__ import annotations

import csv
import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.catalog.credibility import score
from backend.catalog.seed import load_seed
from backend.core.config import PROCESSED


@pytest.fixture(scope="module")
def api():
    from backend.api.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def t():
    return {n: pd.read_parquet(PROCESSED / f"atlas_{n}.parquet") for n in ("investigations", "resources", "test_points", "resource_points")}


# ------------------------------------------------------------------ adapter layer: real data first
def test_every_usable_real_test_becomes_a_test_point(t):
    tests = pd.read_parquet(PROCESSED / "tests.parquet")
    usable = set(tests.loc[~tests.excluded.astype(bool), "test_id"])
    real = t["test_points"][t["test_points"].origin == "psi"]
    assert set(real.code) == usable and len(real) == 1848
    assert not set(tests.loc[tests.excluded.astype(bool), "test_id"]) & set(real.code), "excluded rows never reach the UI"


def test_every_psi_table_is_a_data_resource_with_its_download_url(t):
    manifest = json.loads((PROCESSED.parent / "raw" / "psi_manifest.json").read_text(encoding="utf-8"))
    psi = t["resources"][t["resources"].origin == "psi"].set_index("dataset")
    assert set(psi.index) == set(manifest)
    for ds, m in manifest.items():
        assert psi.loc[ds, "url"] == m["url"] and psi.loc[ds, "type"] == "data" and psi.loc[ds, "publisher"] == "NASA PSI"


def test_real_points_trace_to_their_source_row(t):
    real = t["test_points"][t["test_points"].origin == "psi"]
    assert real.source_page.str.match(r"^row \d+$").all() and real.source_file.notna().all()
    assert real.source_resource_id.str.startswith("psi-").all()
    quoted = real.source_quote.dropna()
    assert len(quoted) > 1500 and (quoted.str.split().str.len() <= 31).all(), "quotes stay within 30 words"


def test_verified_only_when_nothing_was_derived_or_flagged(t):
    p = t["test_points"].set_index("code")
    assert not p.loc["SAF2-2-5-UG", "verified"] and "derived" in p.loc["SAF2-2-5-UG", "unverified_reason"]   # "~ 22.1" is approximate
    assert p.loc["FLEX-001", "verified"] and p.loc["FLEX-001", "extraction"] == "manual"
    assert p.loc["FLEX-001", "verified_by"].startswith("PSI table")
    assert not p[p.origin == "seed"].verified.any(), "seed rows stay unverified"


def test_material_is_never_inferred(t):
    p = t["test_points"].set_index("code")
    assert p.loc["BASS2-B3", "material"] == "other"           # the BASS-II row does not name its material
    assert p.loc["BASS2-B1", "material"] == "pmma"
    assert set(p[p.dataset.isin(["flex", "cfi"])].material) == {"droplet"}


# ------------------------------------------------------------------ seed: only where real data has nothing
def test_seed_never_overwrites_a_real_row(t):
    seed = load_seed()
    real_codes = set(t["test_points"].loc[t["test_points"].origin == "psi", "code"])
    assert not {s["code"] for s in seed["test_points"]} & real_codes
    res = t["resources"]
    real_titles = set(res.loc[res.origin != "seed", "title"].str.lower())
    assert not set(res.loc[res.origin == "seed", "title"].str.lower()) & real_titles
    inv = t["investigations"].set_index("slug")
    assert inv.loc["bass", "origin"] == "psi" and inv.loc["sofie", "origin"] == "seed"
    assert inv.loc["bass", "full_name"] == "Burning and Suppression of Solids"      # from the real catalog


def test_seed_placeholders_replaced_by_real_tables_are_skipped(t):
    ids = set(t["resources"].id)
    assert not {"d-bass", "d-saffire", "d-flex", "d-cfig", "d-same"} & ids
    assert {"p-link", "v-saffire", "i-bass"} <= ids


def test_seed_rows_keep_their_labels(t):
    res = t["resources"].set_index("id")
    assert res.loc["v-saffire", "status"] == "placeholder" and pd.isna(res.loc["v-saffire", "url"])
    for s in load_seed()["resources"]:
        if s["key"] in res.index:
            assert res.loc[s["key"], "status"] == s["status"]


def test_seed_step_is_idempotent(t):
    from backend.catalog import seed
    before = {k: len(v) for k, v in t.items()}
    seed.run()
    after = {n: len(pd.read_parquet(PROCESSED / f"atlas_{n}.parquet")) for n in before}
    assert before == after


# ------------------------------------------------------------------ §7 credibility
@pytest.mark.parametrize("p,r,tr,s,label", [(1, 0.8, 1, 94, "High"), (0.85, 0.8, 0.9, 85, "High"), (0.85, 0.6, 0.6, 70, "Medium"),
                                            (0.5, 0.4, 0.4, 44, "Low"), (0.75, 0.7, 0.8, 75, "Medium")])
def test_credibility_formula_and_labels(p, r, tr, s, label):
    out = score("published", "https://x", p, r, tr)
    assert out["score"] == s and out["label"] == label
    assert out["explanation"] == f"Publisher {round(p * 100)} · Review {round(r * 100)} · Traceability {round(tr * 100)}"


def test_placeholder_is_unverified_with_no_score():
    assert score("placeholder", None, 1, 1, 1) == {**score("placeholder", None, 1, 1, 1), "score": None, "label": "Unverified"}
    assert score("published", None, 1, 1, 1)["score"] is None


# ------------------------------------------------------------------ §9 routes, filters and sorts
def test_presets_come_from_the_prototype(api):
    p = {x["key"]: x for x in api.get("/api/presets").json()}
    assert p["moon"]["o2"] == 34 and p["moon"]["psi"] == 8.2 and p["rover"]["u"] == 0


def test_type_filter_and_facets(api, t):
    r = api.get("/api/resources", params={"types": "paper"}).json()
    n_papers = int((t["resources"].type == "paper").sum())
    assert r["total"] == n_papers >= 4 and {i["type"] for i in r["items"]} == {"paper"}
    assert r["facets"]["types"]["data"] == 19, "facets ignore the type filter itself"


def test_cred_min_and_sort_by_credibility(api):
    r = api.get("/api/resources", params={"cred_min": "high", "sort": "cred"}).json()
    scores = [i["credibility"]["score"] for i in r["items"]]
    assert scores and min(scores) >= 85 and scores == sorted(scores, reverse=True)
    v = api.get("/api/resources", params={"cred_min": "verified"}).json()
    assert all(i["credibility"]["score"] is not None for i in v["items"])


def test_investigation_purpose_env_and_search_filters(api):
    r = api.get("/api/resources", params={"inv": "saffire"}).json()
    assert r["total"] and all("saffire" in i["investigations"] for i in r["items"])
    d = api.get("/api/resources", params={"purpose": "detect"}).json()
    assert {"psi-same", "psi-same_r"} <= {i["id"] for i in d["items"]}
    q = api.get("/api/resources", params={"q": "acrylic"}).json()
    assert "p-link" in {i["id"] for i in q["items"]}


def test_near_sort_puts_simulatable_sources_first(api):
    r = api.get("/api/resources", params={"sort": "near", "g": 0, "o2": 17, "psi": 14.7, "u": 5, "material": "pmma"}).json()
    assert r["items"][0]["id"] == "p-link" and r["items"][0]["near"] < 0.01


def test_resource_detail_lists_test_points_simulatable_first(api):
    d = api.get("/api/resources/psi-saffire2").json()
    assert d["points_total"] == 18 and d["test_points"][0]["code"] == "SAF2-2-5-UG"
    assert api.get("/api/resources/nope").status_code == 404


def test_test_points_filters(api):
    sim = api.get("/api/test-points", params={"simulatable": "true"}).json()["items"]
    assert {p["material"] for p in sim} <= {"fabric", "pmma"} and all(p["outcome"] in ("burned", "went_out") for p in sim)
    v = api.get("/api/test-points", params={"investigation": "flex", "verified": "true", "o2_min": 30}).json()
    assert v["total"] > 0 and all(p["o2_pct"] >= 30 and p["verified"] for p in v["items"])


# ------------------------------------------------------------------ export
def test_export_csv_has_a_source_on_every_row(api):
    r = api.post("/api/export", json={"resource_ids": ["psi-saffire2", "p-link"], "format": "csv"})
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 18 + 3 and all(row["source"] for row in rows)
    real = [row for row in rows if row["origin"] == "NASA PSI table"]
    assert all(row["source_url"].startswith("https://psi.nasa.gov") and row["source_location"] for row in real)


def test_export_json_and_bibtex(api):
    j = api.post("/api/export", json={"resource_ids": ["psi-flex"], "format": "json"}).json()
    assert j["resources"][0]["credibility"]["label"] == "High" and len(j["resources"][0]["test_points"]) == 273
    b = api.post("/api/export", json={"resource_ids": ["psi-bass2", "p-link"], "format": "bibtex"}).text
    assert "@misc{psi_bass2" in b and "doi = {10.60555/4qc4-de67}" in b and "@article{p_link" in b
    assert api.post("/api/export", json={"resource_ids": ["nope"], "format": "csv"}).status_code == 404


def test_template_summary_cites_only_listed_resources(api):
    s = api.post("/api/ai/summary", json={"sort": "fit:moon"}).json()
    assert s["source"] == "template" and len(s["citations"]) == 2
    for c in s["citations"]:
        assert f"[{c}]" in s["text"]
    assert "partial gravity" in s["text"]
