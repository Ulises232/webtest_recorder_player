@echo off
setlocal
cd /d "%~dp0"

set GUI_FILE=main.py

where py >NUL 2>NUL
if %ERRORLEVEL%==0 (
  py -c "import pkgutil,sys; sys.exit(0 if pkgutil.find_loader('ttkbootstrap') else 1)"
  if %ERRORLEVEL% NEQ 0 (
    echo Instalando ttkbootstrap...
    py -m pip install ttkbootstrap
  )
  echo Iniciando GUI moderna...
  py "%GUI_FILE%"
  if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La GUI se cerro con codigo %ERRORLEVEL%.
    pause
  )
  goto :eof
)

where python >NUL 2>NUL
if %ERRORLEVEL%==0 (
  python -c "import pkgutil,sys; sys.exit(0 if pkgutil.find_loader('ttkbootstrap') else 1)"
  if %ERRORLEVEL% NEQ 0 (
    echo Instalando ttkbootstrap...
    python -m pip install ttkbootstrap
  )
  echo Iniciando GUI moderna...
  python "%GUI_FILE%"
  if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] La GUI se cerro con codigo %ERRORLEVEL%.
    pause
  )
  goto :eof
)

echo [ERROR] No se encontro Python en PATH.
pause
endlocal
