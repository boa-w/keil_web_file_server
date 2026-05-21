@echo off
setlocal

REM Usage:
REM   run_with_keil_env_test.bat [ROOT_PATH]

set "SCRIPT_DIR=%~dp0"
set "EXE_PATH=%SCRIPT_DIR%dist\keil_web_file_server.exe"

if not exist "%EXE_PATH%" (
  echo [ERROR] EXE not found: %EXE_PATH%
  echo [HINT] Build first: build_exe.bat
  exit /b 1
)

if "%~1"=="" (
  set "ROOT_PATH=%CD%"
) else (
  set "ROOT_PATH=%~1"
)

if not exist "%ROOT_PATH%" (
  echo [ERROR] Root path does not exist: %ROOT_PATH%
  exit /b 1
)

REM Inject Keil-like env vars
set "ARMCC5_ASMOPT=--diag_suppress=9931"
set "ARMCC5_CCOPT=--diag_suppress=9931"
set "ARMCC5_LINKOPT=--diag_suppress=9931"
set "PATH=D:\AppData\Local\Keil_v5\ARM\ARM_Compiler_5.06u7\Bin;%PATH%"

echo [INFO] Launching with injected Keil-like environment...
echo [INFO] EXE : %EXE_PATH%
echo [INFO] ROOT: %ROOT_PATH%

"%EXE_PATH%" "%ROOT_PATH%" --open

endlocal
