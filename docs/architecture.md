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

`web/conversation_manager.py` and `Store` persist project/session/job mappings to `conversation_url`. A local placeholder is used before the first message; after ChatGPT assigns a real `https://chatgpt.com/c/...` URL, it is captured and stored. Project asks navigate back to the latest real project conversation when available.

### Job queue

`jobs.py` uses a thread pool. `start_research` returns immediately and records state in SQLite. Results and markdown artifacts are persisted.

### Storage

SQLite tables: `browser_profiles`, `web_sessions`, `messages`, `jobs`, `browser_events`, `backend_runs`, and `settings`.

### UI adapters

Playwright selectors are centralized in `config/selectors.yaml`. Model labels are configurable in `config/model_modes.yaml`. Extractors and healthcheck are separate modules so UI changes are diagnosable.

### Extension bridge

`web/extension_bridge.py` is a stub for a future bundled worker extension loaded by our Playwright Chromium profile. It is not a user-installed Chrome extension.
