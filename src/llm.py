"""OpenRouter client with two-tier model routing.

The pipeline calls ``triage()`` for cheap, high-volume judgment over the full
candidate pool, and ``writeup()`` for high-quality analysis over the small
final pool. Both go through OpenRouter so the specific model is a config knob,
not hard-coded logic.
"""

from __future__ import annotations

import json
import time

import requests

from . import config

_TIMEOUT = 90


class LLMError(RuntimeError):
    pass


def available() -> bool:
    """True if an OpenRouter key is configured."""
    return bool(config.env("OPENROUTER_API_KEY"))


def _chat(model: str, system: str, user: str, *, json_mode: bool = False,
          max_retries: int = 3) -> str:
    """Low-level chat call with simple retry/backoff."""
    key = config.env("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # OpenRouter ranking headers (optional, harmless).
        "HTTP-Referer": "https://github.com/eamdreview/reviewhub",
        "X-Title": "reviewhub",
    }
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers, json=payload, timeout=_TIMEOUT,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise LLMError(f"transient {resp.status_code}: {resp.text[:200]}")
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001 - retry then surface
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"chat failed after {max_retries} attempts: {last_err}")


def triage(system: str, user: str) -> dict:
    """Cheap-model call that must return JSON. Returns a parsed dict."""
    raw = _chat(config.TRIAGE_MODEL, system, user, json_mode=True)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"triage did not return valid JSON: {raw[:200]}") from exc


def writeup(system: str, user: str) -> str:
    """Quality-model call that returns free-form Markdown."""
    return _chat(config.WRITEUP_MODEL, system, user)
