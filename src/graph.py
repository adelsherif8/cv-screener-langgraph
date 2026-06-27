"""Assemble and run the LangGraph: router -> retriever -> scorer.

A single linear graph. The whole run is wrapped in one Langfuse trace (via
@observe on `run_screen`), so each invocation produces one trace with three
child spans and their generations.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from langfuse import get_client, observe, propagate_attributes
from langgraph.graph import END, START, StateGraph

from .config import get_profile
from .llm import status
from .nodes import retriever_node, router_node, scorer_node
from .state import ScreenState


@lru_cache(maxsize=4)
def build_graph(profile: str = "baseline"):
    """Compile the graph. Cached per profile (graph shape is identical;
    behaviour is driven by the profile carried in state)."""
    g = StateGraph(ScreenState)
    g.add_node("router", router_node)
    g.add_node("retriever", retriever_node)
    g.add_node("scorer", scorer_node)
    g.add_edge(START, "router")
    g.add_edge("router", "retriever")
    g.add_edge("retriever", "scorer")
    g.add_edge("scorer", END)
    return g.compile()


# capture_input/output disabled: we set clean trace I/O explicitly below so the
# trace shows the CV in and the decision out — not the whole noisy state dict
# (Langfuse best practice: don't let every function arg become the trace input).
@observe(name="cv-screen", capture_input=False, capture_output=False)
def run_screen(
    cv_text: str,
    profile: str = "baseline",
    candidate_id: str = "adhoc",
) -> ScreenState:
    """Run one CV through the graph and return the final state.

    Wraps the run in `propagate_attributes` so the profile/candidate tags and a
    descriptive trace name flow to every child span — that's what makes the
    before/after comparison filterable in the Langfuse dashboard.
    """
    graph = build_graph(profile)
    initial: ScreenState = {
        "candidate_id": candidate_id,
        "cv_text": cv_text,
        "profile": profile,
        "usages": [],
    }

    if not status()["langfuse"]:
        final: dict[str, Any] = graph.invoke(initial)
        final["trace_url"] = final["trace_id"] = None
        return final  # type: ignore[return-value]

    client = get_client()
    with propagate_attributes(
        trace_name=f"cv-screen[{profile}]",
        tags=[f"profile:{profile}", f"candidate:{candidate_id}"],
        metadata={"profile": profile, "candidate_id": candidate_id},
    ):
        final = graph.invoke(initial)
        # Explicit, readable trace I/O (instead of the full state dict).
        client.update_current_span(
            input={"candidate_id": candidate_id, "cv_text": cv_text},
            output={
                "track": final.get("router_track"),
                "decision": final.get("decision"),
                "score": final.get("score"),
                "cost_usd": round(sum(u["cost_usd"] for u in final.get("usages", [])), 6),
            },
        )
        try:
            final["trace_id"] = client.get_current_trace_id()
            final["trace_url"] = client.get_trace_url()
        except Exception:
            final["trace_id"] = final["trace_url"] = None
    return final  # type: ignore[return-value]


def totals(state: ScreenState) -> dict[str, Any]:
    """Roll the per-node usage records up into trace-level totals."""
    usages = state.get("usages", [])
    return {
        "prompt_tokens": sum(u["prompt_tokens"] for u in usages),
        "completion_tokens": sum(u["completion_tokens"] for u in usages),
        "total_tokens": sum(u["total_tokens"] for u in usages),
        "cost_usd": sum(u["cost_usd"] for u in usages),
        "per_node": usages,
    }
