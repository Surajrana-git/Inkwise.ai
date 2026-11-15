"""Image checks (Visual Brand Inspector): brand colours, readable text, and copy rules on text in the image."""
import io
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))
from engine import visual  # noqa: E402

BANNER = (ROOT / "app" / "assets" / "sample_banner.png").read_bytes()
W, H = 1200, 628
LINES = [  # where the sample banner's text actually is (fractions of width / height)
    {"text": "Lumora Pay", "box": [136 / W, 66 / H, 330 / W, 104 / H]},
    {"text": "Join 2 million happy", "box": [64 / W, 190 / H, 700 / W, 262 / H]},
    {"text": "users of LumoraPay!", "box": [64 / W, 262 / H, 700 / W, 334 / H]},
    {"text": "India's fastest payment app", "box": [64 / W, 360 / H, 560 / W, 404 / H]},
    {"text": "Sign up now", "box": [104 / W, 472 / H, 404 / W, 520 / H]},
]


def png(img) -> bytes:
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def on_brand_card() -> bytes:
    img = Image.new("RGB", (800, 420), "#1B2A4E")
    d = ImageDraw.Draw(img)
    d.rectangle((0, 330, 800, 420), fill="#12917F")
    try:
        f = ImageFont.truetype("DejaVuSans-Bold.ttf", 44)
    except OSError:
        f = ImageFont.load_default()
    d.text((40, 120), "Pay bills in one tap", font=f, fill="#FFFFFF")
    return png(img)


def test_contrast_ratio_matches_wcag():
    assert visual.contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21, rel=1e-3)
    assert visual.contrast_ratio((119, 119, 119), (255, 255, 255)) == pytest.approx(4.48, abs=0.02)


def test_banner_without_ai_finds_off_brand_colour_and_unreadable_text():
    r = visual.review_image(BANNER, use_ai=False)
    by = {f.source_id: f for f in r["findings"]}
    assert "AI is off" in r["ai_error"] and r["lines"] == []
    col = by["V01"]
    assert col.where == "image" and col.box[1] > .6 and "outside the Lumora palette" in col.why   # the orange button
    low = [f for f in r["findings"] if f.source_id == "V02"]
    assert low and all(f.confidence < 0.9 for f in low)                     # marked as an estimate
    assert any(.5 < f.box[1] < .7 for f in low)                             # the dim "fastest" line
    assert not any(f.box[3] < .55 and f.box[1] > .25 for f in low)          # white headline is fine


def test_banner_with_text_positions_measures_each_line():
    r = visual.review_image(BANNER, lines=LINES)
    flagged = {f.span for f in r["findings"] if f.source_id == "V02"}
    assert flagged == {"“India's fastest payment app”", "“Sign up now”"}
    assert r["text"] == "Lumora Pay. Join 2 million happy users of LumoraPay! India's fastest payment app. Sign up now"


@pytest.mark.parametrize("image", [on_brand_card(), (ROOT / "app/assets/login_bg_desk.jpg").read_bytes(),
                                   (ROOT / "app/assets/logo_icon.png").read_bytes()],
                         ids=["on-brand card", "photo", "logo"])
def test_clean_images_raise_no_false_alarms(image):
    assert visual.review_image(image, use_ai=False)["findings"] == []


def test_parse_lines_handles_boxes_and_junk():
    raw = '```json\n{"lines": [{"text": "Hi", "box_2d": [100, 50, 200, 450]}, {"text": ""}, {"text": "No box"}]}\n```'
    out = visual.parse_lines(raw)
    assert out[0] == {"text": "Hi", "box": [0.05, 0.1, 0.45, 0.2]} and out[1] == {"text": "No box", "box": None}
    assert visual.parse_lines('{"lines": []}') == []


def test_gemini_failure_keeps_rule_checks(monkeypatch):
    def boom(*a, **k):
        raise TimeoutError("offline")
    monkeypatch.setattr(visual, "read_text", boom)
    r = visual.review_image(BANNER, use_ai=True)
    assert "Could not read the image with AI" in r["ai_error"] and any(f.source_id == "V01" for f in r["findings"])


# ---------------------------------------------------------------- services: copy rules on the image's text

@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "v.sqlite3"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import services
    from engine import workflow
    workflow.init_db()
    services._started = False
    services._cache.clear()
    monkeypatch.setattr(services, "_stored_reading", lambda key: {"lines": LINES})
    return services


def test_text_in_the_image_gets_the_copy_checks(svc):
    r = svc.review_image(BANNER, "image/png")
    fs = r["findings"]
    assert all(f["where"] == "image" and f["id"].startswith("i-") for f in fs)
    ids = {f["source_id"] for f in fs}
    assert {"V01", "V02", "F01", "T01"} <= ids                      # colour, contrast, expired fact, banned term
    fact = next(f for f in fs if f["source_id"] == "F01")
    assert fact["box"] and fact["box"][1] < .35 < fact["box"][3]     # boxed around the headline lines
    assert r["stored"] and "2 million" in r["text"]


def test_bad_uploads_are_refused(svc):
    with pytest.raises(svc.InputError, match="not a PNG or JPEG"):
        svc.review_image(b"GIF89a....", "x.gif")
    with pytest.raises(svc.InputError, match="could not be read"):
        svc.review_image(b"\x89PNG broken", "x.png")
    with pytest.raises(svc.InputError, match="limit"):
        svc.review_image(b"\x89PNG" + b"0" * (6 * 1024 * 1024), "big.png")


def test_submission_keeps_its_image(svc):
    sid = svc.submit_for_approval("Banner", "[Image only] Join 2 million", [], "asha")
    svc.save_submission_image(sid, BANNER)
    assert svc.submission_image(sid) == BANNER and svc.submission_image("999") is None
    import theme
    out = theme.annotated_image(BANNER, [{"where": "image", "box": [.1, .1, .5, .3], "n": 1, "category": "visual",
                                           "status": "open"}])
    assert out.startswith(b"\x89PNG")


# ---------------------------------------------------------------- ported from Riyana's first version

def text_image(fg, bg=(255, 255, 255)) -> bytes:
    img = Image.new("RGB", (600, 300), bg)
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except OSError:
        f = ImageFont.load_default()
    for y in (60, 140, 220):
        d.text((30, y - 30), "Pay your bills in one tap", font=f, fill=fg)
    return png(img)


def test_high_contrast_text_passes():
    assert visual.review_image(text_image((0, 0, 0)), use_ai=False)["findings"] == []


def test_light_text_on_dark_background_passes():
    assert visual.review_image(text_image((255, 255, 255), bg=(20, 20, 20)), use_ai=False)["findings"] == []


def test_pale_grey_text_is_flagged_without_ai():
    fs = visual.review_image(text_image((200, 200, 200)), use_ai=False)["findings"]
    assert fs and {f.source_id for f in fs} == {"V02"} and all("contrast" in f.why for f in fs)


def test_missing_logo_is_reported_by_ai_and_present_logo_is_not():
    no_logo = visual.review_image(text_image((0, 0, 0)), reader=lambda b, m: {"lines": [], "logo_present": False})
    assert [(f.source_id, f.checked_by.value) for f in no_logo["findings"]] == [("V03", "ai")]
    yes = visual.review_image(text_image((0, 0, 0)), reader=lambda b, m: {"lines": [], "logo_present": True})
    assert yes["findings"] == []


def test_logo_answer_is_read_from_the_same_reply_as_the_text():
    raw = '```json\n{"lines": [{"text": "Hi", "box_2d": [1, 1, 50, 50]}], "logo_present": false}\n```'
    assert visual.parse_logo(raw) is False and visual.parse_logo('{"lines": []}') is None


@pytest.mark.parametrize("data, word", [(b"\x89PNG not really", "could not be read"),
                                        (png(Image.new("RGB", (8, 8), "white")), "too small")])
def test_bad_inputs_give_a_friendly_message(data, word):
    with pytest.raises(visual.ImageProblem, match=word):
        visual.review_image(data, use_ai=False)


def test_transparent_png_does_not_crash():
    img = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((20, 80), "Lumora Pay", fill=(0, 0, 0, 255))
    assert isinstance(visual.review_image(png(img), use_ai=False)["findings"], list)
