@echo off
cd /d "%~dp0"
set "GIT=C:\Program Files\Git\cmd\git.exe"
if not exist "%GIT%" set "GIT=git"
echo Kod GitHub'ga yuklanmoqda...
echo GitHub'ga kirish oynasi chiqsa: "Sign in with your browser" ni bosing va ruxsat bering.
echo.
"%GIT%" push -u origin main
if errorlevel 1 goto failed
echo.
echo TAYYOR! Kod GitHub'ga yuklandi.
goto end
:failed
echo.
echo Yuklanmadi. Yuqoridagi xabarni Claude'ga yuboring.
:end
pause