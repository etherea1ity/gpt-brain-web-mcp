# Sample Outputs

## ask_brain
```json
{
  "answer": "Conclusion: ...",
  "backend": "web-chatgpt",
  "requested_tier": "thinking_heavy",
  "resolved_tier": "thinking_heavy",
  "fallback_chain": ["thinking_heavy"],
  "session_id": null,
  "conversation_url": "https://chatgpt.com/c/...",
  "job_id": null,
  "warnings": [],
  "sources": [],
  "artifacts": [],
  "project": "Codex Brain",
  "conversation_strategy": "new"
}
```

## async ask/research job result
```json
{
  "job_id": "job_...",
  "kind": "ask",
  "project": "Codex Brain",
  "status": "completed",
  "result": "...",
  "sources": [],
  "artifact_path": null,
  "conversation_url": "https://chatgpt.com/c/...",
  "error": null,
  "warnings": []
}
```

## Deep Research fallback
```json
{
  "job_id": "job_...",
  "kind": "research",
  "status": "completed",
  "requested_research_mode": "deep_research",
  "resolved_research_mode": "web_research_prompt",
  "result": "...",
  "warnings": ["Deep Research UI not available; used web research fallback."],
  "artifact_path": "~/.gpt-brain-web/artifacts/job_....md"
}
```

## needs user action
```json
{
  "job_id": "job_...",
  "status": "needs_user_action",
  "error": "ChatGPT requires user action",
  "warnings": ["ChatGPT prompt box not detectable; run `gpt-brain-web login` or update selectors.yaml."]
}
```
