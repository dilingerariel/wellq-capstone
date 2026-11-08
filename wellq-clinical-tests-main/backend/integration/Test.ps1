param([string[]]$PytestArgs = @(), [switch]$Build)
. (Join-Path $PSScriptRoot 'Common.ps1')
# Keep a user's previous tracked evidence intact. Current reports are private,
# retained, and never require removing a historical runner/container.
$reportRoot = Join-Path $script:RuntimeRoot ('test-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
Assert-IntegrationIsolation -ConfigEvidenceFile (Join-Path $reportRoot 'compose-public.json') -PrivateEvidenceDirectory $reportRoot
if ($Build) { Invoke-IntegrationCompose -ComposeArgs @('build','api-int') }
for ($attempt=0; $attempt -lt 60; $attempt++) {
    $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
    if ($LASTEXITCODE -ne 0) { throw 'Integration API not created; run Start.ps1 first' }
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 1
}
if ($health -ne 'healthy') { throw 'Integration API is not healthy' }
$runner = $script:IntegrationState.project + '-test-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
& docker @script:ComposeArguments run --name $runner --no-deps runner-int test @PytestArgs
$testExit = $LASTEXITCODE
if (-not (Test-Path -LiteralPath (Join-Path $reportRoot 'integration.xml'))) { throw 'Test report could not be retained; runner was preserved' }
Write-Host ('Private report: ' + (Join-Path $reportRoot 'integration.xml'))
Write-Host ('Retained runner: ' + $runner)
if ($testExit -ne 0) { throw 'Integration tests failed; inspect the private report' }
