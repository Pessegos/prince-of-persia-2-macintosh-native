@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" bootstrap.py %*
    goto finish
)
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3 bootstrap.py %*
goto finish

:use_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
python bootstrap.py %*
goto finish

:missing_python
echo Python 3.10 or newer is required. Download it from https://www.python.org/.
pause
exit /b 1

:finish
if errorlevel 1 (
    pause
    exit /b 1
)
exit /b 0
