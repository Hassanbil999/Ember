"""SPEC §11 / §13: AI cites or refuses. Claude is mocked; no test calls the real API."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.ai import ask as ask_mod, cache, llm
from backend.ai.cite import Source, check


@pytest.fixture()
def api(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "PATH", tmp_path / "ai_cache.sqlite")
    from backend.api.main import app
    return TestClient(app)


def fake_llm(monkeypatch, text: str, refused: bool = False, calls: list | None = None):
    monkeypatch.setattr(llm, "enabled", lambda: True)

    def complete(system, user, max_tokens=2048):
        if calls is not None:
            calls.append({"system": system, "user": user})
        return llm.Completion(text, "claude-sonnet-5-5", refused=refused)
    monkeypatch.setattr(llm, "complete", complete)


# ------------------------------------------------------------------ the citation filter
SRC = [Source("S1", "psi-bass2", None, "BASS-II table", "129 tests at 22.2% oxygen"),
       Source("S2", "doc-guide", 33, "Guide, p. 33", "Cool flames burn at about 600 K.")]


def test_unknown_labels_are_dropped_and_known_ones_mapped():
    c = check("BASS-II has 129 tests [S1, S9]. Cool flames exist [S2].", SRC)
    assert c.text == "BASS-II has 129 tests [psi-bass2]. Cool flames exist [doc-guide p.33]."
    assert [x["resource_id"] for x in c.citations] == ["psi-bass2", "doc-guide"]


def test_sentences_without_a_valid_citation_are_dropped():
    c = check("BASS-II has 129 tests [S1]. Fire is hot. Something else [S7].", SRC)
    assert c.text == "BASS-II has 129 tests [psi-bass2]." and len(c.dropped) == 2


def test_numbers_must_appear_in_the_sources():
    c = check("BASS-II has 129 tests [S1]. They ran at 35% oxygen [S1].", SRC)
    assert c.text == "BASS-II has 129 tests [psi-bass2]." and "35" in c.dropped[0]


def test_an_answer_with_no_citations_is_rejected():
    assert check("Fire is hot. Space is cold.", SRC) is None


# ------------------------------------------------------------------ summary
def test_ai_summary_keeps_only_cited_context_ids(api, monkeypatch):
    fake_llm(monkeypatch, "Start with the BASS-II table [S1] and the Saffire paper [S99]. Trust me on this.")
    s = api.post("/api/ai/summary", json={"sort": "fit:moon"}).json()
    assert s["source"] == "ai" and s["model"] == "claude-sonnet-5-5"
    assert "[S99]" not in s["text"] and "Trust me" not in s["text"]
    assert len(s["citations"]) == 1 and f"[{s['citations'][0]}]" in s["text"]
    assert "partial gravity" in s["text"], "the data-checked gaps are appended"


def test_ai_summary_without_citations_falls_back_to_the_template(api, monkeypatch):
    fake_llm(monkeypatch, "These sources are all great.")
    s = api.post("/api/ai/summary", json={"sort": "fit:moon"}).json()
    assert s["source"] == "template" and "no valid citations" in s["note"]


def test_ai_summary_refusal_and_timeout_fall_back(api, monkeypatch):
    fake_llm(monkeypatch, "", refused=True)
    assert api.post("/api/ai/summary", json={}).json()["source"] == "template"
    monkeypatch.setattr(llm, "complete", lambda *a, **k: (_ for _ in ()).throw(llm.AIUnavailable("The AI took longer than 20 s.")))
    s = api.post("/api/ai/summary", json={}).json()
    assert s["source"] == "template" and "20 s" in s["note"]


def test_ai_summary_is_cached(api, monkeypatch):
    calls: list = []
    fake_llm(monkeypatch, "Start with [S1].", calls=calls)
    a = api.post("/api/ai/summary", json={"types": ["paper"]}).json()
    b = api.post("/api/ai/summary", json={"types": ["paper"]}).json()
    assert len(calls) == 1 and b.get("cached") and a["text"] == b["text"]


def test_summary_prompt_never_shows_placeholders_or_team_notes(api, monkeypatch):
    calls: list = []
    fake_llm(monkeypatch, "Start with [S1].", calls=calls)
    api.post("/api/ai/summary", json={"sort": "cred"})
    assert "PLACEHOLDER" not in calls[0]["user"] and "Context notes" not in calls[0]["user"]


# ------------------------------------------------------------------ ask
def test_ask_without_key_is_503_with_the_relevant_passages(api, monkeypatch):
    monkeypatch.setattr(llm, "enabled", lambda: False)
    r = api.post("/api/ai/ask", json={"question": "Why do flames look different in microgravity?"})
    assert r.status_code == 503 and "API key" in r.json()["detail"]
    assert r.json()["passages"] and all(p["resource_id"].startswith(("doc-", "psi-", "p-", "r-", "s-", "n-", "img-")) for p in r.json()["passages"])


def test_ask_off_topic_is_refused_without_calling_the_ai(api, monkeypatch):
    calls: list = []
    fake_llm(monkeypatch, "Paris [S1].", calls=calls)
    j = api.post("/api/ai/ask", json={"question": "What is the capital of France?"}).json()
    assert j["answer"] == ask_mod.NO_COVER and not j["covered"] and calls == []


def test_ask_answer_cites_resource_and_page(api, monkeypatch):
    fake_llm(monkeypatch, "Without buoyancy the flame becomes nearly spherical [S1]. Made-up source [S40].")
    j = api.post("/api/ai/ask", json={"question": "Why do flames look different in microgravity?"}).json()
    assert j["covered"] and j["citations"]
    c = j["citations"][0]
    assert c["resource_id"] == "doc-researchers-guide-combustion-science" and isinstance(c["page"], int)
    assert f"[{c['resource_id']} p.{c['page']}]" in j["answer"] and "S40" not in j["answer"] and "Made-up" not in j["answer"]


def test_ask_uncited_answer_is_refused(api, monkeypatch):
    fake_llm(monkeypatch, "Flames are round in space because of physics.")
    j = api.post("/api/ai/ask", json={"question": "Why do flames look different in microgravity?"}).json()
    assert j["answer"] == ask_mod.NO_COVER and not j["covered"] and "rejected" in j["note"]


def test_ask_never_uses_the_team_context_notes(api, monkeypatch):
    calls: list = []
    fake_llm(monkeypatch, "Smoke detectors matter [S1].", calls=calls)
    api.post("/api/ai/ask", json={"question": "How does smoke detection work on the ISS?"})
    assert calls and "Context notes" not in calls[0]["user"]


# ------------------------------------------------------------------ the SDK call itself
class FakeMessages:
    def __init__(self, stop="end_turn"):
        self.kwargs = None
        self.stop = stop

    def create(self, **kw):
        self.kwargs = kw
        return SimpleNamespace(stop_reason=self.stop, model=kw["model"], content=[SimpleNamespace(type="text", text="ok [S1].")])


def test_complete_request_shape(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    fm = FakeMessages()
    monkeypatch.setattr(llm, "_client", SimpleNamespace(beta=SimpleNamespace(messages=fm), messages=fm))
    out = llm.complete("sys", "user", max_tokens=100)
    assert out.text == "ok [S1]." and not out.refused
    kw = fm.kwargs
    assert kw["model"] == "claude-sonnet-5-5" and kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert kw["output_config"] == {"effort": "low"} and "temperature" not in kw and "thinking" not in kw


def test_complete_uses_model_from_env_and_reports_refusals(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-haiku-5-5")
    fm = FakeMessages(stop="refusal")
    monkeypatch.setattr(llm, "_client", SimpleNamespace(beta=SimpleNamespace(messages=fm), messages=fm))
    out = llm.complete("sys", "user")
    assert out.refused and fm.kwargs["model"] == "claude-haiku-5-5" and "fallbacks" not in fm.kwargs


def test_complete_without_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm.AIUnavailable):
        llm.complete("s", "u")
