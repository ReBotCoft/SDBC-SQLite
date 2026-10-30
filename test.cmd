@echo off

setlocal
set "LO_PYTHON=C:\Program Files\LibreOffice\program\python.exe"

if not exist "%LO_PYTHON%" (
    echo ERRORE: Python di LibreOffice non trovato: %LO_PYTHON%
    exit /b 1
)

pushd "%~dp0"

if "%~1"=="" (
    "%LO_PYTHON%" -m unittest discover -s tests -p "test_*.py" -t tests
) else (
    "%LO_PYTHON%" -m unittest discover -s tests -p "test_*.py" -t tests %*
)
set "ESITO=%errorlevel%"

popd

echo.
if "%ESITO%"=="0" (echo Prove superate.) else (echo Prove NON superate, codice %ESITO%.)

exit /b %ESITO%
