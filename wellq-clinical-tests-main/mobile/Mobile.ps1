param(
    [ValidateSet('Doctor','Devices','Deps','Analyze','Test','Live','Build','Run','Reverse')]
    [string]$Action = 'Test',
    [string]$Device = '',
    [string]$FlutterSdk = 'C:\Dev\tools\flutter'
)
$ErrorActionPreference = 'Stop'
$flutter = Join-Path $FlutterSdk 'bin\flutter.bat'
if (-not (Test-Path -LiteralPath $flutter)) { throw 'Flutter SDK missing. See README.md.' }
$setupFile = 'C:\Dev\tools\wellq-sdk-setup.json'
if (Test-Path -LiteralPath $setupFile) {
    $setup = Get-Content -LiteralPath $setupFile -Raw | ConvertFrom-Json
    $env:JAVA_HOME = $setup.jdk
    $env:ANDROID_HOME = $setup.android_sdk
}
$env:FLUTTER_SUPPRESS_ANALYTICS = 'true'
if ($Action -in @('Run','Reverse')) {
    if (-not $env:ANDROID_HOME) { throw 'Set ANDROID_HOME or install the local SDK described in README.md.' }
    $adb = Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
    if (-not $Device) { throw 'Pass -Device with an authorized Android device ID from Devices.' }
    & $adb -s $Device reverse tcp:8765 tcp:8765
    if ($LASTEXITCODE -ne 0) { throw 'ADB reverse failed. No Android connection was established.' }
}
if ($Action -eq 'Reverse') { return }
if ($Action -eq 'Live') {
    & (Join-Path $PSScriptRoot '..\..\WellQ.ps1') Start
    if ($LASTEXITCODE -ne 0) { throw 'WellQ local startup failed.' }
}
$flutterArguments = @(switch ($Action) {
    'Doctor'  { @('doctor','-v') }
    'Devices' { @('devices') }
    'Deps'    { @('pub','get') }
    'Analyze' { @('analyze') }
    'Test'    { @('test','--reporter','expanded') }
    'Live'    { @('test','test/live_flow_test.dart','--dart-define=WELLQ_LIVE=true','--reporter','expanded') }
    'Build'   { @('build','apk','--debug','--target-platform','android-arm64','--dart-define=WELLQ_SYNTHETIC=true') }
    'Run'     { @('run','--debug','-d',$Device,'--dart-define=WELLQ_SYNTHETIC=true') }
})
Push-Location $PSScriptRoot
try { & $flutter @flutterArguments; $result = $LASTEXITCODE }
finally { Pop-Location }
if ($result -ne 0) { throw ('Flutter command failed: ' + $Action + ' (exit ' + $result + ')') }
