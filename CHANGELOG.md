# Changelog

## [0.5.1] - 2024-05-30
### Changed
- Los reportes de sesiones y la evidencia capturada se guardan ahora en `%APPDATA%\WebRecord` para separar la configuración del código fuente.
- El caché de credenciales continúa ubicándose en `%APPDATA%\ForgeBuild\login_cache.json` para conservar la compatibilidad con la herramienta hermana.

## [0.5.0] - 2024-05-29
### Added
- Tabla `dbo.history_entries` documentada en `docs/database_schema.md` para centralizar los historiales de la aplicación.

### Changed
- Los historiales de URLs y Confluence ahora se leen y escriben desde SQL Server mediante `HistoryDAO`.
- `HistoryDAO` crea automáticamente la tabla `dbo.history_entries` cuando aún no existe en la base de datos.

### Removed
- Archivos locales `url_history.json` y `_confluence_history.json` reemplazados por almacenamiento en base de datos.

## [0.4.0] - 2024-05-28
### Changed
- `iniciar_pruebas.bat` ahora crea `.venv` y sincroniza `requirements-dev.txt` antes de lanzar la aplicacion para evitar faltantes como el driver de base de datos.

### Added
- Pantalla de inicio de sesión que valida credenciales contra la tabla `dbo.users` con hashes PBKDF2.
- Servicio, DAO y DTO dedicados para autenticación reutilizando la arquitectura MVC existente.
- Dependencia `pymssql` para conectarse a SQL Server mediante la cadena `SQLSERVER_CONNECTION_STRING`.
- Selector de usuarios activos con precarga de credenciales almacenadas en `%APPDATA%\ForgeBuild\login_cache.json`.

### Fixed
- Carga diferida de `pymssql` y validación del formato de cadena de conexión para evitar errores al iniciar la aplicación cuando la dependencia aún no está instalada.
- La ventana de inicio de sesión ahora se fuerza al frente para que siempre sea visible al abrir la aplicación.
- La cadena de conexión se resuelve desde `.env` utilizando `BRANCH_HISTORY_DB_URL` y se centraliza en un módulo compartido para evitar duplicaciones.
- Se ajustó el tamaño mínimo del cuadro de inicio de sesión para que los botones **Acceder** y **Cancelar** siempre queden visibles.
- La ventana de inicio de sesión aparece de inmediato y carga el listado de usuarios activos en segundo plano para no bloquear la interfaz cuando SQL Server no responde.
- La carga en segundo plano del listado de usuarios ahora evita invocar Tkinter desde hilos secundarios, eliminando el error `RuntimeError: main thread is not in main loop`.
- El cuadro de inicio de sesión se centra automáticamente y se asegura de mostrarse aunque la ventana principal permanezca oculta.
- Se restableció la geometría base del cuadro de inicio de sesión a `380x260` y se eliminó el modo `transient` para que vuelva a mostrarse correctamente.
- La lista de usuarios activos vuelve a precargarse antes de mostrar el cuadro de inicio de sesión, de modo que el selector aparezca listo sin mostrar la leyenda "Cargando usuarios activos...".

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
