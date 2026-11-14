"""Adapter layer: the team's canonical tables (data/processed/*.parquet) → the SPEC §5 model.

    build.py        `ingest existing`: investigations, resources, test_points, resource_points from real data
    seed.py         `ingest seed`: data/seed.json rows only where no real row exists
    fit.py          `ingest fit`: model parameters fitted to verified test points (§8.4)
    credibility.py  the §7 score

The §5 tables are written as data/processed/atlas_<table>.parquet and into atlas.duckdb. The UI only
reads them through the §9 API (backend/api/routes_catalog.py).
"""
