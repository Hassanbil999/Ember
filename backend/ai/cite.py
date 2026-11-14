"""Cite or refuse (SPEC §11). The model sees sources labelled [S1], [S2], …; this module maps those labels back
to resource ids, drops any label that was not in the context, drops sentences whose numbers do not appear in
the context, and drops sentences left without a citation. An answer with no cited sentence is rejected."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..answer.verifier import _matches, numbers_in

LABEL = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z“\"(])")


@dataclass
class Source:
    label: str                  # S1
    resource_id: str
    page: int | None
    title: str
    text: str                   # everything the model was shown for this source


@dataclass
class Checked:
    text: str                   # with [resource_id] or [resource_id p.N] markers
    citations: list[dict] = field(default_factory=list)
    dropped: list[str] = field(default_factory=list)


def marker(s: Source) -> str:
    return f"[{s.resource_id} p.{s.page}]" if s.page else f"[{s.resource_id}]"


def check(answer: str, sources: list[Source], extra_context: str = "") -> Checked | None:
    """Return the cited, number-checked answer, or None when nothing survives (the caller refuses)."""
    by_label = {s.label: s for s in sources}
    context_nums = []
    for s in sources:
        context_nums += [float(n) for n in numbers_in(s.text + " " + s.title)]
    context_nums += [float(n) for n in numbers_in(extra_context)]
    kept, dropped, used = [], [], []
    for sent in SENT.split(answer.strip()):
        sent = sent.strip()
        if not sent:
            continue
        labels = [lab.strip() for m in LABEL.finditer(sent) for lab in m.group(1).split(",")]
        known = [by_label[lab] for lab in labels if lab in by_label]
        body = LABEL.sub("", sent)
        bad = [n for n in numbers_in(body) if not any(_matches(n, v) for v in context_nums)]
        if not known:
            dropped.append(f"no valid citation: {sent}")
            continue
        if bad:
            dropped.append(f"number not in sources ({', '.join(bad)}): {sent}")
            continue
        def repl(m: re.Match) -> str:
            labs = [x.strip() for x in m.group(1).split(",") if x.strip() in by_label]
            return " ".join(marker(by_label[x]) for x in labs)
        out = re.sub(r"\s+([.,;:])", r"\1", LABEL.sub(repl, sent))
        kept.append(re.sub(r"\s{2,}", " ", out).strip())
        for s in known:
            if s not in used:
                used.append(s)
    if not kept:
        return None
    cites = [{"resource_id": s.resource_id, "page": s.page, "title": s.title} for s in used]
    return Checked(" ".join(kept), cites, dropped)
