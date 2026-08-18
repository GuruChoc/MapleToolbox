@echo off
setlocal
cd /d "%~dp0"

set "PYW=C:\MapleOCR\.venv\Scripts\pythonw.exe"
set "PY=C:\MapleOCR\.venv\Scripts\python.exe"

if exist "%PYW%" (
    start "" "%PYW%" MapleToolbox.py
    exit /b
)

if exist "%PY%" (
    start "" "%PY%" MapleToolbox.py
    exit /b
)

where pythonw >nul 2>&1
if %errorlevel%==0 (
    start "" pythonw MapleToolbox.py
    exit /b
)

where python >nul 2>&1
if %errorlevel%==0 (
    start "" python MapleToolbox.py
    exit /b
)

where pyw >nul 2>&1
if %errorlevel%==0 (
    start "" pyw MapleToolbox.py
    exit /b
)

where py >nul 2>&1
if %errorlevel%==0 (
    start "" py MapleToolbox.py
    exit /b
)

echo Python was not found.
echo Maple Toolbox needs Python 3 with Tkinter.
pause
