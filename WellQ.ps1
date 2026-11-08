param([ValidateSet('Start','Status','Stop','Logs','Test')][string]$Action = 'Status')
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing .venv. See LOCAL_DEVELOPMENT.md.' }
if ($Action -in @('Start','Test')) {
    & docker info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        & docker desktop start
        if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop with its Linux engine first.' }
    }
}
if ($Action -eq 'Test') {
    & $python -B (Join-Path $PSScriptRoot 'wellq-clinical-tests-main\frontend\scripts\local_web.py') test-services
    if ($LASTEXITCODE -ne 0) { throw 'Stop the manual local session and finish other integration tasks before Test.' }
    & (Join-Path $PSScriptRoot 'wellq-clinical-tests-main\backend\integration\Test.ps1') -Build
} else {
    & $python -B (Join-Path $PSScriptRoot 'wellq-clinical-tests-main\frontend\scripts\local_web.py') $Action.ToLowerInvariant()
    if ($LASTEXITCODE -ne 0) { throw 'WellQ local command failed; see the safe diagnostic above.' }
}
