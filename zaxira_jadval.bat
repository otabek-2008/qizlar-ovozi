@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Har 6 soatda Supabase'dan kompyuterga avtomatik zaxira olishni yoqadi (oyna ochilmaydi).
rem Oʻchirish uchun: schtasks /Delete /TN "QizlarOvozi zaxira" /F
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" (
    echo Python topilmadi: %PYW%
    pause
    exit /b
)
schtasks /Create /TN "QizlarOvozi zaxira" /TR "\"%PYW%\" \"%~dp0zaxira.py\"" /SC HOURLY /MO 6 /F
if errorlevel 1 (
    echo.
    echo Jadval yaratilmadi.
) else (
    echo.
    echo TAYYOR! Kompyuter yoqiq boʻlganda har 6 soatda zaxira olinadi.
    echo Zaxiralar: %~dp0zaxira
    echo Oʻchirish: schtasks /Delete /TN "QizlarOvozi zaxira" /F
)
pause
