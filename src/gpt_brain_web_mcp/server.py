from __future__ import annotations

import argparse, json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from . import __version__
from .tools import WebBrainService, expected_tools, get_service


class SyncToolRunner:
    """Run sync browser-backed tool code outside the MCP asyncio loop.

    Playwright's sync API refuses to run in an active asyncio loop. FastMCP
    tool handlers execute under an async server, so all browser operations are
    serialized through one worker thread. This also preserves Playwright's
    thread-affinity for the managed browser context.
    """

    def __init__(self, service: WebBrainService | None = None):
        self.service = service
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpt-brain-web-mcp")

    def _svc(self) -> WebBrainService:
        if self.service is None:
            self.service = get_service()
        return self.service

    async def run(self, method: str, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self.executor, lambda: getattr(self._svc(), method)(*args, **kwargs))


def create_mcp(service=None):
    from mcp.server.fastmcp import FastMCP
    runner = SyncToolRunner(service)
    mcp = FastMCP("gpt-brain-web-mcp")

    @mcp.tool()
    async def ask_brain(question: str, project: str | None = None, context: str | None = None, tier: str | None = None, allow_pro: bool = False, web_search: bool = False, async_request: bool = False, save_session: bool = False, conversation_strategy: str | None = None, session_id: str | None = None, conversation_url: str | None = None, allow_project_fallback: bool = False, retention: str | None = None, cleanup_remote: bool = False) -> dict[str, Any]:
        return await runner.run("tool_ask_brain", question=question, project=project, context=context, tier=tier, allow_pro=allow_pro, web_search=web_search, async_request=async_request, save_session=save_session, conversation_strategy=conversation_strategy, session_id=session_id, conversation_url=conversation_url, allow_project_fallback=allow_project_fallback, retention=retention, cleanup_remote=cleanup_remote)

    @mcp.tool()
    async def ask_web(question: str, project: str | None = None, context: str | None = None, tier: str | None = None, allow_pro: bool = False, save_session: bool = False, conversation_strategy: str | None = None, session_id: str | None = None, conversation_url: str | None = None, allow_project_fallback: bool = False, retention: str | None = None, cleanup_remote: bool = False) -> dict[str, Any]:
        return await runner.run("tool_ask_web", question=question, project=project, context=context, tier=tier, allow_pro=allow_pro, save_session=save_session, conversation_strategy=conversation_strategy, session_id=session_id, conversation_url=conversation_url, allow_project_fallback=allow_project_fallback, retention=retention, cleanup_remote=cleanup_remote)

    @mcp.tool()
    async def start_research(topic: str, project: str | None = None, context: str | None = None, tier: str | None = None, allow_pro: bool = False, deep_research: bool = True, output_format: str = "report", max_runtime_hint_minutes: int = 30, allow_project_fallback: bool = False, retention: str | None = None, cleanup_remote: bool = False) -> dict[str, Any]:
        return await runner.run("start_research", topic=topic, project=project, context=context, tier=tier, allow_pro=allow_pro, deep_research=deep_research, output_format=output_format, max_runtime_hint_minutes=max_runtime_hint_minutes, allow_project_fallback=allow_project_fallback, retention=retention, cleanup_remote=cleanup_remote)

    @mcp.tool()
    async def get_research_result(job_id: str) -> dict[str, Any]: return await runner.run("get_research_result", job_id)
    @mcp.tool()
    async def get_job_result(job_id: str) -> dict[str, Any]: return await runner.run("get_job_result", job_id)
    @mcp.tool()
    async def cancel_research_job(job_id: str) -> dict[str, str]: return await runner.run("cancel_research_job", job_id)
    @mcp.tool()
    async def delete_local_record(record_id: str, record_type: str = "auto", delete_artifact: bool = True) -> dict[str, Any]: return await runner.run("delete_local_record", record_id, record_type, delete_artifact)
    @mcp.tool()
    async def purge_project_records(project: str, include_thread: bool = False) -> dict[str, Any]: return await runner.run("purge_project_records", project, include_thread)
    @mcp.tool()
    async def delete_remote_conversation(conversation_url: str, confirm: bool = False) -> dict[str, Any]: return await runner.run("delete_remote_conversation", conversation_url, confirm)
    @mcp.tool()
    async def list_remote_cleanup(status: str | None = None, project: str | None = None, limit: int = 50) -> dict[str, Any]: return await runner.run("list_remote_cleanup", status, project, limit)
    @mcp.tool()
    async def cleanup_remote_conversations(confirm: bool = False, dry_run: bool = True, status: str = "pending", project: str | None = None, limit: int = 20, cleanup_id: str | None = None) -> dict[str, Any]: return await runner.run("cleanup_remote_conversations", confirm, dry_run, status, project, limit, cleanup_id)
    @mcp.tool()
    async def ui_capabilities_check(visible: bool = False) -> dict[str, Any]: return await runner.run("ui_capabilities_check", visible)
    @mcp.tool()
    async def list_web_sessions(project: str | None = None, limit: int = 20) -> dict[str, Any]: return await runner.run("list_web_sessions", project, limit)
    @mcp.tool()
    async def open_login_window(visible: bool = True) -> dict[str, Any]: return await runner.run("open_login_window", visible)
    @mcp.tool()
    async def doctor(verbose: bool = False) -> dict[str, Any]: return await runner.run("doctor", verbose)
    @mcp.tool()
    async def cleanup_browser() -> dict[str, Any]: return await runner.run("cleanup_browser")
    @mcp.tool()
    async def daemon_status() -> dict[str, Any]: return await runner.run("daemon_status")
    return mcp


def main() -> None:
    p = argparse.ArgumentParser(description="ChatGPT Web Brain Gateway MCP Server")
    p.add_argument("--version", action="store_true"); p.add_argument("--list-tools", action="store_true"); p.add_argument("--doctor", action="store_true"); p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    if args.version: print(__version__); return
    if args.list_tools: print(json.dumps({"tools": expected_tools()}, indent=2)); return
    if args.doctor:
        result = get_service().doctor(args.verbose); print(json.dumps(result, indent=2, ensure_ascii=False)); raise SystemExit(0 if result.get("ok") else 1)
    create_mcp().run()

if __name__ == "__main__": main()
