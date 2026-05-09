# Sample MCP Requests

## ask_brain in an explicit reusable ChatGPT Project
```json
{
  "question": "Review this migration plan and list the riskiest assumptions.",
  "project": "my-project",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "web_search": false,
  "save_session": false,
  "conversation_strategy": "reuse_project"
}
```

## ask_brain as a one-off global/new chat
```json
{
  "question": "Give me a concise second opinion on this design.",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "conversation_strategy": "new"
}
```

## async ask_brain
```json
{
  "question": "Think through this product launch plan and return the top 5 risks.",
  "async_request": true,
  "tier": "thinking_heavy",
  "allow_pro": false
}
```

Then poll:

```json
{ "job_id": "job_..." }
```

## ask_web
```json
{
  "question": "What changed in the latest official Python packaging guidance? Cite source URLs.",
  "project": "tooling",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "conversation_strategy": "new"
}
```

## start_research
```json
{
  "topic": "Evaluate managed browser automation risks for ChatGPT web workflows",
  "project": "brain-web",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "deep_research": true,
  "output_format": "decision_memo",
  "max_runtime_hint_minutes": 30
}
```

## Explicit Pro opt-in
```json
{
  "question": "Do a strict architecture review.",
  "tier": "pro_extended",
  "allow_pro": true,
  "conversation_strategy": "new"
}
```

## Local cleanup
```json
{ "record_id": "job_...", "record_type": "job", "delete_artifact": true }
```

## Guarded remote cleanup
```json
{ "conversation_url": "https://chatgpt.com/c/...", "confirm": true }

## Ephemeral request with immediate remote cleanup

```json
{
  "question": "Reply with exactly: OK",
  "conversation_strategy": "new",
  "retention": "ephemeral",
  "cleanup_remote": true
}
```

## Remote cleanup queue

```json
{ "status": "pending", "limit": 20 }
```
```
