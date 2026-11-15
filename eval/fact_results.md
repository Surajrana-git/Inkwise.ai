# Fact-freshness test group (rules only)

Planted facts with their own recall. Source: `eval/fact_cases.jsonl`. Run: `python eval/run_fact_eval.py`.

- Cases passed: 30/30
- Recall: 100.0% (22/22 planted fact mentions found)
- Precision: 100.0% (22/22 flags were right)

| Case | Result | What it tests |
|---|---|---|
| fx01 | ✅ | same figure, same words |
| fx02 | ✅ | lakh |
| fx03 | ✅ | 2M, 'over' |
| fx04 | ✅ | number words |
| fx05 | ✅ | thousands separators |
| fx06 | ✅ | rounded (within 10%) |
| fx07 | ✅ | rounded down |
| fx08 | ✅ | lakh, year not counted |
| fx09 | ✅ | crore |
| fx10 | ✅ | small count, exact |
| fx11 | ✅ | small count in words |
| fx12 | ✅ | decimal rating is one number |
| fx13 | ✅ | small count |
| fx14 | ✅ | small count in words |
| fx15 | ✅ | minutes |
| fx16 | ✅ | every occurrence |
| fx17 | ✅ | two different expired facts |
| fx18 | ✅ | not expired yet and more than 30 days left (expires 2026-09-30) |
| fx19 | ✅ | expires in 20 days |
| fx20 | ✅ | no figure in the fact (F12) means nothing to compare; handled by AI claim checks |
| fx21 | ✅ | F07 expired on 2026-08-15, five days earlier |
| fx22 | ✅ | different figure: not the approved fact (an unsupported claim, for the AI) |
| fx23 | ✅ | different rating |
| fx24 | ✅ | a year is not a figure |
| fx25 | ✅ | same figure, unrelated topic |
| fx26 | ✅ | no fact about 40% |
| fx27 | ✅ | F06 has no figure to match; left to AI |
| fx28 | ✅ | F20 is valid |
| fx29 | ✅ | one sentence, best match wins |
| fx30 | ✅ | 25% away: a different figure |
