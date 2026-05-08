from __future__ import annotations

from typing import Any
from .backends.web_chatgpt import WebChatGPTBackend
from .config import Settings
from .jobs import JobManager
from .models import BrainRequest, normalize_tier
from .redaction import redact_obj, redact_text
from .store import Store
from .web.daemon_client import DaemonClient

class WebBrainService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env(); self.settings.ensure_dirs()
        self.daemon = DaemonClient(self.settings)
        self.store = self.daemon.store
        self.browser = self.daemon.manager
        self.backend = WebChatGPTBackend(self.settings, self.store, self.browser)
        self.jobs = JobManager(self, self.store, self.settings.artifacts_dir)

    def _session(self, req: BrainRequest) -> str | None:
        if not req.save_session: return None
        sid = self.store.create_session(req.project, req.tier)
        self.store.add_message(sid, "user", req.question + ("\n\n" + req.context if req.context else ""))
        return sid

    def _effective_project(self, project: str | None) -> str:
        return (project or self.settings.default_project).strip() or "Codex Brain"

    def ask_brain(self, req: BrainRequest) -> Any:
        sid = self._session(req)
        res = self.backend.ask_brain(req, sid)
        if sid:
            self.store.update_session(sid, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, summary=res.answer[:500])
            self.store.add_message(sid, "assistant", res.answer)
        return res

    def ask_web(self, req: BrainRequest) -> Any:
        req.web_search = True
        sid = self._session(req)
        res = self.backend.ask_web(req, sid)
        if sid:
            self.store.update_session(sid, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, summary=res.answer[:500])
            self.store.add_message(sid, "assistant", res.answer)
        return res

    def tool_ask_brain(self, **kwargs) -> dict[str, Any]:
        async_request = bool(kwargs.pop("async_request", kwargs.pop("async", False)))
        tier = normalize_tier(kwargs.get("tier") or self.settings.default_tier)
        allow_pro = bool(kwargs.get("allow_pro", self.settings.allow_pro_default))
        project = self._effective_project(kwargs.get("project"))
        conversation_strategy = str(kwargs.get("conversation_strategy") or self.settings.default_conversation_policy or "reuse_project")
        resume_session_id = kwargs.get("session_id") or kwargs.get("resume_session_id")
        resume_conversation_url = kwargs.get("conversation_url") or kwargs.get("resume_conversation_url")
        if async_request:
            started = self.jobs.start_research(kwargs["question"], project, kwargs.get("context"), tier, allow_pro, bool(kwargs.get("web_search", False)), "bullet_summary", 30)
            return {"answer": None, "backend": "web-chatgpt", "job_id": started.job_id, "status": started.status, "warnings": []}
        req = BrainRequest(redact_text(kwargs["question"]), project, redact_text(kwargs.get("context")) if kwargs.get("context") else None, tier, allow_pro, bool(kwargs.get("web_search", False)), False, bool(kwargs.get("save_session", True)), conversation_strategy=conversation_strategy, resume_session_id=resume_session_id, resume_conversation_url=resume_conversation_url)
        res = self.ask_web(req) if req.web_search else self.ask_brain(req)
        return redact_obj(res.to_dict())

    def tool_ask_web(self, **kwargs) -> dict[str, Any]:
        kwargs["web_search"] = True
        return self.tool_ask_brain(**kwargs)

    def start_research(self, **kwargs) -> dict[str, Any]:
        started = self.jobs.start_research(redact_text(kwargs["topic"]), self._effective_project(kwargs.get("project")), redact_text(kwargs.get("context")) if kwargs.get("context") else None, normalize_tier(kwargs.get("tier") or self.settings.default_tier), bool(kwargs.get("allow_pro", self.settings.allow_pro_default)), bool(kwargs.get("deep_research", True)), kwargs.get("output_format", "report"), int(kwargs.get("max_runtime_hint_minutes", 30)))
        return started.to_dict()

    def get_research_result(self, job_id: str): return redact_obj(self.jobs.get(job_id))
    def cancel_research_job(self, job_id: str): return self.jobs.cancel(job_id)
    def list_web_sessions(self, project: str | None = None, limit: int = 20): return redact_obj(self.store.list_sessions(project, limit))
    def open_login_window(self, visible: bool = True):
        old_visible, old_headless = self.settings.visible, self.settings.headless
        self.settings.visible = visible; self.settings.headless = not visible
        try:
            self.browser.start_browser()
            state = self.browser.ensure_login_state()
            return {"status": state, "profile_path": str(self.settings.browser_profile_dir), "message": "Login window opened; complete ChatGPT login manually if needed."}
        finally:
            self.settings.visible, self.settings.headless = old_visible, old_headless
    def doctor(self, verbose: bool = False):
        from .installer import doctor
        return doctor(self.settings, verbose=verbose)
    def cleanup_browser(self):
        cleaned = self.browser.cleanup_zombie_pages(); self.browser.stop_browser(); return {"closed": True, "zombie_pages_cleaned": cleaned, "profile_preserved": True}
    def daemon_status(self): return self.browser.status().to_dict()

_default: WebBrainService | None = None
def get_service() -> WebBrainService:
    global _default
    if _default is None: _default = WebBrainService()
    return _default

def expected_tools():
    return ["ask_brain", "ask_web", "start_research", "get_research_result", "cancel_research_job", "list_web_sessions", "open_login_window", "doctor", "cleanup_browser", "daemon_status"]
