import io
import json

import pytest
from PIL import Image, ImageDraw, ImageFont

from engine import visual
from engine.knowledge import KnowledgeBase
from engine.schemas import Category, Guideline

KB = KnowledgeBase(
    [Guideline(id="G16", title="Accessible contrast", rule="Text must meet a WCAG AA contrast of 4.5:1.",
               category=Category.ACCESSIBILITY),
     Guideline(id="G17", title="Use brand colours", rule="Use only the Lumora colour palette.",
               category=Category.MESSAGING),
     Guideline(id="G18", title="Show the logo", rule="Every image shows the Lumora logo.",
               category=Category.MESSAGING)],
    [], [])
BLUE = (0, 51, 153)
PALETTE = [BLUE, (255, 255, 255), (20, 20, 20)]


def png(draw_fn, size=(640, 320), bg=(255, 255, 255)):
    img = Image.new("RGB", size, bg)
    draw_fn(ImageDraw.Draw(img), img)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def text_image(fill, bg=(255, 255, 255)):
    font = ImageFont.load_default(size=64)

    def draw(d, img):
        d.text((30, 40), "SAVE MORE", fill=fill, font=font)
        d.text((30, 150), "WITH LUMORA", fill=fill, font=font)
    return png(draw, bg=bg)


def review(data, **kw):
    kw.setdefault("palette", PALETTE)
    kw.setdefault("vision", lambda jpeg, prompt: json.dumps({"logo_present": True}))
    return visual.review_image(data, KB, **kw)


def test_low_contrast_text_is_flagged_with_ratio_and_guideline():
    r = review(text_image((190, 190, 190)))
    f = next(x for x in r.findings if x.category == Category.ACCESSIBILITY)
    assert f.source_id == "G16" and f.evidence_verified and f.evidence in f.source_text
    assert f.span.startswith("image: text at the") and ":1" in f.span and f.checked_by.value == "rule"
    assert float(f.span.split("ratio ")[1].split(":")[0]) < 4.5


def test_high_contrast_text_passes():
    assert review(text_image((0, 0, 0))).findings == []


def test_light_text_on_dark_background_passes():
    assert review(text_image((255, 255, 255), bg=(20, 20, 20))).findings == []


def test_off_brand_colour_is_flagged_and_on_brand_is_not():
    red = png(lambda d, i: d.rectangle((0, 0, 640, 200), fill=(230, 30, 30)))
    f = review(red).findings
    assert len(f) == 1 and f[0].category == Category.MESSAGING and f[0].source_id == "G17"
    assert f[0].span.lower().startswith("image: dominant colour #e6")
    blue = png(lambda d, i: d.rectangle((0, 0, 640, 200), fill=BLUE))
    assert review(blue).findings == []


def test_clean_image_passes_all_checks():
    def draw(d, img):
        d.rectangle((0, 0, 640, 120), fill=BLUE)
        d.text((30, 160), "Send money in a few taps", fill=(0, 0, 0), font=ImageFont.load_default(size=40))
    r = review(png(draw))
    assert r.findings == [] and r.model == "injected-vision"


def test_missing_logo_is_reported_by_ai():
    r = review(text_image((0, 0, 0)), vision=lambda j, p: '```json\n{"logo_present": false}\n```')
    f = r.findings[0]
    assert f.span == "image: logo" and f.source_id == "G18" and f.checked_by.value == "ai"


def test_ai_unavailable_gives_unverified_logo_finding_not_a_crash():
    def boom(j, p):
        raise RuntimeError("503 UNAVAILABLE")
    for vision in (boom, lambda j, p: "not json"):
        r = review(text_image((0, 0, 0)), vision=vision)
        f = r.findings[0]
        assert f.source_id == "UNVERIFIED" and f.confidence <= 0.3 and r.model == ""


def test_no_key_and_no_vision_gives_unverified_logo_finding(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = visual.review_image(text_image((0, 0, 0)), KB, palette=PALETTE)
    assert [f.source_id for f in r.findings] == ["UNVERIFIED"] and r.findings[0].span == "image: logo"


@pytest.mark.parametrize("data, word", [
    (b"just some text renamed .png", "could not be read"),
    (b"", "No image"),
    (b"x" * (visual.MAX_BYTES + 1), "larger than 5 MB"),
    (png(lambda d, i: None, size=(1, 1)), "too small"),
])
def test_bad_inputs_give_one_friendly_finding(data, word):
    r = review(data)
    assert len(r.findings) == 1 and word in r.findings[0].why
    assert r.findings[0].suggested_fix and r.findings[0].id == "f-001"


def test_transparent_png_does_not_crash():
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    assert review(buf.getvalue()).findings == []


def test_palette_loader_reads_any_json_layout(tmp_path):
    f = tmp_path / "colours.json"
    f.write_text(json.dumps({"primary": "#003399", "pairs": [{"text": "#FFFFFF", "background": "#003399"}]}))
    assert visual.load_palette(f) == [(0, 51, 153), (255, 255, 255)]
    assert visual.load_palette(tmp_path / "missing.json") == []


def test_wcag_ratio_known_values():
    assert round(visual.contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert visual.contrast_ratio((119, 119, 119), (255, 255, 255)) > 4.4   # #777 on white is about 4.48