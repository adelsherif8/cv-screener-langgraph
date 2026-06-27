"""Generate a second batch of portfolio assets.

  comparison.png      - baseline vs optimized, side by side (real numbers)
  trace-tree.png      - a Langfuse-style span tree rendered from REAL trace data
  code.png            - syntax-highlighted snapshot of the LangGraph definition
  demo-comparison.mp4 - app driven through baseline THEN optimized on one CV
  demo.gif            - shareable GIF of the demo

Each step is independent (try/except) so one failure won't block the rest.
Run: python assets/make_assets2.py
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
A = ROOT / "assets"
U = ROOT / "upwork"
load_dotenv(ROOT / ".env")

FA = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">'
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'SF Mono',ui-monospace,Menlo,Consolas,monospace"


def shoot(page, html, selector, out):
    page.set_content(html, wait_until="networkidle")
    page.wait_for_timeout(450)
    page.locator(selector).screenshot(path=str(out))
    print(f"  wrote {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------
# comparison.png
# --------------------------------------------------------------------------
def comparison_html():
    b = json.loads((ROOT / "eval/results/baseline.json").read_text())["summary"]
    o = json.loads((ROOT / "eval/results/optimized.json").read_text())["summary"]

    def col(title, sumy, model, tone, out_kind, out_text):
        head = "#dc2626" if tone == "bad" else "#16a34a"
        return f"""<div class=col>
          <div class=ch style="color:{head}"><i class="fa-solid {'fa-triangle-exclamation' if tone=='bad' else 'fa-circle-check'}"></i> {title}</div>
          <div class=cm>{model}</div>
          <div class=out style="border-color:{head}33">
            <div class=outk style="color:{head}">{out_kind}</div>
            <div class=outt>{out_text}</div>
          </div>
          <div class=mx>
            <div class=mrow><span>Parse failures</span><b>{sumy['parse_failure_rate']*100:.0f}%</b></div>
            <div class=mrow><span>Decision accuracy</span><b>{sumy['decision_accuracy']*100:.1f}%</b></div>
            <div class=mrow><span>Latency / screen</span><b>{sumy['mean_latency_s']:.2f}s</b></div>
            <div class=mrow><span>Cost / 1k screens</span><b>${sumy['cost_per_1k_screens_usd']:.2f}</b></div>
          </div>
        </div>"""

    return f"""<!doctype html><html><head><meta charset=utf-8>{FA}<style>
    *{{box-sizing:border-box;margin:0;font-family:{FONT}}}
    body{{background:#0b1020;padding:48px}}
    .wrap{{width:1180px}}
    h2{{color:#fff;font-size:27px;letter-spacing:-.5px}}
    .sub{{color:#9aa2c8;font-size:15px;margin:6px 0 24px}}
    .cols{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
    .col{{background:#141b33;border:1px solid #2b3358;border-radius:18px;padding:24px}}
    .ch{{font-size:18px;font-weight:800}}
    .cm{{color:#aeb6dd;font-size:13px;margin:4px 0 16px;font-family:{MONO}}}
    .out{{background:#0e1530;border:1px solid;border-radius:12px;padding:14px;min-height:128px}}
    .outk{{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;margin-bottom:8px}}
    .outt{{color:#cfd5f5;font-size:13px;font-family:{MONO};line-height:1.5;white-space:pre-wrap}}
    .mx{{margin-top:18px}}
    .mrow{{display:flex;justify-content:space-between;padding:9px 0;border-top:1px solid #232a44;font-size:14px;color:#9aa2c8}}
    .mrow b{{color:#fff;font-variant-numeric:tabular-nums}}
    </style></head><body><div class=wrap>
      <h2>Same pipeline, two profiles &mdash; what the traces exposed</h2>
      <div class=sub>The fix: gpt-4o &rarr; gpt-4o-mini and free-text &rarr; schema-constrained JSON. Numbers measured live in Langfuse.</div>
      <div class=cols>
        {col('Baseline','','model: gpt-4o &middot; temp 0.7','bad','Free-text output (unparseable)','&ldquo;Based on the provided job description,\\nhere is an assessment of the\\ncandidate&hellip;&rdquo;  &rarr; score defaulted', )}
        {col('Optimized','','model: gpt-4o-mini &middot; temp 0','good','Structured JSON output', '{{\\n  &quot;decision&quot;: &quot;advance&quot;,\\n  &quot;score&quot;: 85,\\n  &quot;matched_must_haves&quot;: [&hellip;]\\n}}')}
      </div>
    </div></body></html>""".replace("{col('Baseline','',", "{co('Baseline',").replace("{col('Optimized','',", "{co('Optimized',")  # noqa


# The replace hack above is brittle; build columns directly instead.
def comparison_html2():
    b = json.loads((ROOT / "eval/results/baseline.json").read_text())["summary"]
    o = json.loads((ROOT / "eval/results/optimized.json").read_text())["summary"]

    def col(title, sumy, model, tone, out_kind, out_text):
        head = "#dc2626" if tone == "bad" else "#16a34a"
        icon = "fa-triangle-exclamation" if tone == "bad" else "fa-circle-check"
        return f"""<div class=col>
          <div class=ch style="color:{head}"><i class="fa-solid {icon}"></i> {title}</div>
          <div class=cm>{model}</div>
          <div class=out style="border-color:{head}55">
            <div class=outk style="color:{head}">{out_kind}</div>
            <div class=outt>{out_text}</div>
          </div>
          <div class=mx>
            <div class=mrow><span>Parse failures</span><b>{sumy['parse_failure_rate']*100:.0f}%</b></div>
            <div class=mrow><span>Decision accuracy</span><b>{sumy['decision_accuracy']*100:.1f}%</b></div>
            <div class=mrow><span>Latency / screen</span><b>{sumy['mean_latency_s']:.2f}s</b></div>
            <div class=mrow><span>Cost / 1k screens</span><b>${sumy['cost_per_1k_screens_usd']:.2f}</b></div>
          </div>
        </div>"""

    base_out = ("&ldquo;Based on the provided job\n"
                "description, here is an\n"
                "assessment&hellip;&rdquo;\n\n&rarr; no parseable score")
    opt_out = ("{\n  &quot;decision&quot;: &quot;advance&quot;,\n"
               "  &quot;score&quot;: 85,\n"
               "  &quot;matched_must_haves&quot;: [&hellip;]\n}")
    return f"""<!doctype html><html><head><meta charset=utf-8>{FA}<style>
    *{{box-sizing:border-box;margin:0;font-family:{FONT}}}
    body{{background:#0b1020;padding:48px}}
    .wrap{{width:1180px}}
    h2{{color:#fff;font-size:27px;letter-spacing:-.5px}}
    .sub{{color:#9aa2c8;font-size:15px;margin:6px 0 24px}}
    .cols{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}
    .col{{background:#141b33;border:1px solid #2b3358;border-radius:18px;padding:24px}}
    .ch{{font-size:19px;font-weight:800}}
    .cm{{color:#aeb6dd;font-size:13px;margin:4px 0 16px;font-family:{MONO}}}
    .out{{background:#0e1530;border:1px solid;border-radius:12px;padding:14px;min-height:150px}}
    .outk{{font-size:11px;font-weight:800;letter-spacing:.6px;text-transform:uppercase;margin-bottom:10px}}
    .outt{{color:#cfd5f5;font-size:13.5px;font-family:{MONO};line-height:1.55;white-space:pre-wrap}}
    .mx{{margin-top:18px}}
    .mrow{{display:flex;justify-content:space-between;padding:9px 0;border-top:1px solid #232a44;font-size:14px;color:#9aa2c8}}
    .mrow b{{color:#fff;font-variant-numeric:tabular-nums}}
    </style></head><body><div class=wrap>
      <h2>Same pipeline, two profiles &mdash; what the traces exposed</h2>
      <div class=sub>The fix: gpt-4o &rarr; gpt-4o-mini, free-text &rarr; schema-constrained JSON. Measured live in Langfuse.</div>
      <div class=cols>
        {col('Baseline', b, 'model: gpt-4o &middot; temp 0.7', 'bad', 'Free-text output (unparseable)', base_out)}
        {col('Optimized', o, 'model: gpt-4o-mini &middot; temp 0', 'good', 'Structured JSON output', opt_out)}
      </div>
    </div></body></html>"""


# --------------------------------------------------------------------------
# trace-tree.png  (rendered from REAL Langfuse trace data via the API)
# --------------------------------------------------------------------------
def fetch_trace(tag):
    host = os.environ["LANGFUSE_HOST"].rstrip("/")
    auth = base64.b64encode(
        f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()
    ).decode()
    hdr = {"Authorization": f"Basic {auth}"}

    def get(path):
        req = urllib.request.Request(host + path, headers=hdr)
        return json.loads(urllib.request.urlopen(req, timeout=20).read())

    t = get(f"/api/public/traces?limit=1&tags={tag}")["data"][0]
    obs = get(f"/api/public/observations?traceId={t['id']}&limit=50")["data"]
    obs.sort(key=lambda o: o.get("startTime", ""))
    return t, obs


def trace_tree_html():
    t, obs = fetch_trace("profile:optimized")
    icons = {"AGENT": "fa-robot", "RETRIEVER": "fa-magnifying-glass",
             "GENERATION": "fa-wand-magic-sparkles", "EMBEDDING": "fa-vector-square",
             "SPAN": "fa-diagram-project"}
    colors = {"AGENT": "#8b92ff", "RETRIEVER": "#34d399", "GENERATION": "#f59e0b",
              "EMBEDDING": "#22d3ee", "SPAN": "#9aa2c8"}
    rows = ""
    for o in obs:
        ty = o["type"]
        depth = 0 if ty == "SPAN" else (2 if ty in ("GENERATION", "EMBEDDING") else 1)
        usage = o.get("usage") or {}
        cost = o.get("calculatedTotalCost") or o.get("totalCost") or 0
        model = o.get("model") or ""
        toks = f"{usage.get('input','')}&rarr;{usage.get('output','')} tok" if model else ""
        meta = f"<span class=tm>{model} &middot; {toks}</span>" if model else ""
        costs = f"<span class=tc>${cost:.5f}</span>" if cost else ""
        rows += f"""<div class=trow style="padding-left:{depth*28}px">
          <span class=tb style="background:{colors[ty]}1a;color:{colors[ty]}"><i class="fa-solid {icons[ty]}"></i> {ty.lower()}</span>
          <span class=tn>{o['name']}</span>{meta}<span class=sp></span>{costs}
        </div>"""

    total_cost = t.get("totalCost") or 0
    lat = t.get("latency") or 0
    return f"""<!doctype html><html><head><meta charset=utf-8>{FA}<style>
    *{{box-sizing:border-box;margin:0;font-family:{FONT}}}
    body{{background:#0b1020;padding:46px}}
    .card{{width:920px;background:#0f1530;border:1px solid #2b3358;border-radius:18px;overflow:hidden}}
    .hd{{padding:20px 24px;border-bottom:1px solid #232a44;display:flex;align-items:center;gap:12px}}
    .hd .lf{{color:#7c83ff;font-size:20px}}
    .hd .nm{{color:#fff;font-weight:700;font-size:16px;font-family:{MONO}}}
    .hd .pill{{margin-left:auto;display:flex;gap:8px}}
    .pill span{{background:#161d36;border:1px solid #2b3358;border-radius:999px;padding:5px 12px;font-size:12.5px;color:#cfd5f5;font-variant-numeric:tabular-nums}}
    .body{{padding:12px 18px 18px}}
    .trow{{display:flex;align-items:center;gap:10px;padding:10px 6px;border-bottom:1px solid #1a2140}}
    .tb{{font-size:11px;font-weight:700;border-radius:7px;padding:3px 9px;white-space:nowrap}}
    .tn{{color:#e7ebff;font-size:14px;font-family:{MONO}}}
    .tm{{color:#8b93b7;font-size:12.5px;font-family:{MONO}}}
    .sp{{flex:1}}
    .tc{{color:#34d399;font-size:13px;font-weight:700;font-variant-numeric:tabular-nums}}
    .ft{{padding:14px 24px;color:#6b73a0;font-size:12px;border-top:1px solid #232a44}}
    </style></head><body>
    <div class=card>
      <div class=hd><i class="fa-solid fa-chart-line lf"></i>
        <span class=nm>{t['name']}</span>
        <span class=pill><span>{lat:.2f}s</span><span>${total_cost:.5f}</span></span>
      </div>
      <div class=body>{rows}</div>
      <div class=ft><i class="fa-solid fa-circle-info"></i> Real Langfuse trace &mdash; one screening run, three nested spans + auto-captured generations.</div>
    </div></body></html>"""


# --------------------------------------------------------------------------
# code.png  (syntax-highlighted LangGraph definition)
# --------------------------------------------------------------------------
def code_html():
    snippet = '''from langgraph.graph import StateGraph, START, END
from langfuse import observe, propagate_attributes

def build_graph(profile: str):
    g = StateGraph(ScreenState)
    g.add_node("router", router_node)        # @observe(as_type="agent")
    g.add_node("retriever", retriever_node)  # @observe(as_type="retriever")
    g.add_node("scorer", scorer_node)        # @observe(as_type="agent")
    g.add_edge(START, "router")
    g.add_edge("router", "retriever")
    g.add_edge("retriever", "scorer")
    g.add_edge("scorer", END)
    return g.compile()

@observe(name="cv-screen")
def run_screen(cv_text: str, profile: str = "optimized"):
    with propagate_attributes(trace_name=f"cv-screen[{profile}]",
                              tags=[f"profile:{profile}"]):
        return build_graph(profile).invoke({"cv_text": cv_text,
                                            "profile": profile, "usages": []})'''
    esc = (snippet.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f"""<!doctype html><html><head><meta charset=utf-8>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/atom-one-dark.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
    <style>
    *{{box-sizing:border-box;margin:0}}
    body{{background:#0b1020;padding:44px;font-family:{FONT}}}
    .win{{width:860px;background:#0e1426;border:1px solid #2b3358;border-radius:14px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.4)}}
    .bar{{background:#141b33;padding:13px 16px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #232a44}}
    .dot{{width:12px;height:12px;border-radius:50%}}
    .t{{color:#8b93b7;font-size:13px;font-family:{MONO};margin-left:10px}}
    pre{{margin:0}}
    code{{font-family:{MONO};font-size:14px;line-height:1.65;padding:22px!important;background:transparent!important;display:block}}
    </style></head><body>
    <div class=win>
      <div class=bar>
        <span class=dot style="background:#ff5f57"></span>
        <span class=dot style="background:#febc2e"></span>
        <span class=dot style="background:#28c840"></span>
        <span class=t>src/graph.py</span>
      </div>
      <pre><code class="language-python">{esc}</code></pre>
    </div>
    <script>hljs.highlightAll();</script></body></html>"""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    import app as gradio_app

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1300, "height": 1000}, device_scale_factor=2)
        page = ctx.new_page()

        print("static assets:")
        for fn, sel, name in [
            (comparison_html2, ".wrap", "05-comparison.png"),
            (code_html, ".win", "06-code.png"),
        ]:
            try:
                shoot(page, fn(), sel, A / name)
            except Exception as e:
                print(f"  skip {name}: {e}")

        try:
            shoot(page, trace_tree_html(), ".card", A / "07-trace-tree.png")
        except Exception as e:
            print(f"  skip trace-tree (needs live keys): {e}")
        ctx.close()

        # --- comparison video: baseline then optimized on the same CV ---
        print("comparison video:")
        gradio_app.demo.launch(head=gradio_app.HEAD, css=gradio_app.CSS,
                               prevent_thread_lock=True, server_port=7863, quiet=True)
        time.sleep(3)
        url = "http://127.0.0.1:7863"
        cv = ("Full-stack engineer, 4 yrs. React/TypeScript front end AND Node/Express + "
              "Postgres back end. Primary strength is server-side API and database design; "
              "UI is secondary.")
        try:
            ctx = browser.new_context(viewport={"width": 1280, "height": 880},
                                      record_video_dir=str(A / "_vid2"),
                                      record_video_size={"width": 1280, "height": 880})
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1000)
            page.locator("textarea").first.fill(cv)
            for prof in ("baseline", "optimized"):
                page.get_by_test_id(f"{prof}-radio-label").click()
                page.wait_for_timeout(400)
                page.get_by_role("button", name="Screen candidate").click()
                page.wait_for_selector(".gp-badge", timeout=40000)
                page.wait_for_timeout(2600)
            vp = page.video.path()
            ctx.close()
            (A / "demo-comparison.webm").write_bytes(Path(vp).read_bytes())
            Path(vp).unlink(missing_ok=True)
            subprocess.run(["ffmpeg", "-y", "-i", str(A / "demo-comparison.webm"),
                            "-vf", "scale=1280:-2,format=yuv420p", "-movflags", "+faststart",
                            str(A / "demo-comparison.mp4")], capture_output=True)
            print("  wrote assets/demo-comparison.mp4")
        except Exception as e:
            print(f"  skip comparison video: {e}")
        browser.close()
        gradio_app.demo.close()

    # --- gif from the original short demo ---
    print("gif:")
    src = A / "demo.mp4"
    if src.exists():
        pal = A / "_pal.png"
        subprocess.run(["ffmpeg", "-y", "-i", str(src), "-vf",
                        "fps=12,scale=760:-1:flags=lanczos,palettegen", str(pal)], capture_output=True)
        r = subprocess.run(["ffmpeg", "-y", "-i", str(src), "-i", str(pal), "-lavfi",
                            "fps=12,scale=760:-1:flags=lanczos[x];[x][1:v]paletteuse",
                            str(A / "demo.gif")], capture_output=True)
        pal.unlink(missing_ok=True)
        print("  wrote assets/demo.gif" if r.returncode == 0 else f"  gif failed: {r.stderr[-200:]}")

    for d in (A / "_vid2",):
        try:
            d.rmdir()
        except OSError:
            pass

    # copy the new gallery images into upwork/
    for n in ["05-comparison.png", "06-code.png", "07-trace-tree.png"]:
        if (A / n).exists():
            (U / n).write_bytes((A / n).read_bytes())
    if (A / "demo-comparison.mp4").exists():
        (U / "demo-comparison.mp4").write_bytes((A / "demo-comparison.mp4").read_bytes())
    print("done.")


if __name__ == "__main__":
    main()
