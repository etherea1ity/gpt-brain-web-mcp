# Sample MCP Requests

## ask_brain
```json
{
  "question": "Review this migration plan and list the riskiest assumptions.",
  "project": "my-project",
  "tier": "thinking_heavy",
  "allow_pro": false,
  "web_search": false
}
```

## ask_web
```json
{
  "question": "What changed in the latest official Python packaging guidance?",
  "project": "tooling",
  "tier": "thinking_heavy",
  "allow_pro": false
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
  "allow_pro": true
}
```
