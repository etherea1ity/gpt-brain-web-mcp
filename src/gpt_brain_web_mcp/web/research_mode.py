from __future__ import annotations

class ResearchModeManager:
    def detect_deep_research(self, page) -> bool:
        if bool(getattr(page, "deep_research_available", False)):
            return True
        if hasattr(page, "has_visible_text"):
            return bool(page.has_visible_text(["Deep research", "Deep Research"]))
        return False

    def enable_deep_research(self, page) -> bool:
        if hasattr(page, "enable_deep_research"):
            return bool(page.enable_deep_research())
        return bool(getattr(page, "deep_research_available", False))

    def resolve_mode(self, page, requested_deep: bool) -> tuple[str, list[str]]:
        # The Deep Research option is normally hidden behind the composer + menu,
        # so detection must try to open/enable it rather than only scanning the
        # closed page body.
        if requested_deep:
            if self.enable_deep_research(page):
                return "deep_research", []
            return "web_research_prompt", ["Deep Research UI not available; used web research fallback."]
        return "web_research_prompt", []
