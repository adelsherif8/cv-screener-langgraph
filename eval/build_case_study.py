"""Inject real eval numbers into case_study/CASE_STUDY.md.

Reads eval/results/{baseline,optimized}.json (produced by run_eval.py) and
replaces the auto-generated regions between the HTML markers:

    <!-- METRICS:START -->   ... results table ...   <!-- METRICS:END -->
    <!-- FAILURES:START -->  ... concrete examples ... <!-- FAILURES:END -->

So the case study always reflects the latest real run — no hand-copying.

Usage:  python eval/build_case_study.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "eval" / "results"
DOC = ROOT / "case_study" / "CASE_STUDY.md"


def _load(profile: str) -> dict:
    p = RESULTS / f"{profile}.json"
    if not p.exists():
        sys.exit(f"Missing {p}. Run: python eval/run_eval.py")
    return json.loads(p.read_text())


def _delta(b: float, o: float, lower_is_better: bool) -> str:
    if b == 0 and o == 0:
        return "no change"
    if b == 0:
        return "—"
    change = (o - b) / abs(b) * 100
    if abs(change) < 0.5:
        return "no change"
    good = (o < b) if lower_is_better else (o > b)
    arrow = "down" if o < b else "up"
    sign = "improved" if good else "regressed"
    return f"{arrow} {abs(change):.0f}% ({sign})"


def metrics_table(b: dict, o: dict) -> str:
    bs, os_ = b["summary"], o["summary"]
    rows = [
        ("Decision accuracy", "decision_accuracy", False, lambda v: f"{v*100:.1f}%"),
        ("Routing accuracy", "routing_accuracy", False, lambda v: f"{v*100:.1f}%"),
        ("Parse-failure rate", "parse_failure_rate", True, lambda v: f"{v*100:.1f}%"),
        ("Mean latency / screen", "mean_latency_s", True, lambda v: f"{v:.3f} s"),
        ("Mean cost / screen", "mean_cost_usd", True, lambda v: f"${v:.6f}"),
        ("Cost / 1,000 screens", "cost_per_1k_screens_usd", True, lambda v: f"${v:.2f}"),
        ("Mean tokens / screen", "mean_tokens", True, lambda v: f"{v:.0f}"),
    ]
    out = ["| Metric | Baseline | Optimized | Change |", "| --- | --- | --- | --- |"]
    for label, key, lower, fmt in rows:
        bv, ov = bs[key], os_[key]
        out.append(f"| {label} | {fmt(bv)} | {fmt(ov)} | {_delta(bv, ov, lower)} |")
    n = bs["n_runs"]
    out.append("")
    out.append(f"_Computed over {n} labeled candidate runs per profile "
               f"(`data/candidates.json`)._")
    return "\n".join(out)


def failure_examples(b: dict, o: dict, limit: int = 6) -> str:
    """Candidates the baseline got wrong (route or decision) that the optimized
    profile fixed — the concrete payoff of the trace-driven fixes."""
    by_id = {r["id"]: r for r in o["rows"]}
    fixed = []
    for rb in b["rows"]:
        ro = by_id.get(rb["id"])
        if not ro:
            continue
        route_fix = (not rb["route_correct"]) and ro["route_correct"]
        dec_fix = (not rb["decision_correct"]) and ro["decision_correct"]
        if route_fix or dec_fix:
            kinds = []
            if route_fix:
                kinds.append(f"misrouted `{rb['pred_track']}` -> `{ro['pred_track']}` "
                             f"(gold `{rb['gold_track']}`)")
            if dec_fix:
                kinds.append(f"decision `{rb['pred_decision']}` -> `{ro['pred_decision']}` "
                             f"(gold `{rb['gold_decision']}`)")
            fixed.append((rb["id"], "; ".join(kinds)))

    if not fixed:
        return "_No baseline errors were corrected in this run (try `--runs 3` to surface variance)._"
    lines = [f"- **{cid}** — {desc}" for cid, desc in fixed[:limit]]
    return "\n".join(lines)


def replace_region(text: str, tag: str, body: str) -> str:
    start, end = f"<!-- {tag}:START -->", f"<!-- {tag}:END -->"
    if start not in text or end not in text:
        sys.exit(f"Markers for {tag} not found in {DOC}")
    pre = text.split(start)[0]
    post = text.split(end)[1]
    return f"{pre}{start}\n{body}\n{end}{post}"


def main() -> None:
    b, o = _load("baseline"), _load("optimized")
    text = DOC.read_text()
    text = replace_region(text, "METRICS", metrics_table(b, o))
    text = replace_region(text, "FAILURES", failure_examples(b, o))
    DOC.write_text(text)
    print(f"Updated {DOC.relative_to(ROOT)} with live numbers.")


if __name__ == "__main__":
    main()
