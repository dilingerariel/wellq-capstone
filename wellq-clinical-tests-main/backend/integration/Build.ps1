. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
Invoke-IntegrationCompose -ComposeArgs @('build','api-int')
