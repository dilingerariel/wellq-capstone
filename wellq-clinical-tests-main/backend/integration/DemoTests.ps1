. (Join-Path $PSScriptRoot 'Common.ps1')
$demoEvidence = Join-Path $script:BackendRoot 'docs\evidencias_demo'
New-Item -ItemType Directory -Path $demoEvidence -Force | Out-Null
New-Item -ItemType Directory -Path $script:DemoOutputRoot -Force | Out-Null
Assert-IntegrationIsolation -ConfigEvidenceFile (Join-Path $script:DemoOutputRoot 'compose-resolved-redacted.json')
& (Join-Path $PSScriptRoot 'Start.ps1') -ConfigEvidenceFile (Join-Path $script:DemoOutputRoot 'compose-resolved-redacted.json')
for ($attempt=0; $attempt -lt 60; $attempt++) {
    $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 1
}
if ($health -ne 'healthy') { throw 'Own API did not become healthy' }
# Override only the runner evidence mount, preserving the previous audit XMLs.
# This is a fixed path within the authorized backend, never user-provided.
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','--volume',($demoEvidence+':/evidence'),'runner-int','test')
