@echo off
setlocal
set "APP_ROOT=%~dp0"
set "PYTHONPATH=%APP_ROOT%src"
cd /d "%APP_ROOT%"
python -m smb_preprocessor
if errorlevel 1 pause
