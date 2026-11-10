# Evaluation (Riyana + Pritha)

- `dev.jsonl`: about 50 samples for tuning prompts.
- `test.jsonl`: 100 hand-checked samples. **Frozen: never tune on it.**
- `run_eval.py`: precision, recall and citation accuracy.
- `results.md`: final numbers for the demo and README.

One line per sample:
```json
{"id": "s-001", "format": "social", "text": "...", "is_clean": false,
 "errors": [{"type": "claim", "exact_span": "...", "rule_or_fact_id": "UNVERIFIED",
             "explanation": "...", "suggested_fix": "..."}]}
```

## How the sets were built
- `build_dataset.py` writes `dev.jsonl` (50 samples, 12 clean) and `test.jsonl` (100 samples, 25 clean).
- Every planted error comes from a catalogue tied to a real brand-kit ID (glossary banned variants,
  expired facts F01–F08, and the bad examples behind G01–G15), so labels are correct by construction.
  Clean sentences use approved terms, good examples and facts that have not expired.
- `raw/` holds the first datasets generated with Adaption Labs. We did not use them for scoring:
  only about 30% of the test labels used real brand-kit IDs, and many cited the wrong source
  (e.g. a guaranteed-returns claim labelled with a currency fact).

## Baseline (rules only, no AI) on test
Precision 96.1% · Recall 51.0% · Citation accuracy 97.3% · Clean samples wrongly flagged 1/25.
Rules catch terminology (50/50) and expired facts (23/26); claims, tone, accessibility and
messaging need the AI review.
