from __future__ import annotations

import json
import os
import time

from gpt_brain_web_mcp.tools import WebBrainService


def main() -> int:
    if os.getenv("RUN_LIVE_CHATGPT_WEB") != "1":
        print(json.dumps({"ok": False, "skipped": True, "reason": "Set RUN_LIVE_CHATGPT_WEB=1 after `gpt-brain-web login`."}, indent=2))
        return 0
    os.environ["GPT_BRAIN_WEB_MOCK"] = "0"
    svc = WebBrainService()
    report = {"ok": False, "steps": []}

    doctor = svc.doctor(verbose=True)
    report["steps"].append({"name": "doctor", "ok": doctor.get("ok"), "result": doctor})
    if not doctor.get("ok"):
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    ask = svc.tool_ask_brain(question="Reply with exactly: GPT_BRAIN_WEB_LIVE_OK", save_session=True)
    ask_ok = "GPT_BRAIN_WEB_LIVE_OK" in str(ask.get("answer"))
    report["steps"].append({"name": "ask_brain", "ok": ask_ok, "result": ask})
    if not ask_ok:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    web = svc.tool_ask_web(question="Search the web for today's date and reply in one sentence with at least one source URL.", save_session=True)
    web_ok = bool(web.get("answer")) and bool(web.get("sources"))
    report["steps"].append({"name": "ask_web", "ok": web_ok, "result": web})
    if not web_ok:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    started = svc.start_research(topic="Using web sources, in one short paragraph summarize what the Model Context Protocol is and cite source URLs.", output_format="bullet_summary", max_runtime_hint_minutes=5)
    job_id = started["job_id"]
    result = None
    for _ in range(120):
        result = svc.get_research_result(job_id)
        if result["status"] in {"completed", "failed", "cancelled", "needs_user_action"}:
            break
        time.sleep(1)
    research_text = str((result or {}).get("result") or "").strip()
    incomplete_prefixes = (
        "i'll verify", "i’ll verify", "i will verify",
        "i'll search", "i’ll search", "i will search",
        "i'll ground", "i’ll ground", "i will ground",
        "i'll research", "i’ll research", "i will research",
    )
    research_ok = bool(result and result.get("status") == "completed" and research_text and not research_text.lower().startswith(incomplete_prefixes))
    report["steps"].append({"name": "start_research", "ok": research_ok, "started": started, "result": result})
    report["ok"] = all(step.get("ok") for step in report["steps"])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
