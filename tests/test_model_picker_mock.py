from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.web.chatgpt_page import MockChatGPTPage
from gpt_brain_web_mcp.web.model_picker import ModelModeManager


def test_model_picker_uses_yaml_labels_and_fallback(tmp_path):
    manager = ModelModeManager(Settings(home=tmp_path, mock_browser=True).model_modes_path)
    page = MockChatGPTPage(available_mode_labels=["Extended Thinking", "Thinking"])
    selection = manager.select_tier(page, "thinking_heavy", False)
    assert selection.resolved_tier == "thinking_extended"
    assert selection.fallback_chain == ["thinking_heavy", "thinking_extended"]


def test_model_picker_pro_allowed_only_when_opted_in(tmp_path):
    manager = ModelModeManager(Settings(home=tmp_path, mock_browser=True).model_modes_path)
    page = MockChatGPTPage(available_mode_labels=["Pro Extended"])
    no = manager.select_tier(page, "pro_extended", False)
    yes = manager.select_tier(page, "pro_extended", True)
    assert no.resolved_tier == "thinking_normal"
    assert yes.resolved_tier == "pro_extended"
