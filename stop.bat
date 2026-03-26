@echo off
setlocal
cd /d "%~dp0"

if not exist ".\.venv\Scripts\python.exe" (
  echo Missing .venv\Scripts\python.exe
  exit /b 1
)

.\.venv\Scripts\python.exe scripts\server_control.py stop
exit /b %errorlevel%
