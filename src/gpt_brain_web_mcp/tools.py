from __future__ import annotations

from typing import Any
from .backends.web_chatgpt import WebChatGPTBackend
from .config import Settings
from .jobs import JobManager
from .models import BrainRequest, normalize_retention, normalize_tier
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

    def _cleanup_allowed_for_request(self, req: BrainRequest) -> bool:
        # Safety invariant: only delete/queue remote ChatGPT conversations that this
        # request intentionally created. Never clean a resumed URL/session or a
        # reused project thread just because the caller omitted a project.
        return req.conversation_kind == "job" or req.conversation_strategy == "new"

    def _handle_remote_cleanup(self, res, req: BrainRequest, *, job_id: str | None = None, session_id: str | None = None, reason: str = "ephemeral_result"):
        if not getattr(res, "conversation_url", None):
            return res
        wants_cleanup = req.retention in {"ephemeral", "job"} or req.cleanup_remote
        if not wants_cleanup:
            return res
        if not self._cleanup_allowed_for_request(req):
            res.cleanup_remote_status = "skipped_not_new_conversation"
            res.warnings.append("Remote cleanup skipped because this request reused/resumed an existing ChatGPT conversation; cleanup is only automatic for newly-created or job conversations.")
            return res
        if req.retention in {"ephemeral", "job"} or req.cleanup_remote:
            cid = self.store.enqueue_remote_cleanup(res.conversation_url, reason=reason, retention=req.retention, project=req.project, job_id=job_id, session_id=session_id or res.session_id)
            res.cleanup_id = cid
            res.cleanup_remote_status = "queued" if cid else "skipped"
            if req.cleanup_remote and cid:
                report = self.cleanup_remote_conversations(confirm=True, dry_run=False, cleanup_id=cid, limit=1)
                res.cleanup_remote_status = "deleted" if report.get("deleted", 0) else "failed" if report.get("failed", 0) else "skipped"
        return res

    def _request_retention(self, kwargs: dict[str, Any], *, project_explicit: bool, default: str | None = None) -> str:
        return normalize_retention(kwargs.get("retention"), project_explicit=project_explicit, default=default)

    def ask_brain(self, req: BrainRequest) -> Any:
        sid = self._session(req)
        res = self.backend.ask_brain(req, sid)
        res = self._handle_remote_cleanup(res, req, session_id=sid)
        if sid:
            self.store.update_session(sid, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, summary=res.answer[:500])
            self.store.add_message(sid, "assistant", res.answer)
        return res

    def ask_web(self, req: BrainRequest) -> Any:
        req.web_search = True
        sid = self._session(req)
        res = self.backend.ask_web(req, sid)
        res = self._handle_remote_cleanup(res, req, session_id=sid, reason="ephemeral_web_result")
        if sid:
            self.store.update_session(sid, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, summary=res.answer[:500])
            self.store.add_message(sid, "assistant", res.answer)
        return res

    def tool_ask_brain(self, **kwargs) -> dict[str, Any]:
        async_request = bool(kwargs.pop("async_request", kwargs.pop("async", False)))
        tier = normalize_tier(kwargs.get("tier") or self.settings.default_tier)
        allow_pro = bool(kwargs.get("allow_pro", self.settings.allow_pro_default))
        raw_project = kwargs.get("project")
        project_explicit = raw_project is not None and str(raw_project).strip() != ""
        project = self._effective_project(raw_project)
        conversation_strategy = str(kwargs.get("conversation_strategy") or ("new" if not project_explicit else self.settings.default_conversation_policy) or "reuse_project")
        resume_session_id = kwargs.get("session_id") or kwargs.get("resume_session_id")
        resume_conversation_url = kwargs.get("conversation_url") or kwargs.get("resume_conversation_url")
        allow_project_fallback = bool(kwargs.get("allow_project_fallback", False))
        retention = self._request_retention(kwargs, project_explicit=project_explicit)
        cleanup_remote = bool(kwargs.get("cleanup_remote", False))
        if async_request:
            # Release any synchronous browser context before a background worker
            # takes ownership of the same dedicated profile/CDP port.
            try:
                self.browser.stop_browser()
            except Exception:
                pass
            started = self.jobs.start_ask(
                redact_text(kwargs["question"]),
                project,
                redact_text(kwargs.get("context")) if kwargs.get("context") else None,
                tier,
                allow_pro,
                bool(kwargs.get("web_search", False)),
                conversation_strategy,
                resume_session_id,
                resume_conversation_url,
                project_explicit,
                allow_project_fallback,
                retention,
                cleanup_remote,
            )
            return {"answer": None, "backend": "web-chatgpt", "job_id": started.job_id, "status": started.status, "kind": "ask_web" if kwargs.get("web_search") else "ask", "message": started.message, "retention": retention, "cleanup_remote": cleanup_remote, "warnings": []}
        req = BrainRequest(redact_text(kwargs["question"]), project, redact_text(kwargs.get("context")) if kwargs.get("context") else None, tier, allow_pro, bool(kwargs.get("web_search", False)), False, bool(kwargs.get("save_session", self.settings.save_session_default)), conversation_strategy=conversation_strategy, project_explicit=project_explicit, allow_project_fallback=allow_project_fallback, resume_session_id=resume_session_id, resume_conversation_url=resume_conversation_url, retention=retention, cleanup_remote=cleanup_remote)
        res = self.ask_web(req) if req.web_search else self.ask_brain(req)
        return redact_obj(res.to_dict())

    def tool_ask_web(self, **kwargs) -> dict[str, Any]:
        kwargs["web_search"] = True
        return self.tool_ask_brain(**kwargs)

    def start_research(self, **kwargs) -> dict[str, Any]:
        # Research runs in a background worker. Close the synchronous facade first
        # so the worker has exclusive access to the dedicated browser profile.
        try:
            self.browser.stop_browser()
        except Exception:
            pass
        raw_project = kwargs.get("project")
        project_explicit = raw_project is not None and str(raw_project).strip() != ""
        retention = self._request_retention(kwargs, project_explicit=project_explicit, default="job")
        cleanup_remote = bool(kwargs.get("cleanup_remote", False))
        started = self.jobs.start_research(redact_text(kwargs["topic"]), self._effective_project(raw_project), redact_text(kwargs.get("context")) if kwargs.get("context") else None, normalize_tier(kwargs.get("tier") or self.settings.default_tier), bool(kwargs.get("allow_pro", self.settings.allow_pro_default)), bool(kwargs.get("deep_research", True)), kwargs.get("output_format", "report"), int(kwargs.get("max_runtime_hint_minutes", 30)), project_explicit, bool(kwargs.get("allow_project_fallback", False)), retention, cleanup_remote)
        return started.to_dict()

    def get_research_result(self, job_id: str): return redact_obj(self.jobs.get(job_id))
    def get_job_result(self, job_id: str): return self.get_research_result(job_id)
    def cancel_research_job(self, job_id: str): return self.jobs.cancel(job_id)
    def delete_local_record(self, record_id: str, record_type: str = "auto", delete_artifact: bool = True):
        deleted = False
        artifact_deleted = False
        details: dict[str, Any] = {}
        if not record_id:
            return {"record_id": record_id, "deleted": False, "artifact_deleted": False, "record_type": record_type, "error": "missing_record_id"}
        if record_type in {"auto", "session"} and record_id.startswith("ses_"):
            deleted = self.store.delete_session(record_id)
            details["record_type"] = "session"
        elif record_type in {"auto", "job"} and record_id.startswith("job_"):
            details = self.store.delete_job(record_id)
            deleted = bool(details.get("deleted"))
            artifact = details.get("artifact_path")
            if delete_artifact and artifact:
                from pathlib import Path
                path = Path(artifact)
                if path.exists() and path.is_file() and self.settings.artifacts_dir in path.resolve().parents:
                    path.unlink()
                    artifact_deleted = True
            details["record_type"] = "job"
        else:
            details["record_type"] = record_type
        return {"record_id": record_id, "deleted": deleted, "artifact_deleted": artifact_deleted, **details}
    def purge_project_records(self, project: str, include_thread: bool = False):
        return {"project": project, **self.store.purge_project_records(project, include_thread=include_thread)}
    def delete_remote_conversation(self, conversation_url: str, confirm: bool = False):
        if not confirm:
            return {"deleted": False, "error": "confirm=true is required", "conversation_url": conversation_url}
        if not (conversation_url or "").startswith("https://chatgpt.com/c/"):
            return {"deleted": False, "error": "Only explicit https://chatgpt.com/c/... URLs are supported.", "conversation_url": conversation_url}
        page = self.browser.navigate_to_conversation(conversation_url)
        try:
            page.ensure_logged_in()
            deleted = bool(getattr(page, "delete_current_conversation")())
            return {"deleted": deleted, "conversation_url": conversation_url, "remote": "chatgpt-web"}
        finally:
            self.browser.stop_browser()
    def list_remote_cleanup(self, status: str | None = None, project: str | None = None, limit: int = 50):
        return {"items": redact_obj(self.store.list_remote_cleanup(status=status, project=project, limit=limit)), "stats": self.store.remote_cleanup_stats()}

    def cleanup_remote_conversations(self, confirm: bool = False, dry_run: bool = True, status: str = "pending", project: str | None = None, limit: int = 20, cleanup_id: str | None = None):
        if not confirm and not dry_run:
            return {"ok": False, "error": "confirm=true is required for remote deletion", "dry_run": dry_run}
        rows = self.store.list_remote_cleanup(status=status if not cleanup_id else None, project=project, limit=limit, cleanup_id=cleanup_id)
        report = {"ok": True, "dry_run": dry_run, "seen": len(rows), "deleted": 0, "failed": 0, "skipped": 0, "items": []}
        for row in rows:
            item = {"cleanup_id": row.get("cleanup_id"), "conversation_url": row.get("conversation_url"), "status": row.get("status"), "retention": row.get("retention"), "project": row.get("project")}
            if row.get("status") not in {"pending", None}:
                item["action"] = f"skipped_terminal_{row.get('status')}"; report["skipped"] += 1; report["items"].append(item); continue
            if row.get("retention") == "persistent":
                item["action"] = "skipped_persistent"; report["skipped"] += 1; report["items"].append(item); continue
            if dry_run:
                item["action"] = "would_delete"; report["items"].append(item); continue
            result = self.delete_remote_conversation(row.get("conversation_url"), confirm=True)
            if result.get("deleted"):
                self.store.update_remote_cleanup(row["cleanup_id"], status="deleted")
                item["action"] = "deleted"; report["deleted"] += 1
            else:
                err = result.get("error") or "remote_delete_failed"
                self.store.update_remote_cleanup(row["cleanup_id"], status="failed", error=err)
                item["action"] = "failed"; item["error"] = err; report["failed"] += 1
            report["items"].append(item)
        return redact_obj(report)

    def ui_capabilities_check(self, visible: bool = False):
        old_visible, old_headless = self.settings.visible, self.settings.headless
        if visible:
            self.settings.visible = True; self.settings.headless = False
        page = self.browser.acquire_page("ui_check")
        try:
            page.ensure_logged_in()
            deep = page.check_deep_research_ui() if hasattr(page, "check_deep_research_ui") else {"available": False, "warnings": ["Deep Research checker unavailable"]}
            search = page.check_web_search_ui() if hasattr(page, "check_web_search_ui") else {"available": False, "warnings": ["Search checker unavailable"]}
            return {"ok": True, "deep_research": deep, "web_search": search, "profile_path": str(self.settings.browser_profile_dir)}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "profile_path": str(self.settings.browser_profile_dir)}
        finally:
            self.browser.release_page("ui_check")
            self.settings.visible, self.settings.headless = old_visible, old_headless

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
    return ["ask_brain", "ask_web", "start_research", "get_research_result", "get_job_result", "cancel_research_job", "delete_local_record", "purge_project_records", "delete_remote_conversation", "list_remote_cleanup", "cleanup_remote_conversations", "ui_capabilities_check", "list_web_sessions", "open_login_window", "doctor", "cleanup_browser", "daemon_status"]
