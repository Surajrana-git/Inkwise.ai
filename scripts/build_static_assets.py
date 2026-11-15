"""Build app/static/: images served as files (enableStaticServing) instead of base64 inside CSS.

Inline base64 made the page styles 200+ KB, so Streamlit showed the unstyled default page for a
second before the design appeared. Run again after changing a background or the logo:
    python scripts/build_static_assets.py
"""
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "static"


def contours_png(path: Path, stroke: str, scale: float, w: int = 1400, h: int = 1000, ss: int = 2) -> None:
    """Same deterministic contour lines as theme._contours_svg, as a transparent PNG (antialiased)."""
    rgb = tuple(int(stroke.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    img = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    for cx, cy, sc in [(260, 260, 1.0), (1080, 760, 1.25), (900, 160, .8)]:
        for k in range(1, 15):
            r = k * 34 * sc
            pts = []
            for i in range(0, 361, 6):
                a = math.radians(i)
                wob = 1 + .12 * math.sin(3 * a + k * .45) + .07 * math.cos(5 * a - k * .3)
                pts.append(((cx + r * wob * math.cos(a)) * ss, (cy + r * .78 * wob * math.sin(a)) * ss))
            op = (.16 if k % 5 == 0 else .07) * scale
            layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer).line(pts, fill=rgb + (int(255 * op),), width=ss, joint="curve")
            img = Image.alpha_composite(img, layer)
    img.resize((w, h), Image.LANCZOS).save(path, "WEBP", lossless=True, method=6)   # ~70 KB


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("login_bg_desk.jpg", "login_bg_ink.jpg", "logo_icon.png"):
        src = ROOT / "app" / "assets" / name
        if src.exists():
            shutil.copyfile(src, OUT / name)
    for logo in (ROOT / "app" / "inkwise_logo.jpeg", ROOT / "assets" / "inkwise_logo.jpeg", ROOT / "inkwise_logo.jpeg"):
        if logo.exists():
            shutil.copyfile(logo, OUT / "inkwise_logo.jpeg")
            break
    contours_png(OUT / "contours_login.webp", "#9FB4D6", 1.0)
    contours_png(OUT / "contours_inner.webp", "#1B2A4E", .55)
    for p in sorted(OUT.iterdir()):
        print(f"{p.name:24s} {p.stat().st_size / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
