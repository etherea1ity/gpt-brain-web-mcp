from pathlib import Path
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.store import Store
from gpt_brain_web_mcp.web.browser_manager import BrowserSessionManager


def test_dedicated_profile_and_background_defaults(tmp_path):
    settings = Settings(home=tmp_path, mock_browser=True)
    store = Store(settings.db_path)
    manager = BrowserSessionManager(settings, store)
    assert manager.status().headless is True
    assert Path(manager.status().profile_path) == tmp_path / "browser-profile"
    assert "Chrome" not in str(settings.browser_profile_dir)
    manager.start_browser()
    p1 = manager.ensure_context()
    p2 = manager.ensure_context()
    assert p1 is p2


def test_login_state_needs_user_action(tmp_path):
    settings = Settings(home=tmp_path, mock_browser=True)
    store = Store(settings.db_path)
    manager = BrowserSessionManager(settings, store)
    manager.mock_page.logged_in = False
    try:
        manager.mock_page.ensure_logged_in()
    except Exception as exc:
        assert "login" in str(exc).lower()


def test_windows_cdp_fallback_binds_localhost_only(tmp_path):
    settings = Settings(home=tmp_path, mock_browser=True)
    manager = BrowserSessionManager(settings, Store(settings.db_path))
    args = manager._windows_browser_args("chrome.exe", 49222, r"C:\Users\me\.gpt-brain-web\browser-profile")
    assert "--remote-debugging-address=127.0.0.1" in args
    assert "--remote-debugging-address=0.0.0.0" not in args
