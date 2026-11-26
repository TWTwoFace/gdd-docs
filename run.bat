@echo off
setlocal
python -c "import sys" >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0run.py"
) else (
  "%LOCALAPPDATA%\Python312Embed\python.exe" "%~dp0run.py"
)
pause
