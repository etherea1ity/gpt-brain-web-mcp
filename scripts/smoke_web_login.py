from __future__ import annotations
import json, os
from gpt_brain_web_mcp.tools import WebBrainService

if not os.getenv("RUN_LIVE_CHATGPT_WEB"):
    print(json.dumps({"skipped": True, "reason": "Set RUN_LIVE_CHATGPT_WEB=1 after gpt-brain-web login."}, indent=2))
    raise SystemExit(0)
svc = WebBrainService()
result = svc.tool_ask_brain(question="Reply with exactly: LIVE_CHATGPT_WEB_OK", save_session=True)
ok = "LIVE_CHATGPT_WEB_OK" in str(result.get("answer"))
print(json.dumps({"ok": ok, "result": result}, indent=2, ensure_ascii=False))
raise SystemExit(0 if ok else 1)
