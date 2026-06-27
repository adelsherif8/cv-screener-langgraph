"""Gradio demo for the LangGraph CV screener.

Paste a CV (or pick a sample), choose a profile, and watch the router ->
retriever -> scorer pipeline run, with a per-node token/cost breakdown and a
deep link to the Langfuse trace. Runs in mock mode with no keys set.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import gradio as gr

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.graph import run_screen, totals  # noqa: E402
from src.llm import status  # noqa: E402

CANDIDATES = json.loads((ROOT / "data" / "candidates.json").read_text())
SAMPLES = {f"{c['id']} — {c['cv_text'][:48]}…": c["cv_text"] for c in CANDIDATES}

FA = "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css"
HEAD = f'<link rel="stylesheet" href="{FA}">'

CSS = """
.gp-card{border:1px solid #e5e7eb;border-radius:14px;padding:18px 20px;margin:10px 0;
  background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.gp-node{display:flex;align-items:center;gap:10px;font-weight:600;font-size:15px;margin-bottom:8px}
.gp-node i{width:22px;text-align:center;color:#6366f1}
.gp-row{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0}
.gp-chip{background:#f3f4f6;border-radius:999px;padding:4px 12px;font-size:13px;color:#374151}
.gp-badge{padding:5px 14px;border-radius:999px;font-weight:700;font-size:14px;color:#fff}
.gp-advance{background:#16a34a}.gp-reject{background:#dc2626}
.gp-muted{color:#6b7280;font-size:13px}
.gp-metric{font-variant-numeric:tabular-nums;font-weight:700}
.gp-flag{color:#d97706}
.gp-link{color:#4f46e5;text-decoration:none;font-weight:600}
"""


def _chip(icon: str, label: str, value: str) -> str:
    return f'<span class="gp-chip"><i class="fa-solid {icon}"></i> {label}: <b>{value}</b></span>'


def render(cv_text: str, profile: str):
    if not cv_text or not cv_text.strip():
        return "<div class='gp-card gp-muted'>Paste a CV or pick a sample to screen.</div>"

    t0 = time.perf_counter()
    s = run_screen(cv_text, profile=profile, candidate_id="demo")
    latency = time.perf_counter() - t0
    tot = totals(s)

    dec = s["decision"]
    badge_cls = "gp-advance" if dec == "advance" else "gp-reject"
    dec_icon = "fa-circle-check" if dec == "advance" else "fa-circle-xmark"

    agree = s.get("retrieval_agreement")
    agree_html = (
        f'<i class="fa-solid fa-link"></i> agrees with router'
        if agree
        else f'<span class="gp-flag"><i class="fa-solid fa-triangle-exclamation"></i> '
        f'disagrees with router (top match: {s.get("retrieval_top_track")})</span>'
    )

    per_node = "".join(
        f'<span class="gp-chip">{u["node"]} · {u["model"]} · '
        f'{u["total_tokens"]} tok · ${u["cost_usd"]:.5f}</span>'
        for u in tot["per_node"]
    )

    trace_html = ""
    if s.get("trace_url"):
        trace_html = (
            f'<a class="gp-link" href="{s["trace_url"]}" target="_blank">'
            f'<i class="fa-solid fa-arrow-up-right-from-square"></i> '
            f'Open this run in Langfuse</a>'
        )
    elif status()["mock"]:
        trace_html = ('<span class="gp-muted"><i class="fa-solid fa-circle-info"></i> '
                      'Mock mode — set OPENAI_API_KEY + Langfuse keys for live traces.</span>')

    parse_flag = ""
    if s.get("parse_failed"):
        parse_flag = ('<div class="gp-flag"><i class="fa-solid fa-triangle-exclamation"></i> '
                      'Scorer output could not be parsed cleanly — defaulted (baseline failure mode).</div>')

    return f"""
    <div class="gp-card">
      <div class="gp-node"><i class="fa-solid fa-signs-post"></i> Router
        <span class="gp-muted">· agent</span></div>
      <div class="gp-row">
        {_chip("fa-route", "track", s["router_track"])}
        {_chip("fa-user-tie", "seniority", s.get("router_seniority", "n/a"))}
        {_chip("fa-gauge-high", "confidence", f'{s.get("router_confidence", 0):.0%}')}
      </div>
    </div>

    <div class="gp-card">
      <div class="gp-node"><i class="fa-solid fa-magnifying-glass"></i> Retriever
        <span class="gp-muted">· retriever</span></div>
      <div class="gp-row">
        {_chip("fa-briefcase", "matched job", s["retrieved_job"]["title"])}
        {_chip("fa-ruler", "similarity", f'{s.get("retrieval_score", 0):.3f}')}
      </div>
      <div class="gp-row gp-muted">{agree_html}</div>
    </div>

    <div class="gp-card">
      <div class="gp-node"><i class="fa-solid fa-clipboard-check"></i> Scorer
        <span class="gp-muted">· agent</span></div>
      <div class="gp-row">
        <span class="gp-badge {badge_cls}"><i class="fa-solid {dec_icon}"></i> {dec.upper()}</span>
        {_chip("fa-star", "score", f'{s["score"]}/100')}
      </div>
      {parse_flag}
      <div class="gp-row gp-muted">{s.get("reasoning", "")[:280]}</div>
    </div>

    <div class="gp-card">
      <div class="gp-node"><i class="fa-solid fa-receipt"></i> Run accounting
        <span class="gp-muted">· profile: {profile}</span></div>
      <div class="gp-row">
        {_chip("fa-stopwatch", "latency", f'{latency:.2f}s')}
        {_chip("fa-coins", "cost", f'${tot["cost_usd"]:.5f}')}
        {_chip("fa-hashtag", "tokens", str(tot["total_tokens"]))}
      </div>
      <div class="gp-row">{per_node}</div>
      <div class="gp-row">{trace_html}</div>
    </div>
    """


def load_sample(key: str) -> str:
    return SAMPLES.get(key, "")


with gr.Blocks(title="CV Screener — LangGraph + Langfuse") as demo:
    gr.HTML(
        '<h2><i class="fa-solid fa-diagram-project"></i> '
        "Multi-Agent CV Screener</h2>"
        '<p class="gp-muted">LangGraph pipeline (router → retriever → scorer), '
        "instrumented with Langfuse. Compare the <b>baseline</b> and "
        "<b>optimized</b> profiles on the same CV.</p>"
    )
    with gr.Row():
        with gr.Column(scale=1):
            sample = gr.Dropdown(
                choices=list(SAMPLES), label="Load a sample candidate", value=None
            )
            cv = gr.Textbox(label="Candidate CV", lines=10, placeholder="Paste a CV…")
            profile = gr.Radio(
                ["baseline", "optimized"], value="optimized", label="Profile"
            )
            btn = gr.Button("Screen candidate", variant="primary")
        with gr.Column(scale=1):
            out = gr.HTML()

    sample.change(load_sample, sample, cv)
    btn.click(render, [cv, profile], out)

if __name__ == "__main__":
    print(f"Launching demo — status={status()}")
    demo.launch(head=HEAD, css=CSS)
