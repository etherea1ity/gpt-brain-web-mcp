from __future__ import annotations
import shutil, time
from pathlib import Path


def block(python_path: str, home: str, headless: bool = True, default_project: str = "Codex Brain") -> str:
    env = f'{{ "GPT_BRAIN_BACKEND" = "web-chatgpt", "GPT_BRAIN_DEFAULT_TIER" = "thinking_heavy", "GPT_BRAIN_ALLOW_PRO_DEFAULT" = "false", "GPT_BRAIN_DEFAULT_PROJECT" = "{default_project}", "GPT_BRAIN_CONVERSATION_POLICY" = "reuse_project", "GPT_BRAIN_BROWSER_HEADLESS" = "{str(headless).lower()}", "GPT_BRAIN_HOME" = "{home}" }}'
    return f'[mcp_servers.gpt-brain-web]\ncommand = "{python_path}"\nargs = ["-m", "gpt_brain_web_mcp.server"]\nenv = {env}\n'


def merge_config(path: str | Path, python_path: str, home: str, dry_run: bool = False, uninstall: bool = False, headless: bool = True, default_project: str = "Codex Brain") -> str:
    p = Path(path).expanduser(); text = p.read_text(encoding="utf-8") if p.exists() else ""; start = text.find("[mcp_servers.gpt-brain-web]")
    if uninstall:
        if start >= 0:
            nxt = text.find("\n[", start+1); new = text[:start].rstrip()+"\n"+(text[nxt+1:] if nxt>=0 else "")
        else: new = text
    else:
        new_block = block(python_path, home, headless, default_project); nxt = text.find("\n[", start+1) if start >= 0 else -1
        if start >= 0: new = text[:start].rstrip()+"\n\n"+new_block+("\n"+text[nxt+1:] if nxt>=0 else "")
        else: new = text.rstrip()+("\n\n" if text.strip() else "")+new_block
    if dry_run: return new
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists(): shutil.copy2(p, p.with_name(p.name+f".bak.{int(time.time())}"))
    p.write_text(new, encoding="utf-8")
    return str(p)
