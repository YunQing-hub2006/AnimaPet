@echo off
rem AnimaPet launcher (ported from YingPet-v4 run.bat, B5).
rem This file is intentionally pure ASCII:
rem cmd.exe parses .bat files with the OEM codepage, so non-ASCII
rem comments would show as garbage or even break parsing on CJK systems.
setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\pythonw.exe"
set "PYEXE=%~dp0.venv\Scripts\python.exe"

rem 1) local .venv ready -> use it
if exist "%VENV_PY%" goto run

rem 2) compat: reuse an existing venv in a sibling AnimaPet* folder
for /d %%D in ("%~dp0..\AnimaPet*") do (
    if exist "%%D\.venv\Scripts\pythonw.exe" (
        start "" "%%D\.venv\Scripts\pythonw.exe" "%~dp0main.py"
        exit /b 0
    )
)

rem 3) no venv -> find a WINDOWS python (skip msys/git-bash python)
set "PY_BIN="
set "PY_VER="
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PY_BIN (
        "%%P" -c "import sysconfig; raise SystemExit(0 if str(sysconfig.get_path('scripts')).lower().endswith('scripts') else 1)" >nul 2>nul
        if not errorlevel 1 set "PY_BIN=%%P"
    )
)
if not defined PY_BIN (
    py -3 -c "import sysconfig; raise SystemExit(0 if str(sysconfig.get_path('scripts')).lower().endswith('scripts') else 1)" >nul 2>nul
    if not errorlevel 1 (
        set "PY_BIN=py"
        set "PY_VER=-3"
    )
)
if not defined PY_BIN (
    echo [ERROR] No Windows Python found.
    echo Install Python 3.13 from python.org and check "Add python.exe to PATH",
    echo then run this file again.
    pause
    exit /b 1
)

rem remove leftovers from a previous failed/partial venv attempt
if exist "%~dp0.venv" rmdir /s /q "%~dp0.venv"

echo [INFO] First run: creating .venv and installing dependencies, please wait ...
"%PY_BIN%" %PY_VER% -m venv "%~dp0.venv"
if errorlevel 1 goto venv_failed
if not exist "%PYEXE%" goto venv_failed
"%PYEXE%" -m pip install --upgrade pip
"%PYEXE%" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your network and retry.
    pause
    exit /b 1
)

:run
start "" "%VENV_PY%" "%~dp0main.py"
exit /b 0

:venv_failed
echo [ERROR] Failed to create .venv.
pause
exit /b 1
