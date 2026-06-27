"""Offline evaluation harness — the source of the case study's before/after numbers.

Runs every labeled candidate through the graph for one or more profiles and
reports, per profile:
  * decision accuracy  (advance/reject vs gold)
  * routing accuracy   (router track vs gold track)
  * mean latency / run (wall clock)
  * mean cost / run    (USD) and mean tokens / run
  * parse-failure rate  (baseline free-text scorer)

Usage:
  python eval/run_eval.py                 # both profiles, prints comparison
  python eval/run_eval.py --profile baseline
  python eval/run_eval.py --runs 1        # repeats per candidate (avg out variance)
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import RESULTS_DIR  # noqa: E402
from src.graph import run_screen, totals  # noqa: E402
from src.llm import status  # noqa: E402


def load_candidates() -> list[dict]:
    return json.loads((ROOT / "data" / "candidates.json").read_text())


def evaluate(profile: str, runs: int = 1) -> dict:
    candidates = load_candidates()
    rows = []
    for cand in candidates:
        for r in range(runs):
            t0 = time.perf_counter()
            state = run_screen(cand["cv_text"], profile=profile, candidate_id=cand["id"])
            latency = time.perf_counter() - t0
            tot = totals(state)
            rows.append(
                {
                    "id": cand["id"],
                    "gold_track": cand["gold_track"],
                    "gold_decision": cand["gold_decision"],
                    "pred_track": state["router_track"],
                    "pred_decision": state["decision"],
                    "score": state["score"],
                    "route_correct": state["router_track"] == cand["gold_track"],
                    "decision_correct": state["decision"] == cand["gold_decision"],
                    "agreement": state.get("retrieval_agreement"),
                    "parse_failed": state.get("parse_failed", False),
                    "latency_s": round(latency, 3),
                    "cost_usd": tot["cost_usd"],
                    "total_tokens": tot["total_tokens"],
                }
            )

    n = len(rows)
    summary = {
        "profile": profile,
        "n_runs": n,
        "decision_accuracy": round(sum(r["decision_correct"] for r in rows) / n, 3),
        "routing_accuracy": round(sum(r["route_correct"] for r in rows) / n, 3),
        "parse_failure_rate": round(sum(r["parse_failed"] for r in rows) / n, 3),
        "mean_latency_s": round(statistics.mean(r["latency_s"] for r in rows), 3),
        "mean_cost_usd": round(statistics.mean(r["cost_usd"] for r in rows), 6),
        "mean_tokens": round(statistics.mean(r["total_tokens"] for r in rows), 1),
        "cost_per_1k_screens_usd": round(
            statistics.mean(r["cost_usd"] for r in rows) * 1000, 2
        ),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / f"{profile}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2)
    )
    return summary


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def print_comparison(summaries: dict[str, dict]) -> None:
    b, o = summaries.get("baseline"), summaries.get("optimized")
    print("\n" + "=" * 64)
    print(f"  EVAL — mock={status()['mock']}  langfuse={status()['langfuse']}")
    print("=" * 64)
    metrics = [
        ("Decision accuracy", "decision_accuracy", _pct, "up"),
        ("Routing accuracy", "routing_accuracy", _pct, "up"),
        ("Parse-failure rate", "parse_failure_rate", _pct, "down"),
        ("Mean latency (s)", "mean_latency_s", lambda v: f"{v:.3f}", "down"),
        ("Mean cost / screen ($)", "mean_cost_usd", lambda v: f"${v:.6f}", "down"),
        ("Cost / 1k screens ($)", "cost_per_1k_screens_usd", lambda v: f"${v:.2f}", "down"),
        ("Mean tokens / screen", "mean_tokens", lambda v: f"{v:.0f}", "down"),
    ]
    print(f"  {'metric':<26}{'baseline':>14}{'optimized':>14}   Δ")
    print("  " + "-" * 60)
    for label, key, fmt, good in metrics:
        bv = b[key] if b else None
        ov = o[key] if o else None
        delta = ""
        if b and o and isinstance(bv, (int, float)) and bv:
            change = (ov - bv) / abs(bv) * 100
            arrow = "↓" if ov < bv else ("↑" if ov > bv else "→")
            delta = f"{arrow}{abs(change):.0f}%"
        print(f"  {label:<26}{fmt(bv) if b else '-':>14}{fmt(ov) if o else '-':>14}   {delta}")
    print("=" * 64 + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", choices=["baseline", "optimized"], default=None)
    ap.add_argument("--runs", type=int, default=1, help="repeats per candidate")
    args = ap.parse_args()

    profiles = [args.profile] if args.profile else ["baseline", "optimized"]
    summaries = {}
    for p in profiles:
        print(f"\n▶ running profile: {p} ...")
        summaries[p] = evaluate(p, runs=args.runs)
        print(json.dumps(summaries[p], indent=2))

    if len(profiles) == 2:
        print_comparison(summaries)

    # flush any buffered Langfuse spans
    if status()["langfuse"]:
        from langfuse import get_client

        get_client().flush()
        print("✓ flushed traces to Langfuse")


if __name__ == "__main__":
    main()
