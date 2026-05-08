from __future__ import annotations

from ..config import Settings
from ..models import BrainRequest, BrainResult, NeedsUserAction, fallback_sequence
from ..redaction import redact_text
from ..store import Store
from ..web.browser_manager import BrowserSessionManager
from ..web.conversation_manager import ConversationManager
from ..web.model_picker import ModelModeManager
from ..web.result_extractor import ResultExtractor
from ..web.research_mode import ResearchModeManager
from ..web.source_extractor import SourceExtractor
from .base import BrainBackend

class WebChatGPTBackend(BrainBackend):
    name = "web-chatgpt"
    def __init__(self, settings: Settings, store: Store, browser: BrowserSessionManager | None = None):
        self.settings=settings; self.store=store
        self.browser=browser or BrowserSessionManager(settings, store)
        self.modes=ModelModeManager(settings.model_modes_path)
        self.results=ResultExtractor(); self.sources=SourceExtractor(); self.conversations=ConversationManager(store)

    def _ask(self, request: BrainRequest, session_id: str | None, web_search: bool) -> BrainResult:
        warnings=[]
        seq, gate_warnings = fallback_sequence(request.tier, request.allow_pro); warnings.extend(gate_warnings)
        job_key = session_id or "sync"
        page = self.browser.acquire_page(job_key)
        try:
            page.ensure_logged_in()
            force_new = request.conversation_strategy == "new"
            if request.conversation_strategy not in {"reuse_project", "new", "resume_session", "resume_url", "recover_or_new"}:
                warnings.append(f"Unknown conversation_strategy={request.conversation_strategy!r}; using reuse_project.")
                force_new = False
            if getattr(request, "conversation_kind", "project") == "job":
                conv = self.browser.create_or_reuse_conversation(request.conversation_key or session_id or "job", "job", force_new=True)
            elif request.conversation_strategy == "resume_url" and request.resume_conversation_url:
                conv = request.resume_conversation_url
            elif request.conversation_strategy == "resume_session" and request.resume_session_id:
                row = self.store.get_session(request.resume_session_id)
                conv = row.get("conversation_url") if row else None
                if not conv:
                    warnings.append(f"resume_session_id={request.resume_session_id!r} was not found or has no conversation_url; falling back to project policy.")
                    conv = self.browser.create_or_reuse_conversation(request.project if request.project_explicit else None, "project", force_new=False)
            else:
                conv = self.browser.create_or_reuse_conversation(request.project if request.project_explicit else None, "project", force_new=force_new)
            recovery_action = None
            recovery_reason = None
            if conv and conv.startswith("https://"):
                try:
                    page = self.browser.navigate_to_conversation(conv)
                    page.ensure_logged_in()
                except Exception as exc:
                    warnings.append(f"Saved ChatGPT conversation could not be reopened; creating a new project conversation. Reason: {exc}")
                    recovery_action = "created_new"
                    recovery_reason = "saved_conversation_unavailable"
                    self.store.add_event("conversation_recovery", f"Saved conversation unavailable for project={request.project!r}: {exc}", session_id=session_id)
                    conv = self.browser.create_or_reuse_conversation(request.project if request.project_explicit else None, "project", force_new=True)
            if conv and (conv.startswith("chatgpt://local/project/") or conv.startswith("chatgpt://local/job/")) and hasattr(page, "open_project"):
                try:
                    project_opened = True
                    if request.conversation_strategy == "new":
                        project_opened = page.start_new_chat(request.project if request.project_explicit else None)
                    elif request.project_explicit:
                        project_opened = page.open_project(request.project)
                    elif not request.project_explicit and request.conversation_strategy == "new":
                        project_opened = page.start_new_chat(None)
                    if not project_opened and request.conversation_strategy == "new" and not request.allow_project_fallback:
                        raise NeedsUserAction("Could not start a fresh ChatGPT conversation; refusing to send into the current chat. Retry, run doctor, or pass allow_project_fallback=true if current-chat fallback is acceptable.")
                    if request.project_explicit and not project_opened and not request.allow_project_fallback:
                        raise NeedsUserAction(f"ChatGPT project {request.project!r} could not be opened; refusing to send into the current chat. Create/open the project or pass allow_project_fallback=true.")
                    if not project_opened:
                        warnings.append("Requested ChatGPT conversation/project was not opened; allow_project_fallback=true so using current chat context.")
                except Exception as exc:
                    if isinstance(exc, NeedsUserAction):
                        raise
                    if request.project_explicit and not request.allow_project_fallback:
                        raise NeedsUserAction(f"Could not open ChatGPT project {request.project!r}; refusing to send into current chat. Reason: {exc}") from exc
                    warnings.append(f"Could not open ChatGPT project {request.project!r}; allow_project_fallback=true so using current/new chat context. Reason: {exc}")
            selection = self.modes.select_tier(page, request.tier, request.allow_pro)
            warnings.extend(selection.warnings)
            resolved_research_mode = request.requested_research_mode
            if request.requested_research_mode == "deep_research":
                resolved_research_mode, research_warnings = ResearchModeManager().resolve_mode(page, True)
                warnings.extend(research_warnings)
            elif request.requested_research_mode:
                resolved_research_mode = request.requested_research_mode
            page.conversation_url = conv
            if request.conversation_key:
                def _progress(event: str, detail: str) -> None:
                    self.store.add_event(f"job_{event}", detail, job_id=request.conversation_key, session_id=session_id)
                    if event in {"heartbeat", "refresh"}:
                        self.store.update_job(request.conversation_key, status="waiting_for_model")
                try:
                    setattr(page, "progress_callback", _progress)
                except Exception:
                    pass
            prompt = self._render_prompt(request, web_search)
            page.submit_prompt(prompt, web_search=web_search)
            answer = redact_text(self.results.extract_answer(page))
            real_conv = getattr(page, "current_conversation_url", lambda fallback=None: fallback)(conv) or conv
            if request.project and request.project_explicit and getattr(request, "conversation_kind", "project") == "project":
                self.conversations.bind_project(request.project, real_conv)
            if session_id:
                self.conversations.bind_session(session_id, real_conv)
            if getattr(request, "conversation_kind", "project") == "job" and request.conversation_key:
                self.conversations.bind_job(request.conversation_key, real_conv)
            sources = self.sources.extract_sources(page if web_search else answer)
            if web_search and not sources:
                warnings.append("Web Search requested but no sources/citations were detected.")
            if request.requested_research_mode == "deep_research" and hasattr(page, "disable_deep_research"):
                try:
                    page.disable_deep_research()
                except Exception:
                    pass
            return BrainResult(answer=answer, backend=self.name, requested_tier=request.tier, resolved_tier=selection.resolved_tier, fallback_chain=selection.fallback_chain, session_id=session_id, conversation_url=real_conv, warnings=warnings, sources=sources, requested_research_mode=request.requested_research_mode, resolved_research_mode=resolved_research_mode, project=request.project, conversation_strategy=request.conversation_strategy, recovery_action=recovery_action, recovery_reason=recovery_reason)
        except NeedsUserAction as exc:
            return BrainResult(answer="", backend=self.name, requested_tier=request.tier, resolved_tier="", fallback_chain=seq, session_id=session_id, warnings=[*warnings, str(exc)], project=request.project, conversation_strategy=request.conversation_strategy)
        finally:
            self.browser.release_page(job_key)

    def _render_prompt(self, req: BrainRequest, web_search: bool) -> str:
        ctx = f"\n\nContext:\n{redact_text(req.context)}" if req.context else ""
        if web_search:
            return f"Use ChatGPT web/search capability if available. Cite sources with full https:// source URLs.\n\nQuestion:\n{redact_text(req.question)}{ctx}"
        return f"You are a rigorous practical engineering advisor. Answer with conclusion, reasons, tradeoffs, and next steps.\n\nQuestion:\n{redact_text(req.question)}{ctx}"

    def ask_brain(self, request: BrainRequest, session_id: str | None = None) -> BrainResult:
        return self._ask(request, session_id, request.web_search)
    def ask_web(self, request: BrainRequest, session_id: str | None = None) -> BrainResult:
        request.web_search = True
        return self._ask(request, session_id, True)
