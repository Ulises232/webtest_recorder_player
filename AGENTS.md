# Directrices del proyecto

Estas indicaciones aplican a todo el repositorio.

## Arquitectura
- La arquitectura del proyecto debe seguir el patrón MVC o MTV según corresponda al framework utilizado.
- Debe existir una separación clara entre **controladores**, **servicios**, **DAOs** y **DTOs**. Los controladores solo coordinan el flujo, los servicios contienen la lógica de negocio y las validaciones, los DAOs encapsulan el acceso a datos y los DTOs se utilizan para transportar información entre capas cuando existan múltiples atributos relacionados.
- Las vistas no deben contener lógica de validación; cualquier comprobación de datos se realiza en la capa de servicios. Los controladores actúan como puente entre vistas/entradas externas y el núcleo (servicios + DAOs).
- Para cada tabla o colección de datos debe existir su correspondiente DAO. Cada DAO debe proveer métodos CRUD específicos y evitar exponer directamente detalles de la base de datos al resto de capas.
- Mantener los servicios libres de llamadas directas al motor de base de datos; siempre interactúan a través de los DAOs.

## Estilo de código
- Los nombres de variables, funciones, propiedades y métodos deben declararse usando `camelCase`.
- Cada función o método debe contar con una docstring de triple comilla (`"""`) en la primera línea que describa brevemente su propósito, los parámetros que recibe y el valor que retorna (si aplica).
- Incluir anotaciones de tipo (`type hints`) en parámetros y valores de retorno para facilitar el mantenimiento y la detección temprana de errores.
- Para constantes de módulo utilizar `UPPER_SNAKE_CASE` y agruparlas en una sección superior del archivo.
- Importar solamente lo necesario y ordenar los imports siguiendo la convención: estándar, terceros y locales, separados por líneas en blanco.
- Evitar lógica compleja en una sola función; preferir funciones pequeñas y reutilizables.

## Manejo de errores y logging
- Controlar las excepciones en la capa de servicios, registrando los errores con `logging` y propagando mensajes de alto nivel a controladores.
- No capturar excepciones genéricas sin procesarlas; siempre añadir contexto y, de ser posible, encapsularlas en excepciones personalizadas del dominio.
- Configurar el logging en un punto único del proyecto y reutilizarlo mediante `logging.getLogger(__name__)`.

## Pruebas y calidad
- Mantener una cobertura de pruebas adecuada mediante `pytest` u otra herramienta equivalente. Cada servicio y DAO debe contar con pruebas unitarias que validen la lógica crítica.
- Usar `flake8` o `ruff` para asegurar el cumplimiento de estilos y detectar problemas estáticos.
- Incluir pruebas de integración cuando se comuniquen varias capas (por ejemplo, controlador + servicio + DAO) para garantizar la correcta interacción.

## Documentación y mantenimiento
- Actualizar los diagramas o documentos de arquitectura cuando se introduzcan nuevas capas o flujos relevantes.
- Mantener el archivo `CHANGELOG.md` actualizado con cada cambio significativo, siguiendo la convención semántica de versionado acordada para la rama.
- Documentar en los README o guías de despliegue cualquier dependencia externa adicional que sea necesaria para ejecutar el proyecto.
