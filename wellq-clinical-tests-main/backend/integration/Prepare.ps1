. (Join-Path $PSScriptRoot 'Common.ps1')
$python = Join-Path $script:BackendRoot '..\..\.venv\Scripts\python.exe'
& $python -B (Join-Path $PSScriptRoot 'prepare.py')
if ($LASTEXITCODE -ne 0) { throw 'Cannot create synthetic integration identity' }
Assert-IntegrationIsolation
