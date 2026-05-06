#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
NO_CODEX_CONFIG=0
VISIBLE_BROWSER=0
HEADLESS=1
UNINSTALL=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --no-codex-config) NO_CODEX_CONFIG=1 ;;
    --visible-browser) VISIBLE_BROWSER=1; HEADLESS=0 ;;
    --headless) HEADLESS=1; VISIBLE_BROWSER=0 ;;
    --uninstall) UNINSTALL=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: ./install.sh [--dry-run] [--no-codex-config] [--visible-browser|--headless] [--uninstall]
EOF
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
VENV="$ROOT/.venv"
HOME_DIR="${GPT_BRAIN_HOME:-$HOME/.gpt-brain-web}"

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf '[dry-run] %q ' "$@"; echo
  else
    "$@"
  fi
}

if ! "$PYTHON_BIN" - <<'PY' >/dev/null; then
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  echo "Python 3.11+ is required. Set PYTHON=/path/to/python3.11 and rerun." >&2
  exit 1
fi

if [[ "$UNINSTALL" == "1" ]]; then
  if [[ -x "$VENV/bin/python" ]]; then PY="$VENV/bin/python"; else PY="$PYTHON_BIN"; fi
  if [[ "$NO_CODEX_CONFIG" == "0" ]]; then
    UNINSTALL_ARGS=(install --uninstall)
    if [[ "$DRY_RUN" == "1" ]]; then UNINSTALL_ARGS+=(--dry-run); fi
    run "$PY" -m gpt_brain_web_mcp "${UNINSTALL_ARGS[@]}"
  fi
  echo "Uninstall complete. Dedicated profile is preserved at $HOME_DIR. Remove it manually only if desired."
  exit 0
fi

if [[ "$DRY_RUN" == "1" ]]; then
  "$PYTHON_BIN" -m venv --help >/dev/null || true
  echo "[dry-run] create venv: $VENV"
  echo "[dry-run] install package: pip install -e '$ROOT[web,dev]'"
  echo "[dry-run] install Chromium: python -m playwright install chromium"
  echo "[dry-run] create home/profile/db under $HOME_DIR"
  if [[ "$NO_CODEX_CONFIG" == "0" ]]; then echo "[dry-run] merge ~/.codex/config.toml with gpt-brain-web MCP server"; fi
  echo "[dry-run] run doctor and pre-login mock smoke"
  exit 0
fi

if "$PYTHON_BIN" -m venv "$VENV"; then
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  PY_CMD=(python)
  run "${PY_CMD[@]}" -m pip install --upgrade pip
  run "${PY_CMD[@]}" -m pip install -e "$ROOT[web,dev]"
else
  echo "Warning: python venv is unavailable; falling back to user install for this Python." >&2
  echo "Tip: on Debian/Ubuntu, installing python3-venv enables isolated venv installs." >&2
  PY_CMD=("$PYTHON_BIN")
  run "${PY_CMD[@]}" -m pip install --user --break-system-packages -e "$ROOT[web,dev]" || run "${PY_CMD[@]}" -m pip install --user -e "$ROOT[web,dev]"
fi
run "${PY_CMD[@]}" -m playwright install chromium
run mkdir -p "$HOME_DIR/browser-profile" "$HOME_DIR/logs" "$HOME_DIR/artifacts"
chmod 700 "$HOME_DIR" "$HOME_DIR/browser-profile" "$HOME_DIR/logs" "$HOME_DIR/artifacts" 2>/dev/null || true

INSTALL_ARGS=(install)
if [[ "$NO_CODEX_CONFIG" == "1" ]]; then INSTALL_ARGS+=(--no-codex-config); fi
if [[ "$VISIBLE_BROWSER" == "1" ]]; then INSTALL_ARGS+=(--visible-browser); fi
if [[ "$HEADLESS" == "1" ]]; then INSTALL_ARGS+=(--headless); fi
run "${PY_CMD[@]}" -m gpt_brain_web_mcp "${INSTALL_ARGS[@]}"

# Mock smoke should not consume the user's ChatGPT account.
GPT_BRAIN_WEB_MOCK=1 run "${PY_CMD[@]}" -m gpt_brain_web_mcp smoke

cat <<EOF

Installed gpt-brain-web-mcp.
Next steps:
  1. gpt-brain-web login     # opens a dedicated ChatGPT browser profile; log in manually
  2. RUN_LIVE_CHATGPT_WEB=1 gpt-brain-web smoke     # real ChatGPT Web smoke after login
  3. Restart Codex so it reads the merged MCP config.

Profile/db/logs live under: $HOME_DIR
EOF
