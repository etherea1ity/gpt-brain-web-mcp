from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.models import normalize_retention
from gpt_brain_web_mcp.store import Store
from gpt_brain_web_mcp.tools import WebBrainService, expected_tools
from gpt_brain_web_mcp.web.chatgpt_page import MockChatGPTPage


def test_retention_defaults():
    assert normalize_retention(None, project_explicit=False) == "ephemeral"
    assert normalize_retention(None, project_explicit=True) == "persistent"
    assert normalize_retention(None, project_explicit=True, default="job") == "job"


def test_remote_cleanup_queue_store(tmp_path):
    store = Store(tmp_path / "brain.db")
    cid = store.enqueue_remote_cleanup("https://chatgpt.com/c/test-cleanup", reason="test", retention="ephemeral", project="P")
    assert cid
    assert store.list_remote_cleanup(status="pending")[0]["cleanup_id"] == cid
    store.update_remote_cleanup(cid, status="deleted")
    assert store.remote_cleanup_stats()["deleted"] == 1


def test_cleanup_remote_conversations_mock(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    cid = svc.store.enqueue_remote_cleanup("https://chatgpt.com/c/test-cleanup", reason="test", retention="ephemeral")
    dry = svc.cleanup_remote_conversations(dry_run=True)
    assert dry["seen"] == 1
    assert dry["items"][0]["action"] == "would_delete"
    actual = svc.cleanup_remote_conversations(confirm=True, dry_run=False, cleanup_id=cid)
    assert actual["deleted"] == 1
    assert svc.store.list_remote_cleanup(cleanup_id=cid)[0]["status"] == "deleted"


def test_cleanup_skips_persistent(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    cid = svc.store.enqueue_remote_cleanup("https://chatgpt.com/c/persistent", reason="test", retention="persistent")
    actual = svc.cleanup_remote_conversations(confirm=True, dry_run=False, cleanup_id=cid)
    assert actual["deleted"] == 0
    assert actual["skipped"] == 1


def test_ui_capability_mock_page():
    page = MockChatGPTPage(deep_research_available=True, web_search_available=True)
    assert page.check_deep_research_ui()["available"] is True
    assert page.check_web_search_ui()["available"] is True


def test_new_mcp_tools_are_listed():
    tools = set(expected_tools())
    assert {"list_remote_cleanup", "cleanup_remote_conversations", "ui_capabilities_check"}.issubset(tools)


def test_resume_url_is_not_queued_for_cleanup(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    res = svc.tool_ask_brain(
        question="Reply with exactly: SAFE",
        conversation_strategy="resume_url",
        conversation_url="https://chatgpt.com/c/existing-important",
        retention="ephemeral",
        cleanup_remote=True,
    )
    assert res["cleanup_remote_status"] == "skipped_not_new_conversation"
    assert svc.store.list_remote_cleanup() == []
    assert any("reused/resumed" in w for w in res["warnings"])


def test_cleanup_id_terminal_status_is_not_reprocessed(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    cid = svc.store.enqueue_remote_cleanup("https://chatgpt.com/c/already", reason="test", retention="ephemeral")
    svc.store.update_remote_cleanup(cid, status="deleted")
    report = svc.cleanup_remote_conversations(confirm=True, dry_run=False, cleanup_id=cid)
    assert report["deleted"] == 0
    assert report["skipped"] == 1
    assert report["items"][0]["action"] == "skipped_terminal_deleted"


def test_deep_research_fallback_flags_default_off(tmp_path, monkeypatch):
    from gpt_brain_web_mcp.jobs import JobManager
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    jm = JobManager(svc, svc.store, tmp_path / "artifacts")
    monkeypatch.delenv("GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_TIMEOUT", raising=False)
    monkeypatch.delenv("GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_FAILURE", raising=False)
    assert jm._deep_research_timeout_fallback_enabled() is False
    assert jm._deep_research_failure_fallback_enabled() is False
    monkeypatch.setenv("GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_TIMEOUT", "1")
    monkeypatch.setenv("GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_FAILURE", "true")
    assert jm._deep_research_timeout_fallback_enabled() is True
    assert jm._deep_research_failure_fallback_enabled() is True


def test_research_defaults_cleanup_remote_for_job_retention(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    captured = {}
    def fake_start_research(*args):
        captured["retention"] = args[-2]
        captured["cleanup_remote"] = args[-1]
        from gpt_brain_web_mcp.models import JobStartResult
        return JobStartResult("job_fake", "queued", "ok", "now")
    svc.jobs.start_research = fake_start_research
    out = svc.start_research(topic="x")
    assert out["job_id"] == "job_fake"
    assert captured == {"retention": "job", "cleanup_remote": True}


def test_research_persistent_retention_does_not_default_cleanup_remote(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    captured = {}
    def fake_start_research(*args):
        captured["retention"] = args[-2]
        captured["cleanup_remote"] = args[-1]
        from gpt_brain_web_mcp.models import JobStartResult
        return JobStartResult("job_fake", "queued", "ok", "now")
    svc.jobs.start_research = fake_start_research
    svc.start_research(topic="x", retention="persistent")
    assert captured == {"retention": "persistent", "cleanup_remote": False}
