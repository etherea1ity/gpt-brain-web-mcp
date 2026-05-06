import time
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def test_project_conversation_is_reused(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    a = svc.tool_ask_brain(question="a", project="p")
    b = svc.tool_ask_brain(question="b", project="p")
    assert a["conversation_url"] == b["conversation_url"]
    assert a["conversation_url"].startswith("chatgpt://local/project/p")


def test_research_job_uses_job_conversation(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    sync = svc.tool_ask_brain(question="x", project="p")
    started = svc.start_research(topic="job topic", project="p", tier="thinking_heavy")
    for _ in range(50):
        row = svc.get_research_result(started["job_id"])
        if row["status"] == "completed":
            break
        time.sleep(0.05)
    assert row["status"] == "completed"
    assert row["conversation_url"].startswith("chatgpt://local/job/")
    assert row["conversation_url"] != sync["conversation_url"]
