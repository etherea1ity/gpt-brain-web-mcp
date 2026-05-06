from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def test_pro_without_allow_pro_downgrades(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    svc.browser.mock_page.available_mode_labels = ["Pro", "Pro Extended", "Thinking Heavy"]
    result = svc.tool_ask_brain(question="x", tier="pro", allow_pro=False)
    assert result["resolved_tier"] != "pro"
    assert result["resolved_tier"] == "thinking_heavy"
    assert any("allow_pro=false" in w for w in result["warnings"])


def test_pro_extended_requires_allow_pro(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    svc.browser.mock_page.available_mode_labels = ["Pro Extended", "Pro", "Thinking Heavy"]
    no = svc.tool_ask_brain(question="x", tier="pro_extended", allow_pro=False)
    yes = svc.tool_ask_brain(question="x", tier="pro_extended", allow_pro=True)
    assert no["resolved_tier"] != "pro_extended"
    assert yes["resolved_tier"] == "pro_extended"
