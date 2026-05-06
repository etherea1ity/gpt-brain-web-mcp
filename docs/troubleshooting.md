# Troubleshooting

## Login expired

Symptom: tool returns `needs_user_action` or doctor says prompt box missing.

Fix:

```bash
gpt-brain-web login
```

Log in manually. The project will not bypass login, CAPTCHA, or 2FA.

## CAPTCHA / 2FA

Complete it manually in the dedicated login window. Automation stops and reports `needs_user_action`.

## Prompt box not found

Run:

```bash
gpt-brain-web doctor --verbose
```

If ChatGPT UI changed, update `config/selectors.yaml` and rerun doctor.

## Model picker not found

Update mode labels in `config/model_modes.yaml` or selectors in `config/selectors.yaml`. The backend will fallback and warn instead of pretending the mode was selected.

## Deep Research not found

This is expected for accounts/UI states where Deep Research is unavailable. `start_research` falls back to a Web Research prompt and records a warning.

## Headless unstable

Use visible debug mode:

```bash
GPT_BRAIN_BROWSER_VISIBLE=true gpt-brain-web daemon start --visible
```

or install with:

```bash
./install.sh --visible-browser
```

## Browser daemon stuck

```bash
gpt-brain-web cleanup
gpt-brain-web daemon start
```

Cleanup closes the worker/context but preserves the login profile.

## Codex MCP cannot find tools

1. Run `gpt-brain-web mcp install-codex`.
2. Confirm `~/.codex/config.toml` contains `[mcp_servers.gpt-brain-web]`.
3. Restart Codex.
4. Run `python -m gpt_brain_web_mcp.server --list-tools`.

## Windows PowerShell execution policy

If `install.ps1` is blocked, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

## Playwright browser missing

```bash
python -m playwright install chromium
```

or rerun `./install.sh`.

## Config merge failed

Backups are created as `~/.codex/config.toml.bak.<timestamp>`. Restore the backup, then run:

```bash
gpt-brain-web mcp install-codex --dry-run
gpt-brain-web mcp install-codex
```
