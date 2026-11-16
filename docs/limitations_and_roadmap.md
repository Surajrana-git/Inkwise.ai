# Known limitations and roadmap

## Known limitations (today)

| Limitation | Impact | What we do about it now |
|---|---|---|
| AI checks need Gemini, and the free tier can be slow, rate-limited or unreachable | Claims, tone and messaging findings and reading text in images are skipped | Rule checks always run; the page says what was skipped; backup models and hard time limits; stored AI results for the four sample drafts |
| Gemini's answers vary between runs | The same test set gave recall 98.6% in one run and 93.7% in the next (messaging and accessibility findings); 6 of 25 clean drafts were flagged in the final run | Rule checks are repeatable and always run; we report every run, not the best one; next step is averaging several runs and tuning the prompt on the dev set |
| Image contrast without AI is an estimate | It may miss small text or, rarely, flag a texture | The finding says "estimated without AI"; with AI, contrast is measured on each located text line |
| Scanned PDFs and old `.doc` files | No text to check | A clear message asks for a text PDF or `.docx` |
| Demo sign-in, no real accounts or passwords | Anyone with the link can act as any demo person | Every action is in the audit log; roles are enforced in the engine |
| SQLite on Streamlit Cloud's disk | Demo data resets when the app restarts | Demo data is re-seeded automatically on start |
| One workspace and one brand kit per deployment | No multi-brand or agency setup yet | Brand kit is plain JSON, easy to swap |
| Rule-based fact matching needs a figure | Facts without numbers (e.g. "support is available seven days a week") are left to the AI claim check | The AI is always shown the claims guideline and per-claim sources |
| New users find the app hard to understand at first (all five testers said so) | Without the walkthrough, a first visit can feel complicated | Welcome card with one button to start, numbered steps, demo videos (one per person, plus the whole journey); not yet re-tested with the same people |

## Roadmap

**Next (first month after the event)**
- Steadier AI results: average several runs, tune the messaging and accessibility prompt on the dev set only, and cut the 6/25 false alarms on clean drafts.
- Re-test the five people after the changes, timing every task; then test with real marketing teams.
- Company sign-in (Google / Microsoft) with the same roles; a managed Postgres database instead of SQLite.

**Then**
- Integrations where content is written: Google Docs and Word add-ins, a Slack / Teams check command, a CMS webhook
  that blocks publishing until sign-off.
- Several brands and agencies in one workspace, each with its own brand kit, palette and approvers.
- OCR for scanned PDFs; checks for web pages by URL; video captions.
- Fact sources linked to the system of record (finance, product), so a fact expires or updates automatically.

**Later**
- Insights across teams over time: which guideline rewording reduced overrides, and by how much.
- A brand-kit editor with versioning, so every finding can point to the guideline version it was checked against.
