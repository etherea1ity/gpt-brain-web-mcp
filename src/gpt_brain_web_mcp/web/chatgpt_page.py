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
        mapped = self._map_mode_label(label)
        if mapped:
            model, effort = mapped
            if self.select_model_mode(model, effort):
                self.selected_tier = label
                return True
        # Honest fallback: accept the mode only if its label is visible in the current UI.
        try:
            body = self.page.locator("body").inner_text(timeout=3000)
            if label.lower() in body.lower():
                if self._open_model_menu():
                    try:
                        self.page.get_by_text(label, exact=False).last.click(timeout=3000)
                        self.selected_tier = label
                        return True
                    except Exception:
                        pass
        except Exception:
            pass
        return False

    def _map_mode_label(self, label: str) -> tuple[str, str | None] | None:
        low = label.lower()
        if "pro" in low and "extended" in low:
            return ("Pro", "Extended")
        if "pro" in low:
            return ("Pro", "Standard")
        if "heavy" in low or "high" in low:
            return ("Thinking", "Heavy")
        if "extended" in low or "longer" in low:
            return ("Thinking", "Extended")
        if any(x in low for x in ["thinking", "standard", "default", "normal"]):
            return ("Thinking", "Standard")
        if "instant" in low:
            return ("Instant", None)
        return None

    def _open_model_menu(self) -> bool:
        for sel in self.selectors.get("model_picker", []):
            try:
                if sel.startswith("role:button:"):
                    name = sel.split(":", 2)[2]
                    self.page.get_by_role("button", name=name).last.click(timeout=2500)
                else:
                    self.page.locator(sel).last.click(timeout=2500)
                self.page.wait_for_timeout(400)
                if self.page.locator('[role="menu"]').count() > 0:
                    return True
            except Exception:
                continue
        for text in ["Heavy", "Thinking", "Extended", "Instant", "Pro"]:
            try:
                self.page.get_by_text(text, exact=True).last.click(timeout=2500)
                self.page.wait_for_timeout(400)
                if self.page.locator('[role="menu"]').count() > 0:
                    return True
            except Exception:
                continue
        return False

    def select_model_mode(self, model_label: str, effort_label: str | None = None) -> bool:
        """Select ChatGPT's model/mode picker without sending a prompt.

        Current ChatGPT Pro UI exposes rows such as Instant, Thinking and Pro.
        Thinking/Pro rows have a trailing Effort button that opens Light /
        Standard / Extended / Heavy options. This method follows that UI and
        returns false instead of pretending success when the controls are absent.
        """
        if not self._open_model_menu():
            return False
        try:
            rows = self.page.locator('[role="menuitemradio"]')
            target = None
            for i in range(rows.count()):
                row = rows.nth(i)
                try:
                    if model_label.lower() in row.inner_text(timeout=1000).lower():
                        target = row
                        break
                except Exception:
                    continue
            if target is None:
                return False
            if effort_label:
                effort_button = target.locator('[aria-label="Effort"], [data-model-picker-thinking-effort-action="true"]').last
                if effort_button.count() > 0:
                    effort_button.click(timeout=3000)
                    self.page.wait_for_timeout(300)
                    options = self.page.locator('[role="menuitemradio"]')
                    for i in range(options.count()):
                        opt = options.nth(i)
                        try:
                            if opt.inner_text(timeout=1000).strip().lower() == effort_label.lower():
                                opt.click(timeout=3000)
                                self.page.wait_for_timeout(500)
                                self.selected_tier = f"{model_label} {effort_label}"
                                return True
                        except Exception:
                            continue
                # Fall back to selecting the model row if the effort submenu is absent.
            target.click(timeout=3000)
            self.page.wait_for_timeout(500)
            self.selected_tier = model_label if not effort_label else f"{model_label} {effort_label}"
            return True
        finally:
            try:
                self.page.keyboard.press("Escape")
            except Exception:
                pass

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
        self._open_composer_plus_menu()
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

    def _open_composer_plus_menu(self) -> bool:
        for sel in ['[data-testid="composer-plus-btn"]', 'button[aria-label*="Add files"]', 'button[aria-label*="Add"]']:
            try:
                self.page.locator(sel).last.click(timeout=2500)
                self.page.wait_for_timeout(400)
                return True
            except Exception:
                continue
        return False

    def open_project(self, project_name: str) -> bool:
        """Open an existing ChatGPT Project from the dedicated sidebar.

        This is deliberately conservative: it does not create projects or
        upload files. It tries visible project rows first, then expands the
        sidebar's More/Projects affordances when the project list is long.
        """
        name = (project_name or "").strip()
        if not name:
            return False
        self._ensure_sidebar_visible()
        if self._click_project_text(name):
            return True
        self._expand_projects_sidebar()
        if self._click_project_text(name):
            return True
        self._click_sidebar_more()
        self._expand_projects_sidebar()
        if self._click_project_text(name):
            return True
        return False

    def _ensure_sidebar_visible(self) -> None:
        # In normal desktop widths the sidebar is already visible. The buttons
        # below cover collapsed/narrow layouts without depending on CSS classes.
        for label in ["Open sidebar", "Show sidebar", "Sidebar"]:
            try:
                btn = self.page.get_by_role("button", name=label).last
                if btn.count() > 0 and btn.is_visible(timeout=500):
                    btn.click(timeout=1000)
                    self.page.wait_for_timeout(300)
                    return
            except Exception:
                continue

    def _expand_projects_sidebar(self) -> None:
        for label in ["Projects", "Show projects", "More projects"]:
            try:
                self.page.get_by_text(label, exact=False).last.click(timeout=1000)
                self.page.wait_for_timeout(500)
                return
            except Exception:
                pass
            try:
                self.page.get_by_role("button", name=label).last.click(timeout=1000)
                self.page.wait_for_timeout(300)
                return
            except Exception:
                continue

    def _click_sidebar_more(self) -> None:
        for label in ["More", "Show more"]:
            try:
                self.page.get_by_text(label, exact=True).last.click(timeout=1000)
                self.page.wait_for_timeout(500)
                return
            except Exception:
                pass
            try:
                self.page.get_by_role("button", name=label).last.click(timeout=1000)
                self.page.wait_for_timeout(300)
                return
            except Exception:
                continue

    def _click_project_text(self, name: str) -> bool:
        candidates = [
            lambda: self.page.get_by_role("link", name=name, exact=True).last,
            lambda: self.page.get_by_role("button", name=name, exact=True).last,
            lambda: self.page.get_by_text(name, exact=True).last,
        ]
        for make in candidates:
            try:
                loc = make()
                if loc.count() == 0:
                    continue
                try:
                    loc.scroll_into_view_if_needed(timeout=1000)
                except Exception:
                    pass
                loc.click(timeout=2000)
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass
                self.page.wait_for_timeout(800)
                return True
            except Exception:
                continue
        return False

    def disable_deep_research(self) -> bool:
        for label in ["Deep research, click to remove", "Deep Research, click to remove"]:
            try:
                self.page.get_by_label(label).last.click(timeout=2000)
                self.page.wait_for_timeout(500)
                self.deep_research_available = False
                return True
            except Exception:
                continue
        try:
            buttons = self.page.locator("button").filter(has_text="Deep research")
            if buttons.count() > 0:
                buttons.last.click(timeout=2000)
                self.page.wait_for_timeout(500)
                self.deep_research_available = False
                return True
        except Exception:
            pass
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
                try:
                    loc.scroll_into_view_if_needed(timeout=1000)
                except Exception:
                    pass
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
