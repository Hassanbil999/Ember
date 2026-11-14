"""`ingest text` (SPEC §6.4): page-anchored text chunks from the NTRS PDFs, for Ask and for search.

    python -m backend.ingest text --fetch   network: download each NTRS PDF of a registered record (cached in
                                            data/cache/, not committed), extract text per page with PyMuPDF and
                                            write data/raw/ntrs/text/<ntrs id>.jsonl (commit these)
    python -m backend.ingest text           offline: load the committed chunks into atlas_chunks

Chunks stay inside one page (so every citation has an exact page) and hold about 800 tokens (~3,200 chars).
"""
from __future__ import annotations

import json
import re

import pandas as pd

from ..core.config import DATA, RAW
from .build import read, write

TEXT_DIR = RAW / "ntrs" / "text"
CACHE = DATA / "cache" / "ntrs_pdf"
CHUNK_CHARS = 3200
MAX_PAGES, MAX_MB = 120, 40


def chunk_page(text: str, size: int = CHUNK_CHARS) -> list[str]:
    text = re.sub("[  \x0b\x0c\x85]", "\n", text)       # unusual line breaks PDFs carry
    text = re.sub(r"[ \t]+", " ", re.sub(r"-\n(?=[a-z])", "", text)).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    out, cur = [], ""
    for p in paras:
        p = re.sub(r"\s*\n\s*", " ", p)
        if cur and len(cur) + len(p) + 1 > size:
            out.append(cur)
            cur = ""
        while len(p) > size:                       # a single very long paragraph: cut at a sentence end
            cut = p.rfind(". ", 0, size)
            cut = cut + 1 if cut > size // 2 else size
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        cur = (cur + " " + p).strip()
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 80]


def pdf_chunks(pdf_bytes: bytes, rid: str) -> list[dict]:
    import pymupdf as fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    rows = []
    for i, page in enumerate(doc):
        if i >= MAX_PAGES:
            break
        for n, c in enumerate(chunk_page(page.get_text("text"))):
            rows.append({"id": f"{rid}#p{i + 1}-{n}", "resource_id": rid, "page": i + 1, "section": None, "text": c})
    return rows


def fetch(get=None) -> dict:
    if get is None:
        import httpx

        def get(url: str) -> bytes:
            r = httpx.get(url, timeout=120, follow_redirects=True, headers={"User-Agent": "freefall-atlas-ingest/1.0"})
            r.raise_for_status()
            return r.content
    res = read("atlas_resources")
    todo = res[(res.origin == "ntrs") & res.get("pdf_url", pd.Series(dtype=object)).notna()] if "pdf_url" in res else res.iloc[0:0]
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    done, skipped = 0, []
    for r in todo.itertuples():
        out = TEXT_DIR / f"{r.id}.jsonl"
        if out.exists():
            done += 1
            continue
        cached = CACHE / f"{r.id}.pdf"
        try:
            data = cached.read_bytes() if cached.exists() else get(r.pdf_url)
        except Exception as e:                      # one failed download never stops the rest
            skipped.append(f"{r.id}: {type(e).__name__}")
            continue
        if len(data) > MAX_MB * 1e6 or not data.startswith(b"%PDF"):
            skipped.append(f"{r.id}: not a PDF or larger than {MAX_MB} MB")
            continue
        cached.write_bytes(data)
        rows = pdf_chunks(data, r.id)
        if not rows:
            skipped.append(f"{r.id}: no extractable text (scanned?)")
            continue
        out.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
        done += 1
    print(f"text --fetch: {done} documents with text, {len(skipped)} skipped" + (f": {'; '.join(skipped)}" if skipped else ""))
    return {"documents": done, "skipped": skipped}


def run() -> dict:
    chunks = read("atlas_chunks")
    res = read("atlas_resources")
    chunks = chunks[~chunks.resource_id.str.startswith("ntrs-")] if not chunks.empty else chunks
    rows = []
    for f in sorted(TEXT_DIR.glob("*.jsonl")) if TEXT_DIR.exists() else []:
        # split on "\n" only: splitlines() would also break on U+2028 / form feeds inside the PDF text
        rows += [json.loads(line) for line in f.read_text(encoding="utf-8").split("\n") if line.strip()]
    new = pd.DataFrame(rows, columns=["id", "resource_id", "page", "section", "text"])
    new = new[new.resource_id.isin(set(res.id))]
    write({"atlas_chunks": pd.concat([chunks, new], ignore_index=True)})
    print(f"text: {len(new)} chunks from {new.resource_id.nunique()} NTRS documents")
    return {"chunks": len(new), "documents": int(new.resource_id.nunique())}
