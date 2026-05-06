from __future__ import annotations

from ..config import Settings
from ..models import BrainRequest, BrainResult, NeedsUserAction, fallback_sequence
from ..redaction import redact_text
from ..store import Store
from ..web.browser_manager import BrowserSessionManager
from ..web.conversation_manager import ConversationManager
from ..web.model_picker import ModelModeManager
from ..web.result_extractor import ResultExtractor
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
            selection = self.modes.select_tier(page, request.tier, request.allow_pro)
            warnings.extend(selection.warnings)
            if getattr(request, "conversation_kind", "project") == "job":
                conv = self.browser.create_or_reuse_conversation(request.conversation_key or session_id or "job", "job")
            else:
                conv = self.browser.create_or_reuse_conversation(request.project, "project")
            if conv and conv.startswith("https://"):
                page = self.browser.navigate_to_conversation(conv)
            page.conversation_url = conv
            prompt = self._render_prompt(request, web_search)
            page.submit_prompt(prompt, web_search=web_search)
            answer = redact_text(self.results.extract_answer(page))
            real_conv = getattr(page, "current_conversation_url", lambda fallback=None: fallback)(conv) or conv
            if request.project and getattr(request, "conversation_kind", "project") == "project":
                self.conversations.bind_project(request.project, real_conv)
            if session_id:
                self.conversations.bind_session(session_id, real_conv)
            if getattr(request, "conversation_kind", "project") == "job" and request.conversation_key:
                self.conversations.bind_job(request.conversation_key, real_conv)
            sources = self.sources.extract_sources(page if web_search else answer)
            if web_search and not sources:
                warnings.append("Web Search requested but no sources/citations were detected.")
            return BrainResult(answer=answer, backend=self.name, requested_tier=request.tier, resolved_tier=selection.resolved_tier, fallback_chain=selection.fallback_chain, session_id=session_id, conversation_url=real_conv, warnings=warnings, sources=sources)
        except NeedsUserAction as exc:
            return BrainResult(answer="", backend=self.name, requested_tier=request.tier, resolved_tier="", fallback_chain=seq, session_id=session_id, warnings=[*warnings, str(exc)])
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
