@echo off
setlocal
cd /d "%~dp0"

set MANAGE_SCRIPT=scripts\manage_environment.py
set MANAGE_ARGS=run --mode dev

where py >NUL 2>NUL
if %ERRORLEVEL%==0 (
  py "%MANAGE_SCRIPT%" %MANAGE_ARGS%
  goto :checkExit
)

where python >NUL 2>NUL
if %ERRORLEVEL%==0 (
  python "%MANAGE_SCRIPT%" %MANAGE_ARGS%
  goto :checkExit
)

echo [ERROR] No se encontro Python en PATH.
pause
goto :eof

:checkExit
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] La aplicacion finalizo con codigo %ERRORLEVEL%.
  pause
)

endlocal
