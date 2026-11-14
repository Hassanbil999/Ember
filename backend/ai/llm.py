"""Claude via the Anthropic SDK (SPEC §11). One function, `complete()`, so tests can replace it with a fake.

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


def model_name() -> str:
    return os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


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
        raise AIUnavailable("No ANTHROPIC_API_KEY is set.")
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
