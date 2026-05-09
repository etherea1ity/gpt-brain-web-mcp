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
    live_project = os.getenv("GPT_BRAIN_LIVE_PROJECT")
    cleanup_ids = []
    report = {"ok": False, "steps": [], "cleanup": [], "remote_cleanup": [], "live_project": live_project}

    doctor = svc.doctor(verbose=True)
    report["steps"].append({"name": "doctor", "ok": doctor.get("ok"), "result": doctor})
    if not doctor.get("ok"):
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    ask = svc.tool_ask_brain(question="Reply with exactly: GPT_BRAIN_WEB_LIVE_OK", project=live_project, save_session=False, conversation_strategy="new", retention="ephemeral", cleanup_remote=True)
    ask_ok = "GPT_BRAIN_WEB_LIVE_OK" in str(ask.get("answer"))
    report["steps"].append({"name": "ask_brain", "ok": ask_ok, "result": ask})
    if not ask_ok:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    web = svc.tool_ask_web(question="Search the web for today's date and reply in one sentence with at least one source URL.", project=live_project, save_session=False, conversation_strategy="new", retention="ephemeral", cleanup_remote=True)
    web_ok = bool(web.get("answer")) and bool(web.get("sources"))
    report["steps"].append({"name": "ask_web", "ok": web_ok, "result": web})
    if not web_ok:
        print(json.dumps(report, indent=2, ensure_ascii=False)); return 1

    research_timeout = int(os.getenv("GPT_BRAIN_LIVE_RESEARCH_TIMEOUT_SECONDS", "900"))
    started = svc.start_research(topic="Using web sources, in one short paragraph summarize what the Model Context Protocol is and cite source URLs.", project=live_project, output_format="bullet_summary", max_runtime_hint_minutes=max(5, research_timeout // 60), retention="ephemeral", cleanup_remote=True)
    job_id = started["job_id"]
    cleanup_ids.append(job_id)
    result = None
    deadline = time.time() + research_timeout
    last_status = None
    while time.time() < deadline:
        result = svc.get_research_result(job_id)
        if result.get("status") != last_status:
            report["steps"].append({"name": "research_status", "ok": True, "status": result.get("status"), "updated_at": result.get("updated_at")})
            last_status = result.get("status")
        if result["status"] in {"completed", "failed", "cancelled", "needs_user_action"}:
            break
        time.sleep(5)
    research_text = str((result or {}).get("result") or "").strip()
    incomplete_prefixes = (
        "i'll verify", "i’ll verify", "i will verify",
        "i'll search", "i’ll search", "i will search",
        "i'll ground", "i’ll ground", "i will ground",
        "i'll research", "i’ll research", "i will research",
    )
    bogus_markers = ("chat history", "new chat", "search chats", "chatgpt can make mistakes", "use chatgpt web/search capability", "error in message stream", "something went wrong")
    research_ok = bool(
        result
        and result.get("status") == "completed"
        and research_text
        and not research_text.lower().startswith(incomplete_prefixes)
        and not any(marker in research_text.lower()[:1200] for marker in bogus_markers)
    )
    report["steps"].append({"name": "start_research", "ok": research_ok, "started": started, "result": result})
    report["ok"] = all(step.get("ok") for step in report["steps"] if step.get("name") != "research_status")
    report["remote_cleanup"].append(svc.cleanup_remote_conversations(confirm=True, dry_run=False, limit=20))
    for rid in cleanup_ids:
        report["cleanup"].append(svc.delete_local_record(rid))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
