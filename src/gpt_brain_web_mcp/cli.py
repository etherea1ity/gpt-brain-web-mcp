from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .codex_config import merge_config
from .config import Settings
from .installer import doctor as run_doctor
from .tools import WebBrainService, expected_tools


def _print_json(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _codex_config_path() -> Path:
    return Path.home() / ".codex" / "config.toml"


def _install_codex_config(settings: Settings, *, dry_run: bool = False, uninstall: bool = False, headless: bool | None = None) -> dict[str, Any]:
    python_path = sys.executable
    new_text_or_path = merge_config(
        _codex_config_path(),
        python_path,
        str(settings.home),
        dry_run=dry_run,
        uninstall=uninstall,
        headless=settings.headless if headless is None else headless,
        default_project=settings.default_project,
    )
    return {
        "ok": True,
        "dry_run": dry_run,
        "uninstall": uninstall,
        "config_path": str(_codex_config_path()),
        "backup_created": False if dry_run else _codex_config_path().exists(),
        "result": new_text_or_path,
    }


def cmd_install(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if args.visible_browser:
        settings.visible = True; settings.headless = False
    if args.headless:
        settings.visible = False; settings.headless = True
    actions = [
        "check Python 3.11+",
        f"create {settings.home}",
        f"create dedicated browser profile {settings.browser_profile_dir}",
        f"initialize SQLite {settings.db_path}",
        "install package/Playwright via install.sh or pip",
        "install Playwright Chromium",
    ]
    if not args.no_codex_config:
        actions.append(f"merge Codex MCP config at {_codex_config_path()} without overwriting existing content")
    if args.dry_run:
        _print_json({"ok": True, "dry_run": True, "actions": actions, "next": ["gpt-brain-web login", "gpt-brain-web smoke"]})
        return 0
    settings.ensure_dirs()
    from .store import Store
    Store(settings.db_path)
    if args.uninstall:
        if not args.no_codex_config:
            _print_json(_install_codex_config(settings, uninstall=True))
        else:
            _print_json({"ok": True, "uninstall": True, "codex_config": "skipped"})
        return 0
    if not args.no_codex_config:
        _install_codex_config(settings, headless=settings.headless)
    result = run_doctor(settings, verbose=True)
    _print_json({"ok": True, "installed_home": str(settings.home), "doctor": result, "next": ["gpt-brain-web login", "gpt-brain-web smoke"]})
    return 0 if result.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    result = run_doctor(Settings.from_env(), verbose=args.verbose)
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_login(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    settings.visible = True
    settings.headless = False
    settings.mock_browser = False if not args.mock else True
    svc = WebBrainService(settings)
    svc.browser.start_browser()
    timeout_s = int(args.timeout_minutes * 60)
    deadline = time.time() + timeout_s
    print(json.dumps({
        "status": "waiting_for_login",
        "profile_path": str(settings.browser_profile_dir),
        "message": "Dedicated ChatGPT browser window opened. Log in manually; this process will wait until the prompt box is detected.",
        "timeout_minutes": args.timeout_minutes,
    }, indent=2, ensure_ascii=False), flush=True)
    last_state = "unknown"
    try:
        while time.time() < deadline:
            last_state = svc.browser.ensure_login_state()
            if last_state == "logged_in":
                result = {"status": "logged_in", "profile_path": str(settings.browser_profile_dir), "message": "ChatGPT login detected and saved in the dedicated profile."}
                _print_json(result)
                return 0
            time.sleep(2.0)
        _print_json({"status": "needs_user_action", "profile_path": str(settings.browser_profile_dir), "message": "Login was not detected before timeout. Run `gpt-brain-web login` again.", "last_state": last_state})
        return 1
    except KeyboardInterrupt:
        _print_json({"status": "needs_user_action", "profile_path": str(settings.browser_profile_dir), "message": "Login wait interrupted; rerun after completing login if needed.", "last_state": last_state})
        return 130


def cmd_daemon(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if getattr(args, "visible", False):
        settings.visible = True; settings.headless = False
    svc = WebBrainService(settings)
    if args.daemon_cmd == "status":
        _print_json(svc.daemon_status()); return 0
    if args.daemon_cmd == "stop":
        from .web.daemon import stop_pid
        stopped = stop_pid(settings.daemon_pid_path)
        local = svc.cleanup_browser()
        _print_json({"stopped_background_daemon": stopped, **local}); return 0
    if args.daemon_cmd == "start":
        from .web.browser_manager import pid_alive
        pid_text = settings.daemon_pid_path.read_text(encoding="utf-8").strip() if settings.daemon_pid_path.exists() else None
        if pid_alive(pid_text):
            _print_json({"ok": True, "message": "Browser daemon already running.", "status": svc.daemon_status()}); return 0
        if getattr(args, "foreground", False):
            from .web.daemon import serve_forever
            return serve_forever(settings)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        log = open(settings.logs_dir / "daemon.log", "ab", buffering=0)
        cmd = [sys.executable, "-m", "gpt_brain_web_mcp.web.daemon", "--serve"]
        if getattr(args, "visible", False): cmd.append("--visible")
        subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=os.environ.copy())
        time.sleep(0.3)
        _print_json({"ok": True, "message": "Browser daemon launched in background.", "status": svc.daemon_status(), "log_path": str(settings.logs_dir / "daemon.log")})
        return 0
    raise SystemExit(f"unknown daemon command {args.daemon_cmd}")


def cmd_mcp(args: argparse.Namespace) -> int:
    settings = Settings.from_env(); settings.ensure_dirs()
    if args.mcp_cmd == "install-codex":
        _print_json(_install_codex_config(settings, dry_run=args.dry_run)); return 0
    if args.mcp_cmd == "uninstall-codex":
        _print_json(_install_codex_config(settings, dry_run=args.dry_run, uninstall=True)); return 0
    if args.mcp_cmd == "tools":
        _print_json({"tools": expected_tools()}); return 0
    raise SystemExit(f"unknown mcp command {args.mcp_cmd}")


def cmd_policy(args: argparse.Namespace) -> int:
    svc = WebBrainService(Settings.from_env())
    if getattr(args, "resolve", False):
        _print_json(svc.resolve_policy(kind=args.kind, project=args.project, conversation_strategy=args.conversation_strategy, retention=args.retention, cleanup_remote=args.cleanup_remote, save_session=args.save_session, allow_project_fallback=args.allow_project_fallback))
    else:
        _print_json(svc.product_policy())
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    # Default smoke is mock-only for CI; live smoke must be explicit and disables mock.
    if os.getenv("RUN_LIVE_CHATGPT_WEB"):
        os.environ["GPT_BRAIN_WEB_MOCK"] = "0"
    else:
        os.environ["GPT_BRAIN_WEB_MOCK"] = "1"
    settings = Settings.from_env()
    svc = WebBrainService(settings)
    result = svc.tool_ask_brain(question="Reply with exactly: GPT_BRAIN_WEB_SMOKE_OK", save_session=False, conversation_strategy="new", retention="ephemeral", cleanup_remote=bool(os.getenv("RUN_LIVE_CHATGPT_WEB")))
    ok = str(result.get("answer", "")).strip() == "GPT_BRAIN_WEB_SMOKE_OK"
    _print_json({"ok": ok, "mode": "live" if os.getenv("RUN_LIVE_CHATGPT_WEB") else "mock", "result": result})
    return 0 if ok else 1


def cmd_cleanup(args: argparse.Namespace) -> int:
    svc = WebBrainService(Settings.from_env())
    _print_json(svc.cleanup_browser())
    return 0


def cmd_ui_check(args: argparse.Namespace) -> int:
    svc = WebBrainService(Settings.from_env())
    result = svc.ui_capabilities_check(visible=args.visible)
    _print_json(result)
    return 0 if result.get("ok") else 1


def cmd_records(args: argparse.Namespace) -> int:
    svc = WebBrainService(Settings.from_env())
    if args.records_cmd == "list":
        _print_json(svc.list_web_sessions(args.project, args.limit)); return 0
    if args.records_cmd == "delete":
        _print_json(svc.delete_local_record(args.record_id, args.record_type, not args.keep_artifact)); return 0
    if args.records_cmd == "purge-project":
        _print_json(svc.purge_project_records(args.project, args.include_thread)); return 0
    if args.records_cmd == "delete-remote":
        _print_json(svc.delete_remote_conversation(args.conversation_url, args.confirm)); return 0
    if args.records_cmd == "list-projects":
        _print_json(svc.list_projects(args.limit)); return 0
    if args.records_cmd == "open-project":
        _print_json(svc.open_project(args.project)); return 0
    if args.records_cmd == "create-project":
        _print_json(svc.create_project(args.project, args.confirm)); return 0
    if args.records_cmd == "start-project-conversation":
        _print_json(svc.start_project_conversation(args.project, args.question, args.tier, args.cleanup_remote)); return 0
    if args.records_cmd == "delete-project":
        _print_json(svc.delete_remote_project(args.project, args.confirm, args.confirm_name, args.purge_local)); return 0
    if args.records_cmd == "cleanup-list":
        _print_json(svc.list_remote_cleanup(args.status, args.project, args.limit)); return 0
    if args.records_cmd == "cleanup-remote":
        _print_json(svc.cleanup_remote_conversations(confirm=args.confirm, dry_run=args.dry_run, status=args.status, project=args.project, limit=args.limit, cleanup_id=args.cleanup_id)); return 0
    raise SystemExit(f"unknown records command {args.records_cmd}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gpt-brain-web", description="ChatGPT Web Brain Gateway MCP utilities")
    p.add_argument("--version", action="store_true")
    sub = p.add_subparsers(dest="cmd")

    install = sub.add_parser("install", help="Initialize local home/db/profile and merge Codex MCP config")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--no-codex-config", action="store_true")
    install.add_argument("--visible-browser", action="store_true")
    install.add_argument("--headless", action="store_true")
    install.add_argument("--uninstall", action="store_true")
    install.set_defaults(func=cmd_install)

    doctor = sub.add_parser("doctor", help="Run diagnostics")
    doctor.add_argument("--verbose", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    login = sub.add_parser("login", help="Open dedicated ChatGPT login window and wait for manual login")
    login.add_argument("--mock", action="store_true", help="Use mock browser for CI/smoke only")
    login.add_argument("--timeout-minutes", type=float, default=30.0, help="How long to keep the login window open while waiting for manual login")
    login.set_defaults(func=cmd_login)

    daemon = sub.add_parser("daemon", help="Manage browser worker process/context")
    daemon_sub = daemon.add_subparsers(dest="daemon_cmd", required=True)
    dstart = daemon_sub.add_parser("start")
    dstart.add_argument("--visible", action="store_true")
    dstart.add_argument("--foreground", action="store_true", help="Run daemon in the foreground instead of spawning a background process")
    dstart.set_defaults(func=cmd_daemon)
    daemon_sub.add_parser("stop").set_defaults(func=cmd_daemon)
    daemon_sub.add_parser("status").set_defaults(func=cmd_daemon)

    mcp = sub.add_parser("mcp", help="Codex MCP config helpers")
    mcp_sub = mcp.add_subparsers(dest="mcp_cmd", required=True)
    mi = mcp_sub.add_parser("install-codex")
    mi.add_argument("--dry-run", action="store_true")
    mi.set_defaults(func=cmd_mcp)
    mu = mcp_sub.add_parser("uninstall-codex")
    mu.add_argument("--dry-run", action="store_true")
    mu.set_defaults(func=cmd_mcp)
    mcp_sub.add_parser("tools").set_defaults(func=cmd_mcp)

    policy = sub.add_parser("policy", help="Print the product workflow policy or resolve one request")
    policy.add_argument("--resolve", action="store_true", help="Resolve effective policy for a request")
    policy.add_argument("--kind", choices=["ask", "research"], default="ask")
    policy.add_argument("--project")
    policy.add_argument("--conversation-strategy")
    policy.add_argument("--retention")
    policy.add_argument("--cleanup-remote", action="store_true", default=None)
    policy.add_argument("--save-session", action="store_true", default=None)
    policy.add_argument("--allow-project-fallback", action="store_true", default=None)
    policy.set_defaults(func=cmd_policy)

    sub.add_parser("smoke", help="Run mock smoke unless RUN_LIVE_CHATGPT_WEB=1").set_defaults(func=cmd_smoke)
    sub.add_parser("cleanup", help="Close browser worker but preserve profile").set_defaults(func=cmd_cleanup)
    ui = sub.add_parser("ui-check", help="Check Deep Research and Search UI without sending a prompt")
    ui.add_argument("--visible", action="store_true")
    ui.set_defaults(func=cmd_ui_check)
    records = sub.add_parser("records", help="List/delete local SQLite session/job records")
    records_sub = records.add_subparsers(dest="records_cmd", required=True)
    rlist = records_sub.add_parser("list")
    rlist.add_argument("--project")
    rlist.add_argument("--limit", type=int, default=20)
    rlist.set_defaults(func=cmd_records)
    rdel = records_sub.add_parser("delete")
    rdel.add_argument("record_id")
    rdel.add_argument("--record-type", choices=["auto", "session", "job"], default="auto")
    rdel.add_argument("--keep-artifact", action="store_true")
    rdel.set_defaults(func=cmd_records)
    rpurge = records_sub.add_parser("purge-project")
    rpurge.add_argument("project")
    rpurge.add_argument("--include-thread", action="store_true", help="Also remove the local project->conversation pointer")
    rpurge.set_defaults(func=cmd_records)
    rremote = records_sub.add_parser("delete-remote", help="Delete an explicit ChatGPT /c/... conversation from the dedicated profile")
    rremote.add_argument("conversation_url")
    rremote.add_argument("--confirm", action="store_true", help="Required; confirms remote deletion in ChatGPT Web UI")
    rremote.set_defaults(func=cmd_records)
    rplist = records_sub.add_parser("list-projects", help="List visible ChatGPT Projects from the dedicated profile")
    rplist.add_argument("--limit", type=int, default=50)
    rplist.set_defaults(func=cmd_records)
    ropenp = records_sub.add_parser("open-project", help="Open a ChatGPT Project by exact visible name")
    ropenp.add_argument("project")
    ropenp.set_defaults(func=cmd_records)
    rcreatep = records_sub.add_parser("create-project", help="Create a disposable/explicit ChatGPT Project")
    rcreatep.add_argument("project")
    rcreatep.add_argument("--confirm", action="store_true")
    rcreatep.set_defaults(func=cmd_records)
    rstartp = records_sub.add_parser("start-project-conversation", help="Start a new conversation inside a ChatGPT Project")
    rstartp.add_argument("project")
    rstartp.add_argument("--question")
    rstartp.add_argument("--tier")
    rstartp.add_argument("--cleanup-remote", action="store_true")
    rstartp.set_defaults(func=cmd_records)
    rdelp = records_sub.add_parser("delete-project", help="Delete a ChatGPT Project; requires confirm and matching confirm-name")
    rdelp.add_argument("project")
    rdelp.add_argument("--confirm", action="store_true")
    rdelp.add_argument("--confirm-name")
    rdelp.add_argument("--purge-local", action="store_true")
    rdelp.set_defaults(func=cmd_records)
    rclist = records_sub.add_parser("cleanup-list", help="List queued remote ChatGPT conversation cleanup items")
    rclist.add_argument("--status", default=None)
    rclist.add_argument("--project")
    rclist.add_argument("--limit", type=int, default=50)
    rclist.set_defaults(func=cmd_records)
    rclean = records_sub.add_parser("cleanup-remote", help="Process queued remote ChatGPT conversation cleanup items")
    rclean.add_argument("--confirm", action="store_true", help="Required for actual remote deletion")
    rclean.add_argument("--dry-run", action="store_true", default=False, help="Preview deletions without touching ChatGPT")
    rclean.add_argument("--status", default="pending")
    rclean.add_argument("--project")
    rclean.add_argument("--limit", type=int, default=20)
    rclean.add_argument("--cleanup-id")
    rclean.set_defaults(func=cmd_records)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__); return 0
    if not getattr(args, "cmd", None):
        parser.print_help(); return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
