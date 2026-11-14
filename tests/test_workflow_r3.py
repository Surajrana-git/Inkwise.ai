"""Round 3 backend: login, idempotency, fact register + renew + re-check, insights, rewording, seed."""
from datetime import date, timedelta

import pytest

from engine import knowledge, seed, workflow as wf
from engine.schemas import CheckedBy, Category, Finding, FindingStatus, ReviewResult

FIX = "tests/fixtures/brand_kit"


@pytest.fixture(autouse=True)
def temp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "r3.sqlite3"))
    monkeypatch.delenv("INKWISE_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    wf.init_db()
    knowledge.build_index(knowledge.BRAND_KIT_DIR, use_embeddings=False)


def finding(fid, source="G02", cat=Category.CLAIM, span="fastest app"):
    return Finding(id=fid, category=cat, span=span, source_id=source, why="unsupported",
                   suggested_fix="a fast app", confidence=0.8, checked_by=CheckedBy.AI)


# ---------------- login
def test_demo_accounts_sign_in_with_matching_role_only():
    accounts = wf.demo_accounts()
    assert [a["username"] for a in accounts] == ["asha", "meera", "ravi"]
    assert wf.authenticate("ravi", "demo123", "Admin") == {"user": "ravi", "role": "Admin", "team": ""}
    assert wf.authenticate("  Meera ", "demo123", "manager")["team"] == "Product marketing"
    assert wf.authenticate("meera", "demo123", "admin") is None      # role mismatch
    assert wf.authenticate("meera", "wrong", "manager") is None
    assert wf.authenticate("nobody", "demo123", "creator") is None
    assert wf.authenticate("", "", "creator") is None
    assert wf.authenticate("ravi", "demo123", "intern") is None       # bad role never raises


# ---------------- idempotency
def test_same_action_twice_is_a_single_action():
    cid = wf.submit_content("asha", "Post", "We are the fastest app.")
    wf.save_review(cid, ReviewResult(text="x", findings=[finding("f-1")]))
    wf.decide_finding(cid, "f-1", FindingStatus.ACCEPTED, "asha")
    wf.decide_finding(cid, "f-1", FindingStatus.ACCEPTED, "asha")
    wf.approve(cid, "meera", "manager", approved=True)
    wf.approve(cid, "meera", "manager", approved=True)   # double-click: no error
    acts = [h["action"] for h in wf.history(cid) if h["kind"] == "event"]
    assert acts.count("finding_accepted") == 1 and acts.count("approved") == 1


def test_double_submit_returns_same_id():
    f = [{"id": "f-1", "category": "claim", "span": "fast", "source_id": "G07", "why": "w",
          "suggested_fix": "s", "confidence": 0.5, "checked_by": "ai", "status": "accepted"}]
    a = wf.submit_for_approval("Post", "fast app", f, "asha")
    b = wf.submit_for_approval("Post", "fast app", f, "asha")
    assert a == b and len(wf.list_submissions()) == 1


def test_decide_submission_bad_id_is_readable():
    with pytest.raises(wf.WorkflowError, match="Unknown submission"):
        wf.decide_submission("abc", "approved", "", "meera", "manager")


# ---------------- fact register and renewal
def test_fact_register_sorted_by_risk_with_expiring_soon():
    today = date(2026, 11, 14)
    reg = wf.fact_register(today=today)
    order = [r["status"] for r in reg]
    assert order == sorted(order, key=lambda s: {"expired": 0, "expiring_soon": 1, "valid": 2}[s])
    assert reg[0]["status"] == "expired" and reg[0]["days_left"] < 0
    soon = wf.fact_register(today=date(2027, 4, 10))
    assert any(r["status"] == "expiring_soon" and r["days_left"] <= 30 for r in soon)
    assert wf.fact_register(owner="Comms team", today=today)[0]["owner"] == "Comms team"
    assert all(r["status"] == "valid" for r in wf.fact_register(status="valid", today=today))


def test_renew_rules_and_recheck_clears_old_findings():
    kb = knowledge.get_kb()
    f01 = next(f for f in kb.facts if f.id == "F01")
    text = "Lumora Pay has 2 million registered users. Join today."
    cid = wf.submit_content("asha", "Post", text)
    wf.save_review(cid, ReviewResult(text=text, findings=[
        finding("f-1", "F01", Category.OUTDATED_FACT, span=text.split(". ")[0] + "."),
        finding("f-2", "G07")]))

    future = (date.today() + timedelta(days=200)).isoformat()
    with pytest.raises(wf.WorkflowError, match="Only Comms team or an admin"):
        wf.renew_fact("F01", "meera", "manager", future)          # Product marketing cannot renew F01
    with pytest.raises(wf.WorkflowError, match="future"):
        wf.renew_fact("F01", "ravi", "admin", "2020-01-01")
    with pytest.raises(wf.WorkflowError, match="YYYY-MM-DD"):
        wf.renew_fact("F01", "ravi", "admin", "soon")
    with pytest.raises(wf.WorkflowError, match="not found"):
        wf.renew_fact("F99", "ravi", "admin", future)

    out = wf.renew_fact("F01", "asha", "creator", future, note="confirmed with investor update")  # owner's team
    assert out["expires_on"] == future and out["rechecked"] == [cid] and out["cleared"] == 1
    assert not f01.is_expired()
    left = {f.id for f in wf.get_content(cid)["findings"]}
    assert left == {"f-2"}
    acts = [a["action"] for a in wf.global_audit(action_prefix="fact")]
    assert "fact_renewed" in acts
    assert wf.fact_register()[-1]["id"] == "F01" or any(r["id"] == "F01" and r["status"] == "valid" for r in wf.fact_register())

    # a fresh index picks the renewal up again from the DB (reboot case)
    kb2 = knowledge.build_index(knowledge.BRAND_KIT_DIR, use_embeddings=False)
    assert next(f for f in kb2.facts if f.id == "F01").is_expired()
    assert wf.apply_fact_overrides(kb2.facts) == 1
    assert not next(f for f in kb2.facts if f.id == "F01").is_expired()


# ---------------- insights
def _decided(source, status, n, author="asha", decider="asha"):
    for i in range(n):
        cid = wf.submit_content(author, f"{source}-{i}", "fastest app text")
        wf.save_review(cid, ReviewResult(text="x", findings=[finding("f-1", source)]))
        wf.decide_finding(cid, "f-1", status, decider)


def test_guideline_stats_thresholds_and_reasons():
    _decided("G02", FindingStatus.REJECTED, 4)      # 4/5 rejected -> unclear
    _decided("G02", FindingStatus.ACCEPTED, 1)
    _decided("G07", FindingStatus.ACCEPTED, 6)      # accepted -> clear
    _decided("G12", FindingStatus.EDITED, 2)        # only 2 shown -> below threshold
    stats = {s["source_id"]: s for s in wf.guideline_stats()}
    assert stats["G02"]["unclear"] and stats["G02"]["reject_rate"] == 0.8
    assert "rejected 4 of 5" in stats["G02"]["reason"].lower()
    assert not stats["G07"]["unclear"]
    assert not stats["G12"]["unclear"] and "below threshold" in stats["G12"]["reason"].lower()
    assert list(stats)[0] == "G02"                   # unclear first
    # date filter excludes everything in the past
    assert wf.guideline_stats(date_from="2030-01-01") == []
    # role filter: decisions by a manager only
    _decided("G08", FindingStatus.REJECTED, 5, decider="meera")
    by_mgr = {s["source_id"]: s for s in wf.guideline_stats(role="manager")}
    assert by_mgr["G08"]["rejected"] == 5 and by_mgr["G02"]["rejected"] == 0


def test_repeat_issues_by_creator_and_category():
    _decided("T01", FindingStatus.ACCEPTED, 3, author="dev")
    _decided("G07", FindingStatus.ACCEPTED, 1, author="dev")
    # findings on T01 are category CLAIM in this helper; check counts, not names
    by_creator = wf.repeat_issues("creator")
    top = by_creator[0]
    assert top["creator"] == "dev" and top["count"] == 4 and top["repeat"]
    by_cat = wf.repeat_issues("category")
    assert by_cat[0]["count"] == 4 and by_cat[0]["creators"] == 1


def test_rewording_suggest_fallback_llm_and_accept():
    fallback = wf.suggest_rewording("G02")
    assert "Be clear and concise" in fallback
    with pytest.raises(wf.WorkflowError, match="only guidelines"):
        wf.suggest_rewording("F01")
    # a second call is cached, so the llm is not consulted
    assert wf.suggest_rewording("G02", llm=lambda p: "SHOULD NOT BE USED") == fallback
    text = wf.suggest_rewording("G03", llm=lambda p: '"Say what the customer gets. Never pressure them."')
    assert text == "Say what the customer gets. Never pressure them."

    with pytest.raises(wf.WorkflowError, match="Only an admin"):
        wf.accept_rewording("G03", text, "meera", "manager")
    with pytest.raises(wf.WorkflowError, match="too short"):
        wf.accept_rewording("G03", "short", "ravi", "admin")
    wf.accept_rewording("G03", text, "ravi", "admin")
    kb = knowledge.get_kb()
    assert next(g for g in kb.guidelines if g.id == "G03").rule == text
    assert any(a["action"] == "guideline_reworded" for a in wf.global_audit())
    kb2 = knowledge.build_index(knowledge.BRAND_KIT_DIR, use_embeddings=False)
    assert wf.apply_guideline_overrides(kb2.guidelines) == 1


# ---------------- seed
def test_seed_runs_once_and_feeds_insights():
    n = seed.seed_if_empty()
    assert n >= 10
    assert seed.seed_if_empty() == 0                       # already seeded
    subs = wf.list_submissions()
    assert len(subs) == n and any(s["status"] == "pending" for s in subs)
    stats = wf.guideline_stats()
    unclear = {s["source_id"] for s in stats if s["unclear"]}
    assert unclear & set(seed.UNCLEAR)                     # the designed guidelines come out unclear
    rep = [r for r in wf.repeat_issues("creator") if r["repeat"]]
    assert rep
    dash = wf.get_dashboard_stats("admin")
    assert dash["seeded_at"] and dash["pending_approvals"] >= 1
    assert wf.health()["seeded"]


def test_startup_seeds_and_applies_overrides(tmp_path, monkeypatch):
    from engine import bootstrap
    state = bootstrap.startup()
    assert state.seeded_items >= 10 and not state.using_sample_kit
    assert bootstrap.startup().seeded_items == 0
