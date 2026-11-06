. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-IntegrationIsolation
Write-Host 'Stopping only integration API/workers/object gateway to reserve memory for ClamAV.'
Invoke-IntegrationCompose -ComposeArgs @('stop','api-int','worker-int','objects-int')
Invoke-IntegrationCompose -ComposeArgs @('--profile','antivirus','up','-d','clamav-int')
try {
    Invoke-IntegrationCompose -ComposeArgs @('--profile','antivirus','run','--rm','--no-deps','runner-int','clamav')
} finally {
    Invoke-IntegrationCompose -ComposeArgs @('--profile','antivirus','stop','clamav-int')
}
Write-Host 'ClamAV stopped; API/workers remain stopped. Use Start.ps1 before HTTP tests.'
