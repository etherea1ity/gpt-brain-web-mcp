from pathlib import Path
from gpt_brain_web_mcp.codex_config import merge_config


def test_codex_config_merge_preserves_existing_and_backup(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[other]\nvalue = 1\n", encoding="utf-8")
    out = merge_config(cfg, "/python", "/home/brain", dry_run=True)
    assert "[other]" in out
    assert "[mcp_servers.gpt-brain-web]" in out
    assert "GPT_BRAIN_DEFAULT_PROJECT" in out
    assert "GPT_BRAIN_CONVERSATION_POLICY" in out
    merge_config(cfg, "/python", "/home/brain", dry_run=False)
    assert "[other]" in cfg.read_text(encoding="utf-8")
    assert list(tmp_path.glob("config.toml.bak.*"))
    merge_config(cfg, "/python", "/home/brain", uninstall=True)
    assert "gpt-brain-web" not in cfg.read_text(encoding="utf-8")
