@echo off
setlocal
title Create Handbook Runtime Exporter

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run-CreateHandbookExport.ps1"
set "RUNNER_EXIT=%ERRORLEVEL%"

echo.
if not "%RUNNER_EXIT%"=="0" (
  echo The exporter did not complete. Read the message above before closing this window.
) else (
  echo The exporter completed successfully.
)
echo.
pause
exit /b %RUNNER_EXIT%
