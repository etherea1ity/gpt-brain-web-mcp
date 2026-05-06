from __future__ import annotations

from ..store import Store

class ConversationManager:
    def __init__(self, store: Store): self.store = store
    def project_conversation(self, project: str | None) -> str | None:
        row = self.store.find_project_session(project)
        return row.get("conversation_url") if row else None
    def bind_project(self, project: str, conversation_url: str) -> str:
        return self.store.set_project_conversation(project, conversation_url)
    def bind_session(self, session_id: str, conversation_url: str) -> None:
        self.store.update_session(session_id, conversation_url=conversation_url)
    def bind_job(self, job_id: str, conversation_url: str) -> None:
        self.store.update_job(job_id, conversation_url=conversation_url)
