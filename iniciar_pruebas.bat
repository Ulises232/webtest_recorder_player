@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "SKIP_DEPS=0"
set "FORCE_DEPS=0"

:parse_args
if "%~1"=="" goto after_parse

if /I "%~1"=="--skip-deps" (
  set "SKIP_DEPS=1"
) else if /I "%~1"=="--force-deps" (
  set "FORCE_DEPS=1"
  set "SKIP_DEPS=0"
) else (
  echo Opcion desconocida: %~1
  echo Opciones disponibles: --skip-deps --force-deps
  pause
  exit /b 1
)
shift
goto parse_args

:after_parse
set "PYTHON_CMD="
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=python"
  )
)
if not defined PYTHON_CMD (
  echo [ERROR] No se encontro Python en PATH.
  pause
  exit /b 1
)

set "VENV_DIR=.venv"
if not exist "%VENV_DIR%" (
  echo Creando entorno virtual...
  %PYTHON_CMD% -m venv "%VENV_DIR%"
  if errorlevel 1 (
    echo No fue posible crear el entorno virtual.
    pause
    exit /b 1
  )
)

call "%VENV_DIR%\Scripts\activate"

set "REQ_CACHE=%VENV_DIR%\.requirements-dev.cached.txt"

if "%FORCE_DEPS%"=="1" (
  set "SKIP_DEPS=0"
)

if "%SKIP_DEPS%"=="1" (
  if exist "%REQ_CACHE%" (
    fc /b requirements-dev.txt "%REQ_CACHE%" >nul 2>nul
    if errorlevel 1 (
      echo Cambios detectados en requirements-dev.txt. Se reinstalaran dependencias.
      set "SKIP_DEPS=0"
    ) else (
      echo Requisitos sin cambios. Reutilizando dependencias existentes.
    )
  ) else (
    set "SKIP_DEPS=0"
  )
)

if not "%SKIP_DEPS%"=="1" (
  echo Actualizando pip...
  python -m pip install --upgrade pip
  if errorlevel 1 goto deps_error

  echo Instalando dependencias de desarrollo...
  python -m pip install --no-warn-script-location -r requirements-dev.txt
  if errorlevel 1 goto deps_error

  copy /y requirements-dev.txt "%REQ_CACHE%" >nul
) else (
  echo Dependencias existentes listas.
)

echo Iniciando aplicacion...
python main.py
if errorlevel 1 goto run_error

goto end

:deps_error
echo.
echo Hubo un error instalando o actualizando las dependencias.
pause
exit /b 1

:run_error
echo.
echo [ERROR] La aplicacion finalizo con codigo %ERRORLEVEL%.
pause
exit /b %ERRORLEVEL%

:end
echo.
echo Aplicacion finalizada.
endlocal
