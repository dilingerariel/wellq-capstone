$ErrorActionPreference = 'Stop'
$script:BackendRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if ($script:BackendRoot -ne 'C:\Dev\wellq-capstone\wellq-clinical-tests-main\backend') { throw 'Integration must use the authorized C:\Dev checkout' }
$script:RuntimeRoot = Join-Path $PSScriptRoot '.runtime'
$script:EvidenceRoot = Join-Path $script:BackendRoot 'docs\evidencias_integracion'
$script:DemoOutputRoot = Join-Path $PSScriptRoot 'demo-output'
$script:StatePath = Join-Path $script:RuntimeRoot 'state.json'
function Export-IntegrationPublicEvidence {
    param([Parameter(Mandatory=$true)]$Config, [Parameter(Mandatory=$true)][string]$OutputFile,
          [string]$SecretsEnvFile = (Join-Path $script:RuntimeRoot 'integration.env'))
    # Redirect legacy destinations; never replace historical private originals.
    $publicFile = $OutputFile -replace '-redacted\.json$', '-public.json'
    if ($publicFile -notmatch '(-public|\.public)\.json$') { throw 'Public evidence needs an explicit public JSON filename' }
    $python = Join-Path $script:BackendRoot '..\..\.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $python = (Get-Command python -ErrorAction Stop).Source
    }
    $payload = $Config | ConvertTo-Json -Depth 100 -WarningAction Stop
    # Windows PowerShell 5 native pipes may use an ANSI code page. JSON escapes
    # preserve every UTF-16 code unit without relying on the host console locale.
    $payload = [regex]::Replace($payload, '[^\u0000-\u007f]', { param($match) '\u{0:x4}' -f [int][char]$match.Value })
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    # No secret values in argv, traces, temporary input files or error messages.
    $payload | & $python -B (Join-Path $PSScriptRoot 'publication.py') --stdin --output $publicFile --known-secrets-env $SecretsEnvFile --replace-public
    if ($LASTEXITCODE -ne 0) { throw 'Public evidence export refused' }
}
function Load-IntegrationState {
    if (-not (Test-Path -LiteralPath $script:StatePath)) { throw 'Run Prepare.ps1 first' }
    $script:IntegrationState = Get-Content -LiteralPath $script:StatePath -Raw | ConvertFrom-Json
    if ($script:IntegrationState.project -notmatch '^wellq-int-[a-f0-9]{12}$') { throw 'Invalid exclusive project name' }
    if ($script:IntegrationState.db -ne ('wellq_integration_' + $script:IntegrationState.run)) { throw 'Invalid test DB identity' }
    $script:ComposeArguments = @('compose','--env-file',(Join-Path $script:RuntimeRoot 'integration.env'),'-f',(Join-Path $PSScriptRoot 'compose.yaml'),'-p',$script:IntegrationState.project)
    Write-Host ('Compose project: ' + $script:IntegrationState.project)
}
function Invoke-IntegrationCompose {
    param([string[]]$ComposeArgs)
    & docker @script:ComposeArguments @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw ('Integration compose failed: ' + ($ComposeArgs -join ' ')) }
}
function Assert-IntegrationIsolation {
    param([string]$ConfigEvidenceFile = (Join-Path $script:EvidenceRoot 'compose-resolved-redacted.json'))
    Load-IntegrationState
    & docker info --format '{{.ServerVersion}}' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot access Docker Engine. No permission/system changes will be made.' }
    $resolved = & docker @script:ComposeArguments config --format json
    if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve integration configuration' }
    $config = ($resolved -join "`n") | ConvertFrom-Json
    if (($resolved -join "`n") -match 'OneDrive|backend_mongodb_data|wellq-api|wellq-mongodb') { throw 'Legacy resource reference rejected' }
    if ($config.name -ne $script:IntegrationState.project) { throw 'Compose project mismatch' }
    foreach ($service in $config.services.PSObject.Properties) {
        if ($service.Value.ports -or $service.Value.container_name) { throw 'Published ports and global container names forbidden' }
        if ($service.Value.build -and ([IO.Path]::GetFullPath($service.Value.build.context) -ne $script:BackendRoot)) { throw 'Wrong build source' }
        if ($service.Value.environment.MONGODB_URI -and $service.Value.environment.MONGODB_URI -notlike ('*@mongo-int:27017/'+$script:IntegrationState.db+'?*')) { throw 'Non-integration Mongo URI' }
        foreach ($mount in $service.Value.volumes) {
            if ($mount.type -eq 'bind') {
                $path = [IO.Path]::GetFullPath($mount.source)
                if (-not ($path.StartsWith($script:RuntimeRoot+'\') -or $path -eq $script:EvidenceRoot -or $path -eq $script:DemoOutputRoot)) { throw ('Unexpected bind mount: '+$path) }
            }
        }
    }
    foreach ($volume in $config.volumes.PSObject.Properties) {
        if ($volume.Value.external -or -not $volume.Value.name.StartsWith($script:IntegrationState.project+'-')) { throw 'Nonexclusive volume rejected' }
        $existing = & docker volume ls --filter ('name=^'+$volume.Value.name+'$') --format '{{.Name}}'
        if ($existing) {
            $labels = (& docker volume inspect $volume.Value.name --format '{{json .Labels}}') | ConvertFrom-Json
            $owner = $labels.'com.docker.compose.project'
            if ($owner -ne $script:IntegrationState.project) { throw 'Existing volume is not owned by this integration project' }
        }
    }
    foreach ($network in $config.networks.PSObject.Properties) {
        if ($network.Value.external -or -not $network.Value.name.StartsWith($script:IntegrationState.project+'-')) { throw 'Nonexclusive network rejected' }
        $existing = & docker network ls --filter ('name=^'+$network.Value.name+'$') --format '{{.Name}}'
        if ($existing) {
            $labels = (& docker network inspect $network.Value.name --format '{{json .Labels}}') | ConvertFrom-Json
            $owner = $labels.'com.docker.compose.project'
            if ($owner -ne $script:IntegrationState.project) { throw 'Existing network is not owned by this integration project' }
        }
    }
    New-Item -ItemType Directory -Path $script:EvidenceRoot -Force | Out-Null
    Export-IntegrationPublicEvidence -Config $config -OutputFile $ConfigEvidenceFile
    Write-Host 'Isolation checked: no host ports, exclusive volumes/network, C:\Dev source, synthetic-only DB.'
}
