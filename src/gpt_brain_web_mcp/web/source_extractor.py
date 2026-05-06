from __future__ import annotations

import re
from typing import Any
from ..redaction import redact_text

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")

class SourceExtractor:
    def extract_sources(self, page_or_text) -> list[dict[str, Any]]:
        if hasattr(page_or_text, "sources"):
            sources = [self._redact_source(s) for s in list(page_or_text.sources)]
            if sources:
                return sources
            page_or_text = getattr(page_or_text, "last_answer", "")
        text = str(page_or_text or "")
        seen, out = set(), []
        for m in URL_RE.finditer(text):
            url = m.group(0).rstrip(".,;")
            url = redact_text(url)
            if url not in seen:
                seen.add(url); out.append({"url": url, "title": url})
        return out

    def _redact_source(self, source: Any) -> Any:
        if isinstance(source, dict):
            return {k: redact_text(v) if isinstance(v, str) else v for k, v in source.items()}
        if isinstance(source, str):
            return redact_text(source)
        return source
