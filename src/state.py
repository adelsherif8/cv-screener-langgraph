"""LangGraph state schema for the CV screener.

`usages` uses an additive reducer so each node appends its own token/cost
record without clobbering the others; everything else is last-write-wins.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ScreenState(TypedDict, total=False):
    # --- inputs ---
    candidate_id: str
    cv_text: str
    profile: str

    # --- router node output ---
    router_track: str
    router_seniority: str
    router_confidence: float
    router_reason: str

    # --- retriever node output ---
    retrieved_job: dict[str, Any]
    retrieval_top_track: str          # best track by embedding similarity
    retrieval_score: float            # cosine sim of CV to retrieved job
    retrieval_agreement: bool         # does embedding top-match agree w/ router?

    # --- scorer node output ---
    decision: str                     # "advance" | "reject"
    score: int
    reasoning: str
    parse_failed: bool                # baseline free-text parse failed -> defaulted

    # --- accounting (additive across nodes) ---
    usages: Annotated[list[dict[str, Any]], operator.add]

    # --- set on the returned state (outside the graph) ---
    trace_url: str | None
    trace_id: str | None
