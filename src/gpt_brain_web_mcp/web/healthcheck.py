from __future__ import annotations

from dataclasses import asdict, dataclass

@dataclass(slots=True)
class BrowserHealth:
    ok: bool
    login_state: str
    prompt_box_detectable: bool = False
    model_picker_detectable: bool = False
    send_button_detectable: bool = False
    captcha_detected: bool = False
    two_factor_detected: bool = False
    rate_limited: bool = False
    warnings: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.warnings is None: self.warnings = []
    def to_dict(self): return asdict(self)
