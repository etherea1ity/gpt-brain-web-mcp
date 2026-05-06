from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def service(tmp_path):
    return WebBrainService(Settings(home=tmp_path, mock_browser=True))


def test_default_tier_is_thinking_heavy(tmp_path):
    svc = service(tmp_path)
    result = svc.tool_ask_brain(question="Reply with exactly: OK")
    assert result["backend"] == "web-chatgpt"
    assert result["requested_tier"] == "thinking_heavy"
    assert result["resolved_tier"] == "thinking_heavy"
    assert result["session_id"]


def test_fallback_heavy_to_extended_to_normal(tmp_path):
    svc = service(tmp_path)
    page = svc.browser.mock_page
    page.available_mode_labels = ["Extended Thinking", "Thinking"]
    res1 = svc.tool_ask_brain(question="x", tier="thinking_heavy")
    assert res1["resolved_tier"] == "thinking_extended"
    assert "thinking_heavy" in res1["fallback_chain"]
    assert any("fallback" in w.lower() for w in res1["warnings"])
    page.available_mode_labels = ["Thinking"]
    res2 = svc.tool_ask_brain(question="x", tier="thinking_heavy")
    assert res2["resolved_tier"] == "thinking_normal"
