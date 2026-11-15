# Privacy, security, accessibility and responsible AI

## Privacy

- **Synthetic data only.** Lumora, its people, drafts and facts are invented by the team. No real customer data is used
  or needed for the demo.
- **Masking before AI.** Names, email addresses, phone numbers and ID numbers are replaced with placeholders
  (`[NAME_1]`, `[EMAIL_1]` ...) before any text is sent to Gemini (`engine/redact.py`), and restored in the findings
  shown to the user. Brand and product names stay readable so the checks still work.
- **Least data to the model.** Gemini receives the masked text and only the brand-kit entries relevant to it, never
  the audit log, other drafts or user accounts. Images are sent only to read their text and check for the logo.
- **Free-tier note.** Google may use free-tier prompts to improve its products; this is why the demo is synthetic and
  masked. A production deployment would use the paid tier, where prompts are not used for training.
- **Local storage.** Drafts, decisions and the audit log are kept in a SQLite file next to the app; uploaded images are
  stored next to it only to show the approver the creative.

## Security

- **Roles enforced in the engine, not only the UI.** Only Managers (and Reviewers) can approve; Admins cannot sign
  off; nobody can approve their own draft; only a fact's owner team or an Admin can renew it; only an Admin can accept
  a guideline rewording. Each rule raises an error in `engine/workflow.py` whatever the page does.
- **Secrets.** The Gemini key is read from `.env` locally or Streamlit secrets in the cloud; `.env` and secrets are
  git-ignored and never written to logs or the page.
- **Untrusted input.** User text is HTML-escaped wherever it is drawn (tested); uploads are size-limited (5 MB),
  type-checked, and images are refused above 50 million pixels (decompression bombs).
- **Demo sign-in.** The demo has one-click accounts with no password, clearly labelled; company sign-in is on the
  roadmap. Every sign-in and action is still written to the audit log.

## Accessibility

- **In content we check:** copy that relies on colour or position ("tap the green button above") is flagged against
  the accessibility guideline; text in images is measured against WCAG 2.1 AA contrast (4.5:1).
- **In the app:** every status has a text label as well as a colour (Approved / Sent back / Open, ✓ ✎ ✕ markers);
  findings are listed in reading order with numbers that match the highlights; the image view boxes findings with
  numbers, not colour alone.

## Responsible AI

- **AI suggests, people decide.** No change is applied without a person accepting or editing it, and a Manager signs
  off. Rejections are kept and count in Insights.
- **No source, no claim.** Every AI finding must quote words from the source it cites; the code checks the quote, and
  a finding whose quote is not in the source is marked UNVERIFIED with its confidence capped.
- **Disclosure.** The app shows an AI disclosure on every working page, the header shows whether AI is connected, and
  the model that answered is recorded with each review.
- **Honest numbers.** Accuracy is measured on a labelled set and the results file is refused when the AI did not run.
  Insights uses only decisions logged in the workspace and makes no claims about campaign outcomes or time saved.
- **Known limitations** are listed in [limitations_and_roadmap.md](limitations_and_roadmap.md), and AI tools used
  while building are disclosed in [disclosures.md](disclosures.md).
