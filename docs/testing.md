# Testing and reliability

How we know Inkwise works, and how to check it yourself.

## 1. Automated tests: 194

`pytest` runs every test headless, against a temporary database, with no Gemini key, so the rule checks and the
whole workflow are exercised exactly as a judge would meet them offline.

| File | What it proves |
|---|---|
| `tests/test_app_pages.py` | Every page loads for every role; the full journeys: check → accept / edit / reject → send → approve or send back; landing sign-in, user switch, sign out; Help search and guides; History filters and PDF; Brand Kit source focus; Insights team view and review times; image upload and annotated approvals |
| `tests/test_workflow.py`, `tests/test_workflow_r3.py` | Roles, versions, decisions, idempotent approve / submit, no self-approval, Admin cannot sign off, fact register and renewals, insights and thresholds, review times, repeat issues by team |
| `tests/test_rules.py`, `tests/test_fact_freshness.py` | Glossary, readability, expired and expiring facts, every number format (lakh, crore, 2M, words, rounding), years ignored, decimals kept inside sentences, the planted-fact group at 100% |
| `tests/test_review.py`, `tests/test_evidence.py`, `tests/test_engine_fixes.py` | Gemini prompt and parsing, backup models, 429 retry, hung-call deadline, evidence verification (UNVERIFIED when the quote is not in the source), per-claim retrieval |
| `tests/test_visual.py` | Palette, WCAG contrast (line-based and no-AI estimate), logo answer, text-in-image runs the copy rules, no false alarms on photos / logo / a clean on-brand card, bad and huge images refused |
| `tests/test_documents.py` | PDF, Word (with tables) and text import; long files cut to the limit; scanned PDFs, .doc, empty and broken files get a plain message |
| `tests/test_reliability.py` | Long or empty text, double clicks, deciding twice or after someone else, HTML in user text is escaped |
| `tests/test_redact.py`, `test_knowledge.py`, `test_schemas.py`, `test_bootstrap.py` | Personal-data masking, brand-kit loading and search, data contracts, startup and seeding |

## 2. Every control, clicked

A sweep script opens every page as Creator, Manager and Admin and clicks every button, picks every option of every
radio, select box and segmented control, one at a time from a fresh page: about **370 controls**, **no errors** (repeated on the final build).
It also times every page load. In the browser, every tab switch is fully drawn in 0.3 to 0.5 seconds.

Problems the sweep and the browser walk-through found, all fixed: the header did not stay pinned when scrolling; a
fact-renewal confirmation was wiped by a page refresh; several buttons redrew the page twice per click; the selected
Help topic icon was invisible.

## 3. Accuracy

| Evaluation | Result | How to run |
|---|---|---|
| Test set, rules + Gemini (100 samples, 143 labels) | precision 88.7%, recall 98.6%, citation accuracy 92.9%, 4/25 clean flagged (start of Round 3: 83.5% / 95.8% / 83.2% / 10/25) | `python eval/run_eval.py --split test` |
| Test set, rules only, current engine | precision 95.0%, recall 53.1%, citation 97.4%, 2/25 clean flagged | `python eval/run_eval.py --split test --rules-only` |
| Fact-freshness group (30 planted cases, fixed dates) | 30/30, recall 100%, precision 100% (previous checker: 18/30) | `python eval/run_fact_eval.py` |

The evaluation script refuses to overwrite `eval/results.md` when Gemini did not answer every sample, so a silent
rules-only run can never be reported as an AI result (this happened in Round 2 and was found and fixed).

## 4. Reliability by design

- **AI unavailable:** the header shows "AI not connected" from a background check that never blocks a page; rule
  checks always run and the page says what was skipped.
- **Busy or slow AI:** backup models on 429 / overload, a 45-second total budget and a hard deadline per call, so a
  hung network call cannot freeze the page.
- **Bad input:** empty or over-long text, unreadable images and documents, huge or tiny images, decompression bombs
  all get one plain sentence instead of an error.
- **Double clicks and refreshes:** submitting, approving and deciding are idempotent, and a browser refresh keeps the
  demo person signed in on the same page.
- **Screen sizes:** the header and every page were checked at 1100, 1280 and 1440 px wide; nothing clips and the page
  never scrolls sideways.
- **Demo samples:** stored AI results for the four sample drafts, so the demo works even when the free tier is exhausted.
- **No flash between pages:** styles live in the page head and images are served as files, so the design never
  falls back to the default look while a page loads.
