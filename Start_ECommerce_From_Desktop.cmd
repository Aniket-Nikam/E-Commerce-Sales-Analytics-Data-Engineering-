@echo off
setlocal
title E-Commerce Sales Analytics Startup
set "PROJECT=C:\Users\Aniket\Documents\Codex\2026-10-08\i-x20\work\ECommerce_Sales_Analytics_DuckDB"
if not exist "%PROJECT%\Start_ECommerce_Platform.ps1" (
  echo Project launcher not found at:
  echo %PROJECT%
  echo.
  echo If the project was moved, update PROJECT in this file.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT%\Start_ECommerce_Platform.ps1"
if errorlevel 1 pause
endlocal

