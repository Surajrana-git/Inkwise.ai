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
