# Known limitations and roadmap

## Known limitations (today)

| Limitation | Impact | What we do about it now |
|---|---|---|
| AI checks need Gemini, and the free tier can be slow, rate-limited or unreachable | Claims, tone and messaging findings and reading text in images are skipped | Rule checks always run; the page says what was skipped; backup models and hard time limits; stored AI results for the four sample drafts |
| Citation accuracy with Gemini is 92.9%, below our 98% target (up from 83.2%) | 10 of 141 correct findings cite a near-miss source, 7 of them the general claims guideline G07 instead of a specific fact | Unverifiable quotes become UNVERIFIED, so a wrong cite never shows invented evidence; next step is tuning on the dev set |
| Image contrast without AI is an estimate | It may miss small text or, rarely, flag a texture | The finding says "estimated without AI"; with AI, contrast is measured on each located text line |
| Scanned PDFs and old `.doc` files | No text to check | A clear message asks for a text PDF or `.docx` |
| Demo sign-in, no real accounts or passwords | Anyone with the link can act as any demo person | Every action is in the audit log; roles are enforced in the engine |
| SQLite on Streamlit Cloud's disk | Demo data resets when the app restarts | Demo data is re-seeded automatically on start |
| One workspace and one brand kit per deployment | No multi-brand or agency setup yet | Brand kit is plain JSON, easy to swap |
| Rule-based fact matching needs a figure | Facts without numbers (e.g. "support is available seven days a week") are left to the AI claim check | The AI is always shown the claims guideline and per-claim sources |
| Second user test (with time taken and reasons) not repeated yet | Usability evidence is from the first round | Review times from real use are measured in Insights |

## Roadmap

**Next (first month after the event)**
- Raise citation accuracy from 92.9% to 98%: prefer a specific fact over G07 when both match; tune on the dev set only.
- Second user test with five people: time taken per task, where they hesitated, and why.
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
