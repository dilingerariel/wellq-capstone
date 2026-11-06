param([switch]$SkipBuild)
. (Join-Path $PSScriptRoot 'Common.ps1')
$phase = 'preconditions'
try {
    New-Item -ItemType Directory -Path $script:DemoOutputRoot -Force | Out-Null
    $configEvidence = Join-Path $script:DemoOutputRoot 'compose-resolved-redacted.json'
    Assert-IntegrationIsolation -ConfigEvidenceFile $configEvidence
    $phase = 'start isolated services'
    if ($SkipBuild) {
        Invoke-IntegrationCompose -ComposeArgs @('up','-d','setup-int','mongo-int','provision-int','objects-int','api-int','worker-int')
    } else {
        & (Join-Path $PSScriptRoot 'Start.ps1') -ConfigEvidenceFile $configEvidence
    }
    $phase = 'API readiness'
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
        if ($LASTEXITCODE -ne 0) { throw 'Own API container is unavailable' }
        if ($health -eq 'healthy') { break }
        Start-Sleep -Seconds 1
    }
    if ($health -ne 'healthy') { throw 'API did not become healthy; inspect only this project' }
    $phase = 'HTTP upload/confirm/validate/report/export/download'
    Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','demo')
    $phase = 'local PDF renderer'
    $python = Join-Path $script:BackendRoot '..\..\.venv\Scripts\python.exe'
    $renderPython = Join-Path $script:RuntimeRoot 'render-venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $renderPython)) {
        & $python -m venv (Join-Path $script:RuntimeRoot 'render-venv')
        if ($LASTEXITCODE -ne 0) { throw 'Cannot prepare disposable renderer venv' }
    }
    & $renderPython -c "import importlib.util; raise SystemExit(0 if all(importlib.util.find_spec(m) for m in ('pypdfium2', 'PIL')) else 1)"
    if ($LASTEXITCODE -ne 0) {
        & $renderPython -m pip install --disable-pip-version-check --only-binary=:all: pypdfium2==5.14.0 Pillow==13.0.0
        if ($LASTEXITCODE -ne 0) { throw 'Cannot install the two demo-only renderer dependencies' }
    }
    $phase = 'render all downloaded PDF pages'
    & $renderPython -B (Join-Path $PSScriptRoot 'render_demo.py')
    if ($LASTEXITCODE -ne 0) { throw 'PDF rendering failed; do not claim visual verification' }
    Write-Host ('SUCCESS: real HTTP demonstration and page rendering. Open: '+(Join-Path $script:DemoOutputRoot 'wellq-reporte-clinico-demo.pdf'))
    Write-Host ('Pages and incomplete scenario: '+$script:DemoOutputRoot)
    Write-Host 'PNG rendering is automatic; visual inspection remains a separate review. Services left running; Stop.ps1 preserves volumes.'
} catch {
    Write-Error ('Demo failed at ['+$phase+']. Review the reported operation, correct its dependency, and rerun Demo.ps1. No resources were deleted. '+$_.Exception.Message)
    exit 1
}
