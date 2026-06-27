"""Prompt builders for the baseline and optimized profiles.

The *only* substantive difference between baseline and optimized prompts is
clarity and structure — same task, same data. This is deliberate: it lets the
case study attribute the accuracy gain to prompt/agent-config changes rather
than to a different problem definition.
"""
from __future__ import annotations

import json
from typing import Any

TRACKS = ["backend", "frontend", "ml", "data"]

# --------------------------------------------------------------------------
# ROUTER
# --------------------------------------------------------------------------

# Baseline: vague, no definitions, no disambiguation rule. With a hot
# temperature this misroutes "ambiguous" CVs (full-stack, applied-scientist).
ROUTER_BASELINE = (
    "You are a recruiting assistant. Read the CV and say which engineering "
    "role it fits: backend, frontend, ml, or data. Reply with the role.\n\n"
    "CV:\n{cv_text}"
)

# Optimized: explicit track definitions + a disambiguation rule that resolves
# the exact ambiguity the baseline trips on ("classify by primary focus").
ROUTER_OPTIMIZED_SYSTEM = (
    "You are a precise CV-routing classifier. Assign each CV to exactly one "
    "engineering track, then estimate seniority and your confidence.\n\n"
    "Track definitions:\n"
    "- backend: server-side services, APIs, databases, distributed systems.\n"
    "- frontend: web UI in JS/TS frameworks (React/Vue/Angular), client perf, a11y.\n"
    "- ml: training/evaluating/serving ML or LLM models (PyTorch/TensorFlow, NLP).\n"
    "- data: data pipelines, ETL/ELT, warehousing, SQL/dbt/Airflow/Spark.\n\n"
    "Disambiguation rules (critical):\n"
    "1. Many CVs touch multiple areas. Route by the candidate's PRIMARY/CORE "
    "focus and what role they are seeking — not by every keyword present.\n"
    "2. Full-stack who say their core is server-side/APIs/databases -> backend.\n"
    "3. Applied scientists who build ETL only to feed models, but whose core is "
    "model development -> ml (not data).\n"
    "4. Mobile-native (iOS/Android) with no web framework is NOT frontend.\n"
    "Seniority: junior (<2 yrs / no production), mid (2-5 yrs), senior (5+ yrs)."
)


def router_user_prompt(cv_text: str) -> str:
    return f"CV:\n{cv_text}"


# JSON schema used for the optimized router's structured output.
ROUTER_JSON_SCHEMA: dict[str, Any] = {
    "name": "route_decision",
    "schema": {
        "type": "object",
        "properties": {
            "track": {"type": "string", "enum": TRACKS},
            "seniority": {"type": "string", "enum": ["junior", "mid", "senior"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
        },
        "required": ["track", "seniority", "confidence", "reason"],
        "additionalProperties": False,
    },
    "strict": True,
}


# --------------------------------------------------------------------------
# SCORER
# --------------------------------------------------------------------------

# Baseline: vague, no rubric structure, free-text answer. The graph then has
# to regex a number out of prose -> brittle, frequent parse failures.
SCORER_BASELINE = (
    "You are a hiring assistant. Here is a candidate and the job. Tell me if "
    "they are a good fit and how strong they are.\n\n"
    "Job: {job_title}\n{job_blurb}\n\nCandidate CV:\n{cv_text}\n\n"
    "Give your assessment."
)

SCORER_OPTIMIZED_SYSTEM = (
    "You are a rigorous technical screener. Score the candidate against the "
    "job rubric ONLY. Be strict: missing must-haves or no production "
    "experience should lower the score and usually mean 'reject'.\n\n"
    "Decision policy:\n"
    "- advance: meets all/most must-haves with real (production) experience.\n"
    "- reject: missing core must-haves, only academic/bootcamp projects, or "
    "hits a disqualifier.\n"
    "Score 0-100 reflecting must-have coverage and depth."
)


def scorer_optimized_user(cv_text: str, job: dict[str, Any], seniority: str) -> str:
    rubric = job["rubric"]
    return (
        f"JOB: {job['title']}\n{job['blurb']}\n\n"
        f"RUBRIC\n"
        f"  must_have: {json.dumps(rubric['must_have'])}\n"
        f"  nice_to_have: {json.dumps(rubric['nice_to_have'])}\n"
        f"  disqualifiers: {json.dumps(rubric['disqualifiers'])}\n\n"
        f"Router seniority signal: {seniority}\n\n"
        f"CANDIDATE CV:\n{cv_text}"
    )


SCORER_JSON_SCHEMA: dict[str, Any] = {
    "name": "score_decision",
    "schema": {
        "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["advance", "reject"]},
            "score": {"type": "integer", "minimum": 0, "maximum": 100},
            "matched_must_haves": {"type": "array", "items": {"type": "string"}},
            "missing_must_haves": {"type": "array", "items": {"type": "string"}},
            "reasoning": {"type": "string"},
        },
        "required": [
            "decision",
            "score",
            "matched_must_haves",
            "missing_must_haves",
            "reasoning",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}
