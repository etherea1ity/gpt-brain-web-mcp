from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.installer import doctor


def test_doctor_mock_passes_and_reports_login(tmp_path):
    result = doctor(Settings(home=tmp_path, mock_browser=True), verbose=True)
    assert result["ok"] is True
    names = {c["name"]: c for c in result["checks"]}
    assert names["login_state"]["ok"] is True
    assert names["browser_profile_dir"]["ok"] is True
    assert "playwright_installed" in names
