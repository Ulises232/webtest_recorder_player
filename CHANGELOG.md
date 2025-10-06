# Changelog

## [0.2.0] - 2024-05-27
### Changed
- Reestructuración del módulo de la interfaz gráfica siguiendo un esquema por capas con controladores, servicios, DAOs y DTOs.
- División de la lógica de historial, navegador y nombrado en módulos dedicados bajo `app/`.
- Simplificación del punto de entrada `gui_recorder.py` para delegar en el nuevo controlador.

## [0.1.1] - 2024-05-26
### Added
- Documentación del esquema de la base de datos Branch History en `docs/database_schema.md`.
- Directriz en `AGENTS.md` para mantener actualizado el esquema ante cambios en la base de datos.

## [0.1.0] - 2024-05-26
### Added
- Creación del archivo `AGENTS.md` con las directrices de arquitectura y estilo para el proyecto.
### Changed
- Ampliación de las directrices en `AGENTS.md` con pautas adicionales sobre arquitectura, estilo de código, pruebas y mantenimiento.
