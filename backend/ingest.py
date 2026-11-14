"""The team's cleaning pipeline: raw files → canonical tables → validation → chunks → search index.

Run through `python -m backend.ingest canonical` (see backend/ingest_cli.py for every step)."""
from __future__ import annotations

import json
import time

import duckdb
import pandas as pd
import yaml

from .adapters import REGISTRY
from .adapters.pdf_reports import load_pdfs
from .core import config
from .core.config import ARTIFACTS, CONFIG, PROCESSED
from .core.validate import validate

TEST_COLS = ["test_id", "dataset", "investigation_id", "campaign", "fuel", "material", "diluent", "o2_frac",
             "n2_frac", "co2_frac", "he_frac", "burn_time_s", "test_end",
             "pressure_kpa", "o2_pp_kpa", "flow_cm_s", "d0_mm", "thickness_mm", "diameter_mm", "sample_shape", "flow_direction", "gravity_g", "burned",
             "burn_rate_k_mm2_s", "extinction_d_mm", "spread_rate_mm_s", "fuel_flow_mg_s", "heater_ratio", "heat_duration_s", "smoke_aging_s",
             "mass_loss_rate_mg_min", "burner_mm", "oxidizer_o2_frac", "ambient_fuel_frac", "flames_ignited", "notes", "mission_date", "flags", "invalid", "excluded", "demo", "_row"]


def run() -> dict:
    t0 = time.time()
    config.reload()
    inv_cfg = yaml.safe_load((CONFIG / "investigations.yaml").read_text(encoding="utf-8"))["investigations"]
    concepts_cfg = yaml.safe_load((CONFIG / "concepts.yaml").read_text(encoding="utf-8"))
    datasets = config.datasets()
    include_demo = config.load_yaml("profile.yaml").get("include_demo", True)

    all_tests, all_prov, all_log, docs, chunks, published = [], [], [], [], [], {}
    refinery = {"datasets": []}

    for ds_id, cfg in datasets.items():
        if not cfg.get("enabled", True) or (cfg.get("demo") and not include_demo):
            continue
        if cfg["adapter"] == "pdf_reports":
            d, c = load_pdfs(ds_id, cfg)
            docs += d
            chunks += c
            refinery["datasets"].append({"id": ds_id, "title": cfg["title"], "kind": "documents", "demo": cfg.get("demo", False),
                                         "stages": [{"id": "raw", "label": "PDF files", "rows": len(d), "detail": "PyMuPDF text + tables"},
                                                    {"id": "chunks", "label": "Page-anchored chunks", "rows": len(c),
                                                     "detail": "chunked by section, stable anchors"}],
                                         "quality": {"kept": len(c), "flagged": 0, "excluded": 0}, "log": []})
            continue
        adapter = REGISTRY[cfg["adapter"]]
        res = adapter(ds_id, cfg)
        df, log = validate(res.tests, ds_id)
        # make test_id a primary key: excluded duplicate occurrences get a ~dupN suffix
        dup = df.duplicated(subset=["test_id"], keep="first")
        if dup.any():
            n = df[dup].groupby("test_id").cumcount() + 1
            df.loc[dup, "test_id"] = df.loc[dup, "test_id"] + "~dup" + n.astype(str)
            for e in log:
                if e["rule"] == "duplicate":
                    e["test_id"] = df.loc[(df["_row"] == e["source_row"]), "test_id"].iloc[0]
        for c in TEST_COLS:
            if c not in df.columns:
                df[c] = None
        all_tests.append(df[TEST_COLS])
        all_prov += res.provenance
        all_log += log
        published[ds_id] = res.published
        n_ex = int(df["excluded"].sum())
        n_flag = int(((df["flags"].map(len) > 0) & ~df["excluded"]).sum())
        stages = res.stages + [{"id": "validated", "label": "Validated", "rows": len(df) - n_ex,
                                "detail": f"{n_flag} flagged · {n_ex} excluded"}]
        reasons: dict[str, int] = {}
        for e in log:
            reasons[e["rule"]] = reasons.get(e["rule"], 0) + 1
        refinery["datasets"].append({
            "id": ds_id, "title": cfg["title"], "kind": "table", "demo": cfg.get("demo", False),
            "adapter": cfg["adapter"], "license": cfg.get("license"), "stages": stages,
            "quality": {"kept": len(df) - n_ex - n_flag, "flagged": n_flag, "excluded": n_ex, "reasons": reasons},
            "log": log, "columns": cfg["columns"],
            "raw_preview": json.loads(res.raw_preview.astype(str).to_json(orient="records")) if res.raw_preview is not None else [],
        })

    tests = pd.concat(all_tests, ignore_index=True)
    tests["flags"] = tests["flags"].map(json.dumps)
    tests["invalid"] = tests["invalid"].map(lambda d: json.dumps(d if isinstance(d, dict) else {}, ensure_ascii=False))
    tests["image_derived"] = "[]"
    for c in ["n2_frac", "co2_frac", "he_frac", "burn_time_s", "o2_frac", "pressure_kpa", "o2_pp_kpa", "flow_cm_s", "d0_mm", "thickness_mm", "diameter_mm", "gravity_g", "burned",
              "burn_rate_k_mm2_s", "extinction_d_mm", "spread_rate_mm_s", "fuel_flow_mg_s",
              "heater_ratio", "heat_duration_s", "smoke_aging_s", "mass_loss_rate_mg_min",
              "burner_mm", "oxidizer_o2_frac", "ambient_fuel_frac", "flames_ignited"]:
        tests[c] = pd.to_numeric(tests[c], errors="coerce")
    for c in ["campaign", "fuel", "material", "sample_shape", "flow_direction", "notes", "diluent", "mission_date", "investigation_id", "test_end"]:
        tests[c] = tests[c].astype("string")

    invs = []
    for inv in inv_cfg:
        invs.append({**{k: None for k in ["psi_id", "doi", "parent"]}, **inv,
                     "pillars": json.dumps(inv["pillars"]), "years": json.dumps(inv.get("years")),
                     "datasets": json.dumps(inv.get("datasets", [])), "psi_ids": json.dumps(inv.get("psi_ids", [])), "dois": json.dumps(inv.get("dois", {})),
                     "years_source": inv.get("years_source", "approximate"), "test_matrix": inv.get("test_matrix"),
                     "license": "See PSI terms of use", "source_urls": json.dumps(["https://psi.nasa.gov"])})
    inv_df = pd.DataFrame(invs)
    concepts = pd.DataFrame([{**c, "investigations": json.dumps(c["investigations"]), "terms": json.dumps(c["terms"])}
                             for c in concepts_cfg["concepts"]])
    docs_df = pd.DataFrame([{**d, "investigations": json.dumps(d["investigations"])} for d in docs])
    chunks_df = pd.DataFrame(chunks)
    prov_df = pd.DataFrame([{**p, "steps": json.dumps(p["steps"])} for p in all_prov])
    log_df = pd.DataFrame(all_log) if all_log else pd.DataFrame(columns=["dataset", "test_id", "rule", "action", "reason", "detail", "source_row"])
    vars_df = pd.DataFrame([{"name": k, **{kk: (json.dumps(vv) if isinstance(vv, (list, dict)) else vv) for kk, vv in v.items()}}
                            for k, v in config.variables().items()])

    tables = {"investigations": inv_df, "tests": tests, "provenance": prov_df, "validation_log": log_df,
              "documents": docs_df, "chunks": chunks_df, "concepts": concepts, "variables": vars_df}
    db_path = PROCESSED / "atlas.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    for name, df in tables.items():
        df.to_parquet(PROCESSED / f"{name}.parquet", index=False)
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    con.close()

    (ARTIFACTS / "published_values.json").write_text(json.dumps(published), encoding="utf-8")
    (ARTIFACTS / "refinery.json").write_text(json.dumps(refinery, default=str), encoding="utf-8")
    (ARTIFACTS / "glossary.json").write_text(json.dumps(concepts_cfg.get("glossary", {}), ensure_ascii=False), encoding="utf-8")

    from .search.index import build_index
    build_index()
    summary = {"tests": len(tests), "excluded": int(tests["excluded"].sum()), "documents": len(docs_df),
               "chunks": len(chunks_df), "investigations": len(inv_df), "seconds": round(time.time() - t0, 2)}
    print("ingest:", summary)
    return summary


if __name__ == "__main__":
    from .ingest_cli import main
    main()
