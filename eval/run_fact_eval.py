"""Fact-freshness test group (Round 3, Improvement 2): planted facts with their own recall.

Every case says which approved fact a text repeats (if any) and whether, on that day, the fact is
expired or expiring soon. Covers number formats (2M, 20 lakh, 0.5 crore, two million, 2,000,000),
rounded figures, every occurrence, expiring-soon, and negatives that must not be flagged.

Rules only, no AI, fixed dates: the result is the same on every machine.
    python eval/run_fact_eval.py            # prints and writes eval/fact_results.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import knowledge, rules  # noqa: E402

CASES = ROOT / "eval" / "fact_cases.jsonl"
OUT = ROOT / "eval" / "fact_results.md"


def run() -> dict:
    _g, facts, _t = knowledge.load_brand_kit()      # straight from data/brand_kit: no renewals, same on every run
    tp = fp = fn = 0
    rows, misses = [], []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        c = json.loads(line)
        today = date.fromisoformat(c["today"])
        got = Counter((f.source_id, f.freshness) for f in
                      rules.check_expired_facts(c["text"], facts, today) + rules.check_expiring_facts(c["text"], facts, today))
        want = Counter(tuple(x) for x in c["expect"])
        hit = sum((got & want).values())
        tp += hit
        fp += sum((got - want).values())
        fn += sum((want - got).values())
        ok = got == want
        rows.append((c["id"], ok, c["why"]))
        if not ok:
            misses.append(f"{c['id']}: expected {sorted(want.elements())}, got {sorted(got.elements())} | {c['text']}")
    n = len(rows)
    return {"cases": n, "passed": sum(ok for _, ok, _ in rows), "tp": tp, "fp": fp, "fn": fn,
            "recall": tp / (tp + fn) if tp + fn else 1.0, "precision": tp / (tp + fp) if tp + fp else 1.0,
            "rows": rows, "misses": misses}


def report(r: dict) -> str:
    lines = ["# Fact-freshness test group (rules only)", "",
             "Planted facts with their own recall. Source: `eval/fact_cases.jsonl`. "
             "Run: `python eval/run_fact_eval.py`.", "",
             f"- Cases passed: {r['passed']}/{r['cases']}",
             f"- Recall: {r['recall']:.1%} ({r['tp']}/{r['tp'] + r['fn']} planted fact mentions found)",
             f"- Precision: {r['precision']:.1%} ({r['tp']}/{r['tp'] + r['fp']} flags were right)", "",
             "| Case | Result | What it tests |", "|---|---|---|"]
    lines += [f"| {cid} | {'✅' if ok else '❌'} | {why} |" for cid, ok, why in r["rows"]]
    if r["misses"]:
        lines += ["", "## Misses", ""] + [f"- {m}" for m in r["misses"]]
    return "\n".join(lines) + "\n"


def main() -> None:
    r = run()
    text = report(r)
    print(text)
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
