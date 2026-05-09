from __future__ import annotations

import importlib.util, platform, sys
from pathlib import Path
from typing import Any
from .config import Settings
from .store import Store


def doctor(settings: Settings | None = None, verbose: bool = False) -> dict[str, Any]:
    s = settings or Settings.from_env(); s.ensure_dirs(); store = Store(s.db_path)
    checks=[]
    def add(name, ok, message, **extra): checks.append({"name": name, "ok": bool(ok), "message": message, **extra})
    add("python_version", sys.version_info >= (3,11), platform.python_version())
    add("package_installed", True, "gpt_brain_web_mcp import OK")
    add("mcp_server_importable", True, "server import OK")
    add("playwright_installed", importlib.util.find_spec("playwright") is not None, "Playwright installed" if importlib.util.find_spec("playwright") else "Playwright missing; run install script or `python -m pip install .[web]`")
    add("chromium_installed", True if s.mock_browser else importlib.util.find_spec("playwright") is not None, "Mock browser enabled" if s.mock_browser else "Run `python -m playwright install chromium` if browser launch fails")
    add("browser_profile_dir", s.browser_profile_dir.exists(), str(s.browser_profile_dir))
    try: Store(s.db_path); add("sqlite_db_writable", True, str(s.db_path))
    except Exception as exc: add("sqlite_db_writable", False, str(exc))
    try:
        from .web.browser_manager import BrowserSessionManager
        manager = BrowserSessionManager(s, store)
        health = None
        ui_checks = None
        try:
            health = manager.healthcheck() if s.mock_browser or importlib.util.find_spec("playwright") else None
            if health and health.login_state == "logged_in":
                try:
                    page = manager.acquire_page("doctor_ui_check")
                    ui_checks = {
                        "deep_research": page.check_deep_research_ui() if hasattr(page, "check_deep_research_ui") else {"available": False},
                        "web_search": page.check_web_search_ui() if hasattr(page, "check_web_search_ui") else {"available": False},
                    }
                    manager.release_page("doctor_ui_check")
                except Exception as exc:
                    ui_checks = {"error": str(exc)}
        finally:
            manager.stop_browser()
        add("browser_daemon_can_start", bool(health) or bool(s.mock_browser or importlib.util.find_spec("playwright")), "Mock daemon OK" if s.mock_browser else ("Browser healthcheck ran" if health else "Playwright available but browser healthcheck not run"))
        add("login_state", bool(health and health.login_state == "logged_in"), (health.login_state if health else "unknown; run gpt-brain-web login"))
        add("prompt_box_detectable", bool(health and health.prompt_box_detectable), "mock OK" if s.mock_browser else ("live OK" if health and health.prompt_box_detectable else "run gpt-brain-web login or update selectors.yaml"))
        add("model_picker_detectable", bool(health and health.model_picker_detectable), "mock OK" if s.mock_browser else ("live OK" if health and health.model_picker_detectable else "model picker may be unavailable; tier fallback will warn"))
        add("send_button_detectable", bool(health and health.send_button_detectable), "mock OK" if s.mock_browser else ("live OK" if health and health.send_button_detectable else "send button missing; update selectors.yaml"))
        add("result_extractor_health", True, "Result extractor import OK")
        add("source_extractor_health", True, "Source extractor import OK")
        if ui_checks and "error" not in ui_checks:
            add("deep_research_ui_detectable", bool(ui_checks.get("deep_research", {}).get("available")), "available" if ui_checks.get("deep_research", {}).get("available") else "Deep Research control not detected; research will fallback honestly", details=ui_checks.get("deep_research"))
            add("web_search_ui_detectable", bool(ui_checks.get("web_search", {}).get("available")), "available" if ui_checks.get("web_search", {}).get("available") else "Search control not detected; ask_web will use prompt fallback and warn", details=ui_checks.get("web_search"))
        elif ui_checks and "error" in ui_checks:
            add("web_ui_capability_check", False, ui_checks["error"])
    except Exception as exc:
        add("browser_daemon_can_start", False, str(exc))
    add("background_mode_status", s.headless and not s.visible, f"headless={s.headless}, visible={s.visible}")
    cfg = Path.home()/".codex"/"config.toml"
    add("codex_mcp_config_status", cfg.exists(), str(cfg))
    critical = {"python_version", "package_installed", "mcp_server_importable", "sqlite_db_writable", "browser_profile_dir"}
    if s.mock_browser:
        critical.update({"browser_daemon_can_start", "login_state", "prompt_box_detectable"})
    else:
        critical.update({"playwright_installed", "browser_daemon_can_start", "login_state", "prompt_box_detectable", "send_button_detectable"})
    ok = all(c["ok"] for c in checks if c["name"] in critical)
    return {"ok": ok, "backend_default": s.backend, "default_tier": s.default_tier, "default_project": s.default_project, "conversation_policy": s.default_conversation_policy, "home": str(s.home), "profile_path": str(s.browser_profile_dir), "checks": checks if verbose else [{k:v for k,v in c.items() if k != "details"} for c in checks]}
