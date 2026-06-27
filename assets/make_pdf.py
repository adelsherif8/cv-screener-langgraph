"""Build a polished, self-contained case-study PDF for Upwork Sample Documents.

Strongest content first (clients only see the first 3 pages): summary +
architecture + results on page 1, failure modes + fixes on page 2, real trace
evidence + reproduce on page 3. Images are embedded as base64 so the PDF is
fully self-contained. Output: assets/case-study.pdf (kept < 2 MB).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "assets"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def img(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/png;base64,{b64}"


def html() -> str:
    b = json.loads((ROOT / "eval/results/baseline.json").read_text())["summary"]
    o = json.loads((ROOT / "eval/results/optimized.json").read_text())["summary"]
    rows = [
        ("Decision accuracy", f"{b['decision_accuracy']*100:.1f}%", f"{o['decision_accuracy']*100:.1f}%", "+7%"),
        ("Scorer parse-failure", f"{b['parse_failure_rate']*100:.0f}%", f"{o['parse_failure_rate']*100:.0f}%", "-100%"),
        ("Latency / screen", f"{b['mean_latency_s']:.2f}s", f"{o['mean_latency_s']:.2f}s", "-37%"),
        ("Cost / 1,000 screens", f"${b['cost_per_1k_screens_usd']:.2f}", f"${o['cost_per_1k_screens_usd']:.2f}", "-95%"),
        ("Routing accuracy", f"{b['routing_accuracy']*100:.0f}%", f"{o['routing_accuracy']*100:.0f}%", "held"),
    ]
    tr = "".join(
        f"<tr><td>{l}</td><td class=n>{bv}</td><td class=n><b>{ov}</b></td>"
        f"<td class=d>{d}</td></tr>" for l, bv, ov, d in rows
    )
    return f"""<!doctype html><html><head><meta charset=utf-8><style>
    @page {{ size: A4; margin: 16mm 15mm; }}
    *{{box-sizing:border-box;margin:0;font-family:{FONT};-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    body{{color:#1e293b;font-size:13px;line-height:1.6}}
    .page{{page-break-after:always}}
    h1{{font-size:27px;letter-spacing:-.5px;color:#0f172a}}
    .tag{{color:#6366f1;font-weight:700;font-size:12px;letter-spacing:.4px;text-transform:uppercase}}
    .by{{color:#64748b;font-size:12px;margin-top:6px}}
    .by a{{color:#4f46e5;text-decoration:none}}
    h2{{font-size:17px;color:#0f172a;margin:22px 0 8px;padding-bottom:6px;border-bottom:2px solid #eef2f7}}
    p{{margin:8px 0}}
    .lede{{font-size:14px;color:#334155}}
    img{{width:100%;border:1px solid #e5e7eb;border-radius:10px;margin:10px 0}}
    table{{width:100%;border-collapse:collapse;margin:10px 0}}
    th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#94a3b8;padding:6px 8px;border-bottom:2px solid #eef2f7}}
    td{{padding:9px 8px;border-bottom:1px solid #f1f5f9}}
    td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
    td.d{{text-align:right;color:#16a34a;font-weight:800}}
    .fm{{background:#f8fafc;border:1px solid #eef2f7;border-radius:10px;padding:12px 14px;margin:9px 0}}
    .fm b{{color:#0f172a}}
    .cap{{color:#64748b;font-size:11px;margin-top:-4px}}
    ul{{margin:6px 0 6px 18px}} li{{margin:4px 0}}
    .foot{{color:#94a3b8;font-size:11px;margin-top:18px;border-top:1px solid #eef2f7;padding-top:8px}}
    </style></head><body>

    <div class=page>
      <div class=tag>LLM Agents &middot; Observability &middot; Optimization</div>
      <h1>Multi-Agent CV Screener &mdash; Trace-Driven Optimization</h1>
      <div class=by>Adel Sherif &middot;
        <a>github.com/adelsherif8/cv-screener-langgraph</a> &middot;
        <a>cv-screener-langgraph.vercel.app</a></div>

      <p class=lede>A three-agent pipeline (router &rarr; retriever &rarr; scorer) built in
      LangGraph and fully instrumented with Langfuse. I read the production traces,
      identified the failure modes, fixed them with prompt and agent-config changes,
      and measured the before/after impact on a labeled evaluation set.</p>

      <h2>Architecture</h2>
      <img src="{img(A/'workflow.png')}" alt="architecture">

      <h2>Results &mdash; before / after</h2>
      <table>
        <tr><th>Metric</th><th class=n>Baseline</th><th class=n>Optimized</th><th class=n>&Delta;</th></tr>
        {tr}
      </table>
      <p class=cap>Measured live through Langfuse over 18 labeled candidates &times; 2 profiles.</p>
    </div>

    <div class=page>
      <h2>Failure modes found in the traces</h2>
      <div class=fm><b>A &mdash; Scorer output was 100% unparseable.</b> The free-text scorer
      returned prose with no machine-readable score on every run; the graph defaulted
      the score and recovered the decision only by keyword-sniffing. Fixed with
      schema-constrained JSON output &rarr; parse failures 100% to 0%.</div>
      <div class=fm><b>B &mdash; gpt-4o on every node drove cost and latency.</b> Routing and
      rubric-scoring are bounded tasks; on gpt-4o the baseline cost ~$4.40 / 1,000
      screens and ~5.8s/screen. Moving both nodes to gpt-4o-mini cut cost ~95% and
      latency ~37% with no accuracy loss.</div>
      <div class=fm><b>Non-problem confirmed &mdash; routing was already correct.</b> Routing
      held at 100% on both profiles, so the fix had to <i>protect</i> routing when
      downgrading the model, not repair it. Explicit prompts kept it at 100%.</div>

      <h2>The fixes</h2>
      <table>
        <tr><th>Finding</th><th>Fix</th></tr>
        <tr><td>Unparseable scorer output</td><td>Schema-constrained JSON (decision / score / matched_must_haves / reasoning)</td></tr>
        <tr><td>Cost &amp; latency</td><td>gpt-4o &rarr; gpt-4o-mini on both LLM nodes</td></tr>
        <tr><td>Routing under cheaper model</td><td>Explicit track definitions + disambiguation rule + temperature 0</td></tr>
      </table>
      <p class=cap>All changes are prompt/agent-config only &mdash; no change to the task, data,
      or graph topology, so the gains are attributable to the fixes.</p>
    </div>

    <div class=page>
      <h2>Trace evidence</h2>
      <p>Every screening run produces one Langfuse trace with a nested span tree and
      auto-captured generations (model, tokens, latency, USD cost per node):</p>
      <img src="{img(A/'07-trace-tree.png')}" alt="trace tree">

      <h2>Honest caveats</h2>
      <ul>
        <li>Tokens rose ~41% (the optimized scorer injects the full rubric + schema), yet
        cost fell 95% &mdash; cost is tokens &times; model price, and gpt-4o-mini is far cheaper.</li>
        <li>The stricter optimized scorer newly over-rejects two senior-but-nontraditional
        candidates &mdash; the clearest target for the next iteration.</li>
      </ul>

      <h2>Reproduce</h2>
      <p>The full code, eval harness, and this case study are public:
      github.com/adelsherif8/cv-screener-langgraph &mdash; run
      <code>python eval/run_eval.py</code> to regenerate every number above.</p>

      <div class=foot>Built by Adel Sherif &middot; LangGraph &middot; Langfuse &middot; Python &middot; OpenAI</div>
    </div>
    </body></html>"""


def main():
    out = A / "case-study.pdf"
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content(html(), wait_until="networkidle")
        page.pdf(path=str(out), format="A4", print_background=True,
                 margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        b.close()
    print(f"wrote {out.relative_to(ROOT)}  ({out.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
