import time
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def test_research_job_completes_and_artifact_exists(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    started = svc.start_research(topic="mock research", project="p", tier="thinking_heavy", deep_research=True)
    assert started["status"] == "queued"
    job_id = started["job_id"]
    for _ in range(50):
        result = svc.get_research_result(job_id)
        if result["status"] == "completed":
            break
        time.sleep(0.05)
    assert result["status"] == "completed"
    assert result["artifact_path"]
    assert "Deep Research UI not available" in " ".join(result["warnings"])


def test_cancel_research_job(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    started = svc.start_research(topic="cancel me", tier="thinking_heavy")
    status = svc.cancel_research_job(started["job_id"])
    assert status["status"] in {"cancelled", "already_completed"}
