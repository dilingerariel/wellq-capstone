param([string]$ConfigEvidenceFile)
. (Join-Path $PSScriptRoot 'Common.ps1')
if ($ConfigEvidenceFile) { Assert-IntegrationIsolation -ConfigEvidenceFile $ConfigEvidenceFile } else { Assert-IntegrationIsolation }
Invoke-IntegrationCompose -ComposeArgs @('stop','api-int','worker-int','objects-int','mongo-int','clamav-int')
Write-Host 'Only integration services stopped. Volumes retained; no resources deleted.'
