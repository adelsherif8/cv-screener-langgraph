"""LLM + embedding access layer.

Responsibilities:
  * Provide a single OpenAI client, wrapped by Langfuse when keys are present
    so every generation is auto-traced with token usage and cost.
  * Expose `chat()` and `embed()` helpers that always return (payload, usage).
  * Fall back to a deterministic MOCK mode when no OPENAI_API_KEY is set, so
    the graph, eval, and Gradio demo all run offline (no real traces/cost).
"""
from __future__ import annotations

import json
import math
import os
from typing import Any

from dotenv import load_dotenv

from .config import EMBED_MODEL, cost_usd

load_dotenv()

MOCK = not bool(os.getenv("OPENAI_API_KEY"))
_LANGFUSE_ON = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))

if not _LANGFUSE_ON:
    # @observe still initializes a (disabled) client; silence its auth warnings.
    import logging

    logging.getLogger("langfuse").setLevel(logging.CRITICAL)

# Use the Langfuse drop-in wrapper when Langfuse is configured (auto-captures
# generations); otherwise the vanilla OpenAI client. Either way the call sites
# are identical.
_client = None
if not MOCK:
    if _LANGFUSE_ON:
        from langfuse.openai import OpenAI  # type: ignore
    else:
        from openai import OpenAI  # type: ignore
    _client = OpenAI()


def status() -> dict[str, bool]:
    return {"mock": MOCK, "langfuse": _LANGFUSE_ON}


# --------------------------------------------------------------------------
# Chat
# --------------------------------------------------------------------------
def chat(
    *,
    model: str,
    system: str | None,
    user: str,
    temperature: float,
    json_schema: dict[str, Any] | None = None,
    name: str | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Run a chat completion.

    Returns (payload, usage). `payload` is a parsed dict when json_schema is
    given (structured mode), else the raw text. `usage` always carries
    prompt/completion tokens, model and computed cost_usd.
    """
    if MOCK:
        return _mock_chat(model, system, user, json_schema)

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_schema is not None:
        kwargs["response_format"] = {"type": "json_schema", "json_schema": json_schema}
    if name and _LANGFUSE_ON:
        # The langfuse.openai wrapper accepts `name` for the generation label;
        # the vanilla OpenAI client would reject it.
        kwargs["name"] = name

    resp = _client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    u = resp.usage
    usage = _usage(model, u.prompt_tokens, u.completion_tokens)

    if json_schema is not None:
        return json.loads(text), usage
    return text, usage


def embed(texts: list[str]) -> tuple[list[list[float]], dict[str, Any]]:
    """Embed texts. Returns (vectors, usage)."""
    if MOCK:
        return [_mock_embed(t) for t in texts], _usage(EMBED_MODEL, 0, 0)

    resp = _client.embeddings.create(model=EMBED_MODEL, input=texts)
    vectors = [d.embedding for d in resp.data]
    usage = _usage(EMBED_MODEL, resp.usage.prompt_tokens, 0)
    return vectors, usage


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _usage(model: str, p: int, c: int) -> dict[str, Any]:
    return {
        "model": model,
        "prompt_tokens": p,
        "completion_tokens": c,
        "total_tokens": p + c,
        "cost_usd": cost_usd(model, p, c),
    }


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


# --------------------------------------------------------------------------
# MOCK implementations (deterministic, offline)
# --------------------------------------------------------------------------
_TRACK_KEYWORDS = {
    "backend": ["api", "server", "backend", "grpc", "postgres", "microservice", "kafka", "redis"],
    "frontend": ["react", "vue", "angular", "frontend", "css", "ui", "typescript", "a11y"],
    "ml": ["pytorch", "tensorflow", "model", "ml", "llm", "nlp", "training", "rag"],
    "data": ["etl", "elt", "airflow", "dbt", "warehouse", "snowflake", "spark", "sql"],
}


def _mock_chat(model, system, user, json_schema):
    text_l = user.lower()
    usage = _usage(model, max(40, len(user) // 4), 30)

    # Router-shaped request
    if json_schema and json_schema.get("name") == "route_decision" or (
        json_schema is None and "which engineering role" in (system or "").lower()
    ):
        scores = {
            t: sum(text_l.count(k) for k in kws) for t, kws in _TRACK_KEYWORDS.items()
        }
        track = max(scores, key=scores.get)
        seniority = "senior" if any(f"{n} yr" in text_l for n in (5, 6, 7, 8)) else (
            "junior" if ("no production" in text_l or "bootcamp" in text_l) else "mid"
        )
        payload = {"track": track, "seniority": seniority, "confidence": 0.6,
                   "reason": "[mock] keyword match"}
        return (payload if json_schema else track), usage

    # Scorer-shaped request. Only inspect the CV portion of the prompt — the
    # rubric text itself contains disqualifier phrases that would false-trigger.
    cv_part = text_l
    for marker in ("candidate cv:", "candidate:\n", "cv:\n"):
        if marker in text_l:
            cv_part = text_l.split(marker, 1)[1]
            break
    reject = any(k in cv_part for k in ["no production", "bootcamp", "no programming",
                                        "no software engineering", "no ml or data",
                                        "no internship", "thin portfolio",
                                        "copied a few", "light python scripting",
                                        "never shipped"])
    decision = "reject" if reject else "advance"
    score = 35 if reject else 78
    if json_schema:
        payload = {"decision": decision, "score": score, "matched_must_haves": [],
                   "missing_must_haves": [], "reasoning": "[mock] heuristic decision"}
        return payload, usage
    return f"[mock] This candidate seems {'weak' if reject else 'strong'}. Score: {score}/100.", usage


def _mock_embed(text: str) -> list[float]:
    # cheap deterministic embedding: track-keyword histogram, L2-ish space
    text_l = text.lower()
    vec = []
    for t in ["backend", "frontend", "ml", "data"]:
        vec.append(float(sum(text_l.count(k) for k in _TRACK_KEYWORDS[t])))
    # pad with a couple of length features for tie-breaking
    vec += [len(text_l) / 1000.0, text_l.count("year") + text_l.count("yr")]
    return vec
