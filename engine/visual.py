"""Image checks that return the same Finding shape as the text review.
Owner: Riyana (Round 3, task 6).

review_image(image_bytes, kb) -> ReviewResult
  1. contrast     text-like regions below the WCAG AA ratio of 4.5:1   (Pillow, rule)
  2. brand colour dominant colours far from data/brand_kit/colours.json (Pillow, rule)
  3. logo         is the Lumora logo visible?                           (Gemini Vision)

These are heuristics, not a proof. A bad file, a huge file or a tiny image gives one clear
finding and never an exception. If the AI is not available the logo finding is UNVERIFIED.
"""
from __future__ import annotations

import colorsys
import io
import json
import logging
import os
import re
from collections import Counter
from pathlib import Path
from typing import Callable, Optional, Sequence

from PIL import Image

from engine import knowledge
from engine.review import _model_name  # same model setting as the text review
from engine.schemas import UNVERIFIED, Category, CheckedBy, Finding, ReviewResult

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PALETTE_FILE = ROOT / "data" / "brand_kit" / "colours.json"

MAX_BYTES = 5 * 1024 * 1024        # upload limit shown to the user
MAX_PIXELS = 50_000_000            # refuse decompression bombs
MIN_SIDE = 16                      # smaller than this cannot be judged
WCAG_AA = 4.5
TILE = 48                          # contrast is measured on 48 px tiles of a downscaled copy
BG_MIN_SHARE = 0.4                 # a text-like tile has one flat background colour
MIN_FAILING_TILES = 2              # ignore a single odd tile (an icon, a speck)
OFF_BRAND_DELTA_E = 25.0
MIN_COLOUR_SHARE = 0.08
VISION_TIMEOUT_MS = 30_000

RGB = tuple[int, int, int]
Vision = Callable[[bytes, str], str]   # (jpeg bytes, prompt) -> JSON text

LOGO_PROMPT = ('Look at this marketing image for the brand Lumora. Is the Lumora logo or the word "Lumora" '
               'as a logo clearly visible? Answer ONLY JSON: {"logo_present": true or false}')


# ---------------------------------------------------------------- colour maths

def _linear(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def luminance(rgb: RGB) -> float:
    r, g, b = rgb
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def contrast_ratio(a: RGB, b: RGB) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _lab(rgb: RGB) -> tuple[float, float, float]:
    r, g, b = (_linear(v) for v in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116  # noqa: E731
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: RGB, b: RGB) -> float:
    return sum((p - q) ** 2 for p, q in zip(_lab(a), _lab(b))) ** 0.5


def _hex(rgb: RGB) -> str:
    return "#%02x%02x%02x" % rgb


def load_palette(path: Path = PALETTE_FILE) -> list[RGB]:
    """Every #rrggbb code in colours.json (works whatever the file's layout is)."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    codes = dict.fromkeys(re.findall(r"#[0-9a-fA-F]{6}\b", raw))
    return [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in codes]  # type: ignore[misc]


def _as_rgb(c) -> RGB:
    if isinstance(c, str):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    return tuple(int(v) for v in c)  # type: ignore[return-value]


# ---------------------------------------------------------------- loading

def _problem(why: str, fix: str = "Upload a PNG or JPG smaller than 5 MB.") -> Finding:
    return Finding(id="", category=Category.MESSAGING, span="image: file", source_id=UNVERIFIED,
                   why=why, suggested_fix=fix, confidence=1.0, checked_by=CheckedBy.RULE)


def _load(image_bytes: bytes) -> tuple[Optional[Image.Image], Optional[Finding]]:
    if not image_bytes:
        return None, _problem("No image was uploaded.")
    if len(image_bytes) > MAX_BYTES:
        return None, _problem("This image is larger than 5 MB.")
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.width * img.height > MAX_PIXELS:
            return None, _problem("This image has too many pixels to check.")
        img.load()
    except Exception:  # not an image, truncated, or an unsupported format
        return None, _problem("This file could not be read as an image.")
    if min(img.size) < MIN_SIDE:
        return None, _problem("This image is too small to check.", "Upload a larger image.")
    rgba = img.convert("RGBA")
    flat = Image.new("RGB", rgba.size, (255, 255, 255))   # transparent areas count as white
    flat.paste(rgba, mask=rgba.split()[3])
    flat.thumbnail((640, 640))
    return flat, None


# ---------------------------------------------------------------- brand-kit lookup

def _guideline(kb, keywords: Sequence[str]) -> tuple[str, str, str]:
    """(source_id, source_text, evidence) for the first guideline that mentions a keyword."""
    for g in kb.guidelines:
        text = f"{g.title}. {g.rule}"
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if any(k in sentence.lower() for k in keywords):
                found = kb.get(g.id)
                return g.id, found.text if found else text, sentence.strip()
    return UNVERIFIED, "", ""


def _finding(kb, keywords, category, span, why, fix, conf, checked_by=CheckedBy.RULE) -> Finding:
    sid, source_text, evidence = _guideline(kb, keywords)
    return Finding(id="", category=category, span=span, source_id=sid, source_text=source_text,
                   why=why, suggested_fix=fix, confidence=conf if sid != UNVERIFIED else min(conf, 0.6),
                   checked_by=checked_by, evidence=evidence,
                   evidence_verified=bool(evidence and evidence in source_text))


# ---------------------------------------------------------------- 1. contrast

def _tiles(img: Image.Image):
    w, h = img.size
    for ty in range(0, h, TILE):
        for tx in range(0, w, TILE):
            box = (tx, ty, min(tx + TILE, w), min(ty + TILE, h))
            data = img.crop(box).tobytes()            # RGB bytes; avoids the deprecated getdata()
            yield box, list(zip(data[0::3], data[1::3], data[2::3]))


def _text_tile_ratio(pixels: list[RGB]) -> Optional[float]:
    """Contrast between the flat background and the strongest foreground colour, or None."""
    n = len(pixels)
    bucket, count = Counter((r >> 3, g >> 3, b >> 3) for r, g, b in pixels).most_common(1)[0]
    if count / n < BG_MIN_SHARE:
        return None                                    # photo, gradient or busy area
    near = [p for p in pixels if (p[0] >> 3, p[1] >> 3, p[2] >> 3) == bucket]
    bg = tuple(sum(c) // len(near) for c in zip(*near))
    dist = lambda p: sum(abs(a - b) for a, b in zip(p, bg))  # noqa: E731
    far = sorted((p for p in pixels if dist(p) >= 45), key=dist, reverse=True)
    if len(far) < 10 or len(far) / n > 0.45:
        return None                                    # nothing text-like in this tile
    core = far[: max(1, len(far) // 5)]                # most distinct 20%, skips anti-aliasing
    fg = tuple(sum(c) // len(core) for c in zip(*core))
    return contrast_ratio(bg, fg)  # type: ignore[arg-type]


def _where(box, size) -> str:
    cx, cy = (box[0] + box[2]) / 2 / size[0], (box[1] + box[3]) / 2 / size[1]
    v = "top" if cy < 1 / 3 else "middle" if cy < 2 / 3 else "bottom"
    h = "left" if cx < 1 / 3 else "centre" if cx < 2 / 3 else "right"
    return f"{v} {h}"


def check_contrast(img: Image.Image, kb) -> list[Finding]:
    bad = []
    for box, pixels in _tiles(img):
        ratio = _text_tile_ratio(pixels)
        if ratio is not None and ratio < WCAG_AA:
            bad.append((ratio, box))
    if len(bad) < MIN_FAILING_TILES:
        return []
    ratio, box = min(bad)
    where = _where(box, img.size)
    return [_finding(
        kb, ("contrast", "legib", "readab"), Category.ACCESSIBILITY,
        f"image: text at the {where}, ratio {ratio:.1f}:1",
        f"Text at the {where} of the image has a contrast ratio of {ratio:.1f}:1. WCAG AA needs at least "
        f"{WCAG_AA}:1. {len(bad)} regions are affected. This check is a heuristic.",
        "Use a darker text colour or a lighter background so the ratio is at least 4.5:1.", 0.75)]


# ---------------------------------------------------------------- 2. brand colours

def _dominant(img: Image.Image) -> list[tuple[RGB, float]]:
    small = img.copy()
    small.thumbnail((200, 200))
    q = small.quantize(colors=6, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = q.getcolors() or []
    total = sum(c for c, _ in counts) or 1
    return sorted(((tuple(pal[i * 3:i * 3 + 3]), c / total) for c, i in counts), key=lambda x: -x[1])  # type: ignore[misc]


def check_brand_colours(img: Image.Image, kb, palette: Optional[Sequence] = None) -> list[Finding]:
    colours = [_as_rgb(c) for c in palette] if palette is not None else load_palette()
    if not colours:
        log.info("No brand palette found, skipping the brand colour check")
        return []
    out = []
    for rgb, share in _dominant(img):
        r, g, b = (v / 255 for v in rgb)
        _, s, v = colorsys.rgb_to_hsv(r, g, b)
        if share < MIN_COLOUR_SHARE or s < 0.2 or v < 0.15:
            continue                                   # tiny areas, white, black and greys are always fine
        nearest = min(colours, key=lambda c: delta_e(rgb, c))
        de = delta_e(rgb, nearest)
        if de > OFF_BRAND_DELTA_E:
            out.append(_finding(
                kb, ("colour", "color", "palette"), Category.MESSAGING,
                f"image: dominant colour {_hex(rgb)} ({share:.0%} of the image)",
                f"{_hex(rgb)} covers {share:.0%} of the image and is not in the brand palette "
                f"(closest is {_hex(nearest)}, difference {de:.0f}).",
                "Use the brand palette: " + ", ".join(_hex(c) for c in colours[:4]) + ".", 0.65))
        if len(out) == 2:
            break
    return out


# ---------------------------------------------------------------- 3. logo (Gemini Vision)

def _jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _gemini_vision(jpeg: bytes, prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"],
                          http_options=types.HttpOptions(timeout=VISION_TIMEOUT_MS))
    resp = client.models.generate_content(
        model=_model_name(),
        contents=[types.Part.from_bytes(data=jpeg, mime_type="image/jpeg"), prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    return resp.text or ""


def check_logo(img: Image.Image, kb, vision: Optional[Vision] = None) -> tuple[list[Finding], bool]:
    """Return (findings, ai_answered)."""
    ask = vision or (_gemini_vision if os.getenv("GEMINI_API_KEY") else None)
    unavailable = _finding(
        kb, ("logo",), Category.MESSAGING, "image: logo",
        "The logo check needs the AI service, which was not available, so the logo could not be checked.",
        "Check by eye that the Lumora logo is visible.", 0.3, CheckedBy.AI)
    unavailable = unavailable.model_copy(update={"source_id": UNVERIFIED, "source_text": "",
                                                 "evidence": "", "evidence_verified": False})
    if ask is None:
        return [unavailable], False
    try:
        raw = re.sub(r"^```(?:json)?|```$", "", ask(_jpeg(img), LOGO_PROMPT).strip(), flags=re.M).strip()
        present = bool(json.loads(raw).get("logo_present"))
    except Exception as e:  # timeout, 429, bad JSON: say so, do not crash
        log.warning("Logo check failed: %s", e)
        return [unavailable], False
    if present:
        return [], True
    return [_finding(
        kb, ("logo",), Category.MESSAGING, "image: logo",
        "The AI could not see the Lumora logo in this image.",
        "Add the Lumora logo, clearly visible and not cropped.", 0.6, CheckedBy.AI)], True


# ---------------------------------------------------------------- public API

def review_image(image_bytes: bytes, kb: Optional[knowledge.KnowledgeBase] = None, *,
                 palette: Optional[Sequence] = None, vision: Optional[Vision] = None,
                 check_logo_with_ai: bool = True) -> ReviewResult:
    """Check one uploaded image. Never raises: a bad input becomes a single finding."""
    try:
        img, problem = _load(image_bytes)
        if problem:
            return _result([problem], "")
        kb = kb or knowledge.get_kb()
        findings = check_contrast(img, kb) + check_brand_colours(img, kb, palette)
        model = ""
        if check_logo_with_ai:
            logo, answered = check_logo(img, kb, vision)
            findings += logo
            if answered:
                model = _model_name() if vision is None else "injected-vision"
        return _result(findings, model)
    except Exception as e:  # last safety net for the live demo
        log.exception("Image review failed: %s", e)
        return _result([_problem("Something went wrong while checking this image.",
                                 "Try another image, or run the check again.")], "")


def _result(findings: list[Finding], model: str) -> ReviewResult:
    numbered = [f.model_copy(update={"id": f"f-{i:03d}"}) for i, f in enumerate(findings, 1)]
    return ReviewResult(text="(image)", findings=numbered, redactions=0, model=model)