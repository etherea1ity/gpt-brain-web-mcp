from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.tools import WebBrainService


def test_remote_delete_requires_confirm_and_chatgpt_url(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    no = svc.delete_remote_conversation("https://chatgpt.com/c/abc", confirm=False)
    bad = svc.delete_remote_conversation("https://example.com/c/abc", confirm=True)
    yes = svc.delete_remote_conversation("https://chatgpt.com/c/abc", confirm=True)
    assert no["deleted"] is False and "confirm" in no["error"]
    assert bad["deleted"] is False and "chatgpt.com" in bad["error"]
    assert yes["deleted"] is True
