@echo off

setlocal
set "LO_PYTHON=C:\Program Files\LibreOffice\program\python.exe"

if not exist "%LO_PYTHON%" (
    echo ERRORE: Python di LibreOffice non trovato: %LO_PYTHON%
    exit /b 1
)

"%LO_PYTHON%" "%~dp0tools\build_oxt.py" %*
exit /b %errorlevel%
