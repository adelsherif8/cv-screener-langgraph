"""The three graph nodes: router -> retriever -> scorer.

Every node is wrapped with Langfuse's @observe so it shows up as its own span
in the trace tree (with semantic type: agent / retriever). LLM calls inside
the nodes are auto-captured as generations by the langfuse.openai wrapper.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from langfuse import observe

from . import prompts
from .config import DATA_DIR, get_profile
from .llm import chat, cosine, embed
from .state import ScreenState


@lru_cache(maxsize=1)
def _jobs() -> dict[str, dict[str, Any]]:
    data = json.loads((DATA_DIR / "jobs.json").read_text())
    return {j["id"]: j for j in data}


@lru_cache(maxsize=1)
def _job_embeddings() -> dict[str, list[float]]:
    """Embed each job blurb once and cache (the 'index' the retriever hits)."""
    jobs = _jobs()
    ids = list(jobs)
    blurbs = [f"{jobs[i]['title']}. {jobs[i]['blurb']}" for i in ids]
    vectors, _ = embed(blurbs)
    return dict(zip(ids, vectors))


# --------------------------------------------------------------------------
# ROUTER
# --------------------------------------------------------------------------
@observe(name="router", as_type="agent")
def router_node(state: ScreenState) -> ScreenState:
    cfg = get_profile(state["profile"]).router
    cv = state["cv_text"]

    if cfg.structured:
        payload, usage = chat(
            model=cfg.model,
            system=prompts.ROUTER_OPTIMIZED_SYSTEM,
            user=prompts.router_user_prompt(cv),
            temperature=cfg.temperature,
            json_schema=prompts.ROUTER_JSON_SCHEMA,
            name="router-llm",
        )
        return {
            "router_track": payload["track"],
            "router_seniority": payload["seniority"],
            "router_confidence": float(payload["confidence"]),
            "router_reason": payload["reason"],
            "usages": [{"node": "router", **usage}],
        }

    # baseline: free-text answer that we have to keyword-parse
    text, usage = chat(
        model=cfg.model,
        system=prompts.ROUTER_BASELINE.split("\n\n")[0],
        user=prompts.ROUTER_BASELINE.format(cv_text=cv),
        temperature=cfg.temperature,
        name="router-llm",
    )
    track = _parse_track(text)
    return {
        "router_track": track,
        "router_seniority": "unknown",
        "router_confidence": 0.5,
        "router_reason": text.strip()[:200],
        "usages": [{"node": "router", **usage}],
    }


def _parse_track(text: str) -> str:
    t = text.lower()
    hits = [(t.index(tr), tr) for tr in prompts.TRACKS if tr in t]
    if hits:
        return min(hits)[1]  # first track mentioned
    return "backend"  # arbitrary default when the prose names no known track


# --------------------------------------------------------------------------
# RETRIEVER
# --------------------------------------------------------------------------
@observe(name="retriever", as_type="retriever")
def retriever_node(state: ScreenState) -> ScreenState:
    cv = state["cv_text"]
    jobs = _jobs()
    job_vecs = _job_embeddings()

    # Embed the CV and find the best-matching job by cosine similarity. This is
    # the real retrieval signal; it also acts as a cheap cross-check on the
    # router (the 'agreement' flag is how router misroutes get caught at scale).
    cv_vec_list, usage = embed([cv])
    cv_vec = cv_vec_list[0]
    sims = {jid: cosine(cv_vec, v) for jid, v in job_vecs.items()}
    top_track = max(sims, key=sims.get)

    router_track = state.get("router_track", top_track)
    retrieved = jobs.get(router_track, jobs[top_track])  # scorer grounds on router's pick

    return {
        "retrieved_job": retrieved,
        "retrieval_top_track": top_track,
        "retrieval_score": round(sims[retrieved["id"]], 4),
        "retrieval_agreement": top_track == router_track,
        "usages": [{"node": "retriever", **usage}],
    }


# --------------------------------------------------------------------------
# SCORER
# --------------------------------------------------------------------------
@observe(name="scorer", as_type="agent")
def scorer_node(state: ScreenState) -> ScreenState:
    cfg = get_profile(state["profile"]).scorer
    cv = state["cv_text"]
    job = state["retrieved_job"]
    seniority = state.get("router_seniority", "unknown")

    if cfg.structured:
        payload, usage = chat(
            model=cfg.model,
            system=prompts.SCORER_OPTIMIZED_SYSTEM,
            user=prompts.scorer_optimized_user(cv, job, seniority),
            temperature=cfg.temperature,
            json_schema=prompts.SCORER_JSON_SCHEMA,
            name="scorer-llm",
        )
        return {
            "decision": payload["decision"],
            "score": int(payload["score"]),
            "reasoning": payload["reasoning"],
            "parse_failed": False,
            "usages": [{"node": "scorer", **usage}],
        }

    # baseline: free-text answer -> brittle regex parse
    text, usage = chat(
        model=cfg.model,
        system=None,
        user=prompts.SCORER_BASELINE.format(
            job_title=job["title"], job_blurb=job["blurb"], cv_text=cv
        ),
        temperature=cfg.temperature,
        name="scorer-llm",
    )
    decision, score, failed = _parse_assessment(text)
    return {
        "decision": decision,
        "score": score,
        "reasoning": text.strip()[:300],
        "parse_failed": failed,
        "usages": [{"node": "scorer", **usage}],
    }


def _parse_assessment(text: str) -> tuple[str, int, bool]:
    """Extract (decision, score, parse_failed) from free-text prose.

    This is intentionally the kind of brittle post-hoc parsing the baseline
    forces on us — the failure mode the case study fixes with structured output.
    """
    t = text.lower()
    m = re.search(r"(\d{1,3})\s*/\s*100", t) or re.search(r"score[:\s]+(\d{1,3})", t)
    score = int(m.group(1)) if m else -1

    advance_kw = ["advance", "strong fit", "great fit", "good fit", "strong candidate",
                  "recommend", "would move", "proceed"]
    reject_kw = ["reject", "weak", "not a good fit", "not a fit", "do not", "lacks",
                 "too junior", "no production"]
    has_adv = any(k in t for k in advance_kw)
    has_rej = any(k in t for k in reject_kw)

    if has_adv and not has_rej:
        decision = "advance"
    elif has_rej and not has_adv:
        decision = "reject"
    elif score >= 0:
        decision = "advance" if score >= 60 else "reject"
    else:
        # nothing parseable -> default to reject and flag it
        return "reject", 0, True

    if score < 0:
        score = 70 if decision == "advance" else 30
        return decision, score, True  # decision found but no number -> partial parse fail
    return decision, score, False
