@echo off
title Cipher Web Admin Panel
echo.
echo ========================================
echo   Starting Cipher Web Admin Panel
echo ========================================
echo.

REM Set environment variables
set ADMIN_USERNAME=admin
set ADMIN_PASSWORD=admin123
set ADMIN_HOST=0.0.0.0
set ADMIN_PORT=5001
set FLASK_ENV=development

REM Start the web admin panel
python "%~dp0web_admin.py"

pause
