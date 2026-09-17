@echo off
title ComfyUI Anime WebApp Server
setlocal
cd /d %~dp0

if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else if exist "C:\Python31011\python.exe" (
    set PYTHON_EXE=C:\Python31011\python.exe
) else (
    set PYTHON_EXE=python.exe
)

echo Starting ComfyUI WebApp on http://127.0.0.1:8080 ...
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
pause
