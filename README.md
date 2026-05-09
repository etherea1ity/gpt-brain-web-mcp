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
- `list_projects`, `open_project`, `create_project`, `start_project_conversation`, `delete_remote_project`
- `delete_remote_conversation`
- `list_remote_cleanup`
- `cleanup_remote_conversations`
- `ui_capabilities_check`
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
- `retention` controls ChatGPT-side clutter: omitted project defaults to `ephemeral`, explicit project defaults to `persistent`, and research defaults to `job`.
- `cleanup_remote=true` immediately deletes the created ChatGPT `/c/...` conversation after extracting the answer. Without it, ephemeral/job conversations are queued for later cleanup.
- `start_research` always uses an isolated job conversation so Deep Research / web research does not pollute normal project threads. For `retention=job`/`ephemeral`, the result is saved locally and the remote ChatGPT conversation is deleted after completion by default; set `cleanup_remote=false` or `retention=persistent` to keep it in ChatGPT.

For real ChatGPT Projects, the browser adapter opens the dedicated sidebar, expands `More -> Projects` when necessary, and clicks an existing project row. It can also create/delete **explicitly confirmed** projects for disposable workflow spaces, but it never uploads project files automatically.

Project operations exposed to MCP/CLI:

```bash
gpt-brain-web records list-projects --limit 20
gpt-brain-web records open-project "My Project"
gpt-brain-web records create-project "Disposable Test Project" --confirm
gpt-brain-web records start-project-conversation "My Project" --question "Reply with exactly: project-ok" --tier thinking_normal
gpt-brain-web records delete-remote https://chatgpt.com/c/... --confirm
gpt-brain-web records delete-project "Disposable Test Project" --confirm --confirm-name "Disposable Test Project" --purge-local
```

Before every prompt submission the gateway re-checks conversation focus. If the user manually clicked another ChatGPT chat after the gateway selected a target conversation/project, it navigates back to the recorded `conversation_url` or reopens the requested project composer. If focus cannot be confirmed, it fails closed with `needs_user_action` rather than sending the prompt into the wrong chat.


## ask_brain default strategy

```json
{
  "backend": "web-chatgpt",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "web_search": false,
  "async": false,
  "save_session": false,
  "retention": "ephemeral when project omitted; persistent when project is explicit",
  "cleanup_remote": false,
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

`ask_web` opens the composer `+` menu and enables ChatGPT Search/Web Search when visible. It then submits a source-oriented prompt and extracts citations best-effort. If the UI control or sources are missing, the response includes a warning instead of pretending.

Check the live UI without sending a prompt:

```bash
gpt-brain-web ui-check
# or MCP: ui_capabilities_check
```

## Async jobs and research heartbeat

`ask_brain` supports `async_request=true`; `start_research` is always asynchronous. Poll either with `get_job_result` or `get_research_result`. When a research job completes with non-persistent retention, the markdown artifact and SQLite result are saved before the remote ChatGPT thread is deleted.

Long jobs stay inside the workflow: the browser adapter records heartbeat events while waiting for ChatGPT output and can refresh once when no progress is observed. Useful knobs:

```bash
GPT_BRAIN_RESPONSE_TIMEOUT_SECONDS=600
GPT_BRAIN_HEARTBEAT_SECONDS=20
GPT_BRAIN_STALE_REFRESH_SECONDS=240
```

`get_research_result` returns `requested_research_mode` and `resolved_research_mode` so callers can tell whether real Deep Research was used. Deep Research is treated as a slow workflow: by default the worker waits up to `max_runtime_hint_minutes` / `GPT_BRAIN_RESPONSE_TIMEOUT_SECONDS` for success or a visible failure and does **not** silently downgrade to normal web research. If you explicitly want old fallback behavior, set `GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_TIMEOUT=1` or `GPT_BRAIN_DEEP_RESEARCH_FALLBACK_ON_FAILURE=1`.

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

For smoke/live/test calls, prefer automatic cleanup:

```json
{ "question": "...", "conversation_strategy": "new", "retention": "ephemeral", "cleanup_remote": true }
```

Or process the queue later:

```bash
gpt-brain-web records cleanup-list --status pending
gpt-brain-web records cleanup-remote --dry-run
gpt-brain-web records cleanup-remote --confirm
```

The remote delete path only accepts explicit ChatGPT conversation URLs containing `/c/...`, skips `persistent` records, and requires confirmation for actual deletion. Project deletion is even stricter: `delete_remote_project` requires both `confirm=true` and `confirm_name` exactly matching the project name. Use it only for disposable/test projects unless you intentionally want to delete a real ChatGPT Project.

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
