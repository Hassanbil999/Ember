"""`ingest existing`: map the team's canonical tables onto the SPEC §5 model. Reads only; never re-cleans.

Inputs (written by the team's pipeline, `ingest canonical`): tests, provenance, investigations, documents,
chunks (data/processed/*.parquet), plus config/datasets.yaml and data/raw/psi_manifest.json.
Outputs: data/processed/atlas_{investigations,resources,test_points,resource_points,chunks}.parquet.
"""
from __future__ import annotations

import json
import math
import re

import duckdb
import pandas as pd

from ..core import config
from ..core.config import PROCESSED, RAW
from . import credibility
from .groups import FUEL_PHASE_TO_FUEL, GROUPS, MEMBER_TO_GROUP, PILLAR_TO_PURPOSE, material_of, outcome_of

# Variables a test point's numbers come from. A point is verified only if none of these was derived or refused
# (Decision B). Dataset settings (e.g. gravity 0 for an ISS run) count as published.
USED_VARS = ["o2_frac", "pressure_kpa", "flow_cm_s", "gravity_g", "burned", "spread_rate_mm_s"]
SUSPECT_FLAGS = {"implausible", "impossible_value", "fractions_do_not_sum", "extinction_larger_than_start", "rate_without_burn"}
EXTRA_VARS = ["fuel", "campaign", "mission_date", "test_end", "thickness_mm", "diameter_mm", "d0_mm", "burn_time_s",
              "burn_rate_k_mm2_s", "extinction_d_mm", "fuel_flow_mg_s", "burner_mm", "oxidizer_o2_frac", "ambient_fuel_frac",
              "heater_ratio", "heat_duration_s", "smoke_aging_s", "mass_loss_rate_mg_min", "n2_frac", "co2_frac", "he_frac",
              "o2_pp_kpa", "flames_ignited"]
QUOTE_MAX_WORDS = 30

TABLES = ["atlas_investigations", "atlas_resources", "atlas_test_points", "atlas_resource_points", "atlas_chunks",
          "atlas_presets", "atlas_model_params"]


# ------------------------------------------------------------------ helpers
def _val(v):
    """pandas/NumPy scalar → plain Python, NaN/NA → None."""
    if v is None or v is pd.NA:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
        if isinstance(v, float) and math.isnan(v):
            return None
    return v


def _words(s: str, n: int = QUOTE_MAX_WORDS) -> str:
    w = s.split()
    return " ".join(w[:n]) + (" …" if len(w) > n else "")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")


def read(name: str) -> pd.DataFrame:
    p = PROCESSED / f"{name}.parquet"
    return pd.read_parquet(p) if p.exists() else pd.DataFrame()


def write(tables: dict[str, pd.DataFrame]) -> None:
    """Parquet for the API's read model, and the same tables in atlas.duckdb for ad-hoc SQL."""
    con = duckdb.connect(str(PROCESSED / "atlas.duckdb"))
    try:
        for name, df in tables.items():
            df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
            con.register("tmp_df", df)
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM tmp_df")
            con.unregister("tmp_df")
    finally:
        con.close()


def _manifest() -> dict:
    p = RAW / "psi_manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


# ------------------------------------------------------------------ investigations
def _investigations(inv: pd.DataFrame, tests: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for slug, member_ids in GROUPS.items():
        members = [inv.loc[m] for m in member_ids if m in inv.index]
        if not members:
            continue
        ids = [m["id"] for m in members]
        name = " & ".join(ids) if len(ids) <= 2 else ", ".join(ids[:-1]) + " & " + ids[-1]
        purposes, fuels = [], []
        for m in members:
            for p in json.loads(m["pillars"]):
                q = PILLAR_TO_PURPOSE.get(p)
                if q and q not in purposes:
                    purposes.append(q)
            f = FUEL_PHASE_TO_FUEL.get(m["fuel_phase"])
            if f and f not in fuels:
                fuels.append(f)
        # environments the real tests were run in: 0 g → space, 1 g ground tests → earth; flight-only, no tables → space
        g = tests.loc[tests.investigation_id.isin(ids), "gravity_g"].dropna()
        envs = (["space"] if (g < 0.02).any() or g.empty else []) + (["earth"] if ((g - 1).abs() < 0.05).any() else [])
        dois = {}
        for m in members:
            dois.update(json.loads(m["dois"]) if m["dois"] else {})
        first_doi = next(iter(dois.values()), None)
        hardware = " · ".join(dict.fromkeys(str(m["hardware"]) for m in members if m["hardware"]))
        rows.append({
            "slug": slug, "name": name, "full_name": members[0]["name"],
            "purposes": json.dumps(purposes), "fuels": json.dumps(fuels), "envs": json.dumps(envs),
            "hardware": hardware, "summary": members[0]["objectives"],
            "psi_url": f"https://doi.org/{first_doi}" if first_doi else "https://psi.nasa.gov",
            "members": json.dumps([{
                "id": m["id"], "name": m["name"], "psi_ids": json.loads(m["psi_ids"]) if m["psi_ids"] else [],
                "dois": json.loads(m["dois"]) if m["dois"] else {}, "years": json.loads(m["years"]) if m["years"] else None,
                "years_source": m["years_source"], "platform": m["platform"], "objectives": m["objectives"],
                "test_matrix": _val(m["test_matrix"])} for m in members], ensure_ascii=False),
            "origin": "psi",
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ test points
def _test_points(tests: pd.DataFrame, prov: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    datasets = config.datasets()
    pv = {(r.test_id, r.variable): r for r in prov.itertuples()}
    rows = []
    for t in tests.rename(columns={"_row": "src_row"}).itertuples(index=False):
        ds = t.dataset
        cfg = datasets.get(ds, {})
        base_id = t.test_id.split("~")[0]
        mat_text = _val(t.material)
        material = material_of(ds, mat_text)
        fuel = _val(t.fuel)
        if material == "droplet":
            d0 = _val(t.d0_mm)
            desc = f"{fuel or 'Fuel'} droplet" + (f", {d0:g} mm" if d0 else "")
        elif material == "gas":
            desc = f"{fuel or 'Gas'} flame"
        else:
            th = _val(t.thickness_mm)
            desc = (mat_text or "Material not named in the table") + (f", {th:g} mm thick" if th else "")
        invalid = json.loads(t.invalid) if isinstance(t.invalid, str) else (t.invalid or {})
        flags = json.loads(t.flags) if isinstance(t.flags, str) else list(t.flags or [])
        derived, quote_parts = [], []
        for var in USED_VARS:
            p = pv.get((base_id, var))
            if p is None:
                continue
            steps = json.loads(p.steps) if isinstance(p.steps, str) else (p.steps or [])
            if any(s.get("op") == "derive" for s in steps) and _val(getattr(t, var)) is not None:
                derived.append(var)
            if isinstance(p.column, str) and p.column and isinstance(p.raw_value, str) and p.raw_value.strip():
                quote_parts.append(f"{p.column.strip()}: {p.raw_value.strip()}")
        refused = [v for v in USED_VARS if v in invalid]
        suspect = sorted(SUSPECT_FLAGS & set(flags))
        verified = not derived and not refused and not suspect
        why = []
        if derived:
            why.append("derived: " + ", ".join(derived))
        if refused:
            why.append("refused source value: " + ", ".join(refused))
        if suspect:
            why.append("flagged: " + ", ".join(suspect))
        o2 = _val(t.o2_frac)
        notes = " ".join(x for x in [_val(t.test_end), _val(t.notes)] if x)
        extra = {v: _val(getattr(t, v)) for v in EXTRA_VARS if _val(getattr(t, v)) is not None}
        inv_detail = _val(t.investigation_id)
        rows.append({
            "code": t.test_id, "investigation": MEMBER_TO_GROUP.get(inv_detail, _slug(inv_detail or "")),
            "investigation_detail": inv_detail, "source_resource_id": f"psi-{ds}",
            "material": material, "sample_desc": desc, "geometry": _val(t.sample_shape),
            "gravity_g": _val(t.gravity_g), "o2_pct": None if o2 is None else round(o2 * 100, 4),
            "pressure_kpa": _val(t.pressure_kpa), "flow_cm_s": _val(t.flow_cm_s),
            "flow_direction": _val(t.flow_direction) or None, "diluent": _val(t.diluent),
            "outcome": outcome_of(_val(t.burned)), "spread_mm_s": _val(t.spread_rate_mm_s), "notes": notes or None,
            "source_file": (cfg.get("files") or [None])[0], "source_page": f"row {int(t.src_row)}",
            "source_quote": _words("; ".join(quote_parts)) if quote_parts else None,
            "extraction": "manual", "verified": verified,
            "verified_by": f"PSI table read by the team's adapter ({cfg.get('adapter')})" if verified else None,
            "verified_at": manifest.get(ds, {}).get("retrieved_utc") if verified else None,
            "unverified_reason": "; ".join(why) or None,
            "origin": "psi", "dataset": ds, "extra": json.dumps(extra, ensure_ascii=False, default=str),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ resources
def _resources(tests: pd.DataFrame, inv: pd.DataFrame, docs: pd.DataFrame, manifest: dict,
               excluded: dict[str, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    datasets = config.datasets()
    all_dois = {a: d for r in inv.itertuples() for a, d in (json.loads(r.dois) if r.dois else {}).items()}
    res, links = [], []
    for ds, cfg in datasets.items():
        if not cfg.get("enabled", True) or cfg.get("demo") or cfg.get("adapter") == "pdf_reports":
            continue
        mine = tests[tests.dataset == ds]
        m = manifest.get(ds, {})
        acc = m.get("psi_accession") or (re.search(r"PSI-\d+", cfg.get("license") or "") or [None])[0]
        inv_ids = list(dict.fromkeys(mine.investigation_id.dropna().tolist())) or list(cfg.get("investigations") or [])
        years = pd.to_datetime(mine.mission_date, errors="coerce").dt.year.dropna()
        if years.empty and inv_ids and inv_ids[0] in inv.index and inv.loc[inv_ids[0], "years"]:
            ys = json.loads(inv.loc[inv_ids[0], "years"]) or []
            years = pd.Series([y for y in ys if y])
        g = mine.gravity_g.dropna()
        envs = (["space"] if (g < 0.02).any() else []) + (["earth"] if ((g - 1).abs() < 0.05).any() else [])
        n_all = int(mine.shape[0])
        ex = int(excluded.get(ds, 0))
        res.append({
            "id": f"psi-{ds}", "investigation": MEMBER_TO_GROUP.get(inv_ids[0]) if inv_ids else None,
            "investigations": json.dumps(list(dict.fromkeys(MEMBER_TO_GROUP.get(i) for i in inv_ids if MEMBER_TO_GROUP.get(i)))),
            "investigation_detail": ", ".join(inv_ids) or None, "type": "data", "title": cfg["title"],
            "publisher": "NASA PSI", "year": int(years.max()) if not years.empty else None, "format": "CSV",
            "url": m.get("url"), "s3_key": None, "doi": all_dois.get(acc) if acc else None, "psi_id": acc,
            "description": (f"{n_all} tests read as published from the NASA PSI table “{(cfg.get('files') or [''])[0]}”"
                            + (f"; {ex} more set aside with logged reasons" if ex else "") + ". " + (cfg.get("license") or "")).strip(),
            "cred_publisher": credibility.PSI_DATA["publisher"], "cred_review": credibility.PSI_DATA["review"],
            "cred_trace": credibility.PSI_DATA["trace"], "status": "published",
            "envs_override": json.dumps(envs) if "earth" in envs else None, "origin": "psi", "dataset": ds,
        })
        links += [{"resource_id": f"psi-{ds}", "code": c} for c in mine.test_id]
    # PSI tables that hold a test plan rather than tests (FLEX-2): a data resource with no test points
    planned = {ds: m for ds, m in manifest.items() if ds not in datasets}
    for ds, m in planned.items():
        member = next((r for r in inv.itertuples() if m.get("psi_accession") in (json.loads(r.psi_ids) if r.psi_ids else [])), None)
        if member is None:
            continue
        res.append({
            "id": f"psi-{ds}", "investigation": MEMBER_TO_GROUP.get(member.id), "investigations": json.dumps([MEMBER_TO_GROUP.get(member.id)]),
            "investigation_detail": member.id, "type": "data",
            "title": f"{member.id} planned test matrix (NASA {m['psi_accession']} experimental table)",
            "publisher": "NASA PSI", "year": (json.loads(member.years) or [None])[-1] if member.years else None, "format": "CSV",
            "url": m.get("url"), "s3_key": None, "doi": all_dois.get(m["psi_accession"]), "psi_id": m["psi_accession"],
            "description": (member.test_matrix or "Planned test matrix.") + " No individual test results in this table.",
            "cred_publisher": credibility.PSI_DATA["publisher"], "cred_review": credibility.PSI_DATA["review"],
            "cred_trace": credibility.PSI_DATA["trace"], "status": "published", "envs_override": None,
            "origin": "psi", "dataset": ds,
        })
    # NASA documents (Decision D: the team's own context notes are not resources)
    for d in docs.itertuples():
        if bool(d.demo):
            continue
        groups = list(dict.fromkeys(MEMBER_TO_GROUP[i] for i in json.loads(d.investigations) if i in MEMBER_TO_GROUP))
        res.append({
            "id": f"doc-{d.id}", "investigation": groups[0] if groups else None, "investigations": json.dumps(groups),
            "investigation_detail": ", ".join(json.loads(d.investigations)), "type": "report", "title": d.title,
            "publisher": "NASA", "year": int(d.year) if _val(d.year) else None, "format": "PDF",
            "url": _val(d.url), "s3_key": None, "doi": None, "psi_id": None,
            "description": f"{d.citation} {d.pages} pages; its text is searchable and can be quoted by Ask with page numbers.",
            "cred_publisher": credibility.NASA_DOCUMENT["publisher"], "cred_review": credibility.NASA_DOCUMENT["review"],
            "cred_trace": credibility.NASA_DOCUMENT["trace"], "status": "published", "envs_override": None,
            "origin": "document", "dataset": None, "doc_id": d.id,
        })
    return pd.DataFrame(res), pd.DataFrame(links, columns=["resource_id", "code"])


def _chunks(chunks: pd.DataFrame, docs: pd.DataFrame) -> pd.DataFrame:
    real = set(docs.loc[~docs.demo.astype(bool), "id"])
    c = chunks[chunks.doc_id.isin(real)]
    return pd.DataFrame({"id": c.id, "resource_id": "doc-" + c.doc_id, "page": c.page, "section": c.section, "text": c.text})


def run() -> dict:
    tests = read("tests")
    if tests.empty:
        raise SystemExit("No canonical tables: run `python -m backend.ingest canonical` first.")
    excluded = {k: int(v) for k, v in tests[tests.excluded.astype(bool)].groupby("dataset").size().items()}
    usable = tests[~tests.excluded.astype(bool)].copy()
    inv = read("investigations").set_index("id", drop=False)
    docs, chunks, prov = read("documents"), read("chunks"), read("provenance")
    manifest = _manifest()

    investigations = _investigations(inv, usable)
    points = _test_points(usable, prov, manifest)
    resources, links = _resources(usable, inv, docs, manifest, excluded)
    tables = {"atlas_investigations": investigations, "atlas_resources": resources, "atlas_test_points": points,
              "atlas_resource_points": links, "atlas_chunks": _chunks(chunks, docs)}
    write(tables)
    summary = {"investigations": len(investigations), "resources": len(resources), "test_points": len(points),
               "verified_points": int(points.verified.sum()), "links": len(links), "chunks": len(tables["atlas_chunks"])}
    print("existing:", summary)
    return summary
