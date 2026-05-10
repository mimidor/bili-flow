@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

set ROOT=%~dp0
set PYTHON_EXE=%ROOT%.venv\Scripts\python.exe
set SCRIPT_PATH=%ROOT%entrypoints\dev-stack.py

if not exist "%PYTHON_EXE%" (
  echo Virtual environment interpreter not found: "%PYTHON_EXE%"
  echo Run uv sync first.
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo Dev stack entrypoint not found: "%SCRIPT_PATH%"
  exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT_PATH%"
exit /b %ERRORLEVEL%
