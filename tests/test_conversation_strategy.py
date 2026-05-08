from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def test_omitted_project_uses_default_big_project(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True, default_project="Codex Brain"))
    a = svc.tool_ask_brain(question="a")
    b = svc.tool_ask_brain(question="b")
    assert a["project"] == "Codex Brain"
    assert b["project"] == "Codex Brain"
    assert a["conversation_url"] == b["conversation_url"]
    listed = svc.list_web_sessions("Codex Brain")
    assert listed["sessions"]


def test_named_projects_do_not_share_conversation(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    a = svc.tool_ask_brain(question="a", project="A")
    b = svc.tool_ask_brain(question="b", project="B")
    assert a["conversation_url"] != b["conversation_url"]


def test_conversation_strategy_new_stays_in_project_but_changes_url(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    first = svc.tool_ask_brain(question="first", project="P")
    second = svc.tool_ask_brain(question="second", project="P", conversation_strategy="new")
    assert first["project"] == second["project"] == "P"
    assert first["conversation_url"] != second["conversation_url"]
    assert second["conversation_strategy"] == "new"


def test_resume_session_uses_session_conversation_url(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    row_session = svc.store.create_session("P", "thinking_heavy", conversation_url="https://chatgpt.com/c/session123")
    result = svc.tool_ask_brain(question="resume", project="P", conversation_strategy="resume_session", session_id=row_session)
    assert result["conversation_url"] == "https://chatgpt.com/c/session123"
    assert result["conversation_strategy"] == "resume_session"


def test_resume_url_uses_explicit_conversation_url(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    result = svc.tool_ask_brain(question="resume", project="P", conversation_strategy="resume_url", conversation_url="https://chatgpt.com/c/url123")
    assert result["conversation_url"] == "https://chatgpt.com/c/url123"
