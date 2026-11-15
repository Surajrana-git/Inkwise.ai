"""Image checks for a campaign creative (Round 3: Visual Brand Inspector).

Two kinds of check, both cited to the brand kit (data/brand_kit/visual.json):
  V01  brand colours     rule-based (Pillow + numpy): share of the image in colours outside the Lumora palette
  V02  readable text     rule-based contrast ratio (WCAG 2.1) between text and its background
Plus, when Gemini is reachable, the text printed on the image is read (with positions) so that
services.review_image() can run the normal copy checks (expired facts, glossary, claims) on it.

Without AI the colour check still runs, and contrast is estimated by finding text-like areas
(two flat colours, one a thin minority) in a tile grid. Every finding says how it was found.
"""
from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import numpy as np
from PIL import Image

from engine.schemas import CheckedBy, Category, Finding

log = logging.getLogger(__name__)
KIT_PATH = Path(__file__).resolve().parents[1] / "data" / "brand_kit" / "visual.json"
NEUTRAL_SAT = 0.16            # below this saturation a pixel counts as white / grey / black
OFF_BRAND_DIST = 70.0         # perceptual RGB distance from the nearest palette colour


def load_kit() -> dict:
    kit = json.loads(KIT_PATH.read_text(encoding="utf-8"))
    kit["rules_by_id"] = {r["id"]: r for r in kit["rules"]}
    return kit


def _hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*[int(round(c)) for c in rgb[:3]])


def _rgb(hexstr: str) -> np.ndarray:
    h = hexstr.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=float)


def _luminance(rgb) -> float:
    c = np.asarray(rgb, dtype=float) / 255.0
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def contrast_ratio(a, b) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _dist(px: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """'Redmean' colour distance: cheap and close to how people see differences."""
    rmean = (px[..., 0] + ref[0]) / 2
    d = px - ref
    return np.sqrt((2 + rmean / 256) * d[..., 0] ** 2 + 4 * d[..., 1] ** 2 + (2 + (255 - rmean) / 256) * d[..., 2] ** 2)


def _where(box) -> str:
    x = (box[0] + box[2]) / 2
    y = (box[1] + box[3]) / 2
    v = "top" if y < .34 else "bottom" if y > .66 else "middle"
    h = "left" if x < .34 else "right" if x > .66 else "centre"
    return "centre" if (v, h) == ("middle", "centre") else f"{v} {h}" if h != "centre" else v


def open_image(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    img.load()
    if img.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        img = img.convert("RGBA")
        bg.paste(img, mask=img.split()[-1])
        return bg
    return img.convert("RGB")


# ---------------------------------------------------------------- V01 brand colours

def check_colours(img: Image.Image, kit: dict) -> list[Finding]:
    """Quantise to a few colours; a colour block that is saturated, not near any palette colour and covers
    more than the allowed share is off-brand. Blended edge pixels form tiny blocks and are ignored."""
    rule = kit["rules_by_id"]["V01"]
    small = img.copy()
    small.thumbnail((320, 320))
    q = small.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
    idx = np.asarray(q)
    pal = np.array(q.getpalette()[:48], dtype=float).reshape(-1, 3)
    refs = [_rgb(c["hex"]) for c in kit["palette"]]
    bad = []
    for k in range(len(pal)):
        share = float((idx == k).mean())
        if share < 0.005:
            continue
        c = pal[k]
        sat = (c.max() - c.min()) / max(c.max(), 1)
        near = min(float(_dist(c[None, :], r)[0]) for r in refs)
        if c.max() > 48 and sat >= NEUTRAL_SAT and near > OFF_BRAND_DIST:     # near-black counts as neutral
            bad.append((k, share))
    total = sum(sh for _k, sh in bad)
    if total <= rule["max_off_brand_share"]:
        return []
    k_main = max(bad, key=lambda x: x[1])[0]
    mask = np.isin(idx, [k for k, _ in bad])
    ys, xs = np.nonzero(idx == k_main)
    h, w = idx.shape
    box = [round(xs.min() / w, 3), round(ys.min() / h, 3), round((xs.max() + 1) / w, 3), round((ys.max() + 1) / h, 3)]
    main = pal[k_main]
    primary = kit["palette"][0]          # Lumora Teal: the brand's accent for buttons and highlights
    others = len(bad) - 1
    return [Finding(
        id="v-colour", category=Category.VISUAL, span=f"{_hex(main)} colour ({float(mask.mean()):.0%} of the image)",
        source_id="V01", source_text=rule["rule"],
        why=f"{total:.0%} of the image uses colours outside the Lumora palette, mainly {_hex(main)} "
            f"({_where(box)}){f' and {others} more' if others else ''}. The limit is {rule['max_off_brand_share']:.0%}.",
        suggested_fix=f"Recolour it with {primary['name']} {primary['hex']} (the brand accent), or another "
                      f"Lumora palette colour.",
        confidence=1.0, checked_by=CheckedBy.RULE, where="image", box=box)]


# ---------------------------------------------------------------- V02 readable text

def _two_colours(region: np.ndarray):
    """Split a patch into its two main colours. Returns (major, minor, minor_share, mean_error)."""
    pts = region.reshape(-1, 3)
    if len(pts) < 16:
        return None
    lum = pts @ np.array([0.299, 0.587, 0.114])
    lo, hi = np.percentile(lum, 5), np.percentile(lum, 95)
    if hi - lo < 4:
        return None
    a, b = pts[lum <= lo + 2].mean(axis=0), pts[lum >= hi - 2].mean(axis=0)
    for _ in range(6):                                   # small 2-means
        da, db = np.linalg.norm(pts - a, axis=1), np.linalg.norm(pts - b, axis=1)
        m = da <= db
        if m.all() or (~m).all():
            return None
        a, b = pts[m].mean(axis=0), pts[~m].mean(axis=0)
    err = float(np.minimum(da, db).mean())
    share_a = float(m.mean())
    major, minor, minor_share = (a, b, 1 - share_a) if share_a >= .5 else (b, a, share_a)
    return major, minor, minor_share, err


def _contrast_finding(kit, n, ratio, fg, bg, box, span, how, conf) -> Finding:
    rule = kit["rules_by_id"]["V02"]
    return Finding(
        id=f"v-contrast-{n}", category=Category.ACCESSIBILITY, span=span, source_id="V02", source_text=rule["rule"],
        why=f"Text {_where(box)} has a contrast of {ratio:.1f}:1 ({_hex(fg)} on {_hex(bg)}); "
            f"the minimum is {rule['min_contrast']}:1. {how}",
        suggested_fix="Use white or Paper #F7F5F0 text on Navy/Teal, or Navy #1B2A4E text on a light background.",
        confidence=conf, checked_by=CheckedBy.RULE, where="image", box=[round(v, 3) for v in box])


def check_contrast_lines(img: Image.Image, lines: list[dict], kit: dict) -> list[Finding]:
    """Contrast inside each text line that Gemini located (box = fractions)."""
    need = kit["rules_by_id"]["V02"]["min_contrast"]
    px = np.asarray(img, dtype=float)
    H, W = px.shape[:2]
    out = []
    for ln in lines:
        x0, y0, x1, y1 = ln["box"]
        reg = px[int(y0 * H):max(int(y1 * H), int(y0 * H) + 2), int(x0 * W):max(int(x1 * W), int(x0 * W) + 2)]
        two = _two_colours(reg)
        if not two:
            continue
        bg, fg, _share, _err = two
        ratio = contrast_ratio(fg, bg)
        if ratio < need:
            out.append(_contrast_finding(kit, len(out) + 1, ratio, fg, bg, ln["box"], f"“{ln['text']}”",
                                         "Measured on the text line the AI located.", 0.95))
    return out


def _low_contrast_areas(px: np.ndarray, T: int, need: float) -> list[tuple]:
    """Text-like tiles of size T whose two colours fail the contrast rule, grouped into areas.
    Returns [(box, worst_ratio, fg, bg)] with box as fractions."""
    H, W = px.shape[:2]
    low = {}
    for ty in range(0, H - T + 1, T // 2):
        for tx in range(0, W - T + 1, T // 2):
            tile = px[ty:ty + T, tx:tx + T]
            two = _two_colours(tile)
            if not two:
                continue
            bg, fg, share, err = two
            ratio = contrast_ratio(fg, bg)
            if not (0.05 <= share <= 0.45 and err < 16 and 1.2 < ratio < need):
                continue
            minor = np.linalg.norm(tile - fg, axis=2) < np.linalg.norm(tile - bg, axis=2)
            rows = np.abs(np.diff(minor.astype(int), axis=1)).sum(axis=1)
            cols = np.abs(np.diff(minor.astype(int), axis=0)).sum(axis=0)
            busy_r, busy_c = rows[rows > 0], cols[cols > 0]
            # letters: several strokes across a row and down a column; a shape edge crosses once
            if len(busy_r) and len(busy_c) and busy_r.mean() >= 3 and busy_c.mean() >= 2:
                low[(ty, tx)] = (ratio, fg, bg)
    seen, areas = set(), []
    for k in low:
        if k in seen:
            continue
        stack, group = [k], []
        seen.add(k)
        while stack:
            cy, cx = stack.pop()
            group.append((cy, cx))
            for dy in (-T // 2, 0, T // 2):
                for dx in (-T // 2, 0, T // 2):
                    nb = (cy + dy, cx + dx)
                    if nb in low and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        areas.append(group)
    merged = True                       # words of one line come out as separate groups: join them
    while merged:
        merged = False
        for i in range(len(areas)):
            for j in range(i + 1, len(areas)):
                yi, yj = [p[0] for p in areas[i]], [p[0] for p in areas[j]]
                xi, xj = [p[1] for p in areas[i]], [p[1] for p in areas[j]]
                overlap = min(max(yi), max(yj)) - max(min(yi), min(yj))
                gap = max(min(xj) - max(xi), min(xi) - max(xj))
                if overlap >= 0 and gap <= 2 * T:
                    areas[i] += areas.pop(j)
                    merged = True
                    break
            if merged:
                break
    out = []
    for g in areas:
        if len(g) < 4:
            continue
        ys, xs = [p[0] for p in g], [p[1] for p in g]
        box = [min(xs) / W, min(ys) / H, (max(xs) + T) / W, (max(ys) + T) / H]
        worst = min((low[p] for p in g), key=lambda r: r[0])
        out.append((box, *worst))
    return out


def check_contrast_tiles(img: Image.Image, kit: dict) -> list[Finding]:
    """No AI: find text-like areas (two flat colours, one a thin stroked minority) at two tile sizes,
    so both small print and big headlines are seen, and measure their contrast."""
    need = kit["rules_by_id"]["V02"]["min_contrast"]
    small = img.copy()
    small.thumbnail((640, 640))
    px = np.asarray(small, dtype=float)
    base = max(16, min(px.shape[:2]) // 18)
    found = []
    for T in (base, base * 2):
        for area in _low_contrast_areas(px, T, need):
            box = area[0]
            dup = any(min(box[2], b[2]) > max(box[0], b[0]) and min(box[3], b[3]) > max(box[1], b[1]) for b, *_ in found)
            if not dup:
                found.append(area)
    found.sort(key=lambda a: (a[0][2] - a[0][0]) * (a[0][3] - a[0][1]), reverse=True)
    return [_contrast_finding(kit, n, ratio, fg, bg, box, f"Text area ({_where(box)})",
                              "Estimated without AI from the image itself.", 0.7)
            for n, (box, ratio, fg, bg) in enumerate(found[:4], 1)]


# ---------------------------------------------------------------- reading the text (Gemini)

READ_PROMPT = (
    "Read every piece of text printed in this marketing image. Return JSON only: "
    '{"lines": [{"text": "...", "box_2d": [ymin, xmin, ymax, xmax]}]} with box_2d on a 0-1000 scale. '
    "One entry per visual line, top to bottom. Copy the words exactly; do not fix spelling. "
    'If there is no text, return {"lines": []}.')


def read_text_raw(image_bytes: bytes, mime: str = "image/png") -> str:
    from google.genai import types
    from engine import review
    return review._gemini_generate(READ_PROMPT, contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime),
                                                           READ_PROMPT])


def read_text(image_bytes: bytes, mime: str = "image/png") -> list[dict]:
    """Text lines with boxes as fractions: [{"text", "box": [x0, y0, x1, y1]}]. Raises if Gemini fails."""
    return parse_lines(read_text_raw(image_bytes, mime))


def parse_lines(raw) -> list[dict]:
    """Accept the shapes models actually return: {"lines": [...]}, a bare list, another key name,
    'text'/'content'/'line' for the words and 'box_2d'/'box'/'bbox'/'bounding_box' for the position."""
    if isinstance(raw, (dict, list)):
        data = raw
    else:
        txt = (raw or "").strip()
        if txt.startswith("```"):
            txt = txt.split("\n", 1)[1] if "\n" in txt else ""
            txt = txt.rsplit("```", 1)[0]
        start = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0] or [0])
        try:
            data = json.JSONDecoder().raw_decode(txt[start:])[0] if txt else {}   # ignores text after the JSON
        except json.JSONDecodeError:
            data = {}
    if isinstance(data, dict):
        items = data.get("lines")
        if items is None:
            items = next((v for v in data.values() if isinstance(v, list)), [])
    else:
        items = data
    out = []
    for ln in items or []:
        if isinstance(ln, str):
            ln = {"text": ln}
        if not isinstance(ln, dict):
            continue
        t = str(ln.get("text") or ln.get("content") or ln.get("line") or "").strip()
        b = ln.get("box_2d") or ln.get("box") or ln.get("bbox") or ln.get("bounding_box")
        if not t:
            continue
        box = None
        if isinstance(b, dict):
            b = [b.get("ymin"), b.get("xmin"), b.get("ymax"), b.get("xmax")]
        if isinstance(b, (list, tuple)) and len(b) == 4 and all(isinstance(v, (int, float)) for v in b):
            scale = 1.0 if max(b) <= 1.0 else 1000.0
            y0, x0, y1, x1 = [min(max(float(v) / scale, 0), 1) for v in b]
            if x1 > x0 and y1 > y0:
                box = [x0, y0, x1, y1]
        out.append({"text": t, "box": box})
    return out


def join_lines(lines: list[dict]) -> str:
    """Rebuild sentences: a line that continues in lower case joins the previous one; a new capitalised
    line after one without end punctuation starts a new sentence."""
    out = ""
    for ln in lines:
        t = ln["text"].strip()
        if not out:
            out = t
        elif t[:1].islower() or out[-1:] in ",-–":
            out += " " + t
        else:
            out += ("" if out[-1:] in ".!?" else ".") + " " + t
    return out


# ---------------------------------------------------------------- entry point

def review_image(image_bytes: bytes, kb=None, mime: str = "image/png", lines: list[dict] | None = None,
                 use_ai: bool = True) -> dict:
    """Run the image checks. `lines` lets a caller pass a stored reading (demo) instead of calling Gemini.

    Returns {"findings": [Finding], "lines": [...], "text": str, "ai_error": str|None, "size": (w, h)}."""
    kit = load_kit()
    img = open_image(image_bytes)
    ai_error = None
    if lines is None and use_ai:
        try:
            lines = read_text(image_bytes, mime)
        except Exception as e:                       # no key, offline, quota: keep the rule checks
            log.warning("image text reading failed: %s", e)
            ai_error = f"Could not read the text in the image ({type(e).__name__}); colour and contrast were still checked."
            lines = None
    elif lines is None:
        ai_error = "AI is off, so the text in the image was not read; colour and contrast were still checked."
    findings = check_colours(img, kit)
    boxed = [ln for ln in (lines or []) if ln.get("box")]
    findings += check_contrast_lines(img, boxed, kit) if boxed else check_contrast_tiles(img, kit)
    text = join_lines(lines or [])
    return {"findings": findings, "lines": lines or [], "text": text, "ai_error": ai_error, "size": img.size}
