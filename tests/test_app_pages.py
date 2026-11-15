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
         "app/pages/Knowledge_Base.py", "app/pages/Fact_Register.py", "app/pages/Insights.py"]


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


def test_login_screen_shows_demo_accounts_and_rejects_bad_password():
    at = run("app/Home.py", SPLASH)
    assert any("Demo accounts" in m.value for m in at.markdown)
    at.text_input[0].set_value("asha")
    at.text_input[1].set_value("wrong")
    at.selectbox[0].set_value("Creator")
    at.button[0].click().run()
    assert any("did not match" in e.value for e in at.error)
    at.text_input[1].set_value("demo123")
    at.button[0].click().run()
    assert at.session_state["auth"] is True and at.session_state["user"] == "asha"
    assert not at.exception


def test_creator_journey_review_decide_send_then_manager_sees_it():
    at = run("app/pages/1_Review.py", ASHA)
    run_btn = lambda: at.button[labels(at).index("Run review")]
    run_btn().click().run()                                        # empty input
    assert any("Paste some text" in w.value for w in at.warning)
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
    assert "Approve" in labels(m)
    pending_ids = [s["id"] for s in services.list_submissions("pending")]
    assert sid in pending_ids


def test_long_text_is_refused_with_a_readable_message():
    import services
    with pytest.raises(services.InputError, match="limit"):
        services.review_text_full("word " * 5000)
    with pytest.raises(services.InputError, match="Paste"):
        services.review_text_full("   \n ")


def test_fact_register_creator_read_only_admin_renews():
    c = run("app/pages/Fact_Register.py", ASHA)
    assert c.button[0].disabled is True
    a = run("app/pages/Fact_Register.py", RAVI)
    assert a.dataframe[0].value.shape[0] >= 10
    fact_id = a.selectbox[2].value.split(" · ")[0]
    a.button[0].click().run()
    assert not a.exception
    from engine import workflow
    log = workflow.global_audit(5, "fact_renewed")
    assert log and log[0]["detail"].startswith(fact_id)
    reg = {f["id"]: f for f in workflow.fact_register()}
    assert reg[fact_id]["status"] == "valid"


def test_insights_blocked_for_creator_and_admin_can_accept_rewording():
    c = run("app/pages/Insights.py", ASHA)
    assert any("Managers and Admins" in i.value for i in c.info)
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
