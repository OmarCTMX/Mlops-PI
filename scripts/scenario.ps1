<#
.SYNOPSIS
  Ejecuta un escenario con la fuente configurada, guarda las entradas y genera la evidencia.
.EXAMPLE
  .\scripts\scenario.ps1 -Name REF -Duration 240
  .\scripts\scenario.ps1 -Name C1 -Kind C1 -Duration 120
  .\scripts\scenario.ps1 -Name C2 -Kind C2 -Duration 120
#>
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [ValidateSet('generic', 'C1', 'C2', 'S1', 'S2', 'S3', 'S4')][string]$Kind = 'generic',
    [double]$Duration = 120,
    [string]$Config = 'config/config.yaml',
    [string]$DataDir = 'data',
    [string[]]$Set = @(),
    [string]$Notes = ''
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
$inputs = "evidence/$Name/inputs"
if (Test-Path $inputs) { throw "Ya existe $inputs. Usa otro -Name o mueve la evidencia anterior." }

$runArgs = @('--config', $Config, 'run', '--scenario', $Name, '--data-dir', $DataDir,
             '--duration', "$Duration", '--record-inputs', $inputs)
if ($Notes) { $runArgs += @('--notes', $Notes) }
foreach ($s in $Set) { $runArgs += @('--set', $s) }

& $py -m cvmon @runArgs
if ($LASTEXITCODE -ne 0) { throw "El pipeline terminó con error" }

$runId = (& $py -m cvmon --config $Config run-id --scenario $Name --data-dir $DataDir).Trim()
Write-Host "Run: $runId"

if ($Name -eq 'REF') {
    & $py -m cvmon --config $Config reference --data-dir $DataDir --runs $runId --out config/reference.json
    Write-Host "Referencia creada. Ahora ejecuta: python -m cvmon thresholds --out evidence/REF/threshold_justification.md"
    New-Item -ItemType Directory -Force "evidence/$Name" | Out-Null
}
& $py -m cvmon --config $Config finalize --data-dir $DataDir --run $runId --out "evidence/$Name" --kind $Kind --inputs $inputs
exit $LASTEXITCODE
