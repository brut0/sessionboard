$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$HookDir = Join-Path $Root ".git\hooks"
if (-not (Test-Path $HookDir)) {
    New-Item -ItemType Directory -Path $HookDir -Force | Out-Null
}
$HookPath = Join-Path $HookDir "pre-commit"
$Content = @'
#!/usr/bin/env sh
set -eu
if command -v uv >/dev/null 2>&1; then
  uv run python scripts/check_repo_hygiene.py
elif [ -x "$LOCALAPPDATA/Python/pythoncore-3.14-64/Scripts/uv.exe" ]; then
  "$LOCALAPPDATA/Python/pythoncore-3.14-64/Scripts/uv.exe" run python scripts/check_repo_hygiene.py
elif [ -x "$LOCALAPPDATA/Python/pythoncore-3.14-64/python.exe" ]; then
  "$LOCALAPPDATA/Python/pythoncore-3.14-64/python.exe" scripts/check_repo_hygiene.py
else
  python3 scripts/check_repo_hygiene.py || python scripts/check_repo_hygiene.py
fi
'@
[System.IO.File]::WriteAllText($HookPath, ($Content -replace "`r`n", "`n"), (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Installed pre-commit hook at $HookPath"
