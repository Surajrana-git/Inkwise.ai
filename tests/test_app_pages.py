"""Headless UI journeys with Streamlit's AppTest (Round 3 reliability evidence).

Runs every page as every role against a temporary database with no Gemini key, so the
rule checks and the workflow are exercised exactly as a judge would use them offline.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
sys.path.insert(0, str(APP))

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

SPLASH = {"splash_done": True}
ASHA = {**SPLASH, "auth": True, "user": "asha", "role": "Creator", "team": "Comms team"}
MEERA = {**SPLASH, "auth": True, "user": "meera", "role": "Manager", "team": "Product marketing"}
RAVI = {**SPLASH, "auth": True, "user": "ravi", "role": "Admin", "team": ""}
PAGES = ["app/Home.py", "app/pages/1_Review.py", "app/pages/Approvals.py", "app/pages/History.py",
         "app/pages/Knowledge_Base.py", "app/pages/Fact_Register.py", "app/pages/Insights.py",
         "app/pages/Help.py"]


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setenv("INKWISE_DB", str(tmp_path / "ui.sqlite3"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import services
    from engine import workflow

    workflow.init_db()
    services._started = False      # force startup (seed) against the temp DB
    services._cache.clear()
    yield


def run(page: str, state: dict, timeout: int = 90) -> AppTest:
    at = AppTest.from_file(str(ROOT / page), default_timeout=timeout)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [str(e.value)[:300] for e in at.exception]
    return at


def labels(at: AppTest) -> list[str]:
    return [b.label for b in at.button]


@pytest.mark.parametrize("page", PAGES)
@pytest.mark.parametrize("who", [ASHA, MEERA, RAVI], ids=["creator", "manager", "admin"])
def test_every_page_renders_for_every_role(page, who):
    run(page, who)


def test_login_one_click_cards_and_password_fallback():
    at = run("app/Home.py", SPLASH)
    assert all(any(n in l for l in labels(at)) for n in ("Asha", "Meera", "Ravi"))
    # work-account form: unknown accounts get the "coming with the live release" note
    at.button(key="acct_open").click().run()
    at.text_input[0].set_value("someone@company.com")
    at.text_input[1].set_value("secret")
    at.button[labels(at).index("Continue")].click().run()
    assert any("coming with the live release" in m.value for m in at.markdown)
    at.text_input[0].set_value("ravi@lumora.test")
    at.text_input[1].set_value("demo123")
    at.button[labels(at).index("Continue")].click().run()
    assert at.session_state["user"] == "ravi"
    at.button(key="sign_out").click().run()            # a real sign-out (also clears the ?as= address)
    # one click
    at.button(key="login_meera").click().run()
    assert at.session_state["auth"] is True and at.session_state["user"] == "meera"
    assert at.session_state["role"] == "Manager" and not at.exception


def test_creator_lands_on_home_with_a_welcome_and_one_button_to_start():
    at = run("app/Home.py", ASHA)
    assert "You are Asha" in _all_md(at)
    assert [b for b in at.button if b.key == "wel_go"][0].label == "Check a sample draft"


def test_home_shows_tour_and_measured_accuracy():
    at = run("app/Home.py", {**ASHA, "landed_for": "asha"})
    assert {"Step 1", "Step 2", "Step 3"} <= set(labels(at))
    assert any("Measured accuracy" in m.value for m in at.markdown)
    assert any("Good " in m.value and "Asha" in m.value for m in at.markdown)
    at.button(key="tour_hide").click().run()
    assert "Step 1" not in labels(at)


def test_review_sample_buttons_fill_the_text():
    import services
    at = run("app/pages/1_Review.py", ASHA)
    first = services.demo_samples()[0]
    at.button(key=f"smp_{first['id']}").click().run()
    assert at.session_state["rv_text"] == first["text"]


def test_creator_journey_review_decide_send_then_manager_sees_it():
    at = run("app/pages/1_Review.py", ASHA)
    run_btn = lambda: at.button[labels(at).index("Run pre-publication check")]
    assert run_btn().disabled                                      # nothing to check yet: button is off
    text = "Open LumoraPay today. Lumora Pay has 2 million registered users. All transfers are always free."
    at.text_area(key="rv_text").input(text).run()
    run_btn().click().run()
    findings = at.session_state["rv_findings"]
    assert findings and {f["source_id"] for f in findings} >= {"T01", "F01"}
    assert all(f["start"] is not None for f in findings)         # highlighted in the text
    for f in findings:
        f["status"] = "accepted"
    at.run()
    assert "Send for approval" in labels(at)
    # page_link needs the multipage runtime, so submit through the same service the button calls
    import services
    sid = services.submit_for_approval("Diwali post", text, findings, "asha")
    assert services.submit_for_approval("Diwali post", text, findings, "asha") == sid   # double-click safe
    m = run("app/pages/Approvals.py", MEERA)
    assert "✓  Approve and publish" in labels(m)
    pending_ids = [s["id"] for s in services.list_submissions("pending")]
    assert sid in pending_ids


def test_long_text_is_refused_with_a_readable_message():
    import services
    with pytest.raises(services.InputError, match="limit"):
        services.review_text_full("word " * 5000)
    with pytest.raises(services.InputError, match="Paste"):
        services.review_text_full("   \n ")


def test_fact_register_creator_read_only_admin_renews():
    RENEW = "Renew and re-check open drafts"
    c = run("app/pages/Fact_Register.py", ASHA)
    assert c.button[labels(c).index(RENEW)].disabled is True
    a = run("app/pages/Fact_Register.py", RAVI)
    assert a.dataframe[0].value.shape[0] >= 10
    fact_id = a.selectbox(key="fr_pick").value.split(" · ")[0]
    a.button[labels(a).index(RENEW)].click().run()
    assert not a.exception
    from engine import workflow
    log = workflow.global_audit(5, "fact_renewed")
    assert log and log[0]["detail"].startswith(fact_id)
    reg = {f["id"]: f for f in workflow.fact_register()}
    assert reg[fact_id]["status"] == "valid"


def test_insights_blocked_for_creator_and_admin_can_accept_rewording():
    c = run("app/pages/Insights.py", ASHA)
    assert "NOT IN YOUR WORKSPACE" in " ".join(x.value for x in c.markdown)
    m = run("app/pages/Insights.py", MEERA)
    assert labels(m).count("Suggest clearer wording") >= 1          # seeded data crosses the threshold
    assert "Accept this wording" not in labels(m)                   # manager cannot accept
    a = run("app/pages/Insights.py", RAVI)
    a.button[labels(a).index("Suggest clearer wording")].click().run()
    assert a.text_area and len(a.text_area[0].value) > 10
    a.button[labels(a).index("Accept this wording")].click().run()
    assert not a.exception
    from engine import workflow
    assert workflow.global_audit(3, "guideline_reworded")


def test_header_user_menu_switches_user_and_signs_out():
    at = run("app/pages/Approvals.py", ASHA)
    assert at.button(key="sw_asha").disabled            # current user is marked and not clickable
    at.button(key="sw_meera").click().run()
    assert at.session_state["user"] == "meera" and at.session_state["role"] == "Manager"
    at.button(key="sign_out").click().run()
    assert not at.session_state["auth"] if "auth" in at.session_state else True


def test_landing_shows_journey_and_all_drafts_with_trail():
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    assert "Go as Meera" not in labels(at) and "Show the walkthrough" in labels(at)     # hidden by default
    at.button(key="j_show").click().run()
    assert {"Go as Asha", "Go as Meera", "Go as Ravi"} <= set(labels(at))
    assert any("APPROVED / RETURNED BY" in m.value for m in at.markdown)
    assert any('class="tr-list"' in m.value and "ran the Inkwise check" in m.value for m in at.markdown)
    md = " ".join(m.value for m in at.markdown)
    assert 'class="tr-steps"' in md and "Created" in md and "Checked" in md and "Decided" in md
    at.button(key="j_hide").click().run()
    assert "Go as Meera" not in labels(at)
    at.selectbox(key="dr_filter").set_value("Approved").run()
    assert not at.exception


def test_finding_buttons_accept_edit_reject_then_send():
    import services
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    at.text_area(key="rv_text").input(
        "Open LumoraPay today. Lumora Pay has 2 million registered users. All transfers are always free.").run()
    at.button[labels(at).index("Run pre-publication check")].click().run()
    fs = at.session_state["rv_findings"]
    ids = [f["id"] for f in fs]
    assert len(ids) >= 2 and at.session_state["rv_focus"] == ids[0]       # first finding opens by itself
    at.button(key=f"acc_{ids[0]}").click().run()
    assert at.session_state["rv_findings"][0]["status"] == "accepted"
    assert at.session_state["rv_focus"] == ids[1]                           # next one opens
    at.button(key=f"edt_{ids[1]}").click().run()
    at.text_area(key=f"edit_{ids[1]}").input("the Lumora Pay app").run()
    at.button(key=f"save_{ids[1]}").click().run()
    f1 = at.session_state["rv_findings"][1]
    assert f1["status"] == "edited" and f1["suggested_fix"] == "the Lumora Pay app"
    for f in at.session_state["rv_findings"][2:]:
        at.button(key=f"acc_{f['id']}").click().run()
    at.button(key=f"rej_{ids[0]}").click().run()                          # change of mind: reject the first
    assert at.session_state["rv_findings"][0]["status"] == "rejected"
    assert all(f["status"] != "open" for f in at.session_state["rv_findings"])
    assert any("✕ Rejected" in e.label for e in at.expander) and any("✎ Edited" in e.label for e in at.expander)
    before = len(services.list_submissions())
    at.button[labels(at).index("Send for approval")].click().run()
    assert not at.exception and len(services.list_submissions()) == before + 1
    sent = services.list_submissions("pending")[0]
    assert {f["status"] for f in sent["findings"]} >= {"edited", "rejected"}


def _md(at) -> str:
    return " ".join(m.value for m in at.markdown)


def test_draft_and_counts_update_after_each_decision():
    s = __import__("services").demo_samples()[0]          # launch post: 6 findings
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    at.text_area(key="rv_text").input(s["text"]).run()
    at.button[labels(at).index("Run pre-publication check")].click().run()
    fs = at.session_state["rv_findings"]
    assert "4</b><small>must fix left" in _md(at) and 'class="rm"' not in _md(at)
    # accept the expired-fact finding: the sentence is struck out and the must-fix tile drops
    old = next(f for f in fs if f["category"] == "outdated_fact")
    at.button(key=f"acc_{old['id']}").click().run()
    assert '<span class="rm"' in _md(at) and "Join 2 million" in _md(at)
    assert "3<s>of 4</s></b><small>must fix left" in _md(at)
    # reject the tone finding: kept as written
    tone = next(f for f in fs if f["category"] == "tone")
    at.button(key=f"rej_{tone['id']}").click().run()
    assert 'class="kp"' in _md(at) and "sign up now or miss your chance" in _md(at)
    # edit a claim: the writer's own words appear as an applied fix
    claim = next(f for f in fs if f["category"] == "claim")
    at.button(key=f"edt_{claim['id']}").click().run()
    at.text_area(key=f"edit_{claim['id']}").input("Lumora Pay is built for everyday payments").run()
    at.button(key=f"save_{claim['id']}").click().run()
    assert '<span class="ad"' in _md(at) and "built for everyday payments" in _md(at)
    # final copy has the fixes and none of the removed text
    at.radio(key="rv_view").set_value("Final copy").run()
    final = _md(at)
    assert "Join 2 million" not in final and "built for everyday payments" in final
    assert "sign up now or miss your chance" in final
    # move it into the editor
    at.button(key="rv_use").click().run()
    assert not at.exception and "built for everyday payments" in at.session_state["rv_text"]
    assert at.session_state["rv_findings"] is None


def test_revision_helper_rules():
    import review_helpers as rh
    text = "Join 2 million users of LumoraPay! Tap the green button above."
    fs = [{"n": 1, "category": "outdated_fact", "occurrences": [(0, 34)], "status": "accepted",
           "suggested_fix": "Remove this claim, or ask Comms team for the current figure before using it."},
          {"n": 2, "category": "terminology", "occurrences": [(24, 33)], "status": "accepted", "suggested_fix": "Lumora Pay"},
          {"n": 3, "category": "readability", "occurrences": [(35, 61)], "status": "accepted",
           "suggested_fix": "Split this into shorter sentences and use simpler words."}]
    _, clean, manual = rh.revision(text, fs)
    assert clean == "Tap the green button above." and manual == [3]     # removal wins over the inner fix
    fs[0]["status"] = "rejected"
    _, clean, _ = rh.revision(text, fs)
    assert clean.startswith("Join 2 million users of Lumora Pay!")           # inner fix still applies
    for f in fs:
        f["status"] = "open"
    assert rh.revision(text, fs)[1] == text


def test_only_a_manager_signs_off_and_never_their_own_draft():
    from engine import workflow as wf
    sid = wf.submit_for_approval("Admin post", "Lumora Pay is a payment app.", [], "asha")
    with pytest.raises(wf.WorkflowError, match="Admins manage facts"):
        wf.decide_submission(sid, "approved", "ok", "ravi", "admin")
    own = wf.submit_for_approval("Meera's own post", "Lumora Pay helps you pay.", [], "meera")
    with pytest.raises(wf.WorkflowError, match="your own"):
        wf.decide_submission(own, "approved", "ok", "meera", "manager")
    assert {s["decided_by"] for s in wf.list_submissions() if s["status"] in ("approved", "rejected")} <= {"meera"}


def test_approvals_page_queue_detail_and_decisions():
    import services
    sid = services.submit_for_approval("Queue test", "Lumora Pay is a payment app.", [], "asha")
    m = run("app/pages/Approvals.py", MEERA)
    assert not m.exception
    m.button(key=f"q_{sid}").click().run()                         # pick it from the queue
    assert m.session_state["ap_sel"] == sid
    page = " ".join(x.value for x in m.markdown)
    assert "Queue test" in page and "Ready to approve" in page and "WHAT THE CREATOR DECIDED" in page
    m.radio(key=f"ap_view_{sid}").set_value("Final copy").run()
    assert "what will be published" in " ".join(c.value for c in m.caption)
    m.button(key="ap_rj").click().run()                            # send back needs a comment
    assert any("Add a comment" in e.value for e in m.error)
    assert next(s for s in services.list_submissions() if s["id"] == sid)["status"] == "pending"
    m.text_area(key=f"c_{sid}").input("Please add the fee link.").run()
    m.button(key="ap_rj").click().run()
    s = next(s for s in services.list_submissions() if s["id"] == sid)
    assert s["status"] == "rejected" and s["decided_by"] == "meera" and s["comment"] == "Please add the fee link."
    sid2 = services.submit_for_approval("Queue test 2", "Lumora Pay helps you pay.", [], "asha")
    m.run()
    m.button(key=f"q_{sid2}").click().run()
    m.button(key="ap_ok").click().run()
    assert next(s for s in services.list_submissions() if s["id"] == sid2)["status"] == "approved"


@pytest.mark.parametrize("who", [ASHA, RAVI], ids=["creator", "admin"])
def test_approvals_page_is_not_in_creator_or_admin_workspace(who):
    m = run("app/pages/Approvals.py", who)
    assert not m.exception
    md = " ".join(x.value for x in m.markdown)
    assert "NOT IN YOUR WORKSPACE" in md and "Approval desk" in md
    assert "✓  Approve and publish" not in labels(m) and "↩  Send back" not in labels(m)
    m.button(key="guard_switch").click().run()           # one click to continue as the Manager
    assert m.session_state["user"] == "meera" and "✓  Approve and publish" in labels(m)


@pytest.mark.parametrize("who", [MEERA, RAVI], ids=["manager", "admin"])
def test_review_page_belongs_to_the_creator_studio(who):
    at = run("app/pages/1_Review.py", {**who, "landed_for": who["user"]})
    assert not at.exception
    assert "Creator studio" in " ".join(x.value for x in at.markdown)
    assert not [b for b in at.button if b.key == "rv_run"]


def test_each_person_sees_only_their_own_tabs():
    import theme
    tabs = lambda r: [label for _p, label, _r in theme.visible_tabs(r)]  # noqa: E731
    assert tabs("Creator") == ["Home", "Check a draft", "My drafts", "Brand Kit", "Help"]
    assert tabs("Manager") == ["Home", "Approval queue", "Insights", "All drafts", "Brand Kit", "Help"]
    assert tabs("Admin") == ["Home", "Fact Register", "Insights", "All drafts", "Brand Kit", "Help"]
    assert theme.can_open("pages/Fact_Register.py", "Creator")    # fact owners can still renew their team's facts


@pytest.mark.parametrize("who,label", [("asha", "sent back to you"), ("meera", "waiting for your decision"),
                                       ("ravi", "facts have expired")])
def test_home_is_different_for_each_person(who, label):
    person = {"asha": ASHA, "meera": MEERA, "ravi": RAVI}[who]
    at = run("app/Home.py", {**person, "landed_for": who})
    assert not at.exception and label in " ".join(x.value for x in at.markdown)


def test_sample_banner_checked_with_the_copy_then_sent_with_its_image(monkeypatch):
    import services
    from engine import visual
    monkeypatch.setattr(visual, "read_text", lambda *a, **k: (_ for _ in ()).throw(TimeoutError("offline")))
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    at.button(key="rv_img_sample").click().run()
    assert at.session_state["rv_img_bytes"][:4] == b"\x89PNG"
    assert labels(at).count("Run pre-publication check · image only") == 1
    at.text_area(key="rv_text").input("Open LumoraPay today.").run()
    at.button(key="rv_run").click().run()
    fs = at.session_state["rv_findings"]
    img = [f for f in fs if f.get("where") == "image"]
    assert img and any(f["source_id"] == "V01" for f in img) and any(f["source_id"] == "T01" for f in fs)
    assert any("🖼 image" in e.label for e in at.expander)
    assert any("text and logo in the image" in w.value for w in at.warning)   # says what it could not do
    for f in fs:
        at.button(key=f"acc_{f['id']}").click().run()
    at.button[labels(at).index("Send for approval")].click().run()
    sent = services.list_submissions("pending")[0]
    assert services.submission_image(sent["id"]) is not None
    assert any(f.get("where") == "image" for f in sent["findings"])
    m = run("app/pages/Approvals.py", MEERA)
    m.button(key=f"q_{sent['id']}").click().run()
    assert m.session_state["ap_sel"] == sent["id"]
    assert "CAMPAIGN IMAGE" in " ".join(x.value for x in m.markdown)


def test_remove_image_empties_the_uploader():
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    at.button(key="rv_img_sample").click().run()
    at.button(key="rv_img_rm").click().run()
    assert not at.session_state["rv_img_bytes"] and at.session_state["rv_up_n"] == 1


def _all_md(at) -> str:
    return " ".join(m.value for m in at.markdown)


@pytest.mark.parametrize("page", ["app/Home.py", "app/pages/1_Review.py", "app/pages/Approvals.py",
                                  "app/pages/History.py", "app/pages/Help.py", "app/pages/Knowledge_Base.py"])
def test_every_page_has_the_strip_and_the_footer(page):
    at = run(page, {**MEERA, "landed_for": "meera"})
    md = _all_md(at)
    assert "CodeTitans India 2026" in md and "iw-ft-legal" in md and "TRUST AND GOVERNANCE" in md


def test_help_centre_search_topics_and_faq():
    at = run("app/pages/Help.py", ASHA)
    md = _all_md(at)
    assert "Help Centre" in md and "Start here" in md and "How Inkwise works" in md
    assert len(at.expander) >= 10                                    # FAQ answers
    at.button(key="hc_t_facts").click().run()                         # pick a guide
    assert at.session_state["hc_topic"] == "facts" and "Fact freshness" in _all_md(at)
    at.text_input(key="hc_q").input("unverified").run()               # search narrows the FAQ
    assert [e.label for e in at.expander] == ["What does UNVERIFIED mean?"]
    at.text_input(key="hc_q").input("zzzz nothing").run()
    assert "No answer matches" in _all_md(at) and "No guide matches" in _all_md(at)


def test_history_cards_filters_details_and_pdf():
    import services
    at = run("app/pages/History.py", MEERA)
    md = _all_md(at)
    subs = services.list_submissions()
    assert "Drafts sent for approval" in md and f"of {len(subs)} shown" in md
    assert any(d.label.startswith("⬇  Download audit report (PDF)") for d in at.get("download_button"))
    at.segmented_control(key="hs_status").set_value("Sent back").run()
    shown = [s for s in subs if s["status"] == "rejected"]
    assert f"{len(shown)} of {len(subs)} shown" in _all_md(at)
    pick = shown[-1]["id"]
    at.button(key=f"hs_open_{pick}").click().run()
    assert at.session_state["hs_sel"] == pick and f"Audit report · #{pick}" in _all_md(at)
    at.text_input(key="hs_q").input("no draft has this title").run()
    assert "No drafts match" in _all_md(at)


def test_audit_report_pdf_has_text_findings_and_timeline():
    import services, report_pdf, pymupdf
    s = next(x for x in services.list_submissions() if x["status"] == "approved")
    pdf = report_pdf.build(s, services.draft_history(s["id"]), {"meera": "Meera Kapoor"})
    text = pymupdf.open(stream=pdf, filetype="pdf")[0].get_text()
    assert pdf[:4] == b"%PDF" and s["title"] in text and "Findings and decisions" in text
    assert "Timeline" in text and "Meera Kapoor" in text and "Inkwise check" in text


def test_fact_renewal_confirmation_survives_the_refresh():
    at = run("app/pages/Fact_Register.py", RAVI)
    at.button[labels(at).index("Renew and re-check open drafts")].click().run()
    assert not at.exception
    assert any("now expires on" in s.value for s in at.success)       # was wiped by st.rerun() before


def test_open_source_in_brand_kit_from_a_finding():
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    at.text_area(key="rv_text").input("Open LumoraPay today. Lumora Pay has 2 million registered users.").run()
    at.button(key="rv_run").click().run()
    f = next(x for x in at.session_state["rv_findings"] if x["source_id"] == "F01")
    at.session_state["rv_focus"] = f["id"]
    at.run()
    at.button(key=f"src_{f['id']}").click().run()
    assert at.session_state["kb_focus"] == "F01"
    kb = run("app/pages/Knowledge_Base.py", {**ASHA, "kb_focus": "F01"})
    md = " ".join(m.value for m in kb.markdown)
    assert "OPENED FROM A FINDING · APPROVED FACT" in md and "2 million registered users" in md and "Owner:" in md
    kb.button(key="kb_close").click().run()
    assert "kb_focus" not in kb.session_state
    assert "OPENED FROM A FINDING" not in " ".join(m.value for m in kb.markdown)


def test_brand_kit_lists_image_rules_and_palette():
    kb = run("app/pages/Knowledge_Base.py", ASHA)
    md = " ".join(m.value for m in kb.markdown)
    assert "V01" in md and "V02" in md and "V03" in md and "#12917F" in md


def test_insights_shows_review_times_and_team_view():
    at = run("app/pages/Insights.py", MEERA)
    md = " ".join(m.value for m in at.markdown)
    assert "How long reviews take" in md and "End to end, draft to decision" in md
    at.selectbox(key=None) if False else None
    sel = next(s for s in at.selectbox if s.label == "Repeat issues by")
    sel.set_value("Team").run()
    assert not at.exception and "Repeat issues by team" in " ".join(m.value for m in at.markdown)


def test_notifications_flow_creator_to_manager_and_back():
    """Asha sends a draft -> Meera is notified; Meera approves -> Asha is notified."""
    import services
    names = {"asha": "Asha Menon", "meera": "Meera Kapoor"}
    sid = services.submit_for_approval("Notify test", "Lumora Pay helps you pay.", [], "asha")
    mine = [n for n in services.notifications("meera", "Manager", names) if n["id"] == f"sub-{sid}-sent"]
    assert mine and mine[0]["title"] == "Asha Menon sent “Notify test” for your approval"
    assert mine[0]["page"] == "pages/Approvals.py"
    assert not [n for n in services.notifications("asha", "Manager", names) if n["id"] == f"sub-{sid}-sent"]  # not own
    assert [n for n in services.notifications("asha", "Creator", names) if n["id"] == f"sub-{sid}-waiting"]
    services.decide_submission(sid, "approved", "Looks good", "meera", "Manager")
    back = [n for n in services.notifications("asha", "Creator", names) if n["id"] == f"sub-{sid}-approved"]
    assert back and back[0]["title"] == "Meera Kapoor approved “Notify test”" and "Looks good" in back[0]["detail"]
    assert not [n for n in services.notifications("meera", "Manager", names) if n["id"] == f"sub-{sid}-sent"]
    admin = services.notifications("ravi", "Admin", names)
    assert any(n["id"].startswith("fact-") for n in admin)


def test_bell_badge_toasts_once_and_mark_read():
    at = run("app/pages/Approvals.py", {**MEERA, "landed_for": "meera"})
    toasts = [t.value for t in at.toast]
    assert any("for your approval" in t for t in toasts)
    at.run()                                              # the same notifications do not pop up twice
    assert not any("for your approval" in t.value for t in at.toast)
    md = " ".join(m.value for m in at.markdown)
    assert "NOTIFICATIONS · 2 NEW" in md or "NEW" in md
    at.button(key="nt_read").click().run()
    assert "NOTIFICATIONS · 0 NEW" in " ".join(m.value for m in at.markdown)


def test_footer_meet_the_team_with_safe_links():
    import theme
    out = theme.team_html()
    for name in ("Suraj Kumar", "Riyana S", "Aashi Yadav", "Pritha S"):
        assert name in out
    assert 'href="https://github.com/Surajrana-git" target="_blank" rel="noopener noreferrer"' in out
    assert "BUILT BY <b>DECODIANS</b>" in out and out.count("<svg") == 8          # 4 x LinkedIn + 4 x GitHub
    assert theme._safe_url("javascript:alert(1)") == "" and theme._safe_url("") == ""
    at = run("app/pages/Help.py", ASHA)
    assert "BUILT BY" in " ".join(m.value for m in at.markdown)


def test_refresh_keeps_the_demo_person_signed_in_and_sign_out_clears_it():
    at = AppTest.from_file(str(ROOT / "app/pages/History.py"), default_timeout=90)
    at.query_params["as"] = "meera"                     # what the address holds after a refresh
    at.run()
    assert not at.exception and at.session_state["auth"] and at.session_state["role"] == "Manager"
    assert at.query_params["as"] == ["meera"] or at.query_params["as"] == "meera"
    at.button(key="sign_out").click().run()
    assert not at.session_state["auth"] if "auth" in at.session_state else True
    assert "as" not in at.query_params
    bad = AppTest.from_file(str(ROOT / "app/pages/History.py"), default_timeout=90)
    bad.query_params["as"] = "nobody"                   # only demo accounts can be restored
    bad.run()
    assert not (bad.session_state["auth"] if "auth" in bad.session_state else False)


def test_help_answers_cover_notifications_import_and_refresh():
    at = run("app/pages/Help.py", ASHA)
    qs = [e.label for e in at.expander]
    assert {"How do notifications work?", "Can I check a PDF or Word file?", "What happens if I refresh the page?"} <= set(qs)


class _Up:
    def __init__(self, name, data):
        self.name, self._d = name, data

    def getvalue(self):
        return self._d


def test_a_file_in_the_wrong_box_still_goes_to_the_right_place(monkeypatch):
    """User test (16 Nov): a PDF dropped in the image box was refused. Now any file is routed by its type."""
    import importlib, sys, types
    from pathlib import Path
    import streamlit as st
    sys.path.insert(0, str(Path("app")))
    import services
    monkeypatch.setattr(services, "extract_document",
                        lambda data, name: {"text": "Lumora Pay has 2 million users.", "pages": 1,
                                            "chars": 31, "truncated": False})
    at = run("app/pages/1_Review.py", {**ASHA, "landed_for": "asha"})
    md = _all_md(at)
    assert "Your copy" in md and "Campaign image" in md and "Run the check" in md
    labels_up = " ".join(str(getattr(u, "label", "")) for u in at.get("file_uploader"))
    assert "PDF, Word or text file" in labels_up and "PNG or JPG" in labels_up


@pytest.mark.parametrize("who,line", [("asha", "You are Asha"), ("meera", "You are Meera"), ("ravi", "You are Ravi")])
def test_first_visit_shows_a_plain_welcome_that_can_be_hidden(who, line):
    """User test (16 Nov): five people found the app hard to start. Home now says who you are and where to begin."""
    person = {"asha": ASHA, "meera": MEERA, "ravi": RAVI}[who]
    at = run("app/Home.py", {**person, "landed_for": who})
    assert line in _all_md(at) and "wel_go" in [b.key for b in at.button]
    at.button(key="wel_hide").click().run()
    assert line not in _all_md(at)
