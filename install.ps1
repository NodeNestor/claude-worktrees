# Install claude-worktrees plugin — pure stdlib, no venv needed.
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "claude-worktrees: Pure Python stdlib — no dependencies to install."
Write-Host ""

# Verify Python 3.10+ is available
$py = $null
if (Get-Command python -ErrorAction SilentlyContinue) { $py = "python" }
elseif (Get-Command python3 -ErrorAction SilentlyContinue) { $py = "python3" }
else {
    Write-Error "Python not found. Install Python 3.10+."
    exit 1
}

$version = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$major = & $py -c "import sys; print(sys.version_info.major)"
$minor = & $py -c "import sys; print(sys.version_info.minor)"

if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
    Write-Error "Python 3.10+ required (found $version)."
    exit 1
}

Write-Host "Python $version found. Ready to use."
Write-Host ""
Write-Host "Plugin installed at: $ScriptDir"
Write-Host "Add to your Claude Code plugins or use the MCP server directly."
