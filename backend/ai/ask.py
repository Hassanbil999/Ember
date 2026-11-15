"""POST /api/ai/ask: an answer grounded in retrieved passages and resources, with citations (resource id + page).

Retrieval: the hybrid search index (BM25 + local LSA). Only NASA passages are used (the team's own context notes
are excluded, Decision D). A passage counts as relevant only if it shares at least two of the question's
content words (one, for one-word questions); with nothing relevant the answer is "The data here doesn't cover that."
Without an API key, the route returns 503 with the relevant passages so the user still sees the evidence.
"""
from __future__ import annotations

from ..catalog.query import catalog
from ..search.index import search
from ..search.text import tokens
from . import cache, llm
from .cite import Source, check

NO_COVER = "The data here doesn't cover that."
PROMPT_VERSION = "ask-v1"
SYSTEM = f"""You answer questions about NASA microgravity combustion research for spacecraft and habitat fire safety.
Use only the numbered sources given; each has a label like [S2]. Answer in two to four plain sentences (no markdown).
End every sentence with the label(s) of the source(s) that support it, e.g. [S2] or [S1, S3].
Use only numbers that appear in the sources, with their units. Do not add facts from memory.
If the sources do not answer the question, reply exactly: {NO_COVER}"""
MAX_PASSAGES = 6


def _content_tokens(text: str) -> set[str]:
    return {t for t in tokens(text) if len(t) > 2 and not t.isdigit()}


def retrieve(question: str) -> list[dict]:
    c = catalog()
    chunks = c.chunks
    q = _content_tokens(question)
    need = 1 if len(q) <= 1 else 2
    out = []
    for r in search(question, k=40, types=["passage", "resource"])["results"]:
        if r["type"] == "passage":
            ch = chunks.get(r.get("chunk_id"))
            if ch is None:                      # not a NASA passage (e.g. the team's context notes)
                continue
            text, rid, page, title = ch["text"], ch["resource_id"], int(ch["page"]), f"{c.res[ch['resource_id']]['title']}, p. {ch['page']}"
            label = ch.get("section")
        else:
            res = c.res.get(r.get("resource_id"))
            if res is None or res["placeholder"]:
                continue
            text, rid, page, title, label = res["description"] or "", res["id"], None, res["title"], res["type"]
        shared = q & _content_tokens(title + " " + text)
        if len(shared) < need:
            continue
        out.append({"resource_id": rid, "page": page, "title": title, "section": label, "text": text,
                    "score": r["score"], "matched": sorted(shared)})
        if len(out) >= MAX_PASSAGES:
            break
    return out


def ask(question: str) -> dict:
    question = question.strip()
    passages = retrieve(question)
    base = {"question": question, "passages": [{k: p[k] for k in ("resource_id", "page", "title", "section")} | {"excerpt": p["text"][:400]}
                                               for p in passages]}
    if not passages:
        return {**base, "answer": NO_COVER, "citations": [], "covered": False, "source": "retrieval", "model": None}
    if not llm.enabled():
        raise llm.AIUnavailable("Ask needs an AI API key on the server (ANTHROPIC_API_KEY, or a free OpenAI-compatible key: LLM_API_KEY, LLM_BASE_URL, LLM_MODEL).")
    sources = [Source(f"S{i + 1}", p["resource_id"], p["page"], p["title"], p["text"]) for i, p in enumerate(passages)]
    user = f"Question: {question}\n\n" + "\n\n".join(f"[{s.label}] {s.title}\n{s.text}" for s in sources)
    k = cache.key(PROMPT_VERSION, llm.model_name(), SYSTEM, user)
    hit = cache.get(k)
    if hit:
        return {**hit, "cached": True}
    out = llm.complete(SYSTEM, user, max_tokens=4096)
    if out.refused:
        res = {**base, "answer": "The AI declined to answer this question.", "citations": [], "covered": False, "source": "ai", "model": out.model}
    elif out.text.strip().rstrip(".") == NO_COVER.rstrip("."):
        res = {**base, "answer": NO_COVER, "citations": [], "covered": False, "source": "ai", "model": out.model}
    else:
        checked = check(out.text, sources, extra_context=question)
        if checked is None:                     # nothing cited, or every sentence had an unsupported number: refuse
            res = {**base, "answer": NO_COVER, "citations": [], "covered": False, "source": "ai", "model": out.model,
                   "note": "The AI answer was rejected: it did not cite the passages it was given."}
        else:
            res = {**base, "answer": checked.text, "citations": checked.citations, "covered": True, "source": "ai",
                   "model": out.model, "dropped": len(checked.dropped)}
    cache.put(k, res)
    return res
