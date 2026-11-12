"""Provider-agnostic LLM interface. Optional: the platform works fully with provider=none.

FA_LLM_PROVIDER = none | anthropic | openai | ollama
FA_LLM_MODEL    = model id (e.g. claude-sonnet-5-5, gpt-..., llama3)
ANTHROPIC_API_KEY / OPENAI_API_KEY / OLLAMA_URL as appropriate.

The LLM may only rephrase a sentence that was composed from retrieved evidence. The
rephrased text is re-verified; if it fails verification the template sentence is kept.
"""
from __future__ import annotations

import os

import httpx

PROMPT = ("Rephrase the sentence for a {role} reader. Keep every number, unit and identifier exactly as written. "
          "Do not add facts. Reply with the sentence only.\n\nSentence: {text}")


class LLM:
    name = "none"

    def rephrase(self, text: str, role: str = "researcher") -> str:
        return text


class Anthropic(LLM):
    name = "anthropic"

    def rephrase(self, text, role="researcher"):
        r = httpx.post("https://api.anthropic.com/v1/messages", timeout=20, headers={
            "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
            json={"model": os.environ.get("FA_LLM_MODEL", "claude-haiku-5-5"), "max_tokens": 200,
                  "messages": [{"role": "user", "content": PROMPT.format(role=role, text=text)}]})
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()


class OpenAICompatible(LLM):
    name = "openai"

    def rephrase(self, text, role="researcher"):
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        r = httpx.post(f"{base}/chat/completions", timeout=20,
                       headers={"Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', '')}"},
                       json={"model": os.environ.get("FA_LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
                             "messages": [{"role": "user", "content": PROMPT.format(role=role, text=text)}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


class Ollama(LLM):
    name = "ollama"

    def rephrase(self, text, role="researcher"):
        r = httpx.post(f"{os.environ.get('OLLAMA_URL', 'http://localhost:11434')}/api/generate", timeout=30,
                       json={"model": os.environ.get("FA_LLM_MODEL", "llama3"), "stream": False,
                             "prompt": PROMPT.format(role=role, text=text)})
        r.raise_for_status()
        return r.json()["response"].strip()


def get_llm() -> LLM:
    p = os.environ.get("FA_LLM_PROVIDER", "none").lower()
    try:
        if p == "anthropic" and os.environ.get("ANTHROPIC_API_KEY"):
            return Anthropic()
        if p == "openai":
            return OpenAICompatible()
        if p == "ollama":
            return Ollama()
    except Exception:
        pass
    return LLM()
