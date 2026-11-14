"""The free (OpenAI-compatible) AI provider: picked only when Anthropic is not set, request shape, errors."""
from __future__ import annotations

import io
import json
import urllib.error

import pytest

from backend.ai import llm


@pytest.fixture
def free(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("LLM_MODEL", "free-model")


def test_provider_choice(monkeypatch, free):
    assert llm.provider() == "openai_compatible" and llm.enabled() and llm.model_name() == "free-model"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    assert llm.provider() == "anthropic"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.delenv("LLM_MODEL")
    assert not llm.enabled()


def test_request_and_reply(monkeypatch, free):
    seen = {}

    class R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake(req, timeout):
        seen["url"], seen["auth"], seen["body"], seen["timeout"] = req.full_url, req.headers["Authorization"], json.loads(req.data), timeout
        return R(json.dumps({"model": "free-model", "choices": [{"message": {"content": " Answer [S1]. "}, "finish_reason": "stop"}]}).encode())

    monkeypatch.setattr("urllib.request.urlopen", fake)
    out = llm.complete("SYS", "USER", max_tokens=100, schema={"type": "object"})
    assert out.text == "Answer [S1]." and not out.refused
    assert seen["url"] == "https://example.test/v1/chat/completions" and seen["auth"] == "Bearer test-key"
    b = seen["body"]
    assert b["model"] == "free-model" and b["temperature"] == 0 and b["response_format"] == {"type": "json_object"}
    assert b["messages"][0]["role"] == "system" and "schema" in b["messages"][0]["content"] and b["messages"][1]["content"] == "USER"
    assert seen["timeout"] == llm.TIMEOUT_S


def test_rate_limit_becomes_unavailable(monkeypatch, free):
    def fake(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many", {}, None)
    monkeypatch.setattr("urllib.request.urlopen", fake)
    with pytest.raises(llm.AIUnavailable, match="rate-limited"):
        llm.complete("s", "u")
