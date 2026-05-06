from __future__ import annotations

from ..config import Settings
from .daemon import BrowserDaemon

class DaemonClient:
    """Local client facade. V1 is in-process/lazy; API kept stable for out-of-process daemon."""
    def __init__(self, settings: Settings): self.daemon = BrowserDaemon(settings)
    @property
    def manager(self): return self.daemon.manager
    @property
    def store(self): return self.daemon.store
    def ensure_running(self): return self.daemon.start()
    def status(self): return self.daemon.status()
    def stop(self): return self.daemon.stop()
