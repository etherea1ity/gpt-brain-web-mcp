from __future__ import annotations

class ResultExtractor:
    def extract_answer(self, page) -> str:
        if hasattr(page, "last_answer"):
            return page.last_answer
        return ""

    def is_streaming_complete(self, page) -> bool:
        return not getattr(page, "generation_running", False)
