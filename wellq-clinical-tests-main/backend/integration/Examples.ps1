. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
Invoke-IntegrationCompose -ComposeArgs @('run','--rm','--no-deps','runner-int','examples')
