@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0webui-vue"

where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] npm not found.
  echo [HINT] Install Node.js LTS and ensure npm is in PATH.
  exit /b 1
)

echo [INFO] Installing frontend dependencies...
npm install
if errorlevel 1 goto :fail

echo [INFO] Building Vue frontend...
npm run build
if errorlevel 1 goto :fail

echo [OK] Frontend build completed: %~dp0webui-vue\dist
exit /b 0

:fail
echo [ERROR] Frontend build failed.
exit /b 1
