"""In-process read model over the canonical tables (loaded once from Parquet)."""
from __future__ import annotations

import json
import threading
from functools import cached_property

import pandas as pd

from .config import ARTIFACTS, PROCESSED


class Store:
    _lock = threading.Lock()

    def __init__(self):
        self.reload()

    def reload(self):
        def rd(name):
            p = PROCESSED / f"{name}.parquet"
            return pd.read_parquet(p) if p.exists() else pd.DataFrame()
        self.investigations = rd("investigations")
        self.tests = rd("tests")
        self.provenance = rd("provenance")
        self.validation_log = rd("validation_log")
        self.documents = rd("documents")
        self.chunks = rd("chunks")
        self.concepts = rd("concepts")
        self.variables = rd("variables")
        self.media = rd("media")
        self.measurements = rd("measurements")
        if not self.tests.empty:
            self.tests["flags"] = self.tests["flags"].map(json.loads)
            self.tests["image_derived"] = self.tests["image_derived"].map(json.loads)
            self.tests["invalid"] = self.tests["invalid"].map(json.loads)
            self.tests = self.tests.set_index("test_id", drop=False)
        if not self.chunks.empty:
            self.chunks = self.chunks.set_index("id", drop=False)
        if not self.investigations.empty:
            self.investigations = self.investigations.set_index("id", drop=False)
        if not self.documents.empty:
            self.documents = self.documents.set_index("id", drop=False)
        self.__dict__.pop("glossary", None)
        self.__dict__.pop("published", None)
        self.__dict__.pop("var_meta", None)

    @cached_property
    def glossary(self) -> dict:
        p = ARTIFACTS / "glossary.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    @cached_property
    def published(self) -> dict:
        p = ARTIFACTS / "published_values.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    @cached_property
    def var_meta(self) -> dict:
        from . import config
        return config.variables()

    def usable_tests(self, dataset: str | None = None) -> pd.DataFrame:
        t = self.tests[~self.tests["excluded"]]
        return t[t["dataset"] == dataset] if dataset else t


_store: Store | None = None


def get_store() -> Store:
    global _store
    with Store._lock:
        if _store is None:
            _store = Store()
    return _store


def reset_store():
    global _store
    _store = None
