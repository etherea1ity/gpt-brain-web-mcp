from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .models import DEFAULT_BACKEND, DEFAULT_TIER, normalize_tier


def bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def default_home() -> Path:
    return Path(os.getenv("GPT_BRAIN_HOME", str(Path.home() / ".gpt-brain-web"))).expanduser()


@dataclass(slots=True)
class Settings:
    backend: str = DEFAULT_BACKEND
    default_tier: str = DEFAULT_TIER
    default_project: str = "Codex Brain"
    default_conversation_policy: str = "reuse_project"
    save_session_default: bool = False
    allow_pro_default: bool = False
    home: Path = None  # type: ignore[assignment]
    db_path: Path = None  # type: ignore[assignment]
    browser_profile_dir: Path = None  # type: ignore[assignment]
    logs_dir: Path = None  # type: ignore[assignment]
    artifacts_dir: Path = None  # type: ignore[assignment]
    headless: bool = True
    visible: bool = False
    max_parallel_browser_jobs: int = 1
    mock_browser: bool = False
    chatgpt_url: str = "https://chatgpt.com/"
    selectors_path: Path = None  # type: ignore[assignment]
    model_modes_path: Path = None  # type: ignore[assignment]
    daemon_pid_path: Path = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.home is None:
            self.home = default_home()
        self.home = Path(self.home).expanduser()
        self.db_path = Path(self.db_path or self.home / "brain.db").expanduser()
        self.browser_profile_dir = Path(self.browser_profile_dir or self.home / "browser-profile").expanduser()
        self.logs_dir = Path(self.logs_dir or self.home / "logs").expanduser()
        self.artifacts_dir = Path(self.artifacts_dir or self.home / "artifacts").expanduser()
        root = Path(__file__).resolve().parents[2]
        package_defaults = Path(__file__).resolve().parent / "config_defaults"
        external_selectors = root / "config" / "selectors.yaml"
        external_modes = root / "config" / "model_modes.yaml"
        self.selectors_path = Path(self.selectors_path or (external_selectors if external_selectors.exists() else package_defaults / "selectors.yaml"))
        self.model_modes_path = Path(self.model_modes_path or (external_modes if external_modes.exists() else package_defaults / "model_modes.yaml"))
        self.daemon_pid_path = Path(self.daemon_pid_path or self.home / "daemon.pid")
        self.default_tier = normalize_tier(self.default_tier)

    @classmethod
    def from_env(cls) -> "Settings":
        home = default_home()
        return cls(
            backend=os.getenv("GPT_BRAIN_BACKEND", DEFAULT_BACKEND),
            default_tier=os.getenv("GPT_BRAIN_DEFAULT_TIER", DEFAULT_TIER),
            default_project=os.getenv("GPT_BRAIN_DEFAULT_PROJECT", "Codex Brain"),
            default_conversation_policy=os.getenv("GPT_BRAIN_CONVERSATION_POLICY", "reuse_project"),
            save_session_default=bool_env("GPT_BRAIN_SAVE_SESSION_DEFAULT", False),
            allow_pro_default=bool_env("GPT_BRAIN_ALLOW_PRO_DEFAULT", False),
            home=home,
            db_path=Path(os.getenv("GPT_BRAIN_DB_PATH", str(home / "brain.db"))),
            browser_profile_dir=Path(os.getenv("GPT_BRAIN_BROWSER_PROFILE", str(home / "browser-profile"))),
            headless=bool_env("GPT_BRAIN_BROWSER_HEADLESS", True),
            visible=bool_env("GPT_BRAIN_BROWSER_VISIBLE", False),
            mock_browser=bool_env("GPT_BRAIN_WEB_MOCK", False),
            max_parallel_browser_jobs=int(os.getenv("GPT_BRAIN_MAX_BROWSER_JOBS", "1")),
        )

    def ensure_dirs(self) -> None:
        for path in (self.home, self.browser_profile_dir, self.logs_dir, self.artifacts_dir, self.db_path.parent):
            path.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass
