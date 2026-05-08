from types import SimpleNamespace

from gpt_brain_web_mcp.web.chatgpt_page import ChatGPTPage


def test_mode_label_maps_pro_standard_and_extended():
    page = object.__new__(ChatGPTPage)
    assert page._map_mode_label("Pro") == ("Pro", "Standard")
    assert page._map_mode_label("Pro Extended") == ("Pro", "Extended")
    assert page._map_mode_label("Thinking Heavy") == ("Thinking", "Heavy")
    assert page._map_mode_label("Extended Thinking") == ("Thinking", "Extended")


class _FakeLocator:
    def __init__(self, name="", *, count=1, text=""):
        self.name = name
        self._count = count
        self._text = text
        self.clicked = False
        self.scrolled = False
        self.filled = None

    @property
    def last(self):
        return self

    def nth(self, _):
        return self

    def count(self):
        return self._count

    def wait_for(self, **_):
        return None

    def scroll_into_view_if_needed(self, **_):
        self.scrolled = True

    def click(self, **_):
        self.clicked = True

    def fill(self, value):
        self.filled = value

    def inner_text(self, **_):
        return self._text

    def locator(self, _):
        return _FakeLocator(count=0)

    def filter(self, **_):
        return self


class _FakePage:
    def __init__(self):
        self.role_textbox = _FakeLocator("role-textbox")

    def get_by_role(self, role, **_):
        assert role == "textbox"
        return self.role_textbox

    def locator(self, _):
        return _FakeLocator(count=0)


def test_find_prompt_box_uses_last_role_textbox_and_scrolls():
    fake = _FakePage()
    page = ChatGPTPage(fake, {"prompt_box": ["role:textbox"]})
    loc = page._find_prompt_box()
    assert loc is fake.role_textbox
    assert loc.scrolled is True
