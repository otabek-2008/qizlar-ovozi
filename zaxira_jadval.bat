@echo off
cd /d "%~dp0"
rem Har 6 soatda Supabase'dan kompyuterga avtomatik zaxira olishni yoqadi (oyna ochilmaydi).
rem O'chirish uchun: schtasks /Delete /TN "QizlarOvozi zaxira" /F
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
if not exist "%PYW%" goto nopython
schtasks /Create /TN "QizlarOvozi zaxira" /TR "\"%PYW%\" \"%~dp0zaxira.py\"" /SC HOURLY /MO 6 /F
if errorlevel 1 goto failed
echo.
echo TAYYOR! Kompyuter yoqiq bo'lganda har 6 soatda zaxira olinadi.
echo Zaxiralar: %~dp0zaxira
echo O'chirish: schtasks /Delete /TN "QizlarOvozi zaxira" /F
goto end
:nopython
echo Python topilmadi: %PYW%
goto end
:failed
echo.
echo Jadval yaratilmadi.
:end
pause