"""Re-frame every gallery graphic onto a uniform 4:3 canvas with padding.

Upwork's gallery crop frame is ~4:3, so wide images get their edges cut off.
This composites each source graphic, scaled to fit, centered on a 4:3 brand
canvas — so nothing important sits near an edge and the crop captures it all.

Output: upwork/01..07 (the files you actually upload). Sources stay in assets/.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "assets"
U = ROOT / "upwork"

BG = (11, 16, 32)          # #0b1020 brand background
CANVAS = (2560, 1920)      # 4:3, < 4000px
PAD = 0.94                 # content fills 94% of each axis at most

# source (in assets/) -> output gallery filename (in display order).
# 01-cover.png is left untouched: it's already 4:3 full-bleed and fits the
# crop frame exactly.
ITEMS = [
    ("workflow.png", "02-architecture.png"),
    ("demo-optimized.png", "03-live-demo.png"),
    ("07-trace-tree.png", "04-trace-tree.png"),
    ("metrics.png", "05-results.png"),
    ("05-comparison.png", "06-comparison.png"),
    ("06-code.png", "07-code.png"),
]


def reframe(src: Path, dst: Path):
    im = Image.open(src).convert("RGBA")
    canvas = Image.new("RGBA", CANVAS, BG + (255,))
    max_w, max_h = int(CANVAS[0] * PAD), int(CANVAS[1] * PAD)
    scale = min(max_w / im.width, max_h / im.height)
    # never upscale tiny sources past 1x beyond a sensible cap
    scale = min(scale, 2.2)
    new = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS)
    x = (CANVAS[0] - new.width) // 2
    y = (CANVAS[1] - new.height) // 2
    canvas.paste(new, (x, y), new)
    canvas.convert("RGB").save(dst, "PNG")
    print(f"  {dst.name:24} {CANVAS[0]}x{CANVAS[1]}  ({dst.stat().st_size/1e6:.2f}MB)")


def main():
    # clear old numbered gallery pngs (02-07) but keep 01-cover.png untouched
    for f in U.glob("0[2-7]-*.png"):
        f.unlink()
    print("re-framing to 4:3:")
    for src_name, out_name in ITEMS:
        src = (A / src_name).resolve()
        if not src.exists():
            print(f"  skip {out_name}: missing {src}")
            continue
        reframe(src, U / out_name)


if __name__ == "__main__":
    main()
