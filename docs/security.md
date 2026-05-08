# Security and Privacy

## Browser isolation

The system launches a dedicated Playwright Chromium persistent profile. It does not read default Chrome/Edge/Safari profiles, cookies, passwords, or browser storage.

## Login

The user logs into ChatGPT manually. The tool never stores a password and never bypasses 2FA, CAPTCHA, rate limits, usage limits, or paid plan restrictions.

## Data sent to ChatGPT

Only explicit MCP input fields (`question`, optional `context`, and research topic/context) are sent. The server never automatically uploads the entire repository, `.env`, private keys, or browser cookies.

## Redaction

`redaction.py` filters common secrets before writing logs, SQLite rows, artifacts, and final tool output. Covered patterns include OpenAI-style keys, AWS keys/secrets, GitHub tokens, Bearer/Authorization headers, private keys, and `.env` style secrets.

## Pro opt-in

`allow_pro=false` by default. `pro` and `pro_extended` are only considered when the user explicitly sets `allow_pro=true` and requests a Pro tier.

## Optional API fallback

API fallback is not enabled by default. If implemented/configured later, it must remain explicit and must not silently consume API billing.


## Conversation retention

`save_session=false` by default, so normal MCP calls do not create local message audit records unless requested. Explicit project thread pointers are stored separately from local sessions. Local records can be removed with `delete_local_record` / `records delete`; remote ChatGPT conversation deletion requires an explicit `https://chatgpt.com/c/...` URL and confirmation.

## Project fallback safety

Explicit `project` requests fail closed if the ChatGPT Project cannot be opened. The tool sends into the current chat only when the caller explicitly sets `allow_project_fallback=true`.
