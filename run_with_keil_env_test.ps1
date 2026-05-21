param(
  [string]$RootPath = (Get-Location).Path
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $scriptDir "dist\keil_web_file_server.exe"

if (-not (Test-Path $exePath)) {
  Write-Error "EXE not found: $exePath"
  Write-Host "[HINT] Build first: build_exe.bat"
  exit 1
}

if (-not (Test-Path $RootPath)) {
  Write-Error "Root path does not exist: $RootPath"
  exit 1
}

$env:ARMCC5_ASMOPT = "--diag_suppress=9931"
$env:ARMCC5_CCOPT = "--diag_suppress=9931"
$env:ARMCC5_LINKOPT = "--diag_suppress=9931"
$env:PATH = "D:\AppData\Local\Keil_v5\ARM\ARM_Compiler_5.06u7\Bin;$env:PATH"

Write-Host "[INFO] Launching with injected Keil-like environment..."
Write-Host "[INFO] EXE : $exePath"
Write-Host "[INFO] ROOT: $RootPath"

& $exePath $RootPath --open
