from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.store import Store
from gpt_brain_web_mcp.tools import WebBrainService
from gpt_brain_web_mcp.web.browser_manager import BrowserSessionManager


def test_ensure_login_state_persists_logged_in_and_needs_user_action(tmp_path):
    settings = Settings(home=tmp_path, mock_browser=True)
    store = Store(settings.db_path)
    manager = BrowserSessionManager(settings, store)
    assert manager.ensure_login_state() == "logged_in"
    assert store.get_profile()["login_state"] == "logged_in"
    manager.mock_page.logged_in = False
    assert manager.ensure_login_state() == "needs_user_action"
    assert store.get_profile()["login_state"] == "needs_user_action"


def test_open_login_window_returns_state_contract(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    res = svc.open_login_window(visible=True)
    assert res["status"] == "logged_in"
    assert res["profile_path"].endswith("browser-profile")
    svc.browser.mock_page.logged_in = False
    res2 = svc.open_login_window(visible=True)
    assert res2["status"] == "needs_user_action"
