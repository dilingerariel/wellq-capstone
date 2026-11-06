. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
Invoke-IntegrationCompose -ComposeArgs @('stop','worker-int')
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','restart-prepare')
Invoke-IntegrationCompose -ComposeArgs @('stop','api-int')
Invoke-IntegrationCompose -ComposeArgs @('start','api-int','worker-int')
for ($attempt=0; $attempt -lt 60; $attempt++) {
    $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 1
}
if ($health -ne 'healthy') { throw 'Integration API did not recover after restart' }
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','restart-verify')
