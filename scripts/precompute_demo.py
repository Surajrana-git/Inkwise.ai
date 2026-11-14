"""Pre-compute AI reviews for the demo samples (run on a machine with internet + GEMINI_API_KEY).

    python scripts/precompute_demo.py

Writes data/demo_reviews.json. The app serves these stored results for the exact sample
texts, so the judges' most likely first clicks cost no Gemini quota and work even when the
free tier is exhausted. Any other text is reviewed live as usual. Re-run after changing the
prompt or the brand kit; the file records the model and date it was produced with.
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

from engine.review import review_text  # noqa: E402

SAMPLES = ROOT / "data" / "demo_samples.json"
OUT = ROOT / "data" / "demo_reviews.json"


def key(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode()).hexdigest()


def main() -> None:
    samples = json.loads(SAMPLES.read_text(encoding="utf-8"))
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    for s in samples:
        for attempt in range(3):
            r = review_text(s["text"])
            if r.model:
                break
            print(f"{s['id']}: AI unavailable ({r.ai_error}); retrying in 20 s")
            time.sleep(20)
        if not r.model:
            print(f"{s['id']}: skipped, AI did not answer")
            continue
        out[key(s["text"])] = {
            "sample_id": s["id"], "model": r.model,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "findings": [f.model_dump(mode="json") for f in r.findings],
        }
        print(f"{s['id']}: {len(r.findings)} findings ({r.model})")
        time.sleep(5)
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(out)} samples)")


if __name__ == "__main__":
    main()
