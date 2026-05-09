# Architecture

## Corrected product boundary

The main backend is `web-chatgpt`: a controlled Playwright Chromium persistent profile operated by a local daemon/session manager. API and Codex-account approaches are optional fallbacks only, not the default route.

## Components

```text
MCP Server
  -> WebBrainService
  -> WebChatGPTBackend
  -> BrowserSessionManager / daemon facade
  -> ChatGPTPage adapters
  -> dedicated persistent Playwright Chromium profile
  -> chatgpt.com
```

### MCP Server

`server.py` is thin. It exposes MCP tools and delegates to `tools.WebBrainService`.

### Browser Daemon / Session Manager

`web/browser_manager.py` owns browser lifecycle, page acquisition/release, persistent profile path, healthcheck, login state, and zombie cleanup. V1 is an in-process daemon facade suitable for a long-running MCP server plus a CLI background worker; the module boundaries leave room for a separate IPC daemon.

### Dedicated profile

Default paths:

- Linux/macOS/WSL: `~/.gpt-brain-web/browser-profile`
- Windows: `%USERPROFILE%\.gpt-brain-web\browser-profile`

No default browser profile or cookie jar is read.

In WSL, if Linux Chromium cannot launch because host libraries are missing, the manager can connect to Windows Chrome/Edge over CDP while still using the same dedicated `.gpt-brain-web` profile. The CDP endpoint is bound to `127.0.0.1`, not `0.0.0.0`.

### Conversation manager

`web/conversation_manager.py` and `Store` persist project/session/job mappings to `conversation_url`. A local placeholder is used before the first message; after ChatGPT assigns a real `https://chatgpt.com/c/...` URL, it is captured and stored. When the MCP caller omits `project`, results are labeled with `GPT_BRAIN_DEFAULT_PROJECT` (`Codex Brain`) but the browser starts a fresh global/new chat by default and does not bind that implicit label as a reusable project pointer. Explicit `project` is the only project reuse key. `conversation_strategy` controls reuse (`reuse_project` for explicit projects), fresh thread creation (`new`), and explicit resume (`resume_session` / `resume_url`). Ask jobs and research jobs can run asynchronously and use isolated job conversations.

### Job queue

`jobs.py` uses a thread pool. `start_research` returns immediately and records state in SQLite. Results and markdown artifacts are persisted.

### Storage

SQLite tables: `browser_profiles`, `project_threads`, `web_sessions`, `messages`, `jobs`, `browser_events`, `backend_runs`, `remote_cleanup_queue`, and `settings`. `project_threads` stores explicit project -> latest conversation pointers separately from local audit sessions.

### UI adapters

Playwright selectors are centralized in `config/selectors.yaml`. Model labels are configurable in `config/model_modes.yaml`. Extractors and healthcheck are separate modules so UI changes are diagnosable.

### Extension bridge

`web/extension_bridge.py` is a stub for a future bundled worker extension loaded by our Playwright Chromium profile. It is not a user-installed Chrome extension.


### Real ChatGPT Project navigation

`ChatGPTPage.open_project()` opens existing ChatGPT Projects from the dedicated profile sidebar. It handles the compact sidebar state by expanding `More` and then `Projects`, then clicking the project row. Project create/delete operations exist for explicitly confirmed disposable workflow spaces; deletion requires a matching confirmation name. Missing explicit projects fail closed unless the caller sets `allow_project_fallback=true`. Before every prompt submission `ensure_conversation_focus()` validates the recorded `conversation_url` or requested project composer, recovering from manual user navigation when possible and refusing to send into the wrong chat when not possible. The composer is located by role/textbox and CSS fallbacks each time, so the input box moving downward inside a project or selected mode is handled by locator lookup rather than fixed coordinates. `conversation_strategy=new` calls the page-level new-chat/project-composer flow before prompt submission, not just a local placeholder.


### Async workflow heartbeat

`ask_brain(async_request=true)` and `start_research` return quickly with a job id. While waiting for ChatGPT output, `ChatGPTPage` records heartbeat browser events and marks jobs as `waiting_for_model`. If no progress is observed for `GPT_BRAIN_STALE_REFRESH_SECONDS`, it performs one refresh/recovery attempt instead of abandoning the workflow. `GPT_BRAIN_MAX_BROWSER_JOBS` defaults to `1` so the dedicated profile is serialized by default and does not attempt to bypass account limits.

### Local and remote cleanup

Local records can be deleted with `delete_local_record` / `gpt-brain-web records delete`. Project audit data can be purged with `purge_project_records`. Remote ChatGPT conversation deletion is deliberately guarded: `delete_remote_conversation` only accepts explicit ChatGPT conversation URLs containing `/c/...` and requires confirmation. Remote ChatGPT Project deletion is separately guarded by `confirm=true` plus exact `confirm_name`. Ephemeral/job conversations are queued in `remote_cleanup_queue`; `cleanup_remote=true` processes the specific queued item immediately, while `cleanup_remote_conversations` can dry-run or process queued cleanup later. Persistent records are skipped by bulk cleanup.
