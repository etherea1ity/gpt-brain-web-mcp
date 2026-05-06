# Sample Outputs

## ask_brain
```json
{
  "answer": "Conclusion: ...",
  "backend": "web-chatgpt",
  "requested_tier": "thinking_heavy",
  "resolved_tier": "thinking_heavy",
  "fallback_chain": ["thinking_heavy"],
  "session_id": "ses_...",
  "conversation_url": "https://chatgpt.com/c/...",
  "job_id": null,
  "warnings": [],
  "sources": [],
  "artifacts": []
}
```

## Deep Research fallback
```json
{
  "job_id": "job_...",
  "status": "completed",
  "result": "...",
  "warnings": ["Deep Research UI not available; used web research fallback."],
  "artifact_path": "~/.gpt-brain-web/artifacts/job_....md"
}
```
