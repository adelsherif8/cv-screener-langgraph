"""Central configuration: model profiles, pricing, and paths.

The whole case study hinges on two *profiles* that run the exact same graph
with different model/prompt/decoding settings:

    baseline   -> gpt-4o everywhere, vague prompts, free-text scorer output
    optimized  -> gpt-4o-mini, explicit prompts, structured (JSON) outputs

Flipping PROFILE (env var CV_PROFILE or the function arg) is the only thing
that changes between the "before" and "after" numbers.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "eval" / "results"

# --- OpenAI pricing (USD per 1M tokens) ----------------------------------
# Source: OpenAI public pricing. Kept here so cost is computed locally and is
# reproducible offline; Langfuse also computes cost server-side from usage.
PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
}

EMBED_MODEL = "text-embedding-3-small"


@dataclass(frozen=True)
class NodeCfg:
    model: str
    temperature: float
    # When True the scorer is asked for strict JSON via response_format and
    # the router uses tool/JSON-mode classification. When False we use the
    # legacy free-text prompts that the baseline has to regex-parse.
    structured: bool


@dataclass(frozen=True)
class Profile:
    name: str
    router: NodeCfg
    scorer: NodeCfg
    # Whether the router prompt includes explicit track definitions +
    # disambiguation rules (optimized) or just asks vaguely (baseline).
    detailed_router_prompt: bool = field(default=False)


PROFILES = {
    "baseline": Profile(
        name="baseline",
        router=NodeCfg(model="gpt-4o", temperature=0.7, structured=False),
        scorer=NodeCfg(model="gpt-4o", temperature=0.7, structured=False),
        detailed_router_prompt=False,
    ),
    "optimized": Profile(
        name="optimized",
        router=NodeCfg(model="gpt-4o-mini", temperature=0.0, structured=True),
        scorer=NodeCfg(model="gpt-4o-mini", temperature=0.0, structured=True),
        detailed_router_prompt=True,
    ),
}


def get_profile(name: str | None = None) -> Profile:
    name = name or os.getenv("CV_PROFILE", "baseline")
    if name not in PROFILES:
        raise ValueError(f"Unknown profile {name!r}. Choose from {list(PROFILES)}.")
    return PROFILES[name]


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Compute USD cost for a single call from token counts."""
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (prompt_tokens / 1_000_000) * p["input"] + (
        completion_tokens / 1_000_000
    ) * p["output"]
