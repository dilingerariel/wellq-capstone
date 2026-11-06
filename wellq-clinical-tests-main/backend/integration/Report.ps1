param([Parameter(Mandatory=$true)][string]$BaselinePath)
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
$python = Join-Path $script:BackendRoot '..\..\.venv\Scripts\python.exe'
& $python -B (Join-Path $PSScriptRoot 'report.py') --baseline $BaselinePath
if ($LASTEXITCODE -ne 0) { throw 'Integration report verification failed' }
