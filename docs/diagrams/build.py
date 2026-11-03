"""Embed Lake's local OFL font and render the hand-drawn SVG diagrams at 2×."""
from __future__ import annotations

import base64
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FONT = ROOT / "lake/static/fonts/dm-sans.woff2"
PAPER, INK, TEAL, SURFACE, MUTED = "#f7f4eb", "#26332f", "#146b60", "#ebe6d9", "#68716b"


def main() -> None:
    if not FONT.is_file():
        raise SystemExit(f"Local OFL font not found: {FONT}")
    font = base64.b64encode(FONT.read_bytes()).decode("ascii")
    font_css = ("<style>@font-face{font-family:LakeSans;src:url(data:font/woff2;base64," +
                font + ") format('woff2');font-weight:100 900}</style>")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        for source in sorted((HERE / "src").glob("*.svg")):
            raw = source.read_text(encoding="utf-8")
            match = __import__("re").search(r'viewBox="[\d.]+ [\d.]+ ([\d.]+) ([\d.]+)"', raw)
            if not match:
                raise SystemExit(f"Missing viewBox on {source}")
            width, height = int(float(match.group(1))), int(float(match.group(2)))
            for theme, colors in {
                "light": {"paper": PAPER, "ink": INK, "teal": TEAL, "surface": SURFACE, "muted": MUTED},
                "dark": {"paper": "#202722", "ink": "#f0eee7", "teal": "#71cabb", "surface": "#303a34", "muted": "#b5c0b8"},
            }.items():
                svg = raw
                for token, value in colors.items():
                    svg = svg.replace("{{" + token + "}}", value)
                opening_end = svg.index(">") + 1
                svg = svg[:opening_end] + font_css + svg[opening_end:]
                output = HERE / f"{source.stem}-{theme}.svg"
                output.write_text(svg, encoding="utf-8")
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=2)
                page.set_content(f'<!doctype html><style>html,body{{margin:0;padding:0}}img{{display:block;width:{width}px;height:{height}px}}</style><img id="diagram" src="data:image/svg+xml;base64,'+
                                base64.b64encode(svg.encode()).decode()+'">', wait_until="load")
                page.locator("#diagram").evaluate("img => img.decode()")
                page.screenshot(path=str(output.with_suffix(".png")), full_page=True)
                page.close()
                png_path = output.with_suffix(".png")
                image = Image.open(png_path).convert("RGB")
                image.save(png_path, format="PNG", optimize=True)
                print(f"{output.relative_to(ROOT)} · {png_path.stat().st_size:,} bytes")
        browser.close()


if __name__ == "__main__":
    main()
