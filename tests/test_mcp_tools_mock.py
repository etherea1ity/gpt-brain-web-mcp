from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.server import create_mcp
from gpt_brain_web_mcp.tools import WebBrainService, expected_tools


def test_mcp_tools_and_mock_calls(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    mcp = create_mcp(svc)
    assert mcp is not None
    assert "ask_brain" in expected_tools()
    result = svc.tool_ask_brain(question="Reply with exactly: MCP_OK")
    assert "MCP_OK" in result["answer"]
    web = svc.tool_ask_web(question="find source")
    assert web["sources"]
