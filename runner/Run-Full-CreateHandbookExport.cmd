@echo off
setlocal
title Create Handbook Full Runtime Export

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-CreateHandbookExport.ps1" -Scope full
set "RUNNER_EXIT=%ERRORLEVEL%"

echo.
if not "%RUNNER_EXIT%"=="0" (
  echo The full exporter did not complete. Read the message above before closing this window.
) else (
  echo The full exporter completed successfully.
)
echo.
pause
exit /b %RUNNER_EXIT%
