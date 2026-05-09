from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Tier = Literal["thinking_heavy", "thinking_extended", "thinking_normal", "pro", "pro_extended"]
JobStatus = Literal["queued", "running", "waiting_for_model", "waiting_for_sources", "needs_user_action", "completed", "failed", "cancelled"]
DEFAULT_BACKEND = "web-chatgpt"
DEFAULT_TIER = "thinking_heavy"
THINKING_TIERS = ("thinking_heavy", "thinking_extended", "thinking_normal")
PRO_TIERS = ("pro", "pro_extended")
ALL_TIERS = THINKING_TIERS + PRO_TIERS
RETENTION_POLICIES = ("ephemeral", "job", "persistent")


class BrainWebError(RuntimeError): ...
class NeedsUserAction(BrainWebError): ...
class BrowserUnavailable(BrainWebError): ...
class TierUnavailable(BrainWebError): ...


@dataclass(slots=True)
class BrainRequest:
    question: str
    project: str | None = None
    context: str | None = None
    tier: str = DEFAULT_TIER
    allow_pro: bool = False
    web_search: bool = False
    async_request: bool = False
    save_session: bool = False
    conversation_kind: str = "project"
    conversation_key: str | None = None
    conversation_strategy: str = "reuse_project"
    project_explicit: bool = False
    allow_project_fallback: bool = False
    resume_session_id: str | None = None
    resume_conversation_url: str | None = None
    requested_research_mode: str | None = None
    retention: str = "ephemeral"
    cleanup_remote: bool = False


@dataclass(slots=True)
class BrainResult:
    answer: str
    backend: str = DEFAULT_BACKEND
    requested_tier: str = DEFAULT_TIER
    resolved_tier: str = DEFAULT_TIER
    fallback_chain: list[str] = field(default_factory=list)
    session_id: str | None = None
    conversation_url: str | None = None
    job_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    sources: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    requested_research_mode: str | None = None
    resolved_research_mode: str | None = None
    project: str | None = None
    conversation_strategy: str = "reuse_project"
    recovery_action: str | None = None
    recovery_reason: str | None = None
    retention: str = "ephemeral"
    cleanup_remote: bool = False
    cleanup_remote_status: str | None = None
    cleanup_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class JobStartResult:
    job_id: str
    status: str
    message: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_tier(value: str | None) -> str:
    tier = value or DEFAULT_TIER
    if tier not in ALL_TIERS:
        raise ValueError(f"Unsupported tier {tier!r}; expected one of {', '.join(ALL_TIERS)}")
    return tier


def fallback_sequence(requested_tier: str, allow_pro: bool) -> tuple[list[str], list[str]]:
    requested_tier = normalize_tier(requested_tier)
    warnings: list[str] = []
    if requested_tier in PRO_TIERS and not allow_pro:
        warnings.append(f"Requested {requested_tier} but allow_pro=false; Pro tiers are opt-in only, downgrading to thinking_heavy.")
        requested_tier = "thinking_heavy"
    if requested_tier == "pro_extended":
        return ["pro_extended", "pro", "thinking_heavy", "thinking_extended", "thinking_normal"], warnings
    if requested_tier == "pro":
        return ["pro", "thinking_heavy", "thinking_extended", "thinking_normal"], warnings
    if requested_tier == "thinking_extended":
        return ["thinking_extended", "thinking_normal"], warnings
    if requested_tier == "thinking_normal":
        return ["thinking_normal"], warnings
    return ["thinking_heavy", "thinking_extended", "thinking_normal"], warnings


def normalize_retention(value: str | None, *, project_explicit: bool = False, default: str | None = None) -> str:
    retention = (value or default or ("persistent" if project_explicit else "ephemeral")).strip().lower()
    if retention not in RETENTION_POLICIES:
        raise ValueError(f"Unsupported retention {retention!r}; expected one of {', '.join(RETENTION_POLICIES)}")
    return retention
