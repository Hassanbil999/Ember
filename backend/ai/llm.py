"""The language model behind the AI summary and Ask (SPEC §11). One function, `complete()`, so tests can replace it.

Two providers, picked by which key is set (Anthropic first):
- Claude via the Anthropic SDK: ANTHROPIC_API_KEY (+ ANTHROPIC_MODEL).
- Any OpenAI-compatible chat API, e.g. a free tier: LLM_API_KEY + LLM_BASE_URL + LLM_MODEL
  (Google AI Studio: https://generativelanguage.googleapis.com/v1beta/openai ; Groq: https://api.groq.com/openai/v1).
  Plain HTTPS with the standard library, so no extra dependency.
Either way the callers' rules hold: cite or refuse, numbers checked against the sources.

- Model from ANTHROPIC_MODEL (default claude-sonnet-5-5); enabled only when ANTHROPIC_API_KEY is set.
- 20 s timeout, no retries beyond it, so the UI never hangs.
- Refusals (stop_reason "refusal") come back as `refused=True`; callers then fall back or refuse.
- On models that support it, server-side refusal fallbacks are on ("default" routing), so a policy
  decline on the main model is retried on another model inside the same call.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_MODEL = "claude-sonnet-5-5"
TIMEOUT_S = 20.0
FALLBACK_MODELS = {"claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
EFFORT_MODELS = FALLBACK_MODELS | {"claude-haiku-5-5", "claude-sonnet-5", "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
                                   "claude-sonnet-4-6", "claude-fable-5"}


class AIUnavailable(Exception):
    """No key, a timeout or an API error: the caller decides how to degrade."""


@dataclass
class Completion:
    text: str
    model: str
    refused: bool = False


def provider() -> str | None:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("LLM_API_KEY") and os.environ.get("LLM_BASE_URL") and os.environ.get("LLM_MODEL"):
        return "openai_compatible"
    return None


def model_name() -> str:
    if provider() == "openai_compatible":
        return os.environ["LLM_MODEL"]
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def enabled() -> bool:
    return provider() is not None


def _complete_openai_compatible(system: str, user: str, max_tokens: int, schema: dict | None) -> Completion:
    import json
    import urllib.error
    import urllib.request
    model = model_name()
    body: dict = {"model": model, "max_tokens": max_tokens, "temperature": 0,
                  "messages": [{"role": "system", "content": system + (
                      "\nReply with one JSON object that matches this schema:\n" + json.dumps(schema) if schema else "")},
                               {"role": "user", "content": user}]}
    if schema is not None:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(os.environ["LLM_BASE_URL"].rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + os.environ["LLM_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise AIUnavailable("The AI is rate-limited right now." if e.code == 429 else f"The AI returned an error ({e.code}).") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise AIUnavailable("Could not reach the AI service.") from e
    try:
        choice = data["choices"][0]
        text = (choice["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        raise AIUnavailable("The AI returned an unexpected response.") from e
    return Completion(text, data.get("model", model), refused=choice.get("finish_reason") == "content_filter")


_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)
    return _client


def complete(system: str, user: str, max_tokens: int = 2048, schema: dict | None = None) -> Completion:
    """`schema` (a JSON schema) turns on structured outputs: the text is then guaranteed to be valid JSON."""
    if not enabled():
        raise AIUnavailable("No AI key is set (ANTHROPIC_API_KEY, or LLM_API_KEY + LLM_BASE_URL + LLM_MODEL).")
    if provider() == "openai_compatible":
        return _complete_openai_compatible(system, user, max_tokens, schema)
    import anthropic
    model = model_name()
    kwargs: dict = {"model": model, "max_tokens": max_tokens, "system": system,
                    "messages": [{"role": "user", "content": user}]}
    output_config: dict = {}
    if model in EFFORT_MODELS:
        output_config["effort"] = "low"          # short, grounded answers: thinking depth is not the bottleneck
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    if output_config:
        kwargs["output_config"] = output_config
    try:
        if model in FALLBACK_MODELS:
            msg = _get_client().beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            msg = _get_client().messages.create(**kwargs)
    except anthropic.APITimeoutError as e:
        raise AIUnavailable(f"The AI took longer than {TIMEOUT_S:.0f} s.") from e
    except anthropic.RateLimitError as e:
        raise AIUnavailable("The AI is rate-limited right now.") from e
    except anthropic.APIStatusError as e:
        raise AIUnavailable(f"The AI returned an error ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise AIUnavailable("Could not reach the AI service.") from e
    if msg.stop_reason == "refusal":
        return Completion("", getattr(msg, "model", model), refused=True)
    text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    return Completion(text, getattr(msg, "model", model))
