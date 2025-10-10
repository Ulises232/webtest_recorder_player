# Guía de entornos de desarrollo y producción

Esta guía explica cómo preparar el entorno virtual, ejecutar la aplicación en modo desarrollo y generar el ejecutable para producción utilizando el nuevo script `scripts/manage_environment.py`.

## Requisitos previos

- Python 3.10 o superior disponible en la variable de entorno `PATH`.
- Acceso a Internet para instalar las dependencias declaradas.

## Configuración del entorno virtual

1. Desde la raíz del repositorio ejecute:
   ```bash
   python scripts/manage_environment.py setup --mode dev
   ```
   Este comando crea (o actualiza) la carpeta `.venv` e instala `requirements-dev.txt`, el cual incluye las dependencias de ejecución y de herramientas como PyInstaller.
2. Para un entorno de solo ejecución (producción) utilice:
   ```bash
   python scripts/manage_environment.py setup --mode prod
   ```
   En este caso únicamente se instalan las librerías listadas en `requirements.txt`.
3. Si necesita recrear el entorno desde cero agregue `--recreate` a cualquiera de los comandos anteriores.

> El script almacena un hash de los archivos de requerimientos dentro de `.venv` para evitar reinstalaciones innecesarias. Si el archivo cambia se reinstalarán automáticamente las dependencias.

## Ejecución en modo desarrollo

- Para iniciar la aplicación en modo gráfico utilizando el entorno virtual administrado ejecute:
  ```bash
  python scripts/manage_environment.py run --mode dev
  ```
- En Windows puede continuar utilizando `iniciar_pruebas.bat`, el cual delega la operación al mismo script y garantiza que `.venv` esté sincronizado.

## Pruebas automatizadas

- Ejecute las pruebas con:
  ```bash
  python scripts/manage_environment.py test --mode dev
  ```
  El comando utiliza `pytest` instalado en el entorno virtual.

## Generación del ejecutable (`.exe`)

1. Asegúrese de tener instaladas las dependencias de desarrollo (`setup --mode dev`).
2. Ejecute el siguiente comando para crear un binario listo para distribución:
   ```bash
   python scripts/manage_environment.py build --mode dev --name WebTestRecorder
   ```
   - El ejecutable se genera en la carpeta `dist/`. En Windows se crea el archivo `WebTestRecorder.exe`.
   - Si desea conservar la consola para depurar agregue la bandera `--console`.
   - Para personalizar el ícono del ejecutable agregue `--icon ruta/al/archivo.ico` (por ejemplo un `.ico` en Windows).
 3. Una vez generado el binario puede validarlo con:
   ```bash
   python scripts/manage_environment.py run-exe --path dist/WebTestRecorder.exe
   ```

> En Windows puede utilizar el archivo `generar_ejecutable.bat` para automatizar la construcción desde PowerShell o CMD. El
> script acepta como argumento opcional la ruta al ícono: `generar_ejecutable.bat ruta\al\icono.ico`.

## Personalización avanzada

- Para usar un nombre diferente de carpeta virtual añada `--venv ruta/a/mi_entorno` a cualquier comando.
- Los artefactos temporales y de distribución se ubican en `build/` y `dist/` respectivamente, ambos ignorados por Git.
- El script es idempotente: puede ejecutarlo múltiples veces sin duplicar instalaciones gracias al control de hashes.

Con esta estructura se dispone de un flujo claro de modo **dev** (ejecución y pruebas dentro de `.venv`) y modo **prod** (generación del `.exe` distribuible).
