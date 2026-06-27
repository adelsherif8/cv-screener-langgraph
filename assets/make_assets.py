"""Generate portfolio visual assets with Playwright (no manual screenshots).

Produces, in assets/:
  workflow.png   - styled architecture/node-flow diagram
  metrics.png    - before/after results table (from real eval output)
  demo-optimized.png / demo-baseline.png - real Gradio app screenshots
  demo.webm + demo.mp4 - short screen recording of a screening run

Run: python assets/make_assets.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT))

FA = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">'
FONT = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif")

# --------------------------------------------------------------------------
# 1. Architecture / workflow diagram
# --------------------------------------------------------------------------
def workflow_html() -> str:
    def node(icon, title, sub, tag, tagcolor):
        return f"""
        <div class="node">
          <div class="ic"><i class="fa-solid {icon}"></i></div>
          <div class="tt">{title}</div>
          <div class="sb">{sub}</div>
          <div class="tag" style="background:{tagcolor}">{tag}</div>
        </div>"""

    arrow = '<div class="arrow"><i class="fa-solid fa-arrow-right-long"></i></div>'
    io = lambda icon, t: (f'<div class="io"><i class="fa-solid {icon}"></i><span>{t}</span></div>')

    return f"""<!doctype html><html><head><meta charset=utf-8>{FA}
    <style>
      *{{box-sizing:border-box;margin:0;font-family:{FONT}}}
      body{{background:#0b1020;padding:46px}}
      .wrap{{background:linear-gradient(160deg,#111830,#0b1020);border:1px solid #232a44;
        border-radius:22px;padding:40px 44px;width:1180px}}
      h1{{color:#fff;font-size:26px;margin-bottom:4px;letter-spacing:-.5px}}
      h1 .lf{{color:#7c83ff}}
      .sub{{color:#8b93b7;font-size:14px;margin-bottom:30px}}
      .flow{{display:flex;align-items:center;gap:6px;justify-content:space-between}}
      .io{{display:flex;flex-direction:column;align-items:center;gap:8px;color:#aeb6dd;
        font-size:13px;font-weight:600;width:96px}}
      .io i{{font-size:26px;color:#7c83ff}}
      .node{{background:#161d36;border:1px solid #2b3358;border-radius:16px;padding:18px 14px;
        width:182px;text-align:center;position:relative}}
      .node .ic{{font-size:24px;color:#9aa2ff;margin-bottom:8px}}
      .node .tt{{color:#fff;font-weight:700;font-size:16px}}
      .node .sb{{color:#8b93b7;font-size:12px;margin-top:4px;line-height:1.4}}
      .node .tag{{display:inline-block;margin-top:10px;color:#fff;font-size:10.5px;
        font-weight:700;letter-spacing:.4px;padding:3px 9px;border-radius:999px;text-transform:uppercase}}
      .arrow{{color:#4a5388;font-size:20px}}
      .trace{{margin-top:26px;border-top:1px dashed #2b3358;padding-top:16px;display:flex;
        align-items:center;gap:10px;color:#aeb6dd;font-size:13px}}
      .trace i{{color:#7c83ff}}
      .pill{{background:#1b2240;border:1px solid #2b3358;border-radius:999px;padding:4px 11px;
        font-size:12px;color:#cfd5f5;margin-left:auto}}
    </style></head><body>
    <div class="wrap">
      <h1>Multi-Agent CV Screener &nbsp;<span class="lf">&middot; LangGraph + Langfuse</span></h1>
      <div class="sub">A traced router &rarr; retriever &rarr; scorer pipeline. Every node is a Langfuse span; every model call a captured generation.</div>
      <div class="flow">
        {io('fa-file-lines','CV in')}
        {arrow}
        {node('fa-signs-post','Router','classify track<br>+ seniority','agent','#5b63d6')}
        {arrow}
        {node('fa-magnifying-glass','Retriever','embed CV, fetch<br>job rubric','retriever','#2f9e6b')}
        {arrow}
        {node('fa-clipboard-check','Scorer','score vs rubric<br>structured JSON','agent','#5b63d6')}
        {arrow}
        {io('fa-circle-check','advance / reject')}
      </div>
      <div class="trace">
        <i class="fa-solid fa-chart-line"></i>
        <b style="color:#fff">Langfuse trace</b>&nbsp;captures span tree, model, tokens, latency &amp; USD cost per node
        <span class="pill"><i class="fa-solid fa-tags"></i> tags: profile &middot; candidate</span>
      </div>
    </div></body></html>"""


# --------------------------------------------------------------------------
# 2. Metrics table
# --------------------------------------------------------------------------
def metrics_html() -> str:
    b = json.loads((ROOT / "eval/results/baseline.json").read_text())["summary"]
    o = json.loads((ROOT / "eval/results/optimized.json").read_text())["summary"]
    rows = [
        ("Decision accuracy", f"{b['decision_accuracy']*100:.1f}%", f"{o['decision_accuracy']*100:.1f}%", "+7%", True),
        ("Routing accuracy", f"{b['routing_accuracy']*100:.0f}%", f"{o['routing_accuracy']*100:.0f}%", "held", None),
        ("Scorer parse-failure", f"{b['parse_failure_rate']*100:.0f}%", f"{o['parse_failure_rate']*100:.0f}%", "-100%", True),
        ("Latency / screen", f"{b['mean_latency_s']:.2f}s", f"{o['mean_latency_s']:.2f}s", "-37%", True),
        ("Cost / 1,000 screens", f"${b['cost_per_1k_screens_usd']:.2f}", f"${o['cost_per_1k_screens_usd']:.2f}", "-95%", True),
    ]
    tr = ""
    for label, bv, ov, delta, good in rows:
        color = "#16a34a" if good else "#64748b"
        tr += f"""<tr><td class=lbl>{label}</td><td class=base>{bv}</td>
        <td class=opt>{ov}</td><td class=dl style="color:{color}">{delta}</td></tr>"""
    return f"""<!doctype html><html><head><meta charset=utf-8>{FA}
    <style>
      *{{box-sizing:border-box;margin:0;font-family:{FONT}}}
      body{{background:#0b1020;padding:46px}}
      .card{{background:#fff;border-radius:20px;padding:34px 38px;width:760px}}
      h2{{font-size:23px;color:#0f172a;letter-spacing:-.4px}}
      .s{{color:#64748b;font-size:13px;margin:6px 0 22px}}
      table{{width:100%;border-collapse:collapse}}
      th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.5px;
        color:#94a3b8;padding:0 0 12px}}
      th.r,td.base,td.opt,td.dl{{text-align:right}}
      td{{padding:13px 0;border-top:1px solid #eef2f7;font-size:15px;font-variant-numeric:tabular-nums}}
      td.lbl{{color:#334155;font-weight:600}}
      td.base{{color:#94a3b8}}
      td.opt{{color:#0f172a;font-weight:700}}
      td.dl{{font-weight:800}}
      .foot{{margin-top:18px;color:#94a3b8;font-size:12px;display:flex;gap:8px;align-items:center}}
      .foot i{{color:#6366f1}}
    </style></head><body>
    <div class=card>
      <h2>Trace-driven optimization &mdash; before / after</h2>
      <div class=s>Same LangGraph pipeline, two profiles. gpt-4o &rarr; gpt-4o-mini + structured outputs.</div>
      <table>
        <tr><th>Metric</th><th class=r>Baseline</th><th class=r>Optimized</th><th class=r>&Delta;</th></tr>
        {tr}
      </table>
      <div class=foot><i class="fa-solid fa-circle-check"></i> 18 labeled candidates &times; 2 profiles &middot; measured live via Langfuse</div>
    </div></body></html>"""


def shoot_html(page, html: str, selector: str, out: Path):
    page.set_content(html, wait_until="networkidle")
    page.wait_for_timeout(400)
    page.locator(selector).screenshot(path=str(out))
    print(f"  wrote {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    ASSETS.mkdir(exist_ok=True)
    import app as gradio_app  # noqa: E402  (launches nothing on import)

    gradio_app.demo.launch(head=gradio_app.HEAD, css=gradio_app.CSS,
                           prevent_thread_lock=True, server_port=7862, quiet=True)
    time.sleep(3)
    url = "http://127.0.0.1:7862"
    sample_cv = ("Full-stack engineer, 4 yrs. React/TypeScript front end AND Node/Express + "
                 "Postgres back end. Designed REST APIs, built dashboards, Docker + CI/CD. "
                 "Primary strength and most of my work is server-side API and database design; "
                 "UI is secondary.")

    with sync_playwright() as p:
        browser = p.chromium.launch()

        # --- static diagrams (high-DPI) ---
        ctx = browser.new_context(viewport={"width": 1300, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        print("diagrams:")
        shoot_html(page, workflow_html(), ".wrap", ASSETS / "workflow.png")
        shoot_html(page, metrics_html(), ".card", ASSETS / "metrics.png")
        ctx.close()

        # --- app screenshots ---
        ctx = browser.new_context(viewport={"width": 1320, "height": 1000}, device_scale_factor=2)
        page = ctx.new_page()
        print("app screenshots:")
        for profile in ("optimized", "baseline"):
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(800)
            page.locator("textarea").first.fill(sample_cv)
            page.get_by_test_id(f"{profile}-radio-label").click()
            page.get_by_role("button", name="Screen candidate").click()
            page.wait_for_selector(".gp-badge", timeout=40000)
            page.wait_for_timeout(700)
            out = ASSETS / f"demo-{profile}.png"
            page.screenshot(path=str(out), full_page=True)
            print(f"  wrote {out.relative_to(ROOT)}")
        ctx.close()

        # --- demo video ---
        print("recording video:")
        ctx = browser.new_context(viewport={"width": 1280, "height": 860}, device_scale_factor=1,
                                  record_video_dir=str(ASSETS / "_vid"),
                                  record_video_size={"width": 1280, "height": 860})
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1200)
        page.locator("textarea").first.click()
        page.locator("textarea").first.type(sample_cv, delay=12)
        page.wait_for_timeout(700)
        page.get_by_role("button", name="Screen candidate").click()
        page.wait_for_selector(".gp-badge", timeout=40000)
        page.wait_for_timeout(2500)
        video_path = page.video.path()
        ctx.close()
        browser.close()

    gradio_app.demo.close()

    # rename webm + transcode to mp4
    webm = ASSETS / "demo.webm"
    Path(video_path).replace(webm)
    print(f"  wrote {webm.relative_to(ROOT)}")
    mp4 = ASSETS / "demo.mp4"
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", str(webm), "-vf",
         "scale=1280:-2,format=yuv420p", "-movflags", "+faststart", str(mp4)],
        capture_output=True, text=True)
    print(f"  wrote {mp4.relative_to(ROOT)}" if r.returncode == 0 else f"  ffmpeg failed: {r.stderr[-300:]}")
    # cleanup empty vid dir
    try:
        (ASSETS / "_vid").rmdir()
    except OSError:
        pass


if __name__ == "__main__":
    main()
