param([ValidateSet('suficiente','incompleto')][string]$Scenario = 'suficiente')
$pdf = Join-Path $PSScriptRoot ('demo-output\'+$Scenario+'\wellq-reporte-clinico-demo.pdf')
if (-not (Test-Path -LiteralPath $pdf)) { throw 'Run Demo.ps1 to generate the local PDF first' }
# Only a local synthetic PDF, never a signed URL or token.
Invoke-Item -LiteralPath $pdf
