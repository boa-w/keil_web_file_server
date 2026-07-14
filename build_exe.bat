@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found.
  echo [HINT] Install Node.js LTS and ensure npm is in PATH.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing .venv in project root.
  echo [HINT] Please run: uv venv .venv
  exit /b 1
)

echo [INFO] Installing frontend dependencies...
call npm ci --prefix webui-vue
if errorlevel 1 goto :fail

echo [INFO] Building Vue frontend...
call npm run build --prefix webui-vue
if errorlevel 1 goto :fail

echo [INFO] Preparing pip in the virtual environment...
".venv\Scripts\python.exe" -m pip --version >nul 2>nul
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m ensurepip --upgrade
  if errorlevel 1 goto :fail
)

echo [INFO] Installing Python build dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail

set WORK_TMP=%~dp0build
if exist "%WORK_TMP%" (
  attrib -R "%WORK_TMP%\*" /S /D >nul 2>nul
  rmdir /S /Q "%WORK_TMP%" >nul 2>nul
)
mkdir "%WORK_TMP%"
if errorlevel 1 goto :fail

echo [INFO] Building EXE with .venv Python ...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --onefile --name keil_web_file_server --distpath "%~dp0dist" --workpath "%WORK_TMP%" --specpath "%WORK_TMP%" --collect-all fastapi --collect-all starlette --collect-all pydantic --collect-all uvicorn --add-data "%~dp0webui-vue\dist;webui-vue/dist" keil_web_file_server.py
if errorlevel 1 goto :fail

rmdir /S /Q "%WORK_TMP%" >nul 2>nul
echo [OK] Build completed.
echo [OK] EXE path: %~dp0dist\keil_web_file_server.exe
exit /b 0

:fail
if defined WORK_TMP if exist "%WORK_TMP%" rmdir /S /Q "%WORK_TMP%" >nul 2>nul
echo [ERROR] Build failed.
exit /b 1
