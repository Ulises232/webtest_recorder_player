# Changelog

## [0.4.0] - 2024-05-28
### Changed
- `iniciar_pruebas.bat` ahora crea `.venv` y sincroniza `requirements-dev.txt` antes de lanzar la aplicacion para evitar faltantes como `pyodbc`.

### Added
- Pantalla de inicio de sesión que valida credenciales contra la tabla `dbo.users` con hashes PBKDF2.
- Servicio, DAO y DTO dedicados para autenticación reutilizando la arquitectura MVC existente.
- Dependencia `pyodbc` para conectarse a SQL Server mediante la cadena `SQLSERVER_CONNECTION_STRING`.

### Fixed
- Carga diferida de `pyodbc` para evitar errores al iniciar la aplicación cuando la dependencia aún no está instalada.

## [0.3.0] - 2024-05-27
### Added
- Script `scripts/manage_environment.py` para crear/actualizar `.venv`, ejecutar pruebas y empaquetar la app en modo dev o prod.
- Archivo `requirements-dev.txt` con dependencias adicionales para construcción del ejecutable.
- Guía `docs/dev_prod_setup.md` con los flujos detallados de desarrollo y producción.
- Script por lotes `generar_ejecutable.bat` para compilar el `.exe` en Windows y aceptar un ícono opcional.
- Parámetro `--icon` en `manage_environment.py build` para adjuntar un archivo de ícono al ejecutable generado.

### Changed
- `iniciar_pruebas.bat` ahora usa el script de gestión de entornos para garantizar que la GUI corra dentro de `.venv`.
- `.gitignore` normalizado para preservar la línea final.

## [0.2.0] - 2024-05-26
### Changed
- Reestructura completa hacia una arquitectura estilo MVC con controladores, servicios, DAOs, DTOs y vistas independientes.
- Extracción de la lógica de historiales y lanzamiento de Chrome a servicios reutilizables.

### Added
- Punto de entrada `main.py` y documentación de arquitectura resaltando que se trata de una aplicación de escritorio.

## [0.1.2] - 2024-05-26
### Added
- Directriz en `AGENTS.md` para organizar las vistas en módulos según la acción o caso de uso.

## [0.1.1] - 2024-05-26
### Added
- Documentación del esquema de la base de datos Branch History en `docs/database_schema.md`.
- Directriz en `AGENTS.md` para mantener actualizado el esquema ante cambios en la base de datos.

## [0.1.0] - 2024-05-26
### Added
- Creación del archivo `AGENTS.md` con las directrices de arquitectura y estilo para el proyecto.
### Changed
- Ampliación de las directrices en `AGENTS.md` con pautas adicionales sobre arquitectura, estilo de código, pruebas y mantenimiento.
