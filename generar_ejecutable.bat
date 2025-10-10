@echo off
setlocal
cd /d "%~dp0"

set MANAGE_SCRIPT=scripts\manage_environment.py
set MANAGE_BASE_ARGS=build --mode prod --name WebTestRecorder

set "ICON_SWITCH="
set "ICON_PATH="
if not "%~1"=="" (
  set "ICON_SWITCH=--icon"
  set "ICON_PATH=%~1"
)

where py >NUL 2>NUL
if %ERRORLEVEL%==0 (
  call :runPython "py"
  goto :checkExit
)

where python >NUL 2>NUL
if %ERRORLEVEL%==0 (
  call :runPython "python"
  goto :checkExit
)

echo [ERROR] No se encontro Python en PATH.
pause
goto :eof

:runPython
set "PYTHON_CMD=%~1"
if "%ICON_SWITCH%"=="" (
  %PYTHON_CMD% "%MANAGE_SCRIPT%" %MANAGE_BASE_ARGS%
) else (
  %PYTHON_CMD% "%MANAGE_SCRIPT%" %MANAGE_BASE_ARGS% %ICON_SWITCH% "%ICON_PATH%"
)
exit /b %ERRORLEVEL%

:checkExit
if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] La generacion del ejecutable fallo con codigo %ERRORLEVEL%.
  pause
) else (
  echo.
  echo [OK] Ejecutable generado correctamente.
  pause
)

endlocal
