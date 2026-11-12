"""Hybrid retrieval: BM25 (keyword) + dense embeddings, fused with reciprocal-rank fusion.

Dense embeddings default to a local LSA model (TF-IDF → truncated SVD). If the
`sentence-transformers` package is installed and FA_EMBEDDER=st, a MiniLM model is used
instead. Both run fully locally; no paid API. Everything is precomputed at ingest.
"""
from __future__ import annotations

import json
import os
import pickle
import time
from functools import lru_cache

import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from ..core.config import ARTIFACTS, PROCESSED
from .text import tokens

INDEX_PATH = ARTIFACTS / "search_index.pkl"
RRF_K = 60


class Embedder:
    def __init__(self, texts: list[str]):
        self.kind = "lsa"
        self.st = None
        if os.environ.get("FA_EMBEDDER") == "st":
            try:
                from sentence_transformers import SentenceTransformer
                self.st = SentenceTransformer(os.environ.get("FA_ST_MODEL", "all-MiniLM-L6-v2"))
                self.kind = "sentence-transformers"
            except Exception:
                self.st = None
        if self.st is None:
            self.tfidf = TfidfVectorizer(tokenizer=tokens, lowercase=False, ngram_range=(1, 2),
                                         sublinear_tf=True, min_df=1, token_pattern=None)
            X = self.tfidf.fit_transform(texts)
            n = max(2, min(96, X.shape[1] - 1, X.shape[0] - 1))
            self.svd = TruncatedSVD(n_components=n, random_state=0).fit(X)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self.st is not None:
            return np.asarray(self.st.encode(texts, normalize_embeddings=True))
        return normalize(self.svd.transform(self.tfidf.transform(texts)))

    def __getstate__(self):
        d = dict(self.__dict__)
        d["st"] = None
        return d


def _items() -> list[dict]:
    items = []
    inv = pd.read_parquet(PROCESSED / "investigations.parquet")
    for _, r in inv.iterrows():
        pill = " ".join(json.loads(r.pillars))
        items.append({"id": f"inv:{r.id}", "type": "investigation", "title": f"{r.id} — {r['name']}",
                      "text": f"{r.id} {r.id} {r['name']} {r.objectives} {pill} {r.hardware} {r.fuel_phase} {r.platform}",
                      "node": f"inv:{r.id}", "pillars": json.loads(r.pillars), "investigations": [r.id]})
    con = pd.read_parquet(PROCESSED / "concepts.parquet")
    for _, r in con.iterrows():
        items.append({"id": f"concept:{r.id}", "type": "concept", "title": r["name"],
                      "text": f"{r['name']} {r['name']} {r.definition} {r.plain} {' '.join(json.loads(r.terms))}",
                      "node": f"concept:{r.id}", "investigations": json.loads(r.investigations)})
    docs = pd.read_parquet(PROCESSED / "documents.parquet").set_index("id")
    ch = pd.read_parquet(PROCESSED / "chunks.parquet")
    for _, r in ch.iterrows():
        d = docs.loc[r.doc_id]
        items.append({"id": f"chunk:{r.id}", "type": "passage", "title": f"{d.title} · {r.section} · p.{r.page}",
                      "text": f"{r.section} {r.text}", "node": f"doc:{r.doc_id}", "chunk_id": r.id,
                      "investigations": json.loads(d.investigations), "demo": bool(d.demo)})
    for _, d in docs.reset_index().iterrows():
        items.append({"id": f"doc:{d.id}", "type": "document", "title": d.title, "text": f"{d.title} {d.title}",
                      "node": f"doc:{d.id}", "investigations": json.loads(d.investigations), "demo": bool(d.demo)})
    atlas = ARTIFACTS / "atlas.json"
    if atlas.exists():
        for n in json.loads(atlas.read_text(encoding="utf-8"))["nodes"]:
            if n["type"] in ("dataset", "cluster"):
                items.append({"id": n["id"], "type": n["type"], "title": n["label"],
                              "text": f"{n['label']} {n.get('search_text', '')}", "node": n["id"],
                              "investigations": n.get("investigations", []), "demo": n.get("demo", False)})
    return items


def build_index():
    items = _items()
    texts = [it["text"] for it in items]
    bm25 = BM25Okapi([tokens(t) for t in texts])
    emb = Embedder(texts)
    vecs = emb.encode(texts).astype(np.float32)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump({"items": items, "bm25": bm25, "embedder": emb, "vecs": vecs}, f)
    _load.cache_clear()
    print(f"search index: {len(items)} items, dense={emb.kind} dim={vecs.shape[1]}")


@lru_cache(maxsize=1)
def _load():
    with open(INDEX_PATH, "rb") as f:
        return pickle.load(f)


def reload():
    _load.cache_clear()


def search(q: str, k: int = 20, types: list[str] | None = None, investigation: str | None = None,
           pillar: str | None = None, min_dense: float = 0.05) -> dict:
    t0 = time.perf_counter()
    idx = _load()
    items = idx["items"]
    qt = tokens(q, expand=True)
    bm = idx["bm25"].get_scores(qt) if qt else np.zeros(len(items))
    qv = idx["embedder"].encode([q])[0] if q.strip() else None
    dense = idx["vecs"] @ qv if qv is not None else np.zeros(len(items))

    mask = np.ones(len(items), dtype=bool)
    for i, it in enumerate(items):
        if types and it["type"] not in types:
            mask[i] = False
        if investigation and investigation not in it.get("investigations", []):
            mask[i] = False
        if pillar and it["type"] == "investigation" and pillar not in it.get("pillars", []):
            mask[i] = False

    fused = np.zeros(len(items))
    bm_order = [i for i in np.argsort(-bm) if bm[i] > 0 and mask[i]][:60]
    de_order = [i for i in np.argsort(-dense) if mask[i] and dense[i] > min_dense][:60]
    for r, i in enumerate(bm_order):
        fused[i] += 1 / (RRF_K + r + 1)
    for r, i in enumerate(de_order):
        fused[i] += 1 / (RRF_K + r + 1)
    order = [i for i in np.argsort(-fused) if fused[i] > 0][:k]
    results = [{**{kk: v for kk, v in items[i].items() if kk != "text"}, "score": float(fused[i]),
                "bm25": float(bm[i]), "dense": float(dense[i]),
                "snippet": items[i]["text"][:240]} for i in order]
    return {"results": results, "ms": round((time.perf_counter() - t0) * 1000, 2), "tokens": qt}


def item_text(item_id: str) -> str:
    for it in _load()["items"]:
        if it["id"] == item_id:
            return it["text"]
    return ""
