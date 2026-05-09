# Release Acceptance Report

Date: 2026-05-09 (Asia/Shanghai workspace)

## Alignment / review summary

- Product: main path is ChatGPT Web, not API-first or codex-account-first.
- UX/DX: clone -> install -> login -> smoke path documented; Codex config is merged automatically.
- Browser architecture: dedicated Playwright/Chromium persistent profile; no default browser cookie/profile access.
- Security: Pro is opt-in; CAPTCHA/2FA/rate-limit bypass is forbidden; redaction and guarded deletion are implemented.
- QA: mock/unit tests remain CI checks, but final acceptance uses real ChatGPT Web.
- Conversation hygiene: omitted-project calls default to ephemeral new chats; explicit projects default to persistent reuse; research defaults to isolated job conversations. Ephemeral/job conversations can be deleted immediately with `cleanup_remote=true` or later through the remote cleanup queue.

## Verified commands

### Unit / mock / install checks

```bash
PYTHONPATH=src pytest -q
# 57 passed, live-gated tests skipped unless RUN_LIVE_CHATGPT_WEB=1

PYTHONPATH=src python3 -m gpt_brain_web_mcp.server --list-tools
# listed ask_brain, ask_web, research, cleanup, UI-check, doctor, and daemon tools

GPT_BRAIN_WEB_MOCK=1 PYTHONPATH=src python3 -m gpt_brain_web_mcp.cli ui-check
# ok=true in mock; web_search available; deep_research mock reports unavailable honestly
```

### Live ChatGPT Web checks

The user completed manual login in the dedicated browser profile before these checks.

```bash
GPT_BRAIN_WEB_MOCK=0 PYTHONPATH=src python3 -m gpt_brain_web_mcp.cli doctor --verbose
# ok=true; logged_in; prompt/model/send live OK; Deep Research UI and Search UI detected without sending a prompt

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 PYTHONPATH=src python3 -m gpt_brain_web_mcp.cli smoke
# ok=true; real answer GPT_BRAIN_WEB_SMOKE_OK; remote conversation cleanup_remote_status=deleted

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 PYTHONPATH=src python3 scripts/smoke_mcp.py
# ok=true; real MCP stdio client listed tools and called ask_brain; answer MCP_LIVE_SMOKE_OK; remote cleanup deleted

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 PYTHONPATH=src GPT_BRAIN_RESPONSE_TIMEOUT_SECONDS=420 GPT_BRAIN_STALE_REFRESH_SECONDS=180 GPT_BRAIN_LIVE_RESEARCH_TIMEOUT_SECONDS=720 python3 scripts/live_validate.py
# ok=true; real doctor, ask_brain, ask_web with sources, and async start_research -> get_research_result completed
```

Live validation evidence from the final run:

- `doctor`: `ok=true`; `login_state=logged_in`; `prompt_box_detectable`, `model_picker_detectable`, and `send_button_detectable` live OK; `deep_research_ui_detectable=true`; `web_search_ui_detectable=true`.
- `ask_brain`: returned `GPT_BRAIN_WEB_LIVE_OK`, resolved tier `thinking_heavy`, conversation `https://chatgpt.com/c/69ff3458-592c-8328-9d86-3968b9fcf936`, `retention=ephemeral`, `cleanup_remote_status=deleted`.
- `ask_web`: returned today's date with sources `https://nationaldaycalendar.com/what-day-is-it` and `https://www.calendar-365.com/calendar/2026/May.html`, conversation `https://chatgpt.com/c/69ff3475-a3e0-832a-b804-b649b8fbfa5a`, `cleanup_remote_status=deleted`.
- `start_research`: job `job_02ce8fb2f8b64e03a2d6d3444b08be9f` progressed `queued -> running -> waiting_for_model -> completed`; result included MCP official/source URLs; conversation `https://chatgpt.com/c/69ff3682-138c-8328-85de-5476a88361cf` was remotely deleted by async job cleanup (`Remote cleanup status: deleted`).
- Deep Research was requested and the UI was detectable, but the job honestly resolved to `web_research_prompt` after the Deep Research path did not complete before timeout. The fallback returned sources and passed acceptance.
- `gpt-brain-web records cleanup-list --status pending` returned no pending items; cleanup stats showed deleted items.

## Known limits

- Deep Research is best-effort UI automation: if ChatGPT exposes the control it is selected; if it does not complete before timeout, the workflow honestly falls back to a web-research prompt and records `resolved_research_mode=web_research_prompt`.
- Pro/Pro Extended are not default and require `allow_pro=true`; live Pro mode selection was explored earlier but not consumed as part of final automated acceptance.
- The current daemon is an in-process/session-manager facade plus optional background process, not a network IPC daemon. The module boundary is prepared for future IPC hardening.
- ChatGPT UI can change. Update `config/selectors.yaml` and `config/model_modes.yaml`, then run `doctor --verbose` and `ui-check`.
