from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import Settings
from .models import normalize_retention


@dataclass(frozen=True, slots=True)
class ResolvedWorkflowPolicy:
    kind: str
    project: str
    project_explicit: bool
    conversation_strategy: str
    retention: str
    cleanup_remote: bool
    save_session: bool
    allow_project_fallback: bool
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProductPolicy:
    """The product-level workflow contract for ChatGPT Web Brain.

    Keep this as the single source of truth for default project/conversation
    behavior. UI selectors can change often; these policy decisions should not.
    """

    product_name: str = "ChatGPT Web Brain Gateway MCP"
    default_backend: str = "web-chatgpt"
    default_tier: str = "thinking_heavy"
    default_project: str = "Codex Brain"
    omitted_project_strategy: str = "new"
    explicit_project_strategy: str = "reuse_project"
    omitted_project_retention: str = "ephemeral"
    explicit_project_retention: str = "persistent"
    research_conversation_strategy: str = "new_job_conversation"
    research_retention: str = "job"
    research_cleanup_remote_default: bool = True
    save_session_default: bool = False
    allow_pro_default: bool = False
    max_parallel_browser_jobs: int = 1
    destructive_remote_requires_confirm: bool = True
    project_delete_requires_confirm_name: bool = True
    focus_guard: str = "recover_target_or_fail_closed"

    @classmethod
    def from_settings(cls, settings: Settings) -> "ProductPolicy":
        return cls(
            default_tier=settings.default_tier,
            default_project=settings.default_project,
            explicit_project_strategy=settings.default_conversation_policy,
            save_session_default=settings.save_session_default,
            allow_pro_default=settings.allow_pro_default,
            max_parallel_browser_jobs=settings.max_parallel_browser_jobs,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["rules"] = [
            "No project provided: create a fresh global ChatGPT conversation, keep only local result/artifact, queue remote cleanup.",
            "Explicit project provided: route to that ChatGPT Project, reuse its latest known conversation unless caller asks for conversation_strategy=new.",
            "Research jobs: always isolated async job conversations; Deep Research is first-class when UI is available; remote cleanup defaults on after local artifact is saved.",
            "Before sending any prompt: verify recorded conversation_url or requested project focus; fail closed instead of sending into a manually selected wrong chat.",
            "Pro/Pro Extended are never default; allow_pro=true is required.",
            "Remote conversation/project deletion requires explicit confirmation; project deletion also requires confirm_name to match.",
        ]
        data["recommended_workflows"] = {
            "quick_codex_question": "omit project; use default thinking_heavy; ephemeral cleanup queue keeps ChatGPT tidy",
            "repo_or_product_work": "pass project=<stable ChatGPT Project name>; use reuse_project for continuity or new for a fresh task thread",
            "long_research": "start_research; poll get_job_result; keep local artifact; remote job chat cleans up by default",
            "disposable_validation": "create a short unique project; run tests inside it; delete its conversations/project only after confirming exact name",
        }
        return data

    def resolve_ask(
        self,
        *,
        project: str | None,
        conversation_strategy: str | None,
        retention: str | None,
        cleanup_remote: bool | None,
        save_session: bool | None,
        allow_project_fallback: bool | None,
    ) -> ResolvedWorkflowPolicy:
        explicit = project is not None and str(project).strip() != ""
        effective_project = (project or self.default_project).strip() or self.default_project
        strategy = conversation_strategy or (self.explicit_project_strategy if explicit else self.omitted_project_strategy)
        default_retention = self.explicit_project_retention if explicit else self.omitted_project_retention
        resolved_retention = normalize_retention(retention, project_explicit=explicit, default=default_retention)
        resolved_cleanup = bool(cleanup_remote) if cleanup_remote is not None else False
        notes = []
        if not explicit:
            notes.append("project omitted: label result with default project but use a fresh global/ephemeral ChatGPT conversation")
        else:
            notes.append("explicit project: route to ChatGPT Project by exact visible name and keep persistent by default")
        if strategy in {"resume_url", "resume_session"} and resolved_retention in {"ephemeral", "job"}:
            notes.append("remote cleanup will be skipped for resumed/reused conversations unless a newly-created conversation is confirmed")
        return ResolvedWorkflowPolicy(
            kind="ask",
            project=effective_project,
            project_explicit=explicit,
            conversation_strategy=strategy,
            retention=resolved_retention,
            cleanup_remote=resolved_cleanup,
            save_session=self.save_session_default if save_session is None else bool(save_session),
            allow_project_fallback=False if allow_project_fallback is None else bool(allow_project_fallback),
            notes=notes,
        )

    def resolve_research(
        self,
        *,
        project: str | None,
        retention: str | None,
        cleanup_remote: bool | None,
        allow_project_fallback: bool | None,
    ) -> ResolvedWorkflowPolicy:
        explicit = project is not None and str(project).strip() != ""
        effective_project = (project or self.default_project).strip() or self.default_project
        resolved_retention = normalize_retention(retention, project_explicit=explicit, default=self.research_retention)
        resolved_cleanup = (False if resolved_retention == "persistent" else self.research_cleanup_remote_default) if cleanup_remote is None else bool(cleanup_remote)
        return ResolvedWorkflowPolicy(
            kind="research",
            project=effective_project,
            project_explicit=explicit,
            conversation_strategy=self.research_conversation_strategy,
            retention=resolved_retention,
            cleanup_remote=resolved_cleanup,
            save_session=False,
            allow_project_fallback=False if allow_project_fallback is None else bool(allow_project_fallback),
            notes=["research is always async and isolated from normal project conversations"],
        )
