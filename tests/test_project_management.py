from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService, expected_tools


def test_project_management_tools_listed():
    tools = set(expected_tools())
    assert {"list_projects", "open_project", "create_project", "start_project_conversation", "delete_remote_project"}.issubset(tools)


def test_mock_project_management_guards(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    assert svc.open_project("P")["opened"] is True
    assert svc.create_project("P")["created"] is False
    assert "confirm=true" in svc.create_project("P")["error"]
    assert svc.create_project("P", confirm=True)["created"] is True
    assert svc.start_project_conversation("P")["started"] is True
    assert svc.delete_remote_project("P", confirm=True, confirm_name="wrong")["deleted"] is False
    assert svc.delete_remote_project("P", confirm=True, confirm_name="P")["deleted"] is True
