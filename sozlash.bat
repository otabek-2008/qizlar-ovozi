@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Qizlar ovozi bot
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" sozlash.py
if errorlevel 1 (
    echo.
    echo Sozlash tugallanmadi. Qaytadan ishga tushiring.
    pause
    exit /b
)
echo.
echo Bot ishga tushmoqda... Bot ishlashi uchun SHU OYNANI YOPMANG.
echo.
"%PY%" bot.py
echo.
echo Bot to'xtadi. Xatolik bo'lsa, yuqoridagi yozuvlarni Claude'ga yuboring.
pause
