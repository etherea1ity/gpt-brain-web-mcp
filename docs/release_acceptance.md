# Release Acceptance Report

Date: 2026-05-09 (Asia/Shanghai workspace)

## Alignment / review summary

- Product: main path is ChatGPT Web, not API-first or codex-account-first.
- UX/DX: clone -> install -> login -> smoke path documented; Codex config is merged automatically.
- Browser architecture: dedicated Playwright/Chromium persistent profile; no default browser cookie/profile access.
- Security: Pro is opt-in; CAPTCHA/2FA/rate-limit bypass is forbidden; redaction and guarded deletion are implemented.
- QA: mock/unit tests remain CI checks, but final acceptance uses real ChatGPT Web.
- Critic fixes completed: omitted project no longer silently reuses one giant thread; `new` performs real new-chat navigation; explicit project missing fails closed; send is no longer retried by Enter after a send click; async browser profile ownership is released before worker jobs; local session persistence defaults to false.

## Verified commands

### Unit / mock / install checks

```bash
python3 -m pytest -q
# 47 passed, live-gated tests skipped unless RUN_LIVE_CHATGPT_WEB=1

PYTHONPATH=src python3 scripts/smoke_mcp.py
# ok=true, mode=mock, MCP stdio listed tools and called ask_brain

GPT_BRAIN_WEB_MOCK=1 PYTHONPATH=src python3 -m gpt_brain_web_mcp smoke
# ok=true, mode=mock

./install.sh --dry-run
PYTHONPATH=src python3 -m gpt_brain_web_mcp install --dry-run
# both completed successfully without writing destructive config
```

### Live ChatGPT Web checks

The user completed manual login in the dedicated browser profile before these checks.

```bash
GPT_BRAIN_WEB_MOCK=0 GPT_BRAIN_BROWSER_VISIBLE=true PYTHONPATH=src python3 -m gpt_brain_web_mcp doctor --verbose
# ok=true; login_state=logged_in; prompt_box/model_picker/send_button live OK

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 GPT_BRAIN_BROWSER_VISIBLE=true PYTHONPATH=src python3 -m gpt_brain_web_mcp smoke
# ok=true; real answer GPT_BRAIN_WEB_SMOKE_OK

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 GPT_BRAIN_BROWSER_VISIBLE=true PYTHONPATH=src python3 scripts/smoke_mcp.py
# ok=true; real MCP stdio client listed tools and called ask_brain; answer MCP_LIVE_SMOKE_OK

RUN_LIVE_CHATGPT_WEB=1 GPT_BRAIN_WEB_MOCK=0 GPT_BRAIN_BROWSER_VISIBLE=true PYTHONPATH=src python3 scripts/live_validate.py
# ok=true; real doctor, ask_brain, ask_web with sources, and async start_research -> get_research_result completed
```

Live validation evidence from the final run:

- `ask_brain`: returned `GPT_BRAIN_WEB_LIVE_OK`, resolved tier `thinking_heavy`, new conversation `https://chatgpt.com/c/69fe131d-9cb0-832a-9672-2467850ba693`.
- `ask_web`: returned source URLs including `https://www.calendarr.com/united-states/` and `https://www.calendardate.com/todays.htm`, new conversation `https://chatgpt.com/c/69fe1333-89d0-8333-9490-1c2783ea5a36`.
- `start_research`: job `job_3c04472eaf2b42069c7a4ef488596eea` progressed `queued -> running -> waiting_for_model -> completed`; conversation `https://chatgpt.com/c/69fe1363-0e14-8325-a75c-72037307997f`; resolved research mode `web_research_prompt` with explicit warning because Deep Research UI was not selected/detected in that run.
- Local research job record and artifact were deleted by the validation script after success.

## Known limits

- Deep Research is best-effort UI automation: if ChatGPT exposes the control it is selected; otherwise the job honestly falls back to a web-research prompt and records `resolved_research_mode=web_research_prompt`.
- Pro/Pro Extended are not default and require `allow_pro=true`; live Pro mode selection was explored manually earlier but not consumed as part of final automated acceptance.
- The current daemon is an in-process/session-manager facade plus optional background process, not a network IPC daemon. The module boundary is prepared for future IPC hardening.
- ChatGPT UI can change. Update `config/selectors.yaml` and `config/model_modes.yaml`, then run `doctor --verbose`.
