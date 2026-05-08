from gpt_brain_web_mcp.backends.web_chatgpt import WebChatGPTBackend
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.models import BrainRequest
from gpt_brain_web_mcp.store import Store


class FakePage:
    available_mode_labels = ["Thinking Heavy"]
    selected_tier = None
    conversation_url = None
    last_answer = ""
    sources = []

    def __init__(self, project_ok=True):
        self.project_ok = project_ok
        self.new_chat_called = False
        self.submitted = False

    def ensure_logged_in(self): pass
    def open_project(self, project): return self.project_ok
    def start_new_chat(self, project_name=None):
        self.new_chat_called = True
        return self.project_ok
    def select_mode_label(self, label):
        self.selected_tier = label
        return label == "Thinking Heavy"
    def submit_prompt(self, prompt, web_search=False):
        self.submitted = True
        self.last_answer = "OK"
    def current_conversation_url(self, fallback=None): return fallback


class FakeBrowser:
    def __init__(self, page): self.page = page
    def acquire_page(self, job_key): return self.page
    def release_page(self, job_key): pass
    def create_or_reuse_conversation(self, project, kind, force_new=False): return f"chatgpt://local/project/{project}"


def test_explicit_project_missing_fails_closed(tmp_path):
    page = FakePage(project_ok=False)
    backend = WebChatGPTBackend(Settings(home=tmp_path, mock_browser=True), Store(tmp_path / "brain.db"), FakeBrowser(page))
    req = BrainRequest(question="x", project="Missing", tier="thinking_heavy", project_explicit=True, conversation_strategy="new")
    res = backend.ask_brain(req, "ses_test")
    assert res.answer == ""
    assert page.submitted is False
    assert any("fresh ChatGPT conversation" in w or "could not be opened" in w for w in res.warnings)


def test_new_strategy_invokes_real_new_chat_before_submit(tmp_path):
    page = FakePage(project_ok=True)
    backend = WebChatGPTBackend(Settings(home=tmp_path, mock_browser=True), Store(tmp_path / "brain.db"), FakeBrowser(page))
    req = BrainRequest(question="x", project="P", tier="thinking_heavy", project_explicit=True, conversation_strategy="new")
    res = backend.ask_brain(req, "ses_test")
    assert res.answer == "OK"
    assert page.new_chat_called is True
    assert page.submitted is True


def test_implicit_default_project_starts_global_new_chat_without_project_binding(tmp_path):
    page = FakePage(project_ok=True)
    class RecordingBrowser(FakeBrowser):
        def __init__(self, page):
            super().__init__(page)
            self.calls = []
        def create_or_reuse_conversation(self, project, kind, force_new=False):
            self.calls.append((project, kind, force_new))
            return f"chatgpt://local/project/{project or 'global'}"
    browser = RecordingBrowser(page)
    store = Store(tmp_path / "brain.db")
    backend = WebChatGPTBackend(Settings(home=tmp_path, mock_browser=True), store, browser)
    req = BrainRequest(question="x", project="Codex Brain", tier="thinking_heavy", project_explicit=False, conversation_strategy="new")
    res = backend.ask_brain(req, None)
    assert res.answer == "OK"
    assert browser.calls == [(None, "project", True)]
    assert page.new_chat_called is True
    assert store.find_project_session("Codex Brain") is None


def test_implicit_new_chat_missing_fails_closed(tmp_path):
    page = FakePage(project_ok=False)
    backend = WebChatGPTBackend(Settings(home=tmp_path, mock_browser=True), Store(tmp_path / "brain.db"), FakeBrowser(page))
    req = BrainRequest(question="x", project="Codex Brain", tier="thinking_heavy", project_explicit=False, conversation_strategy="new")
    res = backend.ask_brain(req, None)
    assert res.answer == ""
    assert page.submitted is False
    assert any("fresh ChatGPT conversation" in w for w in res.warnings)
