"""Assemble and run the LangGraph: router -> retriever -> scorer.

A single linear graph. The whole run is wrapped in one Langfuse trace (via
@observe on `run_screen`), so each invocation produces one trace with three
child spans and their generations.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from langfuse import get_client, observe
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


@observe(name="cv-screen")
def run_screen(
    cv_text: str,
    profile: str = "baseline",
    candidate_id: str = "adhoc",
) -> ScreenState:
    """Run one CV through the graph and return the final state.

    Tags the Langfuse trace with the profile + candidate so before/after runs
    are filterable in the dashboard.
    """
    graph = build_graph(profile)
    initial: ScreenState = {
        "candidate_id": candidate_id,
        "cv_text": cv_text,
        "profile": profile,
        "usages": [],
    }

    trace_url = None
    trace_id = None
    if status()["langfuse"]:
        client = get_client()
        client.update_current_trace(
            name=f"cv-screen[{profile}]",
            tags=[f"profile:{profile}", f"candidate:{candidate_id}"],
            metadata={"profile": profile, "candidate_id": candidate_id},
        )

    final: dict[str, Any] = graph.invoke(initial)

    if status()["langfuse"]:
        try:
            trace_id = get_client().get_current_trace_id()
            trace_url = get_client().get_trace_url()
        except Exception:
            pass
    final["trace_url"] = trace_url
    final["trace_id"] = trace_id
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
