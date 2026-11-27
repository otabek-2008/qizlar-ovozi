@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Qizlar ovozi bot
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
if not exist ".env" (
    echo .env fayli yo'q. Avval sozlash.bat ni ishga tushiring.
    pause
    exit /b
)
echo Bot ishga tushmoqda... To'xtatish uchun shu oynani yoping yoki Ctrl+C bosing.
echo.
"%PY%" bot.py
echo.
echo Bot to'xtadi.
pause
