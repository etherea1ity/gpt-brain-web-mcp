from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..models import fallback_sequence
from .selectors import load_simple_yaml


class ModePage(Protocol):
    available_mode_labels: list[str]
    selected_tier: str | None
    def select_mode_label(self, label: str) -> bool: ...


@dataclass(slots=True)
class ModeSelection:
    requested_tier: str
    resolved_tier: str
    fallback_chain: list[str]
    warnings: list[str]


class ModelModeManager:
    def __init__(self, config_path: str | Path):
        self.modes = load_simple_yaml(config_path)

    def labels_for(self, tier: str) -> list[str]:
        item = self.modes.get(tier, {}) if isinstance(self.modes, dict) else {}
        labels = item.get("preferred_labels", []) if isinstance(item, dict) else []
        return [str(x) for x in labels] or [tier]

    def select_tier(self, page: ModePage, requested_tier: str, allow_pro: bool) -> ModeSelection:
        seq, warnings = fallback_sequence(requested_tier, allow_pro)
        tried: list[str] = []
        visible = [x.lower() for x in getattr(page, "available_mode_labels", [])]
        for tier in seq:
            tried.append(tier)
            if tier in {"pro", "pro_extended"} and not allow_pro: continue
            for label in self.labels_for(tier):
                visible_match = (not visible) or (label.lower() in visible)
                if visible_match and page.select_mode_label(label):
                    if tier != requested_tier:
                        warnings.append(f"Tier fallback used: requested {requested_tier}, resolved {tier}.")
                    return ModeSelection(requested_tier, tier, tried, warnings)
        warnings.append("No requested ChatGPT UI mode was found; using current/default UI mode as thinking_normal.")
        chain = tried if tried and tried[-1] == "thinking_normal" else tried + ["thinking_normal"]
        return ModeSelection(requested_tier, "thinking_normal", chain, warnings)
