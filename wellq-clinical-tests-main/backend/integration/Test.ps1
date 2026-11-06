. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
for ($attempt=0; $attempt -lt 60; $attempt++) {
    $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
    if ($LASTEXITCODE -ne 0) { throw 'Integration API not created; run Start.ps1 first' }
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 1
}
if ($health -ne 'healthy') { throw 'Integration API is not healthy' }
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','test')
