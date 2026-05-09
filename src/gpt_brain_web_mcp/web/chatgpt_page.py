from __future__ import annotations

import os
import time
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
    web_search_available: bool = True

    def select_mode_label(self, label: str) -> bool:
        if label in self.available_mode_labels:
            self.selected_tier = label
            return True
        return False

    def ensure_logged_in(self) -> None:
        if not self.logged_in:
            raise NeedsUserAction("ChatGPT login required; run `gpt-brain-web login`.")

    def open_project(self, project_name: str) -> bool:
        return bool(project_name)

    def list_projects(self, limit: int = 50) -> list[str]:
        return []

    def create_project(self, project_name: str) -> bool:
        return bool(project_name)

    def delete_project(self, project_name: str) -> bool:
        return bool(project_name)

    def ensure_conversation_focus(self, conversation_url: str | None = None, project_name: str | None = None) -> bool:
        return True

    def start_new_chat(self, project_name: str | None = None) -> bool:
        self.conversation_url = None
        return True

    def delete_current_conversation(self) -> bool:
        self.conversation_url = None
        return True

    def check_deep_research_ui(self) -> dict:
        return {"available": bool(self.deep_research_available), "enabled": bool(self.deep_research_available), "pill_detected": bool(self.deep_research_available), "warnings": [] if self.deep_research_available else ["Deep Research UI not available in mock page."]}

    def check_web_search_ui(self) -> dict:
        return {"available": bool(self.web_search_available), "enabled": bool(self.web_search_available), "pill_detected": bool(self.web_search_available), "warnings": [] if self.web_search_available else ["Web Search UI not available in mock page."]}

    def enable_web_search(self) -> bool:
        return bool(self.web_search_available)

    def disable_web_search(self) -> bool:
        return True

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
                target_text = ""
                try:
                    target_text = target.inner_text(timeout=1000)
                except Exception:
                    pass
                if effort_label.lower() in target_text.lower():
                    target.click(timeout=3000)
                    self.page.wait_for_timeout(500)
                    self.selected_tier = f"{model_label} {effort_label}"
                    return True
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
                # Do not pretend a requested Standard/Extended/Heavy effort was selected
                # when ChatGPT did not expose that effort control.
                return False
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
        if not self._open_composer_plus_menu():
            self.deep_research_available = False
            return False
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


    def _visible_pill_or_button(self, labels: list[str]) -> bool:
        for label in labels:
            for make in (
                lambda label=label: self.page.get_by_label(label, exact=False).last,
                lambda label=label: self.page.get_by_role("button", name=label, exact=False).last,
                lambda label=label: self.page.get_by_text(label, exact=False).last,
            ):
                try:
                    loc = make()
                    if loc.count() > 0 and loc.is_visible(timeout=500):
                        return True
                except Exception:
                    continue
        return False

    def enable_web_search(self) -> bool:
        if not self._open_composer_plus_menu():
            self.web_search_available = False
            return False
        for label in ["Search", "Search the web", "Web search", "Browse"]:
            try:
                self.page.get_by_text(label, exact=True).last.click(timeout=2500)
                self.page.wait_for_timeout(500)
                self.web_search_available = True
                return True
            except Exception:
                continue
            try:
                self.page.get_by_role("button", name=label, exact=False).last.click(timeout=2500)
                self.page.wait_for_timeout(500)
                self.web_search_available = True
                return True
            except Exception:
                continue
        self.web_search_available = False
        return False

    def disable_web_search(self) -> bool:
        for label in ["Search, click to remove", "Web search, click to remove", "Search the web, click to remove"]:
            try:
                self.page.get_by_label(label).last.click(timeout=1500)
                self.page.wait_for_timeout(300)
                return True
            except Exception:
                continue
        try:
            buttons = self.page.locator("button").filter(has_text="Search")
            if buttons.count() > 0:
                buttons.last.click(timeout=1500)
                self.page.wait_for_timeout(300)
                return True
        except Exception:
            pass
        return False

    def check_deep_research_ui(self) -> dict:
        warnings: list[str] = []
        available = self.enable_deep_research()
        pill = self._visible_pill_or_button(["Deep research", "Deep Research"])
        if available and not pill:
            warnings.append("Deep Research control clicked, but active pill was not detected.")
        if not available:
            warnings.append("Deep Research UI not visible from composer plus menu.")
        if available:
            self.disable_deep_research()
        return {"available": available, "enabled": available, "pill_detected": pill, "warnings": warnings}

    def check_web_search_ui(self) -> dict:
        warnings: list[str] = []
        available = self.enable_web_search()
        pill = self._visible_pill_or_button(["Search", "Web search", "Search the web", "Browse"])
        if available and not pill:
            warnings.append("Search control clicked, but active search pill was not detected.")
        if not available:
            warnings.append("Search/Web Search UI not visible from composer plus menu.")
        if available:
            self.disable_web_search()
        return {"available": available, "enabled": available, "pill_detected": pill, "warnings": warnings}



    def _js_click_exact_text(self, text: str) -> bool:
        try:
            return bool(self.page.evaluate(
                """
                (target) => {
                  const nodes = Array.from(document.querySelectorAll('button,a,[role="button"],[role="menuitem"]'));
                  const el = nodes.find(n => ((n.innerText || n.textContent || '').replace(/\\s+/g, ' ').trim()) === target);
                  if (!el) return false;
                  el.scrollIntoView({block: 'center', inline: 'center'});
                  el.click();
                  return true;
                }
                """,
                text,
            ))
        except Exception:
            return False

    def _visible_clickable_texts(self) -> list[str]:
        try:
            return self.page.evaluate(
                """
                () => Array.from(document.querySelectorAll('button,a,[role="menuitem"],[role="option"],[role="treeitem"]'))
                  .filter(el => {
                    const r = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return r.width > 0 && r.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
                  })
                  .map(el => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim())
                  .filter(Boolean)
                """
            )
        except Exception:
            return []

    def _open_projects_menu(self) -> bool:
        if not self._open_composer_plus_menu():
            return False
        for label in ["Projects", "Project"]:
            for action in ("hover", "click"):
                try:
                    loc = self.page.get_by_text(label, exact=True).last
                    if action == "hover":
                        loc.hover(timeout=1500)
                    else:
                        loc.click(timeout=1500)
                    self.page.wait_for_timeout(500)
                    return True
                except Exception:
                    continue
                try:
                    loc = self.page.get_by_role("menuitem", name=label, exact=False).last
                    if action == "hover":
                        loc.hover(timeout=1500)
                    else:
                        loc.click(timeout=1500)
                    self.page.wait_for_timeout(500)
                    return True
                except Exception:
                    continue
        return False

    def open_project(self, project_name: str) -> bool:
        """Open an existing ChatGPT Project from the dedicated profile UI.

        ChatGPT currently exposes projects both in the side rail and, on some
        layouts, from the composer `+ -> Projects` submenu. Try both and fail
        closed when the exact visible project cannot be selected.
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
        if self._open_projects_menu() and self._click_project_text(name):
            return True
        return False


    def list_projects(self, limit: int = 50) -> list[str]:
        """Best-effort visible project listing.

        Prefer the composer `+ -> Projects` submenu because it exposes a compact
        project list even when the left sidebar is collapsed. Fall back to the
        side rail text list if the submenu is unavailable.
        """
        self._ensure_sidebar_visible()
        self._expand_projects_sidebar()
        self._click_sidebar_more()
        self._expand_projects_sidebar()
        menu_opened = self._open_projects_menu()
        if menu_opened:
            texts = self._visible_clickable_texts()
            project_indexes = [i for i, t in enumerate(texts) if " ".join((t or "").split()).lower() == "projects"]
            if project_indexes:
                texts = texts[project_indexes[-1] + 1:]
        else:
            try:
                texts = self.page.locator("a, button").all_inner_texts()
            except Exception:
                texts = []
        normalized = [" ".join((t or "").split()) for t in texts]
        # If we are looking at the full sidebar DOM, project rows are between
        # the `New project` affordance and the `Recents` section. This avoids
        # returning normal chat history as projects.
        lows = [t.lower() for t in normalized]
        if "new project" in lows and "recents" in lows:
            start = lows.index("new project") + 1
            end = lows.index("recents", start) if "recents" in lows[start:] else len(normalized)
            texts = normalized[start:end]
        else:
            texts = normalized
        skip = {
            "", "new chat", "search", "search chats", "library", "sora", "gpts",
            "projects", "project", "more", "show more", "new project", "chatgpt pro",
            "add photos & files", "recent files", "create image", "deep research",
            "web search", "recents", "skip to content",
        }
        names: list[str] = []
        seen: set[str] = set()
        for raw in texts:
            name = " ".join((raw or "").split())
            low = name.lower()
            if not name or len(name) > 120 or low in skip or name in seen:
                continue
            if low.startswith("chatgpt") or low.startswith("upgrade"):
                continue
            seen.add(name); names.append(name)
            if len(names) >= limit:
                break
        return names

    def create_project(self, project_name: str) -> bool:
        name = (project_name or "").strip()
        if not name:
            return False
        self._ensure_sidebar_visible()
        self._expand_projects_sidebar()
        opened = False
        for label in ["New project", "Create project", "Add project"]:
            try:
                self.page.get_by_role("button", name=label, exact=False).last.click(timeout=2000, force=True)
                self.page.wait_for_timeout(500)
                opened = True
                break
            except Exception:
                try:
                    self.page.get_by_text(label, exact=False).last.click(timeout=2000, force=True)
                    self.page.wait_for_timeout(500)
                    opened = True
                    break
                except Exception:
                    if self._js_click_exact_text(label):
                        self.page.wait_for_timeout(800)
                        opened = True
                        break
                    continue
        if not opened:
            return False
        try:
            try:
                box = self.page.locator('input[placeholder="Copenhagen Trip"]').last
                box.fill(name, timeout=3000)
            except Exception:
                box = self.page.locator("input:visible").last
                box.fill(name, timeout=3000)
        except Exception:
            return False
        for label in ["Create project", "Create", "Done", "Continue"]:
            try:
                self.page.get_by_role("button", name=label, exact=True).last.click(timeout=3000, force=True)
                self.page.wait_for_timeout(1500)
                return self.open_project(name)
            except Exception:
                continue
        return self.open_project(name)

    def ensure_conversation_focus(self, conversation_url: str | None = None, project_name: str | None = None) -> bool:
        if conversation_url and conversation_url.startswith("https://chatgpt.com/c/"):
            try:
                if str(self.page.url).startswith(conversation_url):
                    return True
                self.page.goto(conversation_url, wait_until="domcontentloaded", timeout=20000)
                self.page.wait_for_timeout(800)
                return str(self.page.url).startswith(conversation_url) and self.is_prompt_box_available()
            except Exception:
                return False
        if project_name:
            return self.open_project(project_name) and self.is_prompt_box_available()
        return self.is_prompt_box_available()

    def delete_project(self, project_name: str) -> bool:
        name = (project_name or "").strip()
        if not name or not self.open_project(name):
            return False
        opened_menu = False
        for label in [f"Open project options for {name}", "Show project details", "Open project options", "More options", "More"]:
            try:
                self.page.get_by_label(label, exact=True).click(timeout=2500, force=True)
                self.page.wait_for_timeout(500)
                opened_menu = True
                break
            except Exception:
                try:
                    self.page.get_by_role("button", name=label, exact=False).last.click(timeout=2500, force=True)
                    self.page.wait_for_timeout(500)
                    opened_menu = True
                    break
                except Exception:
                    continue
        if not opened_menu:
            return False
        clicked_delete = False
        for label in ["Delete project", "Delete Project"]:
            try:
                self.page.get_by_text(label, exact=True).last.click(timeout=2500, force=True)
                self.page.wait_for_timeout(700)
                clicked_delete = True
                break
            except Exception:
                continue
        if not clicked_delete:
            return False
        try:
            boxes = self.page.get_by_role("textbox")
            if boxes.count() > 0:
                box = boxes.last
                if box.is_visible(timeout=500):
                    box.fill(name, timeout=1500)
        except Exception:
            pass
        for label in ["Delete", "Delete project", "Confirm"]:
            try:
                self.page.get_by_role("button", name=label, exact=True).last.click(timeout=3000, force=True)
                self.page.wait_for_timeout(2500)
                return True
            except Exception:
                continue
        return False

    def start_new_chat(self, project_name: str | None = None) -> bool:
        """Start a real new ChatGPT composer before sending.

        For explicit projects, opening the project landing page gives a project
        scoped composer. For global/implicit use, click New chat and verify the
        prompt box is available. This is used by `conversation_strategy=new`.
        """
        if project_name:
            return self.open_project(project_name) and self.is_prompt_box_available()
        for label in ["New chat", "Start new chat"]:
            try:
                self.page.get_by_text(label, exact=True).last.click(timeout=2000)
                self.page.wait_for_timeout(800)
                return self.is_prompt_box_available()
            except Exception:
                continue
            try:
                self.page.get_by_role("link", name=label).last.click(timeout=2000)
                self.page.wait_for_timeout(800)
                return self.is_prompt_box_available()
            except Exception:
                continue
        # Direct navigation to the ChatGPT root is a stable way to request a
        # fresh global composer when the sidebar New chat control is not visible
        # in the current responsive layout.
        try:
            self.page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=15000)
            self.page.wait_for_timeout(1000)
            if self.is_prompt_box_available() and "/c/" not in str(self.page.url):
                return True
        except Exception:
            pass
        # If already on an empty composer, consider it usable but not a confirmed
        # navigation.
        try:
            if "/c/" not in str(self.page.url) and self.is_prompt_box_available():
                return True
        except Exception:
            pass
        return False

    def delete_current_conversation(self) -> bool:
        """Delete the currently open ChatGPT conversation via explicit UI controls.

        This should only be called for a caller-supplied conversation URL with a
        separate confirmation flag. It intentionally targets the conversation
        header's "Open conversation options" menu instead of project/sidebar
        option buttons.
        """
        try:
            self.page.get_by_label("Open conversation options").last.click(timeout=3000)
            self.page.wait_for_timeout(500)
            self.page.get_by_text("Delete", exact=True).last.click(timeout=3000)
            self.page.wait_for_timeout(500)
            self.page.locator("button").filter(has_text="Delete").last.click(timeout=3000)
            self.page.wait_for_timeout(2000)
            try:
                return "/c/" not in str(self.page.url)
            except Exception:
                return True
        except Exception:
            return False

    def _ensure_sidebar_visible(self) -> None:
        # In normal desktop widths the sidebar is already visible. The buttons
        # below cover collapsed/narrow layouts without depending on CSS classes.
        for label in ["Open sidebar", "Show sidebar", "Sidebar"]:
            try:
                btn = self.page.get_by_role("button", name=label).last
                if btn.count() > 0 and btn.is_visible(timeout=500):
                    try:
                        btn.click(timeout=1000)
                    except Exception:
                        btn.click(timeout=1000, force=True)
                    self.page.wait_for_timeout(800)
                    return
            except Exception:
                if self._js_click_exact_text(label):
                    self.page.wait_for_timeout(800)
                    return
                continue
            try:
                clicked = bool(self.page.evaluate(
                    """() => { const el = Array.from(document.querySelectorAll('button')).find(b => b.getAttribute('aria-label') === 'Open sidebar'); if (!el) return false; el.click(); return true; }"""
                ))
                if clicked:
                    self.page.wait_for_timeout(800)
                    return
            except Exception:
                pass

    def _expand_projects_sidebar(self) -> None:
        for label in ["Projects", "Show projects", "More projects"]:
            for make in (
                lambda label=label: self.page.get_by_text(label, exact=True).first,
                lambda label=label: self.page.get_by_role("button", name=label, exact=False).first,
                lambda label=label: self.page.get_by_text(label, exact=False).first,
            ):
                try:
                    loc = make()
                    loc.click(timeout=1000, force=True)
                    self.page.wait_for_timeout(500)
                    return
                except Exception:
                    continue
            if self._js_click_exact_text(label):
                self.page.wait_for_timeout(500)
                return

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
                try:
                    loc.click(timeout=2000)
                except Exception:
                    try:
                        loc.click(timeout=2000, force=True)
                    except Exception:
                        if not self._js_click_exact_text(name):
                            raise
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
                    timeout=12000,
                )
            except Exception:
                # Do not submit again: slow DOM/network can hide a successful
                # click for several seconds, and a second Enter duplicates the
                # prompt. If generation/assistant output cannot be observed
                # later, the wait path will fail clearly.
                pass
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
        candidates = [
            'textarea[aria-label*="Chat"]:visible',
            'div[contenteditable="true"][aria-label*="Chat"]:visible',
            '#prompt-textarea:visible',
            'textarea:visible',
            'div[contenteditable="true"]:visible',
        ]
        for css in candidates:
            try:
                locs = self.page.locator(css)
                if locs.count() == 0:
                    continue
                loc = locs.last
                loc.wait_for(state="visible", timeout=1200)
                loc.scroll_into_view_if_needed(timeout=1000)
                return loc
            except Exception:
                continue
        for sel in self.selectors.get("prompt_box", []):
            try:
                if sel == "role:textbox":
                    locs = self.page.get_by_role("textbox")
                else:
                    locs = self.page.locator(sel)
                count = locs.count()
                for i in range(count - 1, -1, -1):
                    loc = locs.nth(i)
                    try:
                        if loc.is_visible(timeout=500):
                            loc.scroll_into_view_if_needed(timeout=1000)
                            return loc
                    except AttributeError:
                        loc.wait_for(state="visible", timeout=1200)
                        loc.scroll_into_view_if_needed(timeout=1000)
                        return loc
                    except Exception:
                        continue
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
        # Do not fall back to the full page body here: during Deep Research or
        # failed submits the body contains sidebars, prompt text, and controls,
        # which can look stable and be mistaken for a completed answer.
        return ""

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
        timeout_s = max(30, int(os.getenv("GPT_BRAIN_RESPONSE_TIMEOUT_SECONDS", "600")))
        stale_refresh_s = int(os.getenv("GPT_BRAIN_STALE_REFRESH_SECONDS", "240"))
        heartbeat_s = max(5, int(os.getenv("GPT_BRAIN_HEARTBEAT_SECONDS", "20")))
        deadline = time.time() + timeout_s
        last_change = time.time()
        last_heartbeat = 0.0
        refreshed = False
        callback = getattr(self, "progress_callback", None)
        while time.time() < deadline:
            cur = self._latest_assistant_text().strip()
            low = cur.lower()
            future_preamble = low.startswith(("i'll ", "i’ll ", "i will ")) and any(word in low[:120] for word in ("verify", "search", "research", "ground", "check"))
            transient = (not cur) or cur == before_text or future_preamble or low in {"thinking", "typing"} or low.startswith("thinking") or low.startswith("thought for")
            running = self._is_generation_running()
            now = time.time()
            if callback and now - last_heartbeat >= heartbeat_s:
                try:
                    callback("heartbeat", cur[-500:] if cur else "waiting for ChatGPT response")
                except Exception:
                    pass
                last_heartbeat = now
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
                stable = 0; last = cur; last_change = now
            if stale_refresh_s > 0 and not refreshed and not running and now - last_change >= stale_refresh_s:
                if callback:
                    try:
                        callback("refresh", f"No visible answer progress for {stale_refresh_s}s; refreshing ChatGPT page once.")
                    except Exception:
                        pass
                try:
                    self.page.reload(wait_until="domcontentloaded", timeout=30000)
                    self.page.wait_for_timeout(3000)
                    refreshed = True
                    last_change = time.time()
                    last = self._latest_assistant_text().strip()
                    stable = 0
                except Exception:
                    refreshed = True
            self.page.wait_for_timeout(1000)
        raise TimeoutError(f"Timed out waiting for ChatGPT response after {timeout_s}s")

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
