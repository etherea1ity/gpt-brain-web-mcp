from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "ask_brain",
    "ask_web",
    "start_research",
    "get_research_result",
    "get_job_result",
    "cancel_research_job",
    "delete_local_record",
    "purge_project_records",
    "delete_remote_conversation",
    "list_remote_cleanup",
    "cleanup_remote_conversations",
    "ui_capabilities_check",
    "list_web_sessions",
    "open_login_window",
    "doctor",
    "cleanup_browser",
    "daemon_status",
}


def _decode_tool_result(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None) or getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", [])
    if not content:
        return None
    text = getattr(content[0], "text", None)
    if text is None:
        return content[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def _run() -> dict[str, Any]:
    live = os.getenv("RUN_LIVE_CHATGPT_WEB") == "1"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if live:
        env["GPT_BRAIN_WEB_MOCK"] = "0"
    else:
        env["GPT_BRAIN_WEB_MOCK"] = "1"

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "gpt_brain_web_mcp.server"],
        cwd=str(ROOT),
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tools = sorted(t.name for t in tools_result.tools)
            nonce = "MCP_LIVE_SMOKE_OK" if live else "MCP_SMOKE_OK"
            call = await session.call_tool(
                "ask_brain",
                {
                    "question": f"Reply with exactly: {nonce}",
                    "save_session": False,
                    "conversation_strategy": "new",
                    "retention": "ephemeral",
                    "cleanup_remote": live,
                },
            )
            decoded = _decode_tool_result(call)
            answer = decoded.get("answer") if isinstance(decoded, dict) else str(decoded)
            normalized_answer = "".join(ch for ch in str(answer) if ch.isalnum()).upper()
            normalized_nonce = "".join(ch for ch in nonce if ch.isalnum()).upper()
            ok = EXPECTED.issubset(set(tools)) and normalized_nonce in normalized_answer
            return {
                "ok": ok,
                "mode": "live" if live else "mock",
                "transport": "mcp_stdio_client",
                "tools": tools,
                "result": decoded,
            }


def main() -> int:
    report = anyio.run(_run)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
