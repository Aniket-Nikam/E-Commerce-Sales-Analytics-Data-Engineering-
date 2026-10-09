@echo off
setlocal
title E-Commerce Sales Analytics Startup
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start_ECommerce_Platform.ps1"
if errorlevel 1 pause
endlocal

