# ChatGPT Web Brain Gateway MCP

`gpt-brain-web-mcp` lets Codex Desktop, Codex CLI, and other MCP clients call a managed local "external brain" backed by the **ChatGPT web UI**.

The default path is **not OpenAI API** and **not codex-account**. The main path is:

```text
MCP Client -> MCP Server -> Local Browser Daemon -> dedicated Playwright Chromium profile -> chatgpt.com
```

## Why web-first?

Some ChatGPT capabilities are account/UI features: model picker modes, Thinking/Thinking Heavy, Extended Thinking, Web Search, and Deep Research. This project treats the logged-in ChatGPT web session as the brain while keeping it local, explicit, and diagnosable.

API fallback can be added/configured separately, but it is not default. Codex-account fallback is not default either.

## Why a dedicated browser profile?

The daemon launches a Playwright Chromium persistent profile under `~/.gpt-brain-web/browser-profile` (or `%USERPROFILE%\.gpt-brain-web\browser-profile` on Windows). It does **not** use your daily Chrome/Edge/Safari, does **not** read their cookies, and does **not** steal profiles. You log in manually once using `gpt-brain-web login`; subsequent daemon calls reuse that dedicated profile.

## Safety boundaries

- No password storage.
- No default browser cookie/profile access.
- No CAPTCHA, 2FA, rate-limit, usage-limit, or paywall bypass.
- No automatic purchase/upgrade clicks.
- No default Pro / Pro Extended usage.
- No default repo upload. Only explicit `question`/`context` is sent.
- Secrets are redacted before logs, SQLite storage, and final output.

If login expires or ChatGPT asks for user action, jobs return `needs_user_action` and tell you to run `gpt-brain-web login`.

## Install

### macOS / Linux / WSL

```bash
git clone <repo>
cd gpt-brain-web-mcp
./install.sh
```

### Windows PowerShell

```powershell
git clone <repo>
cd gpt-brain-web-mcp
.\install.ps1
```

Install does the ordinary setup:

1. Checks Python 3.11+.
2. Creates `.venv`.
3. Installs this package with Playwright.
4. Installs Playwright Chromium.
5. Creates `~/.gpt-brain-web` directories.
6. Initializes SQLite.
7. Safely merges `~/.codex/config.toml` and creates a timestamp backup.
8. Runs doctor and a pre-login mock smoke (this is only an install sanity check).

Dry run:

```bash
./install.sh --dry-run
# Windows
.\install.ps1 -DryRun
```

Skip Codex config merge:

```bash
./install.sh --no-codex-config
```

Uninstall Codex config while preserving the login profile:

```bash
./install.sh --uninstall
# or
gpt-brain-web mcp uninstall-codex
```

## First login

```bash
gpt-brain-web login
```

A dedicated Playwright Chromium window opens at `chatgpt.com`. Log in yourself. The tool does not type credentials, solve 2FA, or bypass CAPTCHA. When done, close the window or leave the worker profile for the daemon.

## Common commands

```bash
gpt-brain-web doctor --verbose
gpt-brain-web daemon start
gpt-brain-web daemon status
gpt-brain-web daemon stop
gpt-brain-web smoke
gpt-brain-web cleanup
gpt-brain-web mcp install-codex
gpt-brain-web mcp uninstall-codex
```

Mock smoke does not consume your account and is not final acceptance. Live smoke is gated:

```bash
RUN_LIVE_CHATGPT_WEB=1 gpt-brain-web smoke
```

It sends one short prompt and requires you to have already run `gpt-brain-web login`.

Full live validation for maintainers:

```bash
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 python scripts/live_validate.py
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 python scripts/smoke_mcp.py
```

This exercises real `doctor`, real `ask_brain`, real `ask_web`, real asynchronous `start_research -> get_research_result`, and a real MCP stdio client/tool call.

## Codex MCP configuration

Install merges a block like this without deleting existing settings:

```toml
[mcp_servers.gpt-brain-web]
command = "/path/to/gpt-brain-web-mcp/.venv/bin/python"
args = ["-m", "gpt_brain_web_mcp.server"]
env = { "GPT_BRAIN_BACKEND" = "web-chatgpt", "GPT_BRAIN_DEFAULT_TIER" = "thinking_heavy", "GPT_BRAIN_ALLOW_PRO_DEFAULT" = "false", "GPT_BRAIN_BROWSER_HEADLESS" = "true", "GPT_BRAIN_HOME" = "/home/you/.gpt-brain-web" }
```

Restart Codex after changing MCP config.

## MCP tools

- `ask_brain`
- `ask_web`
- `start_research`
- `get_research_result`
- `cancel_research_job`
- `list_web_sessions`
- `open_login_window`
- `doctor`
- `cleanup_browser`
- `daemon_status`

### ask_brain default strategy

```json
{
  "backend": "web-chatgpt",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "web_search": false,
  "async": false
}
```

Fallback order:

```text
thinking_heavy -> thinking_extended -> thinking_normal
```

If the UI does not expose the requested mode, the result includes `fallback_chain` and `warnings`. The server does not pretend a mode was used if it could not be selected.

### Pro / Pro Extended

Pro tiers are opt-in only:

```json
{
  "question": "Run a strict architecture review",
  "tier": "pro_extended",
  "allow_pro": true
}
```

If `allow_pro=false`, requests for `pro` or `pro_extended` are downgraded/warned.

### ask_web

`ask_web` enables ChatGPT web/search capability if visible in the UI. Sources/citations are extracted best-effort. If sources are missing, the response includes a warning.

### start_research

`start_research` is always asynchronous. It quickly returns a `job_id`; use `get_research_result` to poll. The backend attempts to detect and select a visible Deep Research UI control. If that UI is not detectable/selectable for the logged-in account, the job falls back to a Web Research prompt and records:

```text
Deep Research UI not available; used web research fallback.
```

## Running tests

```bash
python -m pip install -e '.[dev]'
GPT_BRAIN_WEB_MOCK=1 pytest
```

Live tests are gated and skipped by default:

```bash
RUN_LIVE_CHATGPT_WEB=1 pytest tests/live
```

## UI changes

Selectors live in `config/selectors.yaml`; model/mode label mappings live in `config/model_modes.yaml`. If ChatGPT changes labels or controls, update these YAML files and run:

```bash
gpt-brain-web doctor --verbose
```

## Troubleshooting

See [`docs/troubleshooting.md`](docs/troubleshooting.md).

## One-click handoff to another user

Tell them:

```bash
git clone <repo>
cd gpt-brain-web-mcp
./install.sh
gpt-brain-web login
RUN_LIVE_CHATGPT_WEB=1 gpt-brain-web smoke
```

No large manual config copy is required.
