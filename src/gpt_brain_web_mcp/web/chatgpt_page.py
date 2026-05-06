from __future__ import annotations

from dataclasses import dataclass, field
from ..models import NeedsUserAction


@dataclass
class MockChatGPTPage:
    logged_in: bool = True
    available_mode_labels: list[str] = field(default_factory=lambda: ["Thinking Heavy", "Extended Thinking", "Thinking", "Standard"])
    selected_tier: str | None = None
    conversation_url: str | None = None
    last_answer: str = ""
    generation_running: bool = False
    sources: list[dict] = field(default_factory=list)
    deep_research_available: bool = False

    def select_mode_label(self, label: str) -> bool:
        if label in self.available_mode_labels:
            self.selected_tier = label
            return True
        return False

    def ensure_logged_in(self) -> None:
        if not self.logged_in:
            raise NeedsUserAction("ChatGPT login required; run `gpt-brain-web login`.")

    def submit_prompt(self, prompt: str, *, web_search: bool = False) -> None:
        self.ensure_logged_in()
        self.generation_running = True
        prefix = "Mock ChatGPT web answer"
        if "Reply with exactly:" in prompt:
            self.last_answer = prompt.split("Reply with exactly:", 1)[1].strip().splitlines()[0]
        else:
            self.last_answer = f"{prefix}: {prompt[:300]}"
        self.sources = [{"title": "Mock source", "url": "https://example.com/mock"}] if web_search else []
        self.generation_running = False


class ChatGPTPage:
    """Thin Playwright page adapter. Selectors are intentionally centralized elsewhere."""
    def __init__(self, page, selectors: dict[str, list[str]]):
        self.page = page
        self.selectors = selectors
        self.available_mode_labels: list[str] = []
        self.selected_tier: str | None = None
        self.conversation_url: str | None = None
        self.last_answer: str = ""
        self.sources: list[dict] = []
        self.generation_running = False

    def select_mode_label(self, label: str) -> bool:
        # Honest V1: accept the mode only if its label is visible in the current UI.
        try:
            body = self.page.locator("body").inner_text(timeout=3000)
            if label.lower() in body.lower():
                self.selected_tier = label
                return True
        except Exception:
            pass
        return False

    def has_visible_text(self, labels: list[str]) -> bool:
        try:
            body = self.page.locator("body").inner_text(timeout=3000).lower()
        except Exception:
            return False
        return any(label.lower() in body for label in labels)

    def enable_deep_research(self) -> bool:
        """Best-effort Deep Research UI activation.

        This intentionally does not fake success. It only returns true when a
        visible control with a known Deep Research label can be clicked.
        """
        labels = ["Deep research", "Deep Research"]
        for label in labels:
            try:
                self.page.get_by_text(label, exact=False).last.click(timeout=3000)
                self.deep_research_available = True
                return True
            except Exception:
                continue
        self.deep_research_available = False
        return False

    def ensure_logged_in(self) -> None:
        if not self.is_prompt_box_available():
            raise NeedsUserAction("ChatGPT prompt box not detectable; run `gpt-brain-web login` or update selectors.yaml.")

    def is_prompt_box_available(self) -> bool:
        for sel in self.selectors.get("prompt_box", []):
            try:
                if sel.startswith("role:"):
                    continue
                if self.page.locator(sel).count() > 0:
                    return True
            except Exception:
                continue
        return False

    def submit_prompt(self, prompt: str, *, web_search: bool = False) -> None:
        self.ensure_logged_in()
        before = self._assistant_count()
        before_text = self._latest_assistant_text()
        before_user = self._user_count()
        box = self._find_prompt_box()
        if box is None:
            raise NeedsUserAction("Prompt box missing; run doctor/login or update selectors.yaml.")
        try:
            box.fill(prompt)
        except Exception:
            box.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.type(prompt, delay=1)
        sent = False
        for sel in self.selectors.get("send_button", []):
            try:
                if sel.startswith("role:button:"):
                    name = sel.split(":", 2)[2]
                    self.page.get_by_role("button", name=name).last.click(timeout=3000)
                else:
                    self.page.locator(sel).last.click(timeout=3000)
                sent = True; break
            except Exception:
                continue
        if not sent:
            self.page.keyboard.press("Enter")
        else:
            try:
                self.page.wait_for_function(
                    "(before) => document.querySelectorAll('[data-message-author-role=\"user\"]').length > before",
                    arg=before_user,
                    timeout=3000,
                )
            except Exception:
                # Some ChatGPT builds do not expose the user message immediately; press Enter as fallback.
                self.page.keyboard.press("Enter")
        self._wait_for_assistant_after(before, before_text)
        self.last_answer = self._latest_assistant_text()
        self.sources = self._extract_sources_from_dom()
        self.conversation_url = self.current_conversation_url(self.conversation_url)

    def current_conversation_url(self, fallback: str | None = None) -> str | None:
        try:
            url = str(self.page.url)
            if url.startswith("https://chatgpt.com/") and "/c/" in url:
                return url
        except Exception:
            pass
        return fallback

    def _find_prompt_box(self):
        for sel in self.selectors.get("prompt_box", []):
            try:
                if sel == "role:textbox":
                    loc = self.page.get_by_role("textbox").last
                else:
                    loc = self.page.locator(sel).last
                loc.wait_for(state="visible", timeout=3000)
                return loc
            except Exception:
                continue
        return None

    def _assistant_count(self) -> int:
        try:
            return self.page.locator('[data-message-author-role="assistant"]').count()
        except Exception:
            return 0

    def _user_count(self) -> int:
        try:
            return self.page.locator('[data-message-author-role="user"]').count()
        except Exception:
            return 0

    def _latest_assistant_text(self) -> str:
        for sel in self.selectors.get("assistant_messages", []) + ['[data-message-author-role="assistant"]']:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    return loc.last.inner_text(timeout=5000).strip()
            except Exception:
                continue
        return self.page.locator("body").inner_text(timeout=5000)[-5000:]

    def _extract_sources_from_dom(self) -> list[dict]:
        out, seen = [], set()
        try:
            scope = self.page.locator('[data-message-author-role="assistant"]').last
            links = scope.locator('a[href^="http"]')
            count = min(links.count(), 20)
            for i in range(count):
                link = links.nth(i)
                href = link.get_attribute("href") or ""
                if not href or "chatgpt.com" in href or href in seen:
                    continue
                seen.add(href)
                try:
                    title = link.inner_text(timeout=1000).strip() or href
                except Exception:
                    title = href
                out.append({"url": href, "title": title})
        except Exception:
            pass
        return out

    def _wait_for_assistant_after(self, before: int, before_text: str = "") -> None:
        # Wait until a new assistant message appears or the latest assistant text changes from the previous answer.
        try:
            self.page.wait_for_function(
                "([before, beforeText]) => { const els=[...document.querySelectorAll('[data-message-author-role=\"assistant\"]')]; const last=els.at(-1)?.innerText?.trim() || ''; return els.length > before || (last && last !== beforeText); }",
                arg=[before, before_text],
                timeout=90000,
            )
        except Exception:
            self.page.wait_for_timeout(3000)
        last = ""
        stable = 0
        for _ in range(150):
            cur = self._latest_assistant_text().strip()
            low = cur.lower()
            future_preamble = low.startswith(("i'll ", "i’ll ", "i will ")) and any(word in low[:120] for word in ("verify", "search", "research", "ground", "check"))
            transient = (not cur) or cur == before_text or future_preamble or low in {"thinking", "typing"} or low.startswith("thinking") or low.startswith("thought for")
            running = self._is_generation_running()
            if transient:
                stable = 0
            elif running:
                stable = 0
                last = cur
            elif cur == last:
                stable += 1
                if stable >= 4:
                    return
            else:
                stable = 0; last = cur
            self.page.wait_for_timeout(1000)

    def _is_generation_running(self) -> bool:
        """Best-effort generation-state check.

        ChatGPT Web can pause for several seconds while browsing or thinking. A
        text-only stability check can therefore return an incomplete preamble.
        Prefer explicit stop-control detection when the current UI exposes it,
        then fall back to text stability in `_wait_for_assistant_after`.
        """
        for sel in self.selectors.get("stop_button", []):
            try:
                if sel.startswith("role:button:"):
                    name = sel.split(":", 2)[2]
                    loc = self.page.get_by_role("button", name=name).last
                else:
                    loc = self.page.locator(sel).last
                if loc.count() > 0 and loc.is_visible(timeout=500):
                    return True
            except Exception:
                continue
        return False
