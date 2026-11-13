<#
.SYNOPSIS
  Reproduce las entradas guardadas de un escenario con la fuente 'sequence' y compara los scores.
.EXAMPLE
  .\scripts\replay.ps1 -Name C2
#>
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [string]$Config = 'config/config.yaml',
    [string]$DataDir = 'data'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$py = '.\.venv\Scripts\python.exe'
$orig = (& $py -m cvmon --config $Config run-id --scenario $Name --data-dir $DataDir).Trim()
& $py -m cvmon --config $Config run --scenario "$Name-REPLAY" --data-dir $DataDir `
    --set source.type=sequence --set "source.path=evidence/$Name/inputs" `
    --set source.capture_fps=20 --set sampling.sample_interval_s=0 `
    --notes "Reproducción de $orig desde evidence/$Name/inputs"
$replay = (& $py -m cvmon --config $Config run-id --scenario "$Name-REPLAY" --data-dir $DataDir).Trim()
& $py -m cvmon --config $Config replay-check --data-dir $DataDir --orig $orig --replay $replay --out "evidence/$Name/replay_check.json"
exit $LASTEXITCODE
