# Round 3 delivery: the three committed improvements

In Round 2 we committed to three improvements. This page lists every item we promised, what was built, where it is,
and how to check it. Status: ✅ delivered · ⚠️ delivered with a stated gap.

## 1. Evidence-grounded findings

| Promised | Status | Where / how to check |
|---|---|---|
| Re-run the eval correctly | ✅ | The Round 2 "1.2% recall" came from a different test file and a script that never loaded the API key. Fixed; `eval/run_eval.py` now refuses to write results if the AI did not answer. `eval/results.md` |
| Recall ≥ 80% | ✅ 93.7% (was 51.0% in Round 2; previous Round 3 run 98.6%) | `eval/results.md` (rules + Gemini, test set, 100 samples, 99 answered by Gemini) |
| Precision ≥ 75% | ✅ 84.3% (previous run 88.7%) | same |
| Citation accuracy ≥ 98% | ✅ 98.5% (132/134; was 83.2% at the start of Round 3, 92.9% before the claims rule) | Evidence verification and per-claim retrieval removed most wrong cites (G03 and G12 went from 11 to 1). 10 of 141 remained, 7 of them labelled G07: unsupported superlatives and "instant" promises that the AI cited to another source. A new rule check now catches these and cites G07 itself (`rules.check_unsupported_claims`); rules alone now cite correctly 89/89 (100%). Re-measured with Gemini: 98.5%, the only wrong citations left are 2 for G12 |
| Per-claim retrieval | ✅ | `engine/review.py` `_source_listing`: the brand kit is searched for every sentence (claim) as well as the whole text, round-robin up to 18 sources, and the claims guideline G07 is always included. In a long draft, whole-text search alone missed F07, F02 and F06; per-claim retrieval keeps them (`tests/test_evidence.py`) |
| Code checks the quoted evidence exists in the cited source; otherwise UNVERIFIED | ✅ | `engine/review.py` `_verify_evidence`; tests `tests/test_evidence.py` |
| Evidence phrase highlighted inside the source quote | ✅ | Check a draft → open any finding |
| One-click open of the source | ✅ | Check a draft → finding → **Open G07 in Brand Kit ↗** shows the full entry (owner, expiry, source). Test `test_open_source_in_brand_kit_from_a_finding` |
| Image checks in the same finding format | ✅ | `engine/visual.py`: V01 palette and V02 WCAG contrast (Pillow, no AI), V03 logo with Gemini Vision; Gemini also reads the text in the image and the copy rules run on it. Check a draft → **Use sample banner**. Brand Kit → **Image rules**. Tests `tests/test_visual.py` |

## 2. Fact freshness

| Promised | Status | Where / how to check |
|---|---|---|
| "Expiring soon" flag (within 30 days) | ✅ | Fact Register status; a draft that repeats a still-valid fact expiring within 30 days now gets an advisory finding with the days left (`rules.check_expiring_facts`) |
| Each finding names the fact owner | ✅ | Finding text, quote and `fact_owner` field |
| Fact Register sorted by risk, filters by owner and expiry | ✅ | Fact Register page |
| Owner or admin renews / re-verifies, logged, drafts re-checked | ✅ | Fact Register → **Renew and re-check open drafts** (impact preview first; confirmation after) |
| Every occurrence flagged, not only the first | ✅ | Review highlights all occurrences; the rule checks every sentence |
| Matching for lakh / crore, percentages and rounded numbers | ✅ | `engine/rules.py`: 2M = 2 million = 20 lakh = 0.2 crore = 2,000,000 = "two million"; 40% = 40 percent; big figures match within 10% ("over 2 million", "2.1M"); years are not figures; decimals no longer split sentences |
| Separate planted-fact test group with its own recall | ✅ 30/30, recall 100%, precision 100% | `eval/fact_cases.jsonl`, `python eval/run_fact_eval.py` → `eval/fact_results.md`. The previous checker scored 18/30 (recall 50%) on the same cases |
| Live renew-and-recheck demo | ✅ | Sign in as Ravi → Fact Register |

## 3. Guideline Clarity Insights

| Promised | Status | Where / how to check |
|---|---|---|
| Plotly Insights page for Manager and Admin | ✅ | Insights tab (hidden for Creators) |
| Override and reject rate per guideline | ✅ | Grouped bar chart with the threshold lines |
| Repeat issues by category and by creator or team | ✅ | **Repeat issues by** Category / Creator / Team |
| Likely-unclear guidelines with documented thresholds | ✅ | `docs/clarity_thresholds.md` |
| Suggested clearer wording an admin can accept (logged) | ✅ | Insights → suggest → Admin accepts → `guideline_reworded` in the audit log; Brand Kit shows "reworded" |
| Filters by date and role; real logged decisions only | ✅ | Date range and "Decisions by" filters; no claims about campaign outcomes |

## Also planned for Round 3, and the Round 2 known gaps

| Item | Status |
|---|---|
| PDF / DOCX review | ✅ Check a draft → **Import from a PDF, Word or text file** (tables included; scanned PDFs and old .doc files get a clear message) |
| Only the first occurrence was highlighted | ✅ all occurrences |
| Role selector was not a real login | ✅ improved: sign-in page with one-click demo people, a work-account form, switch user, sign out. Real company accounts are on the roadmap |
| No accessibility checker beyond the AI | ✅ WCAG contrast and palette rules on images; accessibility guideline checks in copy |
| No review-time measurement | ✅ Insights → **How long reviews take** (check, creator, sign-off, end to end; medians from the audit log). We do not claim "time saved" without a baseline |
| Free-tier Gemini slow or unavailable | ✅ backup models, a 45 s total budget, a hard per-call deadline, background AI status in the header, rule checks always run, stored AI results for the four sample drafts |
| User tests lacked reasons and time taken | ✅ second test with five new people, with where they got stuck and why (`docs/user_testing.md`); every problem they named was fixed the same day: files go to the right box, numbered steps, a welcome card, and demo videos (one per person, plus the whole journey). Real review times are measured in Insights |
| Demo data resets when the app restarts | ⚠️ by design on Streamlit Cloud (SQLite on an ephemeral disk); a managed database is on the roadmap |

## Beyond the commitments

A workspace per person (Creator studio, Approval desk, Admin console) with only the tabs that person needs, a call to action at the top of each Home, and a clear way back if someone opens another person's page. Notifications for every role (bell and pop-ups), sign-in that survives a refresh, a Help Centre with guides and FAQ,
audit-report PDFs, a draft trail timeline, redesigned Approvals (readiness checks, Manager-only sign-off, no
self-approval), live tracked changes and Final copy on Review, and image findings boxed on the creative. Every status in
the UI has a text label as well as a colour.
