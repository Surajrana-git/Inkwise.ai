#!/usr/bin/env bash
# Creates one GitHub Issue per relay step. Needs the GitHub CLI: `brew install gh && gh auth login`
# Run from the repo folder:  bash scripts/create_issues.sh
set -e
R="Surajrana-git/Inkwise.ai"
mk() { gh issue create -R "$R" --title "$1" --body "$2" || true; }

mk "Step 1 · Suraj · Repo skeleton + Finding schema"        "Skeleton, schemas.py, interface stubs, main protected."
mk "Step 2 · Pritha · Lumora brand kit"                    "guidelines.json, facts.json, glossary.json in data/brand_kit (see README there)."
mk "Step 3 · Suraj · knowledge.py (ChromaDB search)"       "load_brand_kit, build_index, search(text) -> SourceMatch list. Tests."
mk "Step 4 · Riyana · review.py + rules.py"                "review_text(text) -> cited Findings; glossary + expired facts as rules; UNVERIFIED."
mk "Step 5 · Aashi · Review page on real engine"           "Paste text -> real findings cards with accept/edit/reject."
mk "Step 6 · Suraj · workflow.py (roles, approvals, audit)" "SQLite: content, versions, findings, decisions, audit log."
mk "Step 7 · Aashi · Login, Approvals, History pages"      "Wired to workflow.py."
mk "Step 8 · Riyana · Fixes, redaction, confidence, retry" "redact before every Gemini call; retry on 429."
mk "Step 9 · Suraj · Deploy to Streamlit Cloud"            "Seed data on startup; E2E on live link."
mk "Step 10 · Pritha · Live walk-through + bug list + eval data" "Issues for bugs; dev/test sets in eval/."
mk "Step 11 · Riyana · run_eval.py + override logging"     "Precision, recall, citation accuracy."
mk "Step 12 · Aashi · UI fixes, states, Knowledge Base page" ""
mk "Step 13 · Pritha · 5 user tests"                       "docs/user_testing.md"
mk "Step 14 · Suraj · Feature freeze 18:00, fixes, architecture.md" ""
mk "Step 15 · Pritha · README, disclosures, contributions"  ""
echo "Done."
