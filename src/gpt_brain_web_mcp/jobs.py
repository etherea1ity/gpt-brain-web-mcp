from __future__ import annotations

import json
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from .models import BrainRequest, JobStartResult
from .redaction import redact_text
from .store import Store, now

class JobManager:
    def __init__(self, service, store: Store, artifact_dir: str | Path):
        self.service = service; self.store = store; self.artifact_dir = Path(artifact_dir); self.artifact_dir.mkdir(parents=True, exist_ok=True)
        try: self.artifact_dir.chmod(0o700)
        except OSError: pass
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(getattr(service.settings, "max_parallel_browser_jobs", 1))), thread_name_prefix="gpt-brain-web-job")
        self.cancelled: set[str] = set(); self.lock = threading.Lock()
        self.worker_browsers: dict[str, Any] = {}
        self.futures: dict[str, Future] = {}

    def start_ask(
        self,
        question: str,
        project: str | None,
        context: str | None,
        tier: str,
        allow_pro: bool,
        web_search: bool,
        conversation_strategy: str,
        resume_session_id: str | None = None,
        resume_conversation_url: str | None = None,
        project_explicit: bool = False,
        allow_project_fallback: bool = False,
    ) -> JobStartResult:
        jid = self.store.create_job(project, "ask_web" if web_search else "ask", tier, None)
        self.futures[jid] = self.executor.submit(
            self._run_ask,
            jid,
            question,
            project,
            context,
            tier,
            allow_pro,
            web_search,
            conversation_strategy,
            resume_session_id,
            resume_conversation_url,
            project_explicit,
            allow_project_fallback,
        )
        return JobStartResult(jid, "queued", "Ask job queued.", now())

    def _run_ask(
        self,
        jid: str,
        question: str,
        project: str | None,
        context: str | None,
        tier: str,
        allow_pro: bool,
        web_search: bool,
        conversation_strategy: str,
        resume_session_id: str | None,
        resume_conversation_url: str | None,
        project_explicit: bool,
        allow_project_fallback: bool,
    ) -> None:
        if self._is_cancelled(jid):
            self.store.update_job(jid, status="cancelled"); return
        self.store.update_job(jid, status="running")
        try:
            from .backends.web_chatgpt import WebChatGPTBackend
            from .web.browser_manager import BrowserSessionManager
            browser = BrowserSessionManager(self.service.settings, self.store)
            with self.lock:
                self.worker_browsers[jid] = browser
            session_id = self.store.create_session(project, tier) if project else None
            if session_id:
                self.store.add_message(session_id, "user", question + ("\n\n" + context if context else ""))
            try:
                req = BrainRequest(
                    question=question,
                    project=project,
                    context=context,
                    tier=tier,
                    allow_pro=allow_pro,
                    web_search=web_search,
                    save_session=False,
                    conversation_strategy=conversation_strategy,
                    project_explicit=project_explicit,
                    allow_project_fallback=allow_project_fallback,
                    conversation_key=jid,
                    resume_session_id=resume_session_id,
                    resume_conversation_url=resume_conversation_url,
                )
                backend = WebChatGPTBackend(self.service.settings, self.store, browser)
                res = backend.ask_web(req, session_id) if web_search else backend.ask_brain(req, session_id)
                if self._is_cancelled(jid):
                    self.store.update_job(jid, status="cancelled", resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, warnings_json=res.warnings, sources_json=res.sources)
                    return
            finally:
                browser.stop_browser()
                with self.lock:
                    self.worker_browsers.pop(jid, None)
            if session_id:
                self.store.update_session(session_id, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, summary=res.answer[:500])
                self.store.add_message(session_id, "assistant", res.answer)
            status = "completed" if res.answer else "needs_user_action"
            error = None if res.answer else "ChatGPT requires user action or returned no answer"
            self.store.update_job(jid, status=status, resolved_tier=res.resolved_tier, conversation_url=res.conversation_url, result_redacted=res.answer, error_redacted=error, warnings_json=res.warnings, sources_json=res.sources)
        except Exception as exc:
            if self._is_cancelled(jid):
                self.store.update_job(jid, status="cancelled")
            else:
                self.store.update_job(jid, status="needs_user_action" if "login" in str(exc).lower() else "failed", error_redacted=redact_text(str(exc)))
        finally:
            with self.lock:
                self.futures.pop(jid, None)

    def start_research(self, topic: str, project: str | None, context: str | None, tier: str, allow_pro: bool, deep_research: bool, output_format: str, max_runtime_hint_minutes: int, project_explicit: bool = False, allow_project_fallback: bool = False) -> JobStartResult:
        jid = self.store.create_job(project, "research", tier, "deep_research" if deep_research else "web_research_prompt")
        self.futures[jid] = self.executor.submit(self._run_research, jid, topic, project, context, tier, allow_pro, deep_research, output_format, max_runtime_hint_minutes, project_explicit, allow_project_fallback)
        return JobStartResult(jid, "queued", "Research job queued.", now())

    def _is_cancelled(self, jid: str) -> bool:
        with self.lock:
            return jid in self.cancelled

    def _run_research(self, jid: str, topic: str, project: str | None, context: str | None, tier: str, allow_pro: bool, deep_research: bool, output_format: str, max_runtime_hint_minutes: int, project_explicit: bool, allow_project_fallback: bool) -> None:
        if self._is_cancelled(jid):
            self.store.update_job(jid, status="cancelled"); return
        self.store.update_job(jid, status="running")
        try:
            # Use a fresh browser/backend facade inside the worker thread; Playwright sync objects are thread-affine.
            from .backends.web_chatgpt import WebChatGPTBackend
            from .web.browser_manager import BrowserSessionManager
            browser = BrowserSessionManager(self.service.settings, self.store)
            with self.lock:
                self.worker_browsers[jid] = browser
            try:
                if self._is_cancelled(jid):
                    self.store.update_job(jid, status="cancelled"); return
                requested_mode = "deep_research" if deep_research else "web_research_prompt"
                warnings: list[str] = []
                if self._is_cancelled(jid):
                    self.store.update_job(jid, status="cancelled", resolved_research_mode=requested_mode, warnings_json=warnings); return
                prompt = (
                    f"Research topic: {topic}\n"
                    f"Output format: {output_format}\n"
                    f"Runtime hint: {max_runtime_hint_minutes} minutes.\n\n"
                    "Return the final answer directly now. Do not narrate that you will verify, search, or research later.\n"
                    "Include executive summary, evidence table when useful, recommendation, risks/unknowns, sources, and next steps."
                )
                req = BrainRequest(question=prompt, project=project, context=context, tier=tier, allow_pro=allow_pro, web_search=True, save_session=False, conversation_kind="job", conversation_key=jid, conversation_strategy="new", project_explicit=project_explicit, allow_project_fallback=allow_project_fallback, requested_research_mode=requested_mode)
                try:
                    res = WebChatGPTBackend(self.service.settings, self.store, browser).ask_web(req, None)
                except TimeoutError:
                    if requested_mode != "deep_research":
                        raise
                    warnings.append("Deep Research did not complete before timeout; used web research fallback.")
                    res, browser = self._run_web_research_fallback(browser, jid, prompt, project, context, tier, allow_pro, project_explicit, allow_project_fallback, BrowserSessionManager, WebChatGPTBackend)
                if requested_mode == "deep_research" and self._bad_research_answer(getattr(res, "answer", "")):
                    warnings.append("Deep Research returned no usable final answer; used web research fallback.")
                    res, browser = self._run_web_research_fallback(browser, jid, prompt, project, context, tier, allow_pro, project_explicit, allow_project_fallback, BrowserSessionManager, WebChatGPTBackend)
                if self._is_cancelled(jid):
                    self.store.update_job(jid, status="cancelled", resolved_tier=res.resolved_tier, resolved_research_mode=res.resolved_research_mode or requested_mode, conversation_url=res.conversation_url, warnings_json=res.warnings + warnings, sources_json=res.sources)
                    return
            finally:
                browser.stop_browser()
                with self.lock:
                    self.worker_browsers.pop(jid, None)
            all_warnings = res.warnings + warnings
            if not res.answer and any("login" in w.lower() or "prompt box" in w.lower() for w in all_warnings):
                self.store.update_job(jid, status="needs_user_action", resolved_tier=res.resolved_tier, resolved_research_mode=res.resolved_research_mode or requested_mode, conversation_url=res.conversation_url, error_redacted="ChatGPT requires user action", warnings_json=all_warnings, sources_json=res.sources)
                return
            artifact = self._write_artifact(jid, topic, res.answer, res.sources, all_warnings)
            self.store.update_job(jid, status="completed", resolved_tier=res.resolved_tier, resolved_research_mode=res.resolved_research_mode or requested_mode, conversation_url=res.conversation_url, artifact_path=str(artifact), result_redacted=res.answer, warnings_json=all_warnings, sources_json=res.sources)
        except Exception as exc:
            if self._is_cancelled(jid):
                self.store.update_job(jid, status="cancelled")
            else:
                self.store.update_job(jid, status="needs_user_action" if "login" in str(exc).lower() else "failed", error_redacted=redact_text(str(exc)))
        finally:
            with self.lock:
                self.futures.pop(jid, None)

    def _bad_research_answer(self, text: str) -> bool:
        low = (text or "").strip().lower()
        if not low:
            return True
        bad_prefixes = ("error in message stream", "retry", "something went wrong")
        return low.startswith(bad_prefixes) or low in {"error", "retry"}

    def _run_web_research_fallback(self, browser, jid: str, prompt: str, project: str | None, context: str | None, tier: str, allow_pro: bool, project_explicit: bool, allow_project_fallback: bool, BrowserSessionManager, WebChatGPTBackend):
        try:
            browser.stop_browser()
        except Exception:
            pass
        browser = BrowserSessionManager(self.service.settings, self.store)
        with self.lock:
            self.worker_browsers[jid] = browser
        fallback_req = BrainRequest(question=prompt, project=project, context=context, tier=tier, allow_pro=allow_pro, web_search=True, save_session=False, conversation_kind="job", conversation_key=jid, conversation_strategy="new", project_explicit=project_explicit, allow_project_fallback=allow_project_fallback, requested_research_mode="web_research_prompt")
        return WebChatGPTBackend(self.service.settings, self.store, browser).ask_web(fallback_req, None), browser

    def _write_artifact(self, jid: str, topic: str, answer: str, sources: list[dict[str, Any]], warnings: list[str]) -> Path:
        path = self.artifact_dir / f"{jid}.md"
        lines = [f"# Research: {redact_text(topic)}", "", "## Result", "", redact_text(answer), "", "## Sources"]
        lines += [f"- {s.get('title') or s.get('url')}: {s.get('url') or s}" for s in sources] or ["- No sources detected."]
        if warnings: lines += ["", "## Warnings", *[f"- {redact_text(w)}" for w in warnings]]
        path.write_text("\n".join(lines)+"\n", encoding="utf-8")
        try: path.chmod(0o600)
        except OSError: pass
        return path

    def get(self, job_id: str) -> dict[str, Any]:
        row = self.store.get_job(job_id)
        if not row:
            return {"job_id": job_id, "kind": None, "status": "failed", "result": None, "sources": [], "artifact_path": None, "conversation_url": None, "created_at": None, "updated_at": None, "error": "not_found", "warnings": []}
        return {"job_id": row["job_id"], "kind": row.get("kind"), "project": row.get("project"), "status": row["status"], "result": row.get("result_redacted"), "sources": row.get("sources", []), "artifact_path": row.get("artifact_path"), "conversation_url": row.get("conversation_url"), "requested_research_mode": row.get("requested_research_mode"), "resolved_research_mode": row.get("resolved_research_mode"), "created_at": row.get("created_at"), "updated_at": row.get("updated_at"), "error": row.get("error_redacted"), "warnings": row.get("warnings", [])}

    def cancel(self, job_id: str) -> dict[str, str]:
        row = self.store.get_job(job_id)
        if not row: return {"job_id": job_id, "status": "not_found"}
        if row["status"] == "completed": return {"job_id": job_id, "status": "already_completed"}
        with self.lock:
            self.cancelled.add(job_id)
            browser = self.worker_browsers.get(job_id)
        if browser is not None:
            try:
                browser.release_page(job_id)
                browser.stop_browser()
            except Exception:
                pass
        self.store.update_job(job_id, status="cancelled"); self.service.browser.release_page(job_id)
        return {"job_id": job_id, "status": "cancelled"}
