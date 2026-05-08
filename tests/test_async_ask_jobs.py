import time
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService, expected_tools


def test_async_ask_brain_creates_ask_job_not_research(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    started = svc.tool_ask_brain(question="Reply with exactly: ASYNC_OK", async_request=True, project="P")
    assert started["kind"] == "ask"
    job_id = started["job_id"]
    for _ in range(50):
        row = svc.get_job_result(job_id)
        if row["status"] == "completed":
            break
        time.sleep(0.05)
    assert row["kind"] == "ask"
    assert row["status"] == "completed"
    assert row["result"] == "ASYNC_OK"
    assert row["requested_research_mode"] is None


def test_async_ask_web_has_sources(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    started = svc.tool_ask_brain(question="find source", async_request=True, web_search=True, project="P")
    for _ in range(50):
        row = svc.get_job_result(started["job_id"])
        if row["status"] == "completed":
            break
        time.sleep(0.05)
    assert row["kind"] == "ask_web"
    assert row["sources"]


def test_delete_local_job_and_session_records(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    ask = svc.tool_ask_brain(question="x", project="P", save_session=True)
    deleted_session = svc.delete_local_record(ask["session_id"])
    assert deleted_session["deleted"] is True
    started = svc.start_research(topic="cleanup", project="P")
    job_id = started["job_id"]
    for _ in range(50):
        row = svc.get_job_result(job_id)
        if row["status"] == "completed":
            break
        time.sleep(0.05)
    deleted_job = svc.delete_local_record(job_id)
    assert deleted_job["deleted"] is True
    assert svc.get_job_result(job_id)["error"] == "not_found"


def test_expected_tools_include_generic_job_and_delete():
    assert "get_job_result" in expected_tools()
    assert "delete_local_record" in expected_tools()
    assert "delete_remote_conversation" in expected_tools()
    assert "purge_project_records" in expected_tools()
