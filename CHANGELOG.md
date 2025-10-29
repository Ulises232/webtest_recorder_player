# Changelog

## [0.8.0] - 2024-06-02
### Added
- Vista **Generar DDE/HU** con listado de tarjetas, captura de análisis y recomendación, historial de ejecuciones y exportación de resultados JSON desde `app/views/generar_dde_hu_view.py`.
- Controlador, servicio, DAOs y DTOs dedicados para coordinar la generación con LLM local incluyendo cálculo de completitud, guardado de borradores y regeneración (`app/controllers/cards_controller.py`, `app/services/card_ai_service.py`, `app/daos/cards_dao.py`, `app/dtos/card_ai_dto.py`, `app/services/llm_client.py`, `app/services/card_prompt_builder.py`).
- Pruebas unitarias que validan el flujo principal del servicio de tarjetas simulando LLM y persistencia (`tests/test_card_ai_service.py`).
- Tablas `dbo.cards_ai_inputs` y `dbo.cards_ai_outputs` documentadas en `docs/database_schema.md` para conservar los datos capturados y los resultados generados por IA.

### Changed
- `MainController` inicializa el nuevo controlador de tarjetas y lo expone a la interfaz para consumir el LLM a través del backend.
- `main_view.py` incorpora la vista de generación DDE/HU en el menú principal y la navegación lateral.

### Fixed
- Corrección en los callbacks asíncronos de la vista **Generar DDE/HU** para mantener el mensaje de error disponible al mostrar cuadros de diálogo y evitar excepciones `NameError`.
- Ajuste en el DAO de resultados de IA para que la tabla `cards_ai_outputs` se prepare aun cuando `cards_ai_inputs` no exista todavía, evitando el error al abrir el historial desde una tarjeta sin ejecuciones previas.

## [0.7.1] - 2024-06-01
### Added
- Controladores especializados para autenticación, historial, navegador, nomenclatura y sesiones que encapsulan la coordinación con sus servicios correspondientes.
- Directriz en `AGENTS.md` que establece que cada vista debe contar con un controlador dedicado cuando sea necesario.

### Changed
- `MainController` ahora agrega los nuevos controladores especializados en lugar de concentrar todas las operaciones en una sola clase.
- Las vistas de inicio de sesión y pruebas se actualizaron para interactuar con los controladores especializados expuestos por `MainController`.

## [0.7.0] - 2024-05-31
### Added
- Tablero inicial en la sección de pruebas con tabla moderna, acciones rápidas y botón para crear sesiones nuevas.
- Acciones para ver, editar, eliminar y preparar la descarga de sesiones directamente desde la interfaz.
- Métodos en `SessionDAO`, `SessionService` y `MainController` para listar, actualizar y eliminar sesiones existentes.
- Botón **Actualizar sesión** dentro de la pestaña de evidencias para guardar los metadatos cargados desde el tablero.

### Changed
- La vista de pruebas ahora organiza el flujo en pestañas y solo muestra los controles inferiores cuando corresponde.
 - Los controles del tablero de sesiones mantienen un estilo caricaturesco y ahora exhiben botones de acciones con tipografía destacada en lugar de iconos.
- La acción **Editar** abre la pestaña principal de evidencias reutilizando todas las herramientas (incluida la edición de capturas) en lugar de mostrar una ventana modal separada.
- Las acciones dentro del tablero ahora se renderizan como botones azules al estilo de **Crear sesión**, conservando las restricciones para propietarios.
- Los botones de acciones del tablero usan una variante compacta que mantiene el estilo azul sin dominar el contenido de cada fila.

### Fixed
- Se impide editar o eliminar sesiones creadas por otros usuarios mostrando avisos claros en la tabla.
- Se corrigió la alineación de la tabla del tablero de sesiones para que coincida con los encabezados y conserve el estilo azul.
- Se reordenó el tablero para que la tabla permanezca debajo de los controles principales de creación y actualización.

## [0.6.1] - 2024-05-30
### Added
- Vistas independientes para generación automática, generación manual y pruebas con sus componentes encapsulados dentro de `app/views`.

### Changed
- `main_view.py` delega la construcción de cada sección del menú a módulos especializados para reducir su tamaño y facilitar el mantenimiento.
- Nuevas directrices en `AGENTS.md` que obligan a crear un módulo por cada vista expuesta en la ventana principal.
- El cuadro de inicio de sesión ahora reside en `app/views/login_view.py` y la ventana principal solo lo invoca como módulo independiente.

### Fixed
- Se corrigió un `NameError` en la vista de pruebas que impedía inicializar los controles inferiores al abrir la aplicación.

## [0.6.0] - 2024-05-30
### Added
- Tablas `dbo.recorder_sessions`, `dbo.recorder_session_evidences` y `dbo.recorder_session_pauses` documentadas en `docs/database_schema.md` para registrar sesiones, evidencias y pausas desde la aplicación de escritorio.
- DAOs, DTOs y el `SessionService` para crear sesiones, capturar evidencias, registrar pausas y calcular los tiempos de duración.
- Controles en la GUI para iniciar, pausar/reanudar y finalizar sesiones con un cronómetro en vivo, listado de evidencias y botón para editar capturas existentes.
- Pruebas unitarias de `SessionService` que validan el flujo principal sin requerir conexión a SQL Server.

### Changed
- La generación de reportes y la edición de evidencias actualizan las rutas de salida en la sesión activa para mantener sincronizado el almacenamiento.

### Fixed
- Se corrigió el enlace de los campos de salida para que inicialicen correctamente el seguimiento de la sesión y eviten errores al arrancar la aplicación.

## [0.5.1] - 2024-05-29
### Fixed
- Normalizada la integración con los cuadros de diálogo para que usen `ttkbootstrap` cuando está disponible y hagan `fallback` a Tkinter, evitando excepciones `AttributeError` y asegurando que los mensajes solo aparezcan en pantalla.
- Se dejan habilitados los cuadros de diálogo nativos de Tkinter por defecto para conservar la confirmación original cuando se cierra con la "tacha" y evitar ventanas duplicadas.

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
