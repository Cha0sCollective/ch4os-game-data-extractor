@echo off
setlocal
title All of Create Aeronautics Pack Runtime Export

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-CreateHandbookExport.ps1" -Scope pack
set "RUNNER_EXIT=%ERRORLEVEL%"

echo.
if not "%RUNNER_EXIT%"=="0" (
  echo The pack exporter did not complete. Read the message above before closing this window.
) else (
  echo The pack exporter completed successfully.
)
echo.
pause
exit /b %RUNNER_EXIT%
