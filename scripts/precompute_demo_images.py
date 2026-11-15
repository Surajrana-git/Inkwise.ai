"""Store Gemini's reading of the demo banner, so the image demo works without a live AI call.

Run once from the project folder (needs GEMINI_API_KEY in .env):
    python scripts/precompute_demo_images.py
Writes data/demo_images.json, keyed by the sha256 of each image: the text lines Gemini read (with
positions) and the copy-check findings for that text. Like demo_reviews.json, these are real AI results
saved earlier; the colour and contrast checks still run live every time.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from engine import review, visual  # noqa: E402

IMAGES = [ROOT / "app" / "assets" / "sample_banner.png"]
OUT = ROOT / "data" / "demo_images.json"


def main() -> None:
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for p in IMAGES:
        data = p.read_bytes()
        k = hashlib.sha256(data).hexdigest()
        if k in out and "--force" not in sys.argv:
            print(f"{p.name}: already stored (use --force to redo)")
            continue
        lines = None
        for attempt in range(3):
            try:
                raw = visual.read_text_raw(data, "image/png")
                lines = visual.parse_lines(raw)
                if not lines:
                    print(f"{p.name}: Gemini's reply had no text lines. Raw reply:\n{raw[:1500]}")
                    lines = None
                break
            except Exception as e:
                print(f"{p.name}: reading failed ({type(e).__name__}: {str(e)[:120]}); retrying in 20 s")
                time.sleep(20)
        if lines is None:
            print(f"{p.name}: skipped, AI did not answer")
            continue
        text = visual.join_lines(lines)
        r = review.review_text(text) if text else None
        out[k] = {"image": p.name, "model": review._last_model,
                  "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "lines": lines, "text": text,
                  "text_findings": [f.model_dump(mode="json") for f in r.findings] if r and r.model else None}
        print(f"{p.name}: {len(lines)} lines read; {len(r.findings) if r else 0} copy findings "
              f"({'AI + rules' if r and r.model else 'rules only, will re-run live'})")
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(out)} images)")


if __name__ == "__main__":
    main()
