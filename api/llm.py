"""
llm.py
Dietary Intelligence.

Primary: Amazon Bedrock (Converse API, AWS credential chain / EC2 instance role), trying
config.BEDROCK_MODELS in order.
Fallback: OpenRouter (OpenAI-compatible chat completions) model chain below.
If every Bedrock model fails (permissions, throttling, invalid output), the request
continues down the OpenRouter chain, so the endpoint keeps working.

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


# ---------------------------------------------------------------------------
# Amazon Bedrock (primary) - Converse API, works for every Bedrock model family
# ---------------------------------------------------------------------------
_bedrock_client = None
_bedrock_lock = threading.Lock()


def bedrock_enabled() -> bool:
    return bool(config.BEDROCK_MODELS)


def _get_bedrock():
    global _bedrock_client
    with _bedrock_lock:
        if _bedrock_client is None:
            import boto3
            from botocore.config import Config
            _bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=config.BEDROCK_REGION,
                config=Config(read_timeout=config.LLM_TIMEOUT_SECONDS, connect_timeout=10,
                              retries={"max_attempts": 2, "mode": "standard"}),
            )
        return _bedrock_client


def _call_bedrock(model: str, system: str, user: str, max_tokens: int) -> str:
    resp = _get_bedrock().converse(
        modelId=model,
        system=[{"text": system}],
        messages=[{"role": "user", "content": [{"text": user}]}],
        inferenceConfig={"maxTokens": max_tokens},
    )
    stop = resp.get("stopReason")
    if stop in ("content_filtered", "guardrail_intervened"):
        raise LlmError(f"{model} blocked the response ({stop}).")
    # keep only answer text (reasoning models also return reasoningContent blocks)
    text = "".join(b.get("text", "") for b in resp["output"]["message"]["content"]).strip()
    if len(text) < MIN_COMPLETION_CHARS:
        raise LlmError(f"{model} returned a non-answer ({text[:60]!r}).")
    return text


def _bedrock_failure(model: str, exc: Exception) -> dict:
    label = f"bedrock:{model}"
    if isinstance(exc, LlmError):
        return {"model": label, "reason": exc.message}
    code = getattr(exc, "response", {}) or {}
    code = code.get("Error", {}).get("Code") if isinstance(code, dict) else None
    reason = f"{type(exc).__name__}({code})" if code else type(exc).__name__
    return {"model": label, "reason": f"{reason} {str(exc)[:160]}".strip()}


def _try_bedrock(system: str, user: str, max_tokens: int, failures: list, attempts=None,
                 validate=None):
    """Tries each Bedrock model in order. `validate(text)` may raise to reject an answer
    (e.g. invalid JSON) and move to the next model. Returns (result, "bedrock:<model>")
    where result is validate(text) or the text, or (None, None) when every model failed."""
    for model in config.BEDROCK_MODELS:
        label = f"bedrock:{model}"
        if attempts is not None:
            attempts.append(label)
        try:
            text = _call_bedrock(model, system, user, max_tokens)
            usage.record(label)
            return (validate(text) if validate else text), label
        except (ValueError, KeyError, TypeError) as exc:
            failures.append({"model": label, "reason": f"invalid output: {str(exc)[:120]}"})
        except Exception as exc:  # noqa: BLE001 - any Bedrock problem -> next model
            failures.append(_bedrock_failure(model, exc))
    return None, None


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


# ---------------------------------------------------------------------------
# RAG: guideline excerpts retrieved for the patient's profile
# ---------------------------------------------------------------------------
_rag_index = None
_rag_lock = threading.Lock()


def _get_rag_index():
    """Loads models/rag_index.json once; returns None (RAG off) if it does not exist."""
    global _rag_index
    with _rag_lock:
        if _rag_index is None:
            import os
            if not os.path.exists(config.RAG_INDEX_PATH):
                return None
            from hemosense.rag import Index
            _rag_index = Index.load(config.RAG_INDEX_PATH)
        return _rag_index


def retrieve_sources(payload: dict) -> list:
    index = _get_rag_index()
    if index is None:
        return []
    from hemosense.rag import query_for
    hits = index.search(query_for(payload), k=config.RAG_TOP_K)
    return [{"ref": f"S{i}", "source": h["source"], "page": h["page"], "text": h["text"]}
            for i, h in enumerate(hits, start=1)]


def _rag_block(sources: list) -> str:
    lines = ["\n\nReference excerpts from Indian and WHO anaemia guidelines:"]
    for s in sources:
        page = f", p.{s['page']}" if s["page"] else ""
        lines.append(f"[{s['ref']}] ({s['source']}{page}) {s['text']}")
    lines.append(
        "\nBase your advice on these excerpts where they are relevant and cite them inline "
        "as [S1], [S2] etc. Do not cite an excerpt for a claim it does not support. If the "
        "excerpts do not cover something, you may use general nutrition knowledge without a citation."
    )
    return "\n".join(lines)


def generate_recommendations(payload: dict, preferred_model=None, max_tokens=None,
                             use_rag: bool = True) -> dict:
    """
    Runs the dietary prompt: Bedrock models first, then the OpenRouter chain.
    With use_rag (and an index on disk) guideline excerpts are added and returned as `sources`.
    Returns {recommendations, model_used, attempts, failures, disclaimer, sources}.
    Raises LlmError (-> 503) if every model fails or nothing is configured.
    """
    max_tokens = max_tokens or config.LLM_MAX_TOKENS
    sources = retrieve_sources(payload) if use_rag else []
    user_text = (
        "Patient screening + context (JSON):\n"
        + str(payload)
        + (_rag_block(sources) if sources else "")
        + "\nGive dietary recommendations as instructed."
    )
    if sources:
        max_tokens = max(max_tokens, 900)           # room for inline citations
    attempts = []
    failures = []

    def _result(text, model):
        return {
            "recommendations": text,
            "model_used": model,
            "attempts": attempts,
            "failures": failures,
            "disclaimer": DISCLAIMER,
            "sources": [{k: s[k] for k in ("ref", "source", "page")} for s in sources],
        }

    # 1) Bedrock models, unless the caller explicitly asked for an OpenRouter model
    wants_openrouter = bool(preferred_model and preferred_model.strip())
    if bedrock_enabled() and not wants_openrouter:
        text, label = _try_bedrock(SYSTEM_PROMPT, user_text, max_tokens, failures, attempts)
        if text:
            return _result(text, label)

    # 2) OpenRouter fallback chain
    if not config.OPENROUTER_API_KEY:
        raise LlmError(
            "No LLM available: Bedrock failed or is disabled and OPENROUTER_API_KEY is not set.",
            failures=failures,
        )
    models = []
    if wants_openrouter:
        models.append(preferred_model.strip())
    models.extend(m for m in config.LLM_MODELS if m not in models)

    import openai
    from openai import OpenAI

    client = OpenAI(
        api_key=config.OPENROUTER_API_KEY,
        base_url=config.OPENROUTER_BASE_URL,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]

    for model in models:
        attempts.append(model)
        try:
            text = _call_chat(client, model, messages, max_tokens)
            usage.record(model)
            return _result(text, model)
        except openai.APITimeoutError:
            failures.append({"model": model, "reason": "timeout"})
        except openai.APIConnectionError:
            failures.append({"model": model, "reason": "connection_error"})
        except LlmError as exc:
            failures.append({"model": model, "reason": exc.message})
        except Exception as exc:  # noqa: BLE001 (429 / 401 / 400 / 5xx / provider errors)
            failures.append(_failure_reason(model, exc))

    raise LlmError(
        "All LLM models failed. Check GET /diet/usage, Bedrock access and OPENROUTER_API_KEY.",
        failures=failures,
    )

# ---------------------------------------------------------------------------
# Structured (JSON) generation with validation, used by the AI diet planner
# ---------------------------------------------------------------------------
def _extract_json(text: str):
    import json
    import re

    t = re.sub(r"<think>.*?</think>", "", text, flags=re.S)          # reasoning models
    t = re.sub(r"^```(?:json)?|```$", "", t.strip(), flags=re.M).strip()
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end <= start:
        raise LlmError("no JSON object in the reply")
    return json.loads(t[start:end + 1])


def chat_json(system: str, user: str, validate, max_tokens: int = 2000) -> dict:
    """Ask each Bedrock model, then each OpenRouter model, for a JSON object; `validate(obj)`
    must return the cleaned object or raise ValueError. Returns {"data", "model_used", "failures"}."""
    failures = []

    if bedrock_enabled():
        data, label = _try_bedrock(system, user, max_tokens, failures,
                                   validate=lambda text: validate(_extract_json(text)))
        if label:
            return {"data": data, "model_used": label, "failures": failures}

    if not config.OPENROUTER_API_KEY:
        raise LlmError("No model produced a valid plan (Bedrock failed, no OpenRouter key).",
                       failures=failures)
    import openai
    from openai import OpenAI

    client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    for model in config.LLM_MODELS:
        try:
            text = _call_chat(client, model, messages, max_tokens)
            usage.record(model)
            data = validate(_extract_json(text))
            return {"data": data, "model_used": model, "failures": failures}
        except (ValueError, KeyError, TypeError) as exc:
            failures.append({"model": model, "reason": f"invalid plan: {str(exc)[:120]}"})
        except openai.APITimeoutError:
            failures.append({"model": model, "reason": "timeout"})
        except openai.APIConnectionError:
            failures.append({"model": model, "reason": "connection_error"})
        except LlmError as exc:
            failures.append({"model": model, "reason": exc.message})
        except Exception as exc:  # noqa: BLE001
            failures.append(_failure_reason(model, exc))
    raise LlmError("No model produced a valid plan.", failures=failures)
