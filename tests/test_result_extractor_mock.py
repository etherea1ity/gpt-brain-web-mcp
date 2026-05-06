from gpt_brain_web_mcp.web.chatgpt_page import MockChatGPTPage
from gpt_brain_web_mcp.web.result_extractor import ResultExtractor
from gpt_brain_web_mcp.web.source_extractor import SourceExtractor


def test_result_and_source_extractors():
    page = MockChatGPTPage()
    page.submit_prompt("hello", web_search=True)
    assert ResultExtractor().extract_answer(page).startswith("Mock ChatGPT web answer")
    assert ResultExtractor().is_streaming_complete(page)
    assert SourceExtractor().extract_sources(page)[0]["url"] == "https://example.com/mock"
    assert SourceExtractor().extract_sources("see https://example.org/a.")[0]["url"] == "https://example.org/a"


def test_structured_sources_are_redacted():
    page = MockChatGPTPage()
    page.sources = [{"title": "signed", "url": "https://example.com/a?token=secret&safe=ok"}]
    source = SourceExtractor().extract_sources(page)[0]
    assert "secret" not in source["url"]
    assert "safe=ok" in source["url"]
