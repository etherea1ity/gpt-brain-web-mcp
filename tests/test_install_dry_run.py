import subprocess
from pathlib import Path


def test_install_dry_run_does_not_create_venv():
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(["bash", "install.sh", "--dry-run"], cwd=root, text=True, capture_output=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run]" in proc.stdout
