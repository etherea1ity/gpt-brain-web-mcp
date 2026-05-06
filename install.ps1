param(
  [switch]$DryRun,
  [switch]$NoCodexConfig,
  [switch]$VisibleBrowser,
  [switch]$Headless,
  [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = $env:PYTHON
if (-not $Python) { $Python = "python" }
$HomeDir = if ($env:GPT_BRAIN_HOME) { $env:GPT_BRAIN_HOME } else { Join-Path $HOME ".gpt-brain-web" }
$Venv = Join-Path $Root ".venv"

function Run-Cmd([string[]]$Cmd) {
  if ($DryRun) { Write-Host "[dry-run] $($Cmd -join ' ')" } else { & $Cmd[0] $Cmd[1..($Cmd.Count-1)]; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }
}

& $Python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11+ is required. Set `$env:PYTHON to a Python 3.11 executable." }

if ($Uninstall) {
  $Py = if (Test-Path (Join-Path $Venv "Scripts\python.exe")) { Join-Path $Venv "Scripts\python.exe" } else { $Python }
  if (-not $NoCodexConfig) { Run-Cmd @($Py, "-m", "gpt_brain_web_mcp", "install", "--uninstall") }
  Write-Host "Uninstall complete. Dedicated profile preserved at $HomeDir"
  exit 0
}

if ($DryRun) {
  Write-Host "[dry-run] create venv: $Venv"
  Write-Host "[dry-run] install package: pip install -e '$Root[web,dev]'"
  Write-Host "[dry-run] install Chromium: python -m playwright install chromium"
  Write-Host "[dry-run] create home/profile/db under $HomeDir"
  if (-not $NoCodexConfig) { Write-Host "[dry-run] merge Codex MCP config" }
  exit 0
}

Run-Cmd @($Python, "-m", "venv", $Venv)
$PyExe = Join-Path $Venv "Scripts\python.exe"
Run-Cmd @($PyExe, "-m", "pip", "install", "--upgrade", "pip")
Run-Cmd @($PyExe, "-m", "pip", "install", "-e", "$Root[web,dev]")
Run-Cmd @($PyExe, "-m", "playwright", "install", "chromium")
New-Item -ItemType Directory -Force -Path (Join-Path $HomeDir "browser-profile"), (Join-Path $HomeDir "logs"), (Join-Path $HomeDir "artifacts") | Out-Null
$Args = @("-m", "gpt_brain_web_mcp", "install")
if ($NoCodexConfig) { $Args += "--no-codex-config" }
if ($VisibleBrowser) { $Args += "--visible-browser" }
if ($Headless) { $Args += "--headless" }
$FullArgs = @($PyExe) + $Args
Run-Cmd $FullArgs
$env:GPT_BRAIN_WEB_MOCK="1"
Run-Cmd @($PyExe, "-m", "gpt_brain_web_mcp", "smoke")
Write-Host "Installed. Next: gpt-brain-web login; gpt-brain-web smoke; restart Codex."
