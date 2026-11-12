"""Citation verifier. A sentence survives only if:
  * every quoted span exists verbatim (whitespace-normalized) in the cited chunk, and
  * every number in the sentence is backed by a citation: a span containing it, a cited row
    field equal to it (to display precision), or an aggregate recomputed from cited rows.
"""
from __future__ import annotations

import re

import numpy as np

NUM_RE = re.compile(r"(?<![A-Za-z\d.])[-+]?\d+(?:\.\d+)?(?![\d])")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("­", "")).strip().lower()


def numbers_in(text: str) -> list[str]:
    clean = re.sub(r"\b[A-Za-z]+[-–]?\d+[A-Za-z0-9-]*\b", " ", text)  # skip ids like FX-012, BASS-II, O2, d0
    clean = re.sub(r"[§#]\d+(\.\d+)*", " ", clean)
    return NUM_RE.findall(clean)


def _matches(num: str, value: float) -> bool:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return False
    x = float(num)
    decimals = len(num.split(".")[1]) if "." in num else 0
    tol = 0.5 * 10 ** (-decimals) + 1e-9
    candidates = [value, value * 100]          # fractions shown as percent
    return any(abs(x - c) <= tol or (c != 0 and abs(x - c) / abs(c) < 0.005) for c in candidates)


def aggregate(op: str, values: list[float]) -> float | None:
    v = [x for x in values if x is not None and not (isinstance(x, float) and np.isnan(x))]
    if op == "count":
        return float(len(values))
    if not v:
        return None
    return {"min": min(v), "max": max(v), "median": float(np.median(v)), "mean": float(np.mean(v)),
            "sum": float(sum(v)), "share": float(np.mean(v)), "count_true": float(sum(1 for x in v if x))}.get(op)


def verify_sentence(sentence: dict, chunks, tests) -> tuple[bool, list[str]]:
    problems = []
    backing: list[float] = []
    span_texts: list[str] = []
    for c in sentence.get("citations", []):
        kind = c["kind"]
        if kind == "chunk":
            if c["target"] not in chunks.index:
                problems.append(f"unknown chunk {c['target']}")
                continue
            if _norm(c["span"]) not in _norm(chunks.loc[c["target"], "text"]):
                problems.append(f"span not found in {c['target']}")
                continue
            span_texts.append(c["span"])
        elif kind == "query":
            # restating the user's own (parsed) conditions is not a claim
            span_texts.append(c["text"])
        elif kind == "row":
            if c["target"] not in tests.index:
                problems.append(f"unknown row {c['target']}")
                continue
            for f in c.get("fields", []):
                v = tests.loc[c["target"], f]
                backing.append(None if v is None else float(v) if not isinstance(v, str) else None)
        elif kind == "aggregate":
            rows = [r for r in c["rows"] if r in tests.index]
            if len(rows) != len(c["rows"]):
                problems.append("aggregate cites unknown rows")
                continue
            vals = [tests.loc[r, c["field"]] for r in rows]
            vals = [None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v) for v in vals]
            got = aggregate(c["op"], vals)
            if got is None or not _matches(c["display"], got if c["op"] != "share" else got):
                problems.append(f"aggregate {c['op']}({c['field']}) = {got} does not match {c['display']}")
                continue
            backing.append(got)
            if c["op"] == "count_true":
                backing.append(float(len(rows)))
    for num in numbers_in(sentence["text"]):
        ok = any(num in s for s in span_texts) or any(_matches(num, b) for b in backing if b is not None)
        if not ok:
            problems.append(f"number {num} has no supporting citation")
    if not sentence.get("citations"):
        problems.append("no citation")
    return (len(problems) == 0), problems


def verify_blocks(sentences: list[dict], chunks, tests) -> tuple[list[dict], list[dict]]:
    kept, dropped = [], []
    for s in sentences:
        ok, probs = verify_sentence(s, chunks, tests)
        (kept if ok else dropped).append({**s, "verified": ok, "problems": probs})
    return kept, dropped
