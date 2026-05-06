#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$ROOT/.venv/bin/gpt-brain-web" ]]; then
  exec "$ROOT/.venv/bin/gpt-brain-web" doctor --verbose
fi
exec python3 -m gpt_brain_web_mcp doctor --verbose
