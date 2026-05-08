# One-click install

For a fresh clone:

```bash
git clone <repo>
cd gpt-brain-web-mcp
./install.sh
gpt-brain-web login
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 gpt-brain-web smoke
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 python scripts/live_validate.py
```

Windows:

```powershell
git clone <repo>
cd gpt-brain-web-mcp
.\install.ps1
gpt-brain-web login
$env:RUN_LIVE_CHATGPT_WEB="1"; $env:GPT_BRAIN_WEB_MOCK="0"; gpt-brain-web smoke
```

`install` creates a venv when available, falls back to a user install on systems without `python3-venv`, safely merges Codex MCP config, and creates a backup. The installer uses only a pre-login mock smoke; real acceptance happens after `gpt-brain-web login`. Use `--dry-run` to inspect actions and `--no-codex-config` to skip the merge.

Uninstall the MCP config while preserving the login profile:

```bash
./install.sh --uninstall
```


After live validation, clean local test records when needed:

```bash
gpt-brain-web records list
gpt-brain-web records delete <job_id_or_session_id>
```

Remote ChatGPT cleanup is explicit and guarded:

```bash
gpt-brain-web records delete-remote https://chatgpt.com/c/... --confirm
```
