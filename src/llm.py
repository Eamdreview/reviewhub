"""OpenRouter client with two-tier model routing.

The pipeline calls ``triage_batch()`` for cheap, high-volume judgment over the
candidate pool (batched to cut cost and rate-limiting), and ``writeup()`` for
high-quality analysis over the small final pool. Both go through OpenRouter so
the model is a config knob, not hard-coded logic.

Robustness: cheap models often ignore JSON-mode or wrap JSON in prose/fences,
so JSON parsing is lenient. Token usage is logged so daily cost is visible.
"""

from __future__ import annotations

import json
import logging
import re
import time

import requests

from . import config

log = logging.getLogger("reviewhub.llm")
_TIMEOUT = 120


class LLMError(RuntimeError):
    pass


def available() -> bool:
    """True if an OpenRouter key is configured."""
    return bool(config.env("OPENROUTER_API_KEY"))


def _post(payload: dict) -> dict:
    key = config.env("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set")
    resp = requests.post(
        f"{config.OPENROUTER_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/eamdreview/reviewhub",
            "X-Title": "reviewhub",
        },
        json=payload, timeout=_TIMEOUT,
    )
    if resp.status_code == 429 or resp.status_code >= 500:
        raise LLMError(f"transient {resp.status_code}: {resp.text[:200]}")
    if resp.status_code == 400 and "response_format" in resp.text:
        # Some models reject JSON mode — signal caller to retry without it.
        raise _JsonModeUnsupported(resp.text[:200])
    resp.raise_for_status()
    return resp.json()


class _JsonModeUnsupported(RuntimeError):
    pass


def _chat(model: str, system: str, user: str, *, json_mode: bool = False,
          max_retries: int = 3) -> str:
    """Chat call with retry/backoff and a JSON-mode fallback. Logs usage."""
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
            data = _post(payload)
            usage = data.get("usage", {})
            if usage:
                log.info("model=%s tokens: prompt=%s completion=%s total=%s",
                         model, usage.get("prompt_tokens"),
                         usage.get("completion_tokens"), usage.get("total_tokens"))
            return data["choices"][0]["message"]["content"]
        except _JsonModeUnsupported:
            payload.pop("response_format", None)  # retry immediately without JSON mode
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise LLMError(f"chat failed after {max_retries} attempts: {last_err}")


def _extract_json(raw: str):
    """Parse JSON even when wrapped in ```fences``` or surrounding prose."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    fenced = re.search(r"```(?:json)?\s*(.+?)```", raw, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Last resort: grab the outermost {...} or [...] span.
    m = re.search(r"(\{.*\}|\[.*\])", raw, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise LLMError(f"could not parse JSON from model output: {raw[:200]}")


def triage_batch(system: str, user: str) -> dict:
    """Cheap-model call returning a JSON object (lenient parsing)."""
    raw = _chat(config.TRIAGE_MODEL, system, user, json_mode=True)
    parsed = _extract_json(raw)
    if isinstance(parsed, list):          # model returned a bare array
        return {"results": parsed}
    return parsed


def writeup(system: str, user: str) -> str:
    """Quality-model call that returns free-form Markdown."""
    return _chat(config.WRITEUP_MODEL, system, user)
