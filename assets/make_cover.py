"""Generate an Upwork portfolio cover/thumbnail (4:3, branded, stat-forward)."""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "upwork"
FA = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">'
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def node(icon, label, tag, color):
    return f"""<div class=n><div class=ni><i class="fa-solid {icon}"></i></div>
      <div class=nl>{label}</div><div class=nt style="color:{color}">{tag}</div></div>"""


def stat(n, l):
    return f'<div class=st><div class=stn>{n}</div><div class=stl>{l}</div></div>'


HTML = f"""<!doctype html><html><head><meta charset=utf-8>{FA}<style>
*{{box-sizing:border-box;margin:0;font-family:{FONT}}}
body{{margin:0}}
.cover{{width:1280px;height:960px;background:radial-gradient(1200px 600px at 50% -10%,#1a2348,#0b1020);
  padding:70px 74px;display:flex;flex-direction:column;justify-content:space-between}}
.top .kick{{display:inline-flex;gap:9px;align-items:center;background:#161d36;border:1px solid #2b3358;
  color:#aeb6dd;border-radius:999px;padding:8px 16px;font-size:16px;font-weight:600}}
.kick i{{color:#7c83ff}}
h1{{color:#fff;font-size:62px;line-height:1.08;letter-spacing:-1.5px;margin:26px 0 0}}
h1 .ac{{color:#8b92ff}}
.sub{{color:#9aa2c8;font-size:23px;margin-top:16px;max-width:920px}}
.flow{{display:flex;align-items:center;gap:14px;margin:8px 0}}
.n{{background:#141b33;border:1px solid #2b3358;border-radius:16px;padding:18px 10px;width:172px;text-align:center}}
.ni{{font-size:26px;color:#9aa2ff}}
.nl{{color:#fff;font-weight:700;font-size:18px;margin-top:8px}}
.nt{{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;margin-top:6px}}
.ar{{color:#4a5388;font-size:24px}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}
.st{{background:#141b33;border:1px solid #2b3358;border-radius:16px;padding:22px;text-align:center}}
.stn{{font-size:40px;font-weight:800;color:#34d399;letter-spacing:-1px}}
.stl{{color:#9aa2c8;font-size:15px;margin-top:6px}}
.foot{{display:flex;align-items:center;gap:12px;color:#aeb6dd;font-size:18px}}
.foot .stack{{display:flex;gap:10px;margin-left:auto}}
.chip{{background:#161d36;border:1px solid #2b3358;border-radius:999px;padding:7px 15px;font-size:15px;color:#cfd5f5}}
</style></head><body>
<div class=cover>
  <div class=top>
    <span class=kick><i class="fa-solid fa-diagram-project"></i> LLM Agents &middot; Observability &middot; Optimization</span>
    <h1>Multi-Agent CV Screener<br><span class=ac>traced &amp; optimized end-to-end</span></h1>
    <div class=sub>A LangGraph router &rarr; retriever &rarr; scorer pipeline, instrumented with Langfuse &mdash; failure modes found in the traces, then fixed.</div>
  </div>

  <div class=flow>
    {node('fa-signs-post','Router','agent','#8b92ff')}
    <div class=ar><i class="fa-solid fa-arrow-right-long"></i></div>
    {node('fa-magnifying-glass','Retriever','retriever','#34d399')}
    <div class=ar><i class="fa-solid fa-arrow-right-long"></i></div>
    {node('fa-clipboard-check','Scorer','agent','#8b92ff')}
    <div class=ar><i class="fa-solid fa-arrow-right-long"></i></div>
    {node('fa-circle-check','Decision','advance / reject','#aeb6dd')}
  </div>

  <div class=stats>
    {stat('+7%','decision accuracy')}
    {stat('&minus;37%','latency / screen')}
    {stat('&minus;95%','cost / 1k screens')}
    {stat('100&rarr;0%','parse failures')}
  </div>

  <div class=foot>
    <i class="fa-solid fa-chart-line" style="color:#7c83ff"></i> Measured live via Langfuse
    <div class=stack>
      <span class=chip>LangGraph</span><span class=chip>Langfuse</span>
      <span class=chip>Python</span><span class=chip>OpenAI</span>
    </div>
  </div>
</div></body></html>"""


def main():
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1280, "height": 960}, device_scale_factor=2)
        page = ctx.new_page()
        page.set_content(HTML, wait_until="networkidle")
        page.wait_for_timeout(500)
        page.locator(".cover").screenshot(path=str(OUT / "01-cover.png"))
        b.close()
    print("wrote upwork/01-cover.png")


if __name__ == "__main__":
    main()
