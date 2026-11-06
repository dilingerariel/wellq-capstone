param([string]$ConfigEvidenceFile)
. (Join-Path $PSScriptRoot 'Common.ps1')
if ($ConfigEvidenceFile) { Assert-IntegrationIsolation -ConfigEvidenceFile $ConfigEvidenceFile } else { Assert-IntegrationIsolation }
Invoke-IntegrationCompose -ComposeArgs @('build')
Invoke-IntegrationCompose -ComposeArgs @('up','-d','setup-int','mongo-int','provision-int','objects-int','api-int','worker-int')
Invoke-IntegrationCompose -ComposeArgs @('ps','--all')
