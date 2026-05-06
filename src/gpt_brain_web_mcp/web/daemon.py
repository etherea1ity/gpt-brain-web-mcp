from __future__ import annotations

import argparse
import os
import signal
import time
from pathlib import Path
from typing import Any

from ..config import Settings
from ..store import Store
from .browser_manager import BrowserSessionManager, pid_alive


class BrowserDaemon:
    """Local daemon core.

    V1 supports two deployments:
    - in-process/lazy daemon facade used by MCP tests and simple embedding;
    - background process launched by `gpt-brain-web daemon start` and tracked by pid file.

    The browser profile remains dedicated in both modes.
    """
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        self.settings.ensure_dirs()
        self.store = Store(self.settings.db_path)
        self.manager = BrowserSessionManager(self.settings, self.store)
    def start(self): self.manager.start_browser(); return self.status()
    def stop(self): self.manager.stop_browser(); return self.status()
    def status(self): return self.manager.status().to_dict()
    def healthcheck(self): return self.manager.healthcheck().to_dict()


def read_pid(path: str | Path) -> int | None:
    try:
        return int(Path(path).read_text(encoding="utf-8").strip())
    except Exception:
        return None


def write_pid(path: str | Path) -> None:
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(str(os.getpid()), encoding="utf-8")
    try: p.chmod(0o600)
    except OSError: pass


def stop_pid(path: str | Path) -> bool:
    pid = read_pid(path)
    if not pid or not pid_alive(pid):
        try: Path(path).unlink()
        except OSError: pass
        return False
    os.kill(pid, signal.SIGTERM)
    return True


def serve_forever(settings: Settings | None = None) -> int:
    daemon = BrowserDaemon(settings)
    write_pid(daemon.settings.daemon_pid_path)
    stopping = {"value": False}
    def _stop(_signum: int, _frame: Any) -> None:
        stopping["value"] = True
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        daemon.start()
        while not stopping["value"]:
            time.sleep(1.0)
    finally:
        daemon.stop()
        try: daemon.settings.daemon_pid_path.unlink()
        except OSError: pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="gpt-brain-web browser daemon")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--visible", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    if args.visible:
        settings.visible = True; settings.headless = False
    if args.serve:
        return serve_forever(settings)
    print(BrowserDaemon(settings).status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
