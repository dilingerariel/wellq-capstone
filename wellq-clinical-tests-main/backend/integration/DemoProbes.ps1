. (Join-Path $PSScriptRoot 'Common.ps1')
New-Item -ItemType Directory -Path $script:DemoOutputRoot -Force | Out-Null
Assert-IntegrationIsolation -ConfigEvidenceFile (Join-Path $script:DemoOutputRoot 'compose-resolved-redacted.json')
# API must already be running at the reviewed source; only refresh runner tooling.
if ((& docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}') -ne 'healthy') {
    throw 'Run Demo.ps1 first; own API must be healthy'
}
Invoke-IntegrationCompose -ComposeArgs @('build','api-int')
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','demo-probes')
