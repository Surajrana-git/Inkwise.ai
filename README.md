# Inkwise.ai

**Content governance before you publish. Every claim, traced to its source.**

Inkwise checks campaign copy and creatives against a brand's guidelines, approved facts and glossary. Every finding
cites the exact source it relies on, or is marked **UNVERIFIED**. A person decides every change, and a manager signs off
before anything counts as approved.

**Live demo:** https://inkwiseai-jobnp9jkgfoutv5jeuvvs7.streamlit.app/
Team **DECODIANS** · CodeTitans India 2026 (title sponsor Inkloom) · Round 3: The Finish

| Member | Role | Built |
|---|---|---|
| Suraj Kumar (lead) | Backend | Workflow, audit log, fact register, insights engine, reliability, deployment, app shell |
| Riyana S | AI / ML | Gemini review engine, evidence verification, rule checks, privacy masking, first image checks, evaluation |
| Aashi Yadav | Frontend | Review screen: inline highlights, evidence quotes, expiry badges, input warnings |
| Pritha S | Product / Research | Lumora brand kit, user testing, documentation |

---

## Try it in 3 minutes (no explanation needed)

Open the live link and pick a person on the sign-in page. No password is needed. You can switch person at any time from
the name in the top-right corner, and the **Help** tab answers every question below.

| Person | Role | Try this |
|---|---|---|
| **Asha Menon** | Creator | Review → load **Launch post** → **Run pre-publication check** → Accept / Edit / Reject each finding (the draft updates live) → **Send for approval**. Add the **sample banner** to check an image too. |
| **Meera Kapoor** | Manager | Approvals → read the readiness checks and the creator's decisions → **Approve** or **Send back** (a comment is required). Insights → unclear guidelines, review times. |
| **Ravi Sharma** | Admin | Fact Register → renew an expired fact → open drafts that cite it are re-checked. Accept a clearer guideline wording in Insights. |

The **Review** page also shows a five-step guided story that switches to the right person for each step.

All data is synthetic: **Lumora** is a fictional fintech brand written by the team.

## What it does

1. **Check:** paste copy, import a **PDF, Word or text file**, and optionally add the campaign **image**. Rules run first
   (glossary, expired and expiring facts, readability, image colour and contrast), then Gemini looks for claims, tone,
   messaging and accessibility issues, using only the brand-kit entries it is shown.
2. **Explain:** each finding is highlighted in the text (every occurrence), names its source, quotes the evidence with the
   matching words highlighted, and has an **Open in Brand Kit** link to the full source. Image findings are boxed on the
   image.
3. **Decide:** Accept, Edit or Reject. The draft updates live as tracked changes; **Final copy** shows the clean text.
4. **Sign off:** only a Manager approves or sends back, never on their own draft.
5. **Audit:** History has every draft with who decided what and when, a **PDF audit report** per draft and CSV export.
6. **Improve:** Insights shows guidelines people keep overriding, repeat issues by category, creator or team, and how
   long each review stage takes.

## The three Round 3 improvements (committed in Round 2)

Details and proof for each item: [docs/round3_delivery.md](docs/round3_delivery.md).

1. **Evidence-grounded findings:** the code verifies that the quoted evidence really exists in the cited source,
   otherwise the finding becomes UNVERIFIED; evidence is highlighted inside the source quote; one click opens the full
   source; images get the same finding format (WCAG contrast and brand colours without AI, logo and text-in-image with
   Gemini Vision).
2. **Fact freshness:** facts have owners and expiry dates; expired **and expiring-soon** facts are flagged on every
   occurrence; figures match in any form (2M = 2 million = 20 lakh = 0.2 crore, two million, 2,000,000, rounded within
   10%); the Fact Register is sorted by risk with owner filters; renewing a fact is logged and re-checks open drafts.
   A separate planted-fact test group has its own recall.
3. **Guideline Clarity Insights:** override and reject rates per guideline from real logged decisions, likely-unclear
   guidelines by documented thresholds, repeat issues by category, creator or team, a suggested clearer wording that an
   Admin accepts (logged), filters by date and role, and measured review times.

## Evaluation

Labelled sets: `eval/test.jsonl` (100 samples, 143 labelled errors, 25 clean) and `eval/dev.jsonl` (50 samples, used
for tuning). Every label points to a real brand-kit ID. Details: [eval/README.md](eval/README.md).

| Setup (test set) | Precision | Recall | Citation accuracy | Clean samples wrongly flagged |
|---|---:|---:|---:|---:|
| Rules + Gemini (`eval/results.md`) | 83.5% | 95.8% | 83.2% | 10 / 25 |
| Rules only, current engine | 95.0% | 53.1% | 97.4% | 2 / 25 |

Recall by type with Gemini: terminology 50/50, claims 23/23, tone 19/20, messaging 11/12, accessibility 11/12,
outdated facts 23/26 (rules alone now catch 26/26 after the number-matching work).

**Fact-freshness test group** (`eval/fact_cases.jsonl`, rules only, fixed dates): **30/30 cases, recall 100%,
precision 100%**. The previous checker scored 18/30 on the same cases.

Run them yourself:
```bash
python eval/run_eval.py --split test            # rules + Gemini (needs GEMINI_API_KEY)
python eval/run_eval.py --split test --rules-only
python eval/run_fact_eval.py                    # fact-freshness group, writes eval/fact_results.md
```

## Architecture

A pure-Python engine (`engine/`) with a Streamlit app (`app/`) on top. Design and decisions:
[docs/architecture.md](docs/architecture.md).

```text
engine/
  schemas.py     data contracts: Finding (with evidence, owner, freshness, image box), Guideline, Fact, Term
  knowledge.py   brand kit loading and search (keyword search by default, embeddings optional)
  redact.py      masks names, emails, phone numbers and IDs before any AI call
  rules.py       glossary, expired / expiring facts (unit-aware), readability
  review.py      Gemini review with evidence verification, backup models, hard time limits
  visual.py      image checks: palette (V01), WCAG contrast (V02), logo + text reading with Gemini (V03)
  workflow.py    roles, versions, decisions, approvals, fact register, insights, audit log (SQLite)
app/             Streamlit pages: Home, Review, Approvals, Fact Register, Insights, History, Brand Kit, Help
data/brand_kit/  Lumora guidelines (15), facts (20), glossary (15), image rules and palette
eval/            labelled sets, fact-freshness group, evaluation scripts and results
docs/            delivery, architecture, testing, responsible design, limitations and roadmap, deploy, disclosures
tests/           189 automated tests
```

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt        # macOS with Python 3.9: pip install "cryptography<45" first
cp .env.example .env                   # add GEMINI_API_KEY (optional: every rule check works without it)
streamlit run app/Home.py
pytest                                 # 189 tests
```

## Documentation

| Document | What it covers |
|---|---|
| [docs/round3_delivery.md](docs/round3_delivery.md) | Each Round 3 commitment, what was built, and the proof |
| [docs/testing.md](docs/testing.md) | Automated tests, the control sweep, evaluations, reliability checks |
| [docs/responsible_design.md](docs/responsible_design.md) | Privacy, security, accessibility and responsible AI |
| [docs/limitations_and_roadmap.md](docs/limitations_and_roadmap.md) | Known limitations and the plan after the event |
| [docs/clarity_thresholds.md](docs/clarity_thresholds.md) | Insights thresholds |
| [docs/architecture.md](docs/architecture.md) · [docs/deploy.md](docs/deploy.md) · [docs/disclosures.md](docs/disclosures.md) | Design, deployment, APIs, models, data and AI-assisted development |
| [docs/docs/user_testing.md](docs/docs/user_testing.md) | User testing |
