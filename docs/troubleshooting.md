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

Run `gpt-brain-web ui-check` to inspect the composer `+` menu without sending a prompt. Deep Research can be very slow; by default `start_research` waits for real completion/failure up to `max_runtime_hint_minutes` instead of falling back. If the UI is unavailable or the job times out, the status becomes `failed` / `needs_user_action` with an explicit message. Set `GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_TIMEOUT=1` or `GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_FAILURE=1` only if you intentionally want web-research prompt fallback. The adapter also tries to remove the Deep Research pill after use so later normal asks do not inherit the mode.

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


## Explicit project fails closed

If a request includes `project="..."` and the ChatGPT Project cannot be opened from the dedicated sidebar, the tool refuses to send into the current chat by default. Create/open the project in ChatGPT, update the project name, or explicitly pass `allow_project_fallback=true` when current-chat fallback is acceptable.

## Project list/open/create/delete problems

Project UI labels can change. Start with non-destructive checks:

```bash
gpt-brain-web records list-projects --limit 20
gpt-brain-web records open-project "Exact Project Name"
```

For disposable validation only, creation/deletion require explicit confirmation:

```bash
gpt-brain-web records create-project "GPT Brain Test" --confirm
gpt-brain-web records delete-project "GPT Brain Test" --confirm --confirm-name "GPT Brain Test" --purge-local
```

If the gateway opened one conversation but you manually clicked another chat, the next send re-validates focus and either navigates back to the recorded conversation/project or returns `needs_user_action`. It should not silently submit into the manually selected chat.

## Job stays `waiting_for_model`

Long jobs emit heartbeat events while ChatGPT is thinking. If no progress is observed, the adapter refreshes once after `GPT_BRAIN_STALE_REFRESH_SECONDS` (default 240s). If the status does not change after the configured timeout, run `gpt-brain-web doctor --verbose` and inspect local records with `gpt-brain-web records list`.

## Remote cleanup

Use `gpt-brain-web records delete <job_id>` for local SQLite cleanup. Ephemeral/job ChatGPT conversations are queued for remote cleanup; inspect/process them with:

```bash
gpt-brain-web records cleanup-list --status pending
gpt-brain-web records cleanup-remote --dry-run
gpt-brain-web records cleanup-remote --confirm
```

To delete one ChatGPT web conversation directly, pass the exact `/c/...` URL (including project-scoped `/g/.../c/...` URLs) and `--confirm`:

```bash
gpt-brain-web records delete-remote https://chatgpt.com/c/... --confirm
```

The tool will not delete remote conversations without an explicit URL and confirmation.
