"""
llm.py
Dietary Intelligence via OpenRouter (OpenAI-compatible chat completions).

Design for free-tier daily limits:
  - a priority-ordered model list (HEMOSENSE_LLM_MODELS in config)
  - automatic fallback: on 429 (free caps), 5xx, timeout or provider error the
    client moves to the next model in the chain
  - lightweight in-process per-model request counters (GET /diet/usage)

The API key is read from the environment only and is never logged or returned.
"""

import threading
import time

from api import config

SYSTEM_PROMPT = (
    "You are a clinical nutrition assistant inside a smartphone anemia-screening app. "
    "A patient's screening result is provided as JSON. Produce practical, culturally "
    "sensitive dietary guidance that matches the anemia severity, in plain markdown "
    "with short sections: 'Foods to prioritise', 'Meal timing tips', 'What to avoid / "
    "limit', and 'When to see a clinician'. Prioritise iron-rich foods, mention pairing "
    "iron-rich meals with vitamin C and avoiding tea/coffee near meals. Respect any "
    "dietary preference (vegetarian/vegan) or allergies. If the screening result is "
    "'Normal', give a prevention-focused response. End every answer with the fixed "
    "disclaimer line: 'This is screening guidance only and does not replace medical "
    "advice — please consult a clinician for a diagnosis.'"
)

MIN_COMPLETION_CHARS = 200  # a real dietary plan is always longer than this

DISCLAIMER = (
    "This is screening guidance only and does not replace medical advice. "
    "The hemoglobin estimate is not a diagnosis — please consult a clinician."
)


class LlmError(Exception):
    def __init__(self, message: str, failures=None):
        self.message = message
        self.failures = failures or []
        super().__init__(message)


class _UsageTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._events = []  # (timestamp, model)

    def record(self, model: str):
        with self._lock:
            now = time.time()
            self._events.append((now, model))
            # keep only the last 24h so counters stay bounded
            cutoff = now - 86400
            self._events = [(ts, m) for (ts, m) in self._events if ts >= cutoff]

    def snapshot(self) -> dict:
        with self._lock:
            now = time.time()
            day_cutoff = now - 86400
            hour_cutoff = now - 3600
            rows = {}
            for ts, mdl in self._events:
                if ts >= day_cutoff:
                    rows[mdl] = rows.get(mdl, 0) + 1
            last_hour = sum(1 for ts, _ in self._events if ts >= hour_cutoff)
            today = [{"model": mdl, "requests": n}
                     for mdl, n in sorted(rows.items(), key=lambda kv: -kv[1])]
            return {"today": today, "last_hour": last_hour}


usage = _UsageTracker()


def _failure_reason(model: str, exc: Exception) -> dict:
    code = 0
    if hasattr(exc, "status_code") and exc.status_code:
        code = exc.status_code
    body = getattr(exc, "response", None)
    detail = ""
    if body is not None and hasattr(body, "text"):
        detail = (body.text or "")[:160]

    if code == 429:
        reason = "rate_limited(429)"
    elif 500 <= code < 600:
        reason = f"server_error({code})"
    elif code == 401:
        reason = "auth_error(401)"
    else:
        reason = type(exc).__name__

    return {"model": model, "reason": f"{reason} {detail}".strip()}


def _call_chat(client, model: str, messages, max_tokens: int) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        extra_headers={"HTTP-Referer": "https://github.com/", "X-Title": "HemoSense API"},
        timeout=config.LLM_TIMEOUT_SECONDS,
    )
    content = resp.choices[0].message.content
    if not content or not content.strip():
        raise LlmError(f"{model} returned an empty completion.")
    # The openrouter/free auto-router sometimes lands on a safety classifier that
    # answers e.g. "User Safety: safe" -- treat that as a failure and fall back.
    if len(content.strip()) < MIN_COMPLETION_CHARS:
        raise LlmError(f"{model} returned a non-answer ({content.strip()[:60]!r}).")
    return content.strip()


def generate_recommendations(payload: dict, preferred_model=None, max_tokens=None) -> dict:
    """
    Runs the dietary prompt against the model chain.
    Returns {recommendations, model_used, attempts, failures, disclaimer}.
    Raises LlmError (-> 503) if every model fails or no API key is configured.
    """
    if not config.OPENROUTER_API_KEY:
        raise LlmError(
            "OPENROUTER_API_KEY is not set. Add it to api/.env to enable "
            "the Dietary Intelligence endpoint.",
        )

    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    models = []
    if preferred_model and preferred_model.strip():
        models.append(preferred_model.strip())
    models.extend(m for m in config.LLM_MODELS if m not in models)
    if not models:
        raise LlmError("No LLM models configured (HEMOSENSE_LLM_MODELS is empty).")

    import openai
    from openai import OpenAI

    client = OpenAI(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )

    user_text = (
        "Patient screening + context (JSON):\n"
        + str(payload)
        + "\nGive dietary recommendations as instructed."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    attempts = []
    failures = []

    for model in models:
        attempts.append(model)
        try:
            text = _call_chat(client, model, messages, max_tokens)
            usage.record(model)
            return {
                "recommendations": text,
                "model_used": model,
                "attempts": attempts,
                "failures": failures,
                "disclaimer": DISCLAIMER,
            }
        except openai.RateLimitError as exc:
            failures.append(_failure_reason(model, exc))
        except openai.AuthenticationError as exc:
            failures.append(_failure_reason(model, exc))
        except openai.APITimeoutError as exc:
            failures.append({"model": model, "reason": "timeout"})
        except openai.APIConnectionError as exc:
            failures.append({"model": model, "reason": "connection_error"})
        except openai.BadRequestError as exc:
            # model slug no longer exists / bad params: do not retry, but record
            failures.append(_failure_reason(model, exc))
        except LlmError as exc:
            failures.append({"model": model, "reason": exc.message})
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_reason(model, exc))

    raise LlmError(
        "All LLM models failed (free-tier limits likely exhausted). "
        "Check GET /diet/usage and OPENROUTER_API_KEY.",
        failures=failures,
    )