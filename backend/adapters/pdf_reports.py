"""Adapter: PDF reports → Documents + page-anchored Chunks (PyMuPDF).

Chunking: one chunk per (section, page, paragraph group). Section headings are detected by
numbering ("3. Results") or larger font. Anchors are stable: <doc>#p<page>-<section-slug>-<n>.
Tables found by PyMuPDF are stored as extra chunks with section "Table".
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

import pymupdf as fitz  # PyMuPDF
import yaml

from ..core.config import RAW
from .base import slug

HEAD = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+([A-Z][^\n]{2,80})$")
MAX_CHARS = 700


def _doc_id(fname: str) -> str:
    return slug(Path(fname).stem)


def load_pdfs(ds_id: str, cfg: dict) -> tuple[list[dict], list[dict]]:
    folder = RAW / ds_id
    meta = {}
    if (folder / "reports.yaml").exists():
        meta = yaml.safe_load((folder / "reports.yaml").read_text(encoding="utf-8")).get("documents", {})
    docs, chunks = [], []
    for pattern in cfg["files"]:
        for path in sorted(glob.glob(str(folder / pattern))):
            p = Path(path)
            m = meta.get(p.name, {})
            doc_id = _doc_id(p.name)
            pdf = fitz.open(path)
            title = m.get("title") or pdf.metadata.get("title") or p.stem
            authors = m.get("authors", "Unknown")
            year = m.get("year", "n.d.")
            head_size = m.get("heading_min_size")       # documents with unnumbered, larger-font headings
            skip = set(m.get("skip_sections", []))      # e.g. a table of contents: no claims to quote
            want_tables = m.get("tables", True)
            skip_pages = set(m.get("skip_pages", []))
            docs.append({
                "id": doc_id, "title": title, "file": f"data/raw/{ds_id}/{p.name}", "pages": pdf.page_count,
                "investigations": m.get("investigations", []), "demo": bool(m.get("demo", cfg.get("demo", False))),
                "authors": authors, "year": year, "url": m.get("url"),
                "citation": m.get("citation") or f"{authors} ({year}). {title}. Ember corpus file {p.name}.",
            })
            section = "Front matter"
            counter: dict[str, int] = {}
            for pno in range(pdf.page_count):
                page = pdf[pno]
                buf: list[str] = []

                def flush():
                    text = " ".join(buf).strip()
                    buf.clear()
                    if len(text) < 25 or section in skip or pno + 1 in skip_pages:
                        return
                    key = f"{pno + 1}-{slug(section)}"
                    counter[key] = counter.get(key, 0) + 1
                    anchor = f"p{pno + 1}-{slug(section)}-{counter[key]}"
                    chunks.append({"id": f"{doc_id}#{anchor}", "doc_id": doc_id, "page": pno + 1,
                                   "section": section, "anchor": anchor, "text": text, "kind": "text"})

                for block in page.get_text("dict")["blocks"]:
                    if block.get("type") != 0:
                        continue
                    lines = []
                    max_size = 0.0
                    for line in block["lines"]:
                        t = "".join(s["text"] for s in line["spans"]).strip()
                        if t:
                            lines.append(t)
                            max_size = max(max_size, *(s["size"] for s in line["spans"]))
                    text = " ".join(lines).strip()
                    if not text or text.startswith("DEMO FIXTURE") or text.startswith("Compiled context") or re.fullmatch(r"page \d+", text):
                        continue
                    mh = HEAD.match(text)
                    if mh and len(text) < 90 and not head_size:     # numbered lines are list items in such documents
                        flush()
                        section = f"§{mh.group(1)} {mh.group(2).strip()}"
                        continue
                    if head_size and max_size >= head_size and len(text) < 90 and pno > 0:
                        flush()
                        section = text.replace("’", "'").replace("", "'")
                        continue
                    if max_size >= 15 and pno == 0 and section == "Front matter":
                        continue   # title
                    if sum(len(b) for b in buf) + len(text) > MAX_CHARS:
                        flush()
                    buf.append(text)
                flush()
                try:
                    for ti, tab in enumerate(page.find_tables().tables if want_tables else []):
                        rows = tab.extract()
                        if rows and len(rows) > 1:
                            txt = " | ".join(", ".join(str(c) for c in row if c) for row in rows)
                            anchor = f"p{pno + 1}-table-{ti + 1}"
                            chunks.append({"id": f"{doc_id}#{anchor}", "doc_id": doc_id, "page": pno + 1,
                                           "section": "Table", "anchor": anchor, "text": txt, "kind": "table"})
                except Exception:
                    pass
            pdf.close()
    return docs, chunks
