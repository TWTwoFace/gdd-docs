@echo off
setlocal
python -c "import sys" >nul 2>nul
if %errorlevel%==0 (
  python -m pip install -r "%~dp0requirements.txt"
) else (
  "%LOCALAPPDATA%\Python312Embed\python.exe" -m pip install -r "%~dp0requirements.txt"
)
pause
