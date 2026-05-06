from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
import uuid

from ..config import Settings
from ..models import BrowserUnavailable, NeedsUserAction
from ..store import Store
from .chatgpt_page import ChatGPTPage, MockChatGPTPage
from .healthcheck import BrowserHealth
from .selectors import load_selectors


def pid_alive(pid: int | str | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


@dataclass(slots=True)
class BrowserStatus:
    running: bool
    pid: str | None
    profile_path: str
    headless: bool
    active_jobs: list[str]
    page_count: int
    login_state: str

    def to_dict(self): return self.__dict__.copy()


class BrowserSessionManager:
    def __init__(self, settings: Settings, store: Store):
        self.settings = settings
        self.store = store
        self.selectors = load_selectors(settings.selectors_path)
        self.context = None
        self.browser = None
        self._external_browser_proc = None
        self.pages: dict[str, object] = {}
        self.active_jobs: set[str] = set()
        self.mock_page = MockChatGPTPage(logged_in=True) if settings.mock_browser else None

    def start_browser(self):
        self.settings.ensure_dirs()
        self.store.upsert_profile(str(self.settings.browser_profile_dir), "logged_in" if self.settings.mock_browser else "unknown", self.settings.headless)
        if self.settings.mock_browser:
            return self.mock_page
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise BrowserUnavailable("Playwright is not installed. Run `gpt-brain-web install` or `python -m pip install .[web]`.") from exc
        self._pw = sync_playwright().start()
        headless = self.settings.headless and not self.settings.visible
        try:
            self.context = self._pw.chromium.launch_persistent_context(
                str(self.settings.browser_profile_dir),
                headless=headless,
                args=["--no-first-run", "--disable-features=Translate"],
            )
            page = self.context.pages[0] if self.context.pages else self.context.new_page()
            page.goto(self.settings.chatgpt_url, wait_until="domcontentloaded")
            return ChatGPTPage(page, self.selectors)
        except Exception as exc:
            # WSL systems often lack Linux Chromium shared libraries and may not allow sudo apt install.
            # Fall back to a Windows Chrome/Edge executable over CDP, still using a dedicated profile dir.
            if self._looks_like_wsl():
                try:
                    return self._start_windows_browser_over_cdp()
                except Exception as cdp_exc:
                    raise BrowserUnavailable(f"Playwright Chromium failed ({exc}); Windows Chrome/Edge CDP fallback also failed ({cdp_exc}).") from cdp_exc
            raise

    def _looks_like_wsl(self) -> bool:
        try:
            return "microsoft" in Path("/proc/version").read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            return False

    def _find_windows_browser(self) -> str | None:
        candidates = [
            "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
            "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
            "/mnt/c/Program Files/Microsoft/Edge/Application/msedge.exe",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return None

    def _free_port(self) -> int:
        if self._looks_like_wsl():
            return int(os.getenv("GPT_BRAIN_BROWSER_CDP_PORT", "49222"))
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _win_path(self, path: Path) -> str:
        try:
            out = subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
            if out:
                return out
        except Exception:
            pass
        return str(path)

    def _default_windows_profile_wsl(self) -> Path:
        override = os.getenv("GPT_BRAIN_WINDOWS_BROWSER_PROFILE")
        if override:
            return Path(override).expanduser()
        try:
            win_home = subprocess.check_output(
                ["/mnt/c/Windows/System32/cmd.exe", "/c", "echo", "%USERPROFILE%"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip().replace("\r", "")
            if win_home and "%" not in win_home:
                wsl_home = subprocess.check_output(["wslpath", "-u", win_home], text=True, timeout=5).strip()
                if wsl_home:
                    return Path(wsl_home) / ".gpt-brain-web" / "browser-profile"
        except Exception:
            pass
        return self.settings.browser_profile_dir

    def _stop_windows_profile_processes_without_port(self, profile_fragment: str, port: int) -> None:
        ps = Path("/tmp/gpt_brain_web_stop_stale_chrome.ps1")
        escaped_profile = profile_fragment.replace('"', '`"')
        ps.write_text(
            "$profile = \"" + escaped_profile + "\"\n"
            "$port = \"--remote-debugging-port=" + str(port) + "\"\n"
            "$targets = Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and $_.CommandLine -like \"*$profile*\" -and ($_.CommandLine -notlike \"*$port*\" -or $_.CommandLine -like \"*--remote-debugging-address=0.0.0.0*\") }\n"
            "$targets | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force } catch {} }\n",
            encoding="utf-8",
        )
        try:
            subprocess.run(["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", self._win_path(ps)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        except Exception:
            pass

    def _cdp_responds(self, port: int) -> bool:
        import urllib.request
        try:
            with urllib.request.urlopen(f"http://localhost:{port}/json/version", timeout=2) as r:
                return r.status == 200 and b"webSocketDebuggerUrl" in r.read(4096)
        except Exception:
            return False

    def _start_windows_browser_over_cdp(self):
        exe = self._find_windows_browser()
        if not exe:
            raise BrowserUnavailable("No Windows Chrome/Edge executable found for WSL fallback.")
        # Keep the Windows-controlled profile on the Windows filesystem; never use the user's default profile.
        win_profile_wsl = self._default_windows_profile_wsl()
        win_profile_wsl.mkdir(parents=True, exist_ok=True)
        port = self._free_port()
        win_profile = self._win_path(win_profile_wsl)
        self._stop_windows_profile_processes_without_port(win_profile, port)
        args = self._windows_browser_args(exe, port, win_profile)
        if not self._cdp_responds(port):
            self._external_browser_proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        endpoint = f"http://localhost:{port}"
        deadline = time.time() + 20
        last_exc = None
        while time.time() < deadline:
            try:
                self.browser = self._pw.chromium.connect_over_cdp(endpoint)
                self.context = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
                page = self.context.pages[0] if self.context.pages else self.context.new_page()
                try:
                    page.goto(self.settings.chatgpt_url, wait_until="domcontentloaded", timeout=30000)
                except Exception:
                    pass
                self.store.upsert_profile(str(win_profile_wsl), "unknown", self.settings.headless, notes="Using Windows Chrome/Edge CDP fallback from WSL with dedicated profile.")
                return ChatGPTPage(page, self.selectors)
            except Exception as exc:
                last_exc = exc
                time.sleep(0.5)
        raise BrowserUnavailable(f"Timed out connecting to Windows browser CDP: {last_exc}")

    def _windows_browser_args(self, exe: str, port: int, win_profile: str) -> list[str]:
        return [
            exe,
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={win_profile}",
            "--no-first-run",
            "--new-window",
            self.settings.chatgpt_url,
        ]

    def stop_browser(self):
        if self.context:
            try: self.context.close()
            except Exception: pass
            self.context = None
        if self.browser:
            try: self.browser.close()
            except Exception: pass
            self.browser = None
        if self._external_browser_proc:
            try: self._external_browser_proc.terminate()
            except Exception: pass
            self._external_browser_proc = None
        if getattr(self, "_pw", None):
            self._pw.stop(); self._pw = None
        self.pages.clear(); self.active_jobs.clear()

    def ensure_context(self):
        if self.settings.mock_browser:
            return self.mock_page
        if self.context is None:
            return self.start_browser()
        page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return ChatGPTPage(page, self.selectors)

    def ensure_login_state(self) -> str:
        if self.settings.mock_browser:
            if self.mock_page and self.mock_page.logged_in:
                self.store.upsert_profile(str(self.settings.browser_profile_dir), "logged_in", self.settings.headless)
                return "logged_in"
            self.store.upsert_profile(str(self.settings.browser_profile_dir), "needs_user_action", self.settings.headless)
            return "needs_user_action"
        page = self.ensure_context()
        try:
            page.ensure_logged_in()
            self.store.upsert_profile(str(self.settings.browser_profile_dir), "logged_in", self.settings.headless)
            return "logged_in"
        except NeedsUserAction:
            self.store.upsert_profile(str(self.settings.browser_profile_dir), "needs_user_action", self.settings.headless)
            return "needs_user_action"

    def acquire_page(self, job_id: str):
        self.active_jobs.add(job_id)
        page = self.ensure_context()
        self.pages[job_id] = page
        return page

    def release_page(self, job_id: str) -> None:
        self.active_jobs.discard(job_id)
        self.pages.pop(job_id, None)

    def recover_page(self, job_id: str):
        self.release_page(job_id)
        return self.acquire_page(job_id)

    def navigate_to_conversation(self, conversation_url: str):
        page = self.ensure_context()
        if not self.settings.mock_browser and hasattr(page, "page"):
            page.page.goto(conversation_url, wait_until="domcontentloaded")
        page.conversation_url = conversation_url
        return page

    def create_or_reuse_conversation(self, project: str | None, kind: str) -> str:
        existing = self.store.find_project_session(project) if project and kind == "project" else None
        if existing and existing.get("conversation_url"):
            return existing["conversation_url"]
        # ChatGPT creates the real URL after the first message; use a local
        # placeholder only until ChatGPTPage.current_conversation_url can persist
        # the real /c/... URL.
        if kind == "job":
            return f"chatgpt://local/job/{project or uuid.uuid4().hex}"
        url = f"chatgpt://local/project/{project or kind}"
        if project and kind == "project": self.store.set_project_conversation(project, url, title=f"{project} brain")
        return url

    def cleanup_zombie_pages(self) -> int:
        count = len(self.pages)
        self.pages.clear(); self.active_jobs.clear()
        return count

    def healthcheck(self) -> BrowserHealth:
        try:
            login = self.ensure_login_state()
        except BrowserUnavailable as exc:
            return BrowserHealth(False, "unknown", warnings=[str(exc)])
        ok = login == "logged_in"
        return BrowserHealth(ok, login, prompt_box_detectable=ok, model_picker_detectable=ok or self.settings.mock_browser, send_button_detectable=ok)

    def status(self) -> BrowserStatus:
        profile = self.store.get_profile() or {}
        daemon_pid = None
        try:
            daemon_pid = self.settings.daemon_pid_path.read_text(encoding="utf-8").strip() if self.settings.daemon_pid_path.exists() else None
        except OSError:
            daemon_pid = None
        external_running = pid_alive(daemon_pid)
        local_running = bool(self.context or self.settings.mock_browser)
        pid = str(os.getpid()) if local_running else (daemon_pid if external_running else None)
        return BrowserStatus(local_running or external_running, pid, str(self.settings.browser_profile_dir), self.settings.headless and not self.settings.visible, sorted(self.active_jobs), len(self.pages), profile.get("login_state", "logged_in" if self.settings.mock_browser else "unknown"))
