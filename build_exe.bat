@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing .venv in project root.
  echo [HINT] Please run: uv venv .venv
  exit /b 1
)

set UV_BIN=..\.venv\Scripts\uv.exe
if not exist "%UV_BIN%" (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] uv not found.
    echo [HINT] Install uv first, or ensure it is available in PATH.
    exit /b 1
  )
  set UV_BIN=uv
)

echo [INFO] Installing build dependencies with uv ...
"%UV_BIN%" pip install --python ".venv\Scripts\python.exe" -r requirements-build.txt
if errorlevel 1 goto :fail

set WORK_TMP=%TEMP%\keil_web_file_server_build
if exist "%WORK_TMP%" (
  attrib -R "%WORK_TMP%\*" /S /D >nul 2>nul
  rmdir /S /Q "%WORK_TMP%" >nul 2>nul
)

if exist "build" (
  attrib -R "build\*" /S /D >nul 2>nul
  rmdir /S /Q "build" >nul 2>nul
)

if not exist "webui-vue\dist\index.html" (
  echo [ERROR] Missing Vue dist assets: webui-vue\dist\index.html
  echo [HINT] Run build_frontend.bat first.
  exit /b 1
)

echo [INFO] Building EXE with .venv Python ...
"%UV_BIN%" run --python ".venv\Scripts\python.exe" pyinstaller --noconfirm --onefile --name keil_web_file_server --distpath "%~dp0dist" --workpath "%WORK_TMP%" --collect-all fastapi --collect-all starlette --collect-all pydantic --collect-all uvicorn --add-data "webui-vue\dist;webui-vue/dist" keil_web_file_server.py
if errorlevel 1 goto :fail

echo [OK] Build completed.
echo [OK] EXE path: %~dp0dist\keil_web_file_server.exe
exit /b 0

:fail
echo [ERROR] Build failed.
exit /b 1
