# ChatGPT Web Brain Gateway MCP

`gpt-brain-web-mcp` lets Codex Desktop, Codex CLI, OMX, and other MCP clients call a managed local “external brain” backed by the **ChatGPT web UI**.

The default path is **not OpenAI API** and **not codex-account**:

```text
MCP Client -> MCP Server -> Browser daemon/session manager -> dedicated Playwright Chromium profile -> chatgpt.com
```

## Why web-first?

Some ChatGPT capabilities are account/UI features: model picker modes, Thinking/Thinking Heavy, Extended Thinking, Web Search, Pro/Pro Extended, and Deep Research. This project treats the logged-in ChatGPT web session as the brain while keeping the browser local, explicit, and diagnosable.

API and Codex-account backends are optional future/fallback paths only. They are not the default route.

## Why a dedicated browser profile?

The daemon launches a Playwright Chromium persistent profile under `~/.gpt-brain-web/browser-profile` (or `%USERPROFILE%\.gpt-brain-web\browser-profile` on Windows). It does **not** use your daily Chrome/Edge/Safari, does **not** read their cookies, and does **not** steal profiles. You log in manually once using `gpt-brain-web login`; later calls reuse that dedicated profile.

## Safety boundaries

- No password storage.
- No default browser cookie/profile access.
- No CAPTCHA, 2FA, rate-limit, usage-limit, or paywall bypass.
- No automatic purchase/upgrade clicks.
- No default Pro / Pro Extended usage.
- No default repo upload. Only explicit `question`/`context`/`topic` fields are sent.
- Secrets are redacted before logs, SQLite storage, artifacts, and final output.

If login expires or ChatGPT asks for user action, jobs return `needs_user_action` and tell you to run `gpt-brain-web login`.

## Install

### macOS / Linux / WSL

```bash
git clone https://github.com/etherea1ity/gpt-brain-web-mcp.git
cd gpt-brain-web-mcp
./install.sh
```

### Windows PowerShell

```powershell
git clone https://github.com/etherea1ity/gpt-brain-web-mcp.git
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
8. Runs doctor and a pre-login mock smoke. This is only an install sanity check; final acceptance is live ChatGPT Web.

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

A dedicated Playwright Chromium window opens at `chatgpt.com`. Log in yourself. The tool does not type credentials, solve 2FA, bypass CAPTCHA, or read your normal browser profile.

## Common commands

```bash
gpt-brain-web doctor --verbose
gpt-brain-web daemon start
gpt-brain-web daemon status
gpt-brain-web daemon stop
gpt-brain-web smoke
gpt-brain-web cleanup
gpt-brain-web mcp install-codex
gpt-brain-web mcp tools
gpt-brain-web records list
gpt-brain-web records delete <session_or_job_id>
gpt-brain-web records purge-project <project>
```

Mock smoke does not consume your account and is not final acceptance. Live smoke is gated:

```bash
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 gpt-brain-web smoke
```

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
env = { "GPT_BRAIN_BACKEND" = "web-chatgpt", "GPT_BRAIN_DEFAULT_TIER" = "thinking_heavy", "GPT_BRAIN_ALLOW_PRO_DEFAULT" = "false", "GPT_BRAIN_SAVE_SESSION_DEFAULT" = "false", "GPT_BRAIN_DEFAULT_PROJECT" = "Codex Brain", "GPT_BRAIN_CONVERSATION_POLICY" = "reuse_project", "GPT_BRAIN_MAX_BROWSER_JOBS" = "1", "GPT_BRAIN_BROWSER_HEADLESS" = "true", "GPT_BRAIN_HOME" = "/home/you/.gpt-brain-web" }
```

Restart Codex after changing MCP config.

## MCP tools

- `ask_brain`
- `ask_web`
- `start_research`
- `get_research_result`
- `get_job_result`
- `cancel_research_job`
- `list_web_sessions`
- `delete_local_record`
- `purge_project_records`
- `delete_remote_conversation`
- `open_login_window`
- `doctor`
- `cleanup_browser`
- `daemon_status`

## Project and conversation management

The gateway treats `project` as the routing key **only when the MCP caller explicitly provides it**:

- If `project` is omitted, the response is labeled with `GPT_BRAIN_DEFAULT_PROJECT` (`Codex Brain` by default), but ChatGPT is opened in a fresh global/new chat by default. This prevents silent contamination of one giant thread.
- If `project` is provided, `conversation_strategy="reuse_project"` reuses that project's latest known ChatGPT conversation URL.
- If an explicit ChatGPT Project cannot be opened, the request fails closed with `needs_user_action` unless `allow_project_fallback=true` is explicitly provided.
- `conversation_strategy="new"` starts a real new ChatGPT composer before sending; inside an explicit project it opens the project landing composer.
- `conversation_strategy="resume_session"` plus `session_id` resumes a stored local session URL.
- `conversation_strategy="resume_url"` plus `conversation_url` resumes an explicit ChatGPT `/c/...` URL.
- `save_session=false` by default. Set `save_session=true` only when you want a local SQLite audit record.
- `start_research` always uses an isolated job conversation so Deep Research / web research does not pollute normal project threads.

For real ChatGPT Projects, the browser adapter opens the dedicated sidebar, expands `More -> Projects` when necessary, and clicks an existing project row. It does not auto-create projects or upload project files.

## ask_brain default strategy

```json
{
  "backend": "web-chatgpt",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "web_search": false,
  "async": false,
  "save_session": false,
  "conversation_strategy": "new when project omitted; reuse_project when project is explicit"
}
```

Fallback order:

```text
thinking_heavy -> thinking_extended -> thinking_normal
```

If the UI does not expose the requested mode, the result includes `fallback_chain` and `warnings`. The server does not pretend a mode was used if it could not be selected.

## Pro / Pro Extended

Pro tiers are opt-in only:

```json
{
  "question": "Run a strict architecture review",
  "tier": "pro_extended",
  "allow_pro": true
}
```

If `allow_pro=false`, requests for `pro` or `pro_extended` are downgraded/warned.

## ask_web

`ask_web` enables ChatGPT web/search capability if visible in the UI. Sources/citations are extracted best-effort. If sources are missing, the response includes a warning.

## Async jobs and research heartbeat

`ask_brain` supports `async_request=true`; `start_research` is always asynchronous. Poll either with `get_job_result` or `get_research_result`.

Long jobs stay inside the workflow: the browser adapter records heartbeat events while waiting for ChatGPT output and can refresh once when no progress is observed. Useful knobs:

```bash
GPT_BRAIN_RESPONSE_TIMEOUT_SECONDS=600
GPT_BRAIN_HEARTBEAT_SECONDS=20
GPT_BRAIN_STALE_REFRESH_SECONDS=240
```

`get_research_result` returns `requested_research_mode` and `resolved_research_mode` so callers can tell whether real Deep Research was used or a web-research prompt fallback was used. If Deep Research UI is not detectable/selectable for the logged-in account, the job falls back with an explicit warning instead of pretending.

## Cleanup and deletion

Local cleanup:

```bash
gpt-brain-web records list
gpt-brain-web records delete job_...
gpt-brain-web records purge-project "Project Name"
```

Remote ChatGPT conversation deletion is explicit and guarded:

```bash
gpt-brain-web records delete-remote https://chatgpt.com/c/... --confirm
```

The remote delete command only accepts explicit `https://chatgpt.com/c/...` URLs and requires `--confirm`.

## Running tests

```bash
python -m pip install -e '.[dev]'
GPT_BRAIN_WEB_MOCK=1 pytest
```

Live tests are gated and skipped by default:

```bash
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 pytest tests/live
```

Mock/unit tests prove CI behavior. Release acceptance must also pass the live ChatGPT Web validation commands above.

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
git clone https://github.com/etherea1ity/gpt-brain-web-mcp.git
cd gpt-brain-web-mcp
./install.sh
gpt-brain-web login
RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 gpt-brain-web smoke
```

No large manual config copy is required.
