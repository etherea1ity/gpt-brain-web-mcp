# Product workflow policy

This is the stable product contract for ChatGPT Web Brain Gateway MCP. Selectors and ChatGPT UI labels may change; these workflow rules should remain predictable and are exposed through code (`product_policy.py`), CLI (`gpt-brain-web policy`), and MCP (`product_policy`, `resolve_policy`).

## Product positioning

ChatGPT Web Brain is a managed local bridge from Codex/OMX/other MCP clients to the user's logged-in ChatGPT Web capability. The product is not an API-first wrapper and not a Codex-account wrapper. It is a controlled browser worker with a dedicated profile, precise project/conversation routing, durable local records, and explicit cleanup rules.

Primary users:

1. **Solo builder / repo agent**: Codex needs a stronger external ChatGPT reasoning lane while coding.
2. **Research operator**: an agent starts long web/deep-research jobs and polls while the human sleeps.
3. **Product/workflow team**: repeatable project-scoped ChatGPT conversations are used as durable thinking rooms.

## Default route

- Backend: `web-chatgpt`
- Tier: `thinking_heavy`
- Pro: off by default; `allow_pro=true` is required for `pro` / `pro_extended`
- Browser: dedicated persistent profile only; never the user's default Chrome profile
- Concurrency: `GPT_BRAIN_MAX_BROWSER_JOBS=1` by default
- Safety posture: fail closed if target project/conversation focus cannot be verified

## Conversation lifecycle decisions

| Scenario | Caller input | ChatGPT location | Conversation strategy | Retention | Cleanup |
| --- | --- | --- | --- | --- | --- |
| Quick Codex/OMX prompt | omit `project` | fresh global ChatGPT chat, locally labeled `Codex Brain` | `new` | `ephemeral` | queued; immediate only when `cleanup_remote=true` |
| Real repo/product work | `project="Exact Project"` | exact visible ChatGPT Project | `reuse_project` by default | `persistent` | never automatic unless explicitly requested |
| Fresh thread inside a project | `project="Exact Project", conversation_strategy="new"` | exact project composer | `new` | `persistent` | caller controlled |
| Resume known thread | `conversation_strategy="resume_url"` or `resume_session` | recorded `/c/...` URL | resume | caller controlled | automatic cleanup skipped for reused/resumed threads |
| Long research | `start_research(...)` | isolated job conversation | `new_job_conversation` | `job` | default on after local artifact/result is saved |

## Project policy

### Omitted `project`

Use this for quick external-thinking calls from Codex/OMX.

- Local result is labeled as `GPT_BRAIN_DEFAULT_PROJECT` (`Codex Brain` by default)
- Browser starts a **fresh global conversation**
- Retention defaults to `ephemeral`
- Remote cleanup is queued after local result/artifact capture
- This keeps ChatGPT sidebar clutter low and avoids one giant accidental thread

Why not route omitted calls to a default ChatGPT Project? Because agentic calls are often one-off and high volume. A default persistent project would become a noisy dumping ground. Product/repo continuity should be explicit by passing `project="..."`.

### Explicit `project="..."`

Use this for real repo/product/workflow continuity.

- Browser opens the exact visible ChatGPT Project name
- Default strategy is `reuse_project`
- Retention defaults to `persistent`
- `conversation_strategy="new"` starts a fresh conversation inside that project
- If the project cannot be opened, the gateway fails closed unless `allow_project_fallback=true`

## Focus guard

Before sending a prompt, the gateway verifies the recorded `conversation_url` or requested project composer. If the human manually clicked another ChatGPT chat, it tries to recover to the target. If it cannot confirm focus, it returns `needs_user_action` instead of sending into the wrong chat.

This protects the user's personal ChatGPT sessions and is more important than best-effort completion.

## Model/mode policy

- Default ask tier is `thinking_heavy`
- Fallback order: `thinking_heavy -> thinking_extended -> thinking_normal`
- Pro order when explicitly allowed: `pro_extended -> pro -> thinking_heavy -> thinking_extended -> thinking_normal`
- `allow_pro=false` blocks Pro/Pro Extended even if requested
- The resolved tier and fallback chain must be returned to the caller

## Research policy

- `start_research` is always async
- Research uses an isolated job conversation
- Default retention is `job`
- Remote cleanup defaults on after the markdown artifact/result is saved locally
- Deep Research is first-class when the UI is available; fallback must be explicit/honest
- Jobs should be polled by workflow agents; if long-running, keep heartbeat/polling rather than blocking the MCP call

## Deletion policy

- Conversation deletion accepts only explicit ChatGPT URLs containing `/c/...`, including project-scoped `/g/.../c/...` URLs
- Project deletion requires `confirm=true` and `confirm_name` exactly matching the project
- Validation must create disposable projects first, then only delete those disposable projects
- The gateway must never delete pre-existing user projects or conversations unless the caller names them and confirms

## User-facing commands

```bash
gpt-brain-web policy
gpt-brain-web policy --resolve
gpt-brain-web policy --resolve --project "My Repo"
gpt-brain-web policy --resolve --kind research --project "My Repo"
```

MCP tools:

- `product_policy`
- `resolve_policy`

## Commercial-grade acceptance for this policy

- Product defaults are executable, not just documented
- MCP clients can inspect/resolve policy before sending prompts
- Explicit project routing is protected by fail-closed behavior
- Disposable validation projects/conversations can be cleaned up safely
- Live ChatGPT Web doctor/smoke must pass before release claims
