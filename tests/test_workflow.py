import pytest

from engine import workflow as wf
from engine.schemas import CheckedBy, Category, Finding, FindingStatus, ReviewResult


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "test.sqlite3"))
    wf.init_db()


def finding(fid, source="G02", cat=Category.CLAIM):
    return Finding(id=fid, category=cat, span="fastest app", source_id=source, why="unsupported",
                   suggested_fix="a fast app", confidence=0.8, checked_by=CheckedBy.AI)


def reviewed_item():
    cid = wf.submit_content("asha", "Launch post", "We are the fastest app.")
    wf.save_review(cid, ReviewResult(text="We are the fastest app.",
                                     findings=[finding("f-1"), finding("f-2", "UNVERIFIED")]))
    return cid


def test_full_happy_path():
    cid = reviewed_item()
    assert wf.get_content(cid)["status"] == "in_review"
    assert [i["id"] for i in wf.queue("manager")] == [cid]

    wf.decide_finding(cid, "f-1", FindingStatus.ACCEPTED, "asha")
    wf.decide_finding(cid, "f-2", FindingStatus.REJECTED, "asha", note="claim is in campaign brief")
    wf.approve(cid, "meera", "manager", approved=True)

    item = wf.get_content(cid)
    assert item["status"] == "approved"
    assert {f.id: f.status for f in item["findings"]} == {"f-1": FindingStatus.ACCEPTED, "f-2": FindingStatus.REJECTED}
    actions = [h["action"] for h in wf.history(cid) if h["kind"] == "event"]
    assert actions == ["created", "reviewed", "finding_accepted", "finding_rejected", "approved"]


def test_changes_requested_then_new_version():
    cid = reviewed_item()
    wf.approve(cid, "meera", "manager", approved=False, comment="fix the claim")
    assert wf.queue("creator", "asha")[0]["status"] == "changes_requested"
    v = wf.add_version(cid, "We are a fast, reliable app.", "asha")
    assert v == 2
    item = wf.get_content(cid)
    assert item["status"] == "draft" and item["findings"] == []
    assert item["text"].startswith("We are a fast")
    assert len([h for h in wf.history(cid) if h["kind"] == "version"]) == 2


def test_role_rules():
    cid = reviewed_item()
    with pytest.raises(wf.WorkflowError, match="cannot approve"):
        wf.approve(cid, "asha", "creator", approved=True)
    with pytest.raises(wf.WorkflowError, match="own content"):
        wf.approve(cid, "asha", "manager", approved=True)
    with pytest.raises(wf.WorkflowError, match="Unknown role"):
        wf.queue("intern")


def test_cannot_approve_with_open_findings_without_comment():
    cid = reviewed_item()
    with pytest.raises(wf.WorkflowError, match="still open"):
        wf.approve(cid, "meera", "manager", approved=True)
    wf.approve(cid, "meera", "manager", approved=True, comment="accepted risk: legal cleared")
    assert wf.get_content(cid)["status"] == "approved"


def test_approved_content_is_locked():
    cid = reviewed_item()
    wf.approve(cid, "meera", "admin", approved=True, comment="ok")
    with pytest.raises(wf.WorkflowError, match="locked"):
        wf.add_version(cid, "new text", "asha")


def test_decision_stats_for_clarity_insights():
    for _ in range(2):
        cid = reviewed_item()
        wf.decide_finding(cid, "f-1", FindingStatus.REJECTED, "asha")
        wf.decide_finding(cid, "f-2", FindingStatus.ACCEPTED, "asha")
    stats = {s["source_id"]: s for s in wf.decision_stats()}
    assert stats["G02"]["override_rate"] == 1.0
    assert stats["UNVERIFIED"]["override_rate"] == 0.0


def test_unknown_items_and_bad_input():
    with pytest.raises(wf.WorkflowError):
        wf.get_content(999)
    with pytest.raises(wf.WorkflowError, match="empty"):
        wf.submit_content("asha", "t", "   ")
    cid = reviewed_item()
    with pytest.raises(wf.WorkflowError, match="not found"):
        wf.decide_finding(cid, "f-9", FindingStatus.ACCEPTED, "asha")
    assert wf.export_audit_log().count("\n") >= 1


# ---------------- UI adapters used by app/services.py
def ui_finding(fid, status="open", source="G07"):
    return {"id": fid, "category": "claim", "span": "fastest app", "source_id": source, "source_text": "",
            "why": "unsupported", "suggested_fix": "a fast app", "confidence": 0.8,
            "checked_by": "ai", "status": status}


def test_submit_list_decide_roundtrip():
    sid = wf.submit_for_approval("Launch post", "We are the fastest app.",
                                 [ui_finding("f-1", "accepted"), ui_finding("f-2", "rejected", "UNVERIFIED")], "asha")
    pending = wf.list_submissions("pending")
    assert [s["id"] for s in pending] == [sid]
    s = pending[0]
    assert {f["id"]: f["status"] for f in s["findings"]} == {"f-1": "accepted", "f-2": "rejected"}
    assert s["version"] == 1 and s["decided_by"] == ""

    wf.decide_submission(sid, "rejected", "tone down the claim", "meera", "manager")
    done = wf.list_submissions("rejected")[0]
    assert done["decided_by"] == "meera" and done["comment"] == "tone down the claim"
    assert wf.list_submissions("pending") == []


def test_decide_rules_raise_readable_errors():
    sid = wf.submit_for_approval("Post", "text", [ui_finding("f-1")], "asha")
    with pytest.raises(wf.WorkflowError, match="own content"):
        wf.decide_submission(sid, "approved", "", "asha", "manager")
    with pytest.raises(wf.WorkflowError, match="still open"):
        wf.decide_submission(sid, "approved", "", "meera", "manager")


def test_dashboard_activity_and_login(monkeypatch):
    wf.submit_for_approval("Post", "text", [ui_finding("f-1")], "asha")
    stats = wf.get_dashboard_stats("manager")
    assert stats["reviews_today"] == 1 and stats["open_findings"] == 1 and stats["pending_approvals"] == 1
    act = wf.get_recent_activity(3)
    assert act[0]["who"] == "inkwise-ai" and act[0]["status"] in ("open", "ok", "bad")
    monkeypatch.setenv("INKWISE_DEMO_PASSWORD", "pw")
    assert wf.authenticate("meera", "pw", "manager") == {"user": "meera", "role": "manager"}
    assert wf.authenticate("meera", "wrong", "manager") is None


def test_tables_created_automatically(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "fresh.sqlite3"))
    assert wf.list_submissions() == []


def test_ui_role_names_any_case():
    sid = wf.submit_for_approval("Post", "text", [ui_finding("f-1", "accepted")], "asha")
    wf.decide_submission(sid, "approved", "", "meera", "Manager")
    assert wf.list_submissions("approved")[0]["decided_by"] == "meera"
    assert wf.get_dashboard_stats("Admin")["pending_approvals"] == 0
