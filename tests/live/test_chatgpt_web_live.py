import os, pytest
from gpt_brain_web_mcp.tools import WebBrainService


@pytest.mark.skipif(os.getenv("RUN_LIVE_CHATGPT_WEB") != "1", reason="live ChatGPT web test gated")
def test_live_chatgpt_web_short_prompt():
    result = WebBrainService().tool_ask_brain(question="Reply with exactly: LIVE_CHATGPT_WEB_OK", save_session=True)
    assert "LIVE_CHATGPT_WEB_OK" in str(result.get("answer"))
