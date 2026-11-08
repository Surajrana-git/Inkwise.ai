"""Precision, recall and citation accuracy. Owner: Riyana (Step 11).

Run from the repo root:
  python eval/run_eval.py                 # dev set: for tuning, prints only
  python eval/run_eval.py --split test    # FROZEN test set: writes eval/results.md
  python eval/run_eval.py --rules-only    # no Gemini calls (no quota used)

A finding is matched to a labelled error when their spans overlap (case-insensitive).
Precision = matched findings / all findings.  Recall = matched errors / all errors.
Citation accuracy = matched findings whose source_id equals the label's rule_or_fact_id.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.review import review_text  # noqa: E402


def same_span(a: str, b: str) -> bool:
    a, b = a.lower().strip(), b.lower().strip()
    return bool(a) and bool(b) and (a in b or b in a)


def match(findings: list[dict], errors: list[dict]) -> list[tuple[dict, dict]]:
    """Greedy one-to-one matching of findings to labelled errors."""
    used, pairs = set(), []
    for f in findings:
        for i, e in enumerate(errors):
            if i not in used and same_span(f["span"], e["exact_span"]):
                used.add(i)
                pairs.append((f, e))
                break
    return pairs


def load(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def evaluate(samples: list[dict], use_ai: bool, sleep: float) -> dict:
    n_find = n_err = tp = cite_ok = clean_total = clean_flagged = 0
    wrong_cites: Counter = Counter()
    by_type: dict = defaultdict(lambda: [0, 0])  # type -> [found, total]
    for i, s in enumerate(samples, 1):
        result = review_text(s["text"], use_ai=use_ai)
        findings = [{"span": f.span, "source_id": f.source_id} for f in result.findings]
        errors = s.get("errors", [])
        pairs = match(findings, errors)
        n_find += len(findings)
        n_err += len(errors)
        tp += len(pairs)
        for f, e in pairs:
            by_type[e["type"]][0] += 1
            if f["source_id"] == e["rule_or_fact_id"]:
                cite_ok += 1
            else:
                wrong_cites[e["rule_or_fact_id"]] += 1
        for e in errors:
            by_type[e["type"]][1] += 1
        if s.get("is_clean"):
            clean_total += 1
            clean_flagged += bool(findings)
        print(f"[{i}/{len(samples)}] {s.get('id', '')}: findings={len(findings)} "
              f"errors={len(errors)} matched={len(pairs)}", flush=True)
        if use_ai and result.model:
            time.sleep(sleep)  # stay under the Gemini free-tier rate limit
    return dict(n=len(samples), n_find=n_find, n_err=n_err, tp=tp, cite_ok=cite_ok,
                clean_total=clean_total, clean_flagged=clean_flagged,
                wrong_cites=wrong_cites, by_type=dict(by_type))


def report(r: dict, label: str) -> str:
    p = r["tp"] / r["n_find"] if r["n_find"] else 0.0
    rc = r["tp"] / r["n_err"] if r["n_err"] else 0.0
    c = r["cite_ok"] / r["tp"] if r["tp"] else 0.0
    lines = [
        "# Evaluation results", "",
        f"- Set: {label} ({r['n']} samples)",
        f"- Precision: {p:.1%} ({r['tp']}/{r['n_find']} findings match a labelled error)",
        f"- Recall: {rc:.1%} ({r['tp']}/{r['n_err']} labelled errors found)",
        f"- Citation accuracy: {c:.1%} ({r['cite_ok']}/{r['tp']} matched findings cite the labelled source)",
    ]
    if r["clean_total"]:
        lines.append(f"- Clean samples wrongly flagged: {r['clean_flagged']}/{r['clean_total']}")
    lines += ["", "## Recall by error type"]
    for t, (found, total) in sorted(r["by_type"].items()):
        lines.append(f"- {t}: {found}/{total}")
    if r["wrong_cites"]:
        lines += ["", "Labelled sources most often cited wrongly: " +
                  ", ".join(f"{k} ({v})" for k, v in Counter(r["wrong_cites"]).most_common(5))]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=4.0, help="seconds between Gemini calls")
    a = ap.parse_args()

    samples = load(ROOT / "eval" / f"{a.split}.jsonl")[: a.limit]
    r = evaluate(samples, use_ai=not a.rules_only, sleep=a.sleep)
    text = report(r, f"{a.split}, {'rules only' if a.rules_only else 'rules + Gemini'}")
    print("\n" + text)
    if a.split == "test" and not a.rules_only and a.limit is None:
        (ROOT / "eval" / "results.md").write_text(text, encoding="utf-8")
        print("Wrote eval/results.md")


if __name__ == "__main__":
    main()
