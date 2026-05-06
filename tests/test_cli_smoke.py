from gpt_brain_web_mcp.cli import main


def test_cli_smoke_defaults_to_mock(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("RUN_LIVE_CHATGPT_WEB", raising=False)
    monkeypatch.delenv("GPT_BRAIN_WEB_MOCK", raising=False)
    monkeypatch.setenv("GPT_BRAIN_HOME", str(tmp_path / "home"))
    assert main(["smoke"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "mock"' in out
    assert '"GPT_BRAIN_WEB_SMOKE_OK"' in out


def test_cli_smoke_live_mode_is_explicit(monkeypatch, tmp_path, capsys):
    class FakeService:
        def __init__(self, settings): pass
        def tool_ask_brain(self, **kwargs):
            return {"answer": "GPT_BRAIN_WEB_SMOKE_OK"}
    monkeypatch.setattr("gpt_brain_web_mcp.cli.WebBrainService", FakeService)
    monkeypatch.setenv("RUN_LIVE_CHATGPT_WEB", "1")
    monkeypatch.setenv("GPT_BRAIN_WEB_MOCK", "1")
    monkeypatch.setenv("GPT_BRAIN_HOME", str(tmp_path / "home"))
    assert main(["smoke"]) == 0
    out = capsys.readouterr().out
    assert '"mode": "live"' in out
