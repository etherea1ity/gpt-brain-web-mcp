from __future__ import annotations
from abc import ABC, abstractmethod
from ..models import BrainRequest, BrainResult

class BrainBackend(ABC):
    name: str
    @abstractmethod
    def ask_brain(self, request: BrainRequest, session_id: str | None = None) -> BrainResult: ...
    @abstractmethod
    def ask_web(self, request: BrainRequest, session_id: str | None = None) -> BrainResult: ...
