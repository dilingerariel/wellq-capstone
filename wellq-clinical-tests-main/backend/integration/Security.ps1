param([ValidateSet('Before','Test')][string]$Mode = 'Test')
. (Join-Path $PSScriptRoot 'Common.ps1')
$securityEvidence = Join-Path $script:BackendRoot 'docs\evidencias_s01_s02'
New-Item -ItemType Directory -Path $securityEvidence -Force | Out-Null
$configFile = Join-Path $securityEvidence 'compose-resolved-redacted.json'
Assert-IntegrationIsolation -ConfigEvidenceFile $configFile
$mutex = New-Object Threading.Mutex($false, ('Local\'+$script:IntegrationState.project+'-security'))
if (-not $mutex.WaitOne(0)) { throw 'Another focused security run is active' }
try {
Invoke-IntegrationCompose -ComposeArgs @('build','api-int')
# Reuse the original, already-provisioned helpers by exact verified name. Keep
# failed-attempt helpers stopped; never delete containers/volumes to recover.
foreach ($service in @('setup-int','mongo-int','provision-int')) {
    $name = $script:IntegrationState.project+'-'+$service+'-1'
    $entry = (& docker inspect $name | ConvertFrom-Json)[0]
    if ($entry.Config.Labels.'com.docker.compose.project' -ne $script:IntegrationState.project -or
        $entry.Config.Labels.'com.docker.compose.service' -ne $service) { throw 'Unexpected bootstrap owner' }
    & docker start $name | Out-Null
    if ($LASTEXITCODE -ne 0) { throw ('Cannot start own service '+$service) }
    if ($service -ne 'mongo-int') {
        for ($attempt=0; $attempt -lt 60; $attempt++) {
            $status = & docker inspect $name --format '{{.State.Status}}'
            if ($status -eq 'exited') { break }
            Start-Sleep -Seconds 1
        }
        $code = & docker inspect $name --format '{{.State.ExitCode}}'
        if ($status -ne 'exited' -or $code -ne '0') { throw ('Own bootstrap failed: '+$service) }
    }
}
Invoke-IntegrationCompose -ComposeArgs @('up','-d','--no-deps','objects-int','api-int','worker-int')
for ($attempt=0; $attempt -lt 60; $attempt++) {
    $health = & docker inspect ($script:IntegrationState.project+'-api-int-1') --format '{{.State.Health.Status}}'
    if ($health -eq 'healthy') { break }
    Start-Sleep -Seconds 1
}
if ($health -ne 'healthy') { throw 'Own integration API not healthy' }
$operation = if ($Mode -eq 'Before') { 'security-before' } else { 'security-test' }
Invoke-IntegrationCompose -ComposeArgs @('run','--no-deps','--name',($script:IntegrationState.project+'-security-'+[guid]::NewGuid().ToString('N').Substring(0,8)),'--volume',($securityEvidence+':/evidence'),'runner-int',$operation)
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
