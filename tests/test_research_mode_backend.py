from gpt_brain_web_mcp.web.research_mode import ResearchModeManager
from gpt_brain_web_mcp.backends.web_chatgpt import WebChatGPTBackend
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.models import BrainRequest
from gpt_brain_web_mcp.store import Store
from tests.test_project_fail_closed import FakeBrowser, FakePage


class DeepPage(FakePage):
    def __init__(self, enabled=True):
        super().__init__(project_ok=True)
        self.enabled = enabled
        self.deep_enabled_called = False
    def enable_deep_research(self):
        self.deep_enabled_called = True
        return self.enabled
    def disable_deep_research(self):
        return True


def test_research_mode_opens_plus_menu_instead_of_only_scanning_body():
    page = DeepPage(enabled=True)
    resolved, warnings = ResearchModeManager().resolve_mode(page, requested_deep=True)
    assert resolved == "deep_research"
    assert warnings == []
    assert page.deep_enabled_called is True


def test_backend_selects_research_mode_after_new_chat_before_submit(tmp_path):
    page = DeepPage(enabled=True)
    backend = WebChatGPTBackend(Settings(home=tmp_path, mock_browser=True), Store(tmp_path / "brain.db"), FakeBrowser(page))
    req = BrainRequest(question="research", project="Codex Brain", tier="thinking_heavy", project_explicit=False, conversation_strategy="new", requested_research_mode="deep_research")
    res = backend.ask_web(req, None)
    assert res.answer == "OK"
    assert res.requested_research_mode == "deep_research"
    assert res.resolved_research_mode == "deep_research"
    assert page.new_chat_called is True
    assert page.deep_enabled_called is True
