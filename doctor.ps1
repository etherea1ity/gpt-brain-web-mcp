$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Exe = Join-Path $Root ".venv\Scripts\gpt-brain-web.exe"
if (Test-Path $Exe) { & $Exe doctor --verbose } else { python -m gpt_brain_web_mcp doctor --verbose }
exit $LASTEXITCODE
