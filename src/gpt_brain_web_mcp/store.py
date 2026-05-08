from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .redaction import redact_obj, redact_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Store:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try: os.chmod(self.db_path.parent, 0o700)
        except OSError: pass
        self.init_db()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS browser_profiles(profile_id TEXT PRIMARY KEY, profile_path TEXT NOT NULL, login_state TEXT, headless INTEGER, last_checked_at TEXT, created_at TEXT, updated_at TEXT, notes TEXT);
            CREATE TABLE IF NOT EXISTS web_sessions(session_id TEXT PRIMARY KEY, project TEXT, conversation_url TEXT, title TEXT, requested_tier TEXT, resolved_tier TEXT, created_at TEXT, updated_at TEXT, summary TEXT);
            CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY, session_id TEXT, role TEXT, content_redacted TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, project TEXT, kind TEXT, requested_tier TEXT, resolved_tier TEXT, requested_research_mode TEXT, resolved_research_mode TEXT, status TEXT, conversation_url TEXT, artifact_path TEXT, result_redacted TEXT, error_redacted TEXT, created_at TEXT, updated_at TEXT, warnings_json TEXT, sources_json TEXT);
            CREATE TABLE IF NOT EXISTS browser_events(event_id TEXT PRIMARY KEY, job_id TEXT, session_id TEXT, event_type TEXT, detail_redacted TEXT, screenshot_path_optional TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS backend_runs(run_id TEXT PRIMARY KEY, job_id TEXT, session_id TEXT, backend TEXT, duration_ms INTEGER, status TEXT, warning_redacted TEXT, created_at TEXT);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
            """)
            try: os.chmod(self.db_path, 0o600)
            except OSError: pass

    def upsert_profile(self, profile_path: str, login_state: str = "unknown", headless: bool = True, notes: str | None = None) -> str:
        pid = "default"
        ts = now()
        with self.connect() as conn:
            conn.execute("""INSERT INTO browser_profiles(profile_id, profile_path, login_state, headless, last_checked_at, created_at, updated_at, notes)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(profile_id) DO UPDATE SET profile_path=excluded.profile_path, login_state=excluded.login_state, headless=excluded.headless, last_checked_at=excluded.last_checked_at, updated_at=excluded.updated_at, notes=excluded.notes""",
            (pid, profile_path, login_state, int(headless), ts, ts, ts, redact_text(notes)))
        return pid

    def get_profile(self) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM browser_profiles WHERE profile_id='default'").fetchone()
        return dict(row) if row else None

    def create_session(self, project: str | None, requested_tier: str, resolved_tier: str | None = None, conversation_url: str | None = None, title: str | None = None) -> str:
        sid, ts = new_id("ses"), now()
        with self.connect() as conn:
            conn.execute("INSERT INTO web_sessions(session_id, project, conversation_url, title, requested_tier, resolved_tier, created_at, updated_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                         (sid, redact_text(project), conversation_url, redact_text(title), requested_tier, resolved_tier, ts, ts))
        return sid

    def update_session(self, session_id: str, **fields: Any) -> None:
        allowed = {"conversation_url", "title", "resolved_tier", "summary"}
        updates, params = [], []
        for k, v in fields.items():
            if k in allowed:
                updates.append(f"{k}=?")
                params.append(redact_text(v) if isinstance(v, str) else v)
        if not updates: return
        updates.append("updated_at=?"); params.append(now()); params.append(session_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE web_sessions SET {', '.join(updates)} WHERE session_id=?", params)

    def add_message(self, session_id: str, role: str, content: str) -> str:
        mid = new_id("msg")
        with self.connect() as conn:
            conn.execute("INSERT INTO messages(message_id, session_id, role, content_redacted, created_at) VALUES(?, ?, ?, ?, ?)", (mid, session_id, role, redact_text(content), now()))
        return mid

    def set_project_conversation(self, project: str, conversation_url: str, title: str | None = None) -> str:
        existing = self.find_project_session(project)
        if existing:
            self.update_session(existing["session_id"], conversation_url=conversation_url, title=title)
            return existing["session_id"]
        return self.create_session(project, "thinking_heavy", conversation_url=conversation_url, title=title)

    def find_project_session(self, project: str | None) -> dict[str, Any] | None:
        if not project: return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM web_sessions WHERE project=? ORDER BY updated_at DESC LIMIT 1", (redact_text(project),)).fetchone()
        return dict(row) if row else None

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM web_sessions WHERE session_id=?", (session_id,)).fetchone()
        return dict(row) if row else None

    def create_job(self, project: str | None, kind: str, requested_tier: str, requested_research_mode: str | None = None) -> str:
        jid, ts = new_id("job"), now()
        with self.connect() as conn:
            conn.execute("INSERT INTO jobs(job_id, project, kind, requested_tier, requested_research_mode, status, created_at, updated_at, warnings_json, sources_json) VALUES(?, ?, ?, ?, ?, 'queued', ?, ?, '[]', '[]')",
                         (jid, redact_text(project), kind, requested_tier, requested_research_mode, ts, ts))
        return jid

    def update_job(self, job_id: str, **fields: Any) -> None:
        allowed = {"resolved_tier", "resolved_research_mode", "status", "conversation_url", "artifact_path", "result_redacted", "error_redacted", "warnings_json", "sources_json"}
        updates, params = [], []
        for k, v in fields.items():
            if k not in allowed: continue
            updates.append(f"{k}=?")
            if k.endswith("json") and not isinstance(v, str): v = json.dumps(redact_obj(v), ensure_ascii=False)
            elif isinstance(v, str): v = redact_text(v)
            params.append(v)
        if not updates: return
        updates.append("updated_at=?"); params.append(now()); params.append(job_id)
        with self.connect() as conn:
            conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE job_id=?", params)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row: return None
        d = dict(row)
        for key in ("warnings_json", "sources_json"):
            out = key.replace("_json", "")
            try: d[out] = json.loads(d.get(key) or "[]")
            except json.JSONDecodeError: d[out] = []
        return d

    def list_sessions(self, project: str | None = None, limit: int = 20) -> dict[str, list[dict[str, Any]]]:
        limit = max(1, min(int(limit), 100))
        with self.connect() as conn:
            if project:
                sessions = conn.execute("SELECT * FROM web_sessions WHERE project=? ORDER BY updated_at DESC LIMIT ?", (redact_text(project), limit)).fetchall()
                jobs = conn.execute("SELECT * FROM jobs WHERE project=? ORDER BY updated_at DESC LIMIT ?", (redact_text(project), limit)).fetchall()
            else:
                sessions = conn.execute("SELECT * FROM web_sessions ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
                jobs = conn.execute("SELECT * FROM jobs ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return {"sessions": [dict(r) for r in sessions], "jobs": [dict(r) for r in jobs]}

    def add_event(self, event_type: str, detail: str, job_id: str | None = None, session_id: str | None = None, screenshot: str | None = None) -> str:
        eid = new_id("evt")
        with self.connect() as conn:
            conn.execute("INSERT INTO browser_events(event_id, job_id, session_id, event_type, detail_redacted, screenshot_path_optional, created_at) VALUES(?, ?, ?, ?, ?, ?, ?)",
                         (eid, job_id, session_id, event_type, redact_text(detail), screenshot, now()))
        return eid
