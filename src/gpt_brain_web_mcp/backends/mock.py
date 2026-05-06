from __future__ import annotations
from ..models import BrainRequest, BrainResult, fallback_sequence
from .base import BrainBackend

class MockBackend(BrainBackend):
    name = "mock"
    def __init__(self, unavailable_tiers: set[str] | None = None): self.unavailable_tiers = unavailable_tiers or set()
    def _resolve(self, req):
        seq, warnings = fallback_sequence(req.tier, req.allow_pro)
        tried=[]
        for tier in seq:
            tried.append(tier)
            if tier not in self.unavailable_tiers:
                if tier != req.tier: warnings.append(f"Tier fallback used: requested {req.tier}, resolved {tier}.")
                return tier, tried, warnings
        return "thinking_normal", tried, warnings + ["All requested tiers unavailable; mock used thinking_normal."]
    def ask_brain(self, request: BrainRequest, session_id: str | None = None) -> BrainResult:
        tier, chain, warnings = self._resolve(request)
        return BrainResult(f"Mock Web ChatGPT answer: {request.question}", "web-chatgpt", request.tier, tier, chain, session_id, "chatgpt://mock", warnings)
    def ask_web(self, request: BrainRequest, session_id: str | None = None) -> BrainResult:
        res = self.ask_brain(request, session_id); res.sources=[{"title":"Mock source","url":"https://example.com/mock"}]; return res
