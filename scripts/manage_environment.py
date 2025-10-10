"""Command line utilities to manage development and production workflows."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import venv
from pathlib import Path
from typing import Iterable, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_VENV = REPO_ROOT / ".venv"
REQUIREMENTS_DEV = REPO_ROOT / "requirements-dev.txt"
REQUIREMENTS_PROD = REPO_ROOT / "requirements.txt"
DIST_DIR = REPO_ROOT / "dist"
BUILD_DIR = REPO_ROOT / "build"
HASH_PREFIX = ".requirements-"


class EnvironmentCommandError(RuntimeError):
    """Represents a failure when executing an external command."""


def getPythonExecutable(venvPath: Path) -> Path:
    """Return the Python executable that belongs to the given virtual environment.

    Parameters
    ----------
    venvPath: Path
        Directory that stores the virtual environment.

    Returns
    -------
    Path
        Absolute path to the Python interpreter inside the virtual environment.
    """

    scriptsDir = "Scripts" if os.name == "nt" else "bin"
    return venvPath / scriptsDir / ("python.exe" if os.name == "nt" else "python")


def runCommand(command: Iterable[str], description: str) -> None:
    """Execute a command and raise a domain specific error if it fails.

    Parameters
    ----------
    command: Iterable[str]
        Command arguments to execute.
    description: str
        Human readable description used for error messages.

    Raises
    ------
    EnvironmentCommandError
        Raised when the command exits with a non-zero status code.
    """

    try:
        subprocess.run(list(command), check=True)
    except subprocess.CalledProcessError as error:
        raise EnvironmentCommandError(
            f"Fallo al {description}. Codigo de salida: {error.returncode}."
        ) from error


def computeFileHash(filePath: Path) -> str:
    """Calculate the SHA256 hash for a given file.

    Parameters
    ----------
    filePath: Path
        File whose content should be hashed.

    Returns
    -------
    str
        Hexadecimal representation of the hash.
    """

    sha256 = hashlib.sha256()
    with filePath.open("rb") as fileHandle:
        for chunk in iter(lambda: fileHandle.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def readStoredHash(hashFile: Path) -> Optional[str]:
    """Read the previously stored hash from disk if it exists.

    Parameters
    ----------
    hashFile: Path
        File that stores the cached hash value.

    Returns
    -------
    Optional[str]
        Cached hash value or ``None`` when the file is missing.
    """

    if not hashFile.exists():
        return None
    return hashFile.read_text(encoding="utf-8").strip()


def writeStoredHash(hashFile: Path, hashValue: str) -> None:
    """Persist a hash value to disk.

    Parameters
    ----------
    hashFile: Path
        File used to persist the hash value.
    hashValue: str
        Hash value that will be stored.
    """

    hashFile.write_text(hashValue, encoding="utf-8")


def createVirtualEnv(venvPath: Path, recreate: bool) -> None:
    """Create the virtual environment if required.

    Parameters
    ----------
    venvPath: Path
        Directory where the virtual environment should live.
    recreate: bool
        When ``True`` the existing environment will be deleted before creation.
    """

    if recreate and venvPath.exists():
        shutil.rmtree(venvPath)
    if not venvPath.exists():
        builder = venv.EnvBuilder(with_pip=True, clear=False)
        builder.create(venvPath)


def ensureRequirementsInstalled(
    venvPath: Path,
    requirementsFile: Path,
    recreate: bool,
) -> Path:
    """Install requirements inside the managed virtual environment.

    Parameters
    ----------
    venvPath: Path
        Virtual environment directory.
    requirementsFile: Path
        Requirements file that should be installed.
    recreate: bool
        When ``True`` dependencies are always reinstalled.

    Returns
    -------
    Path
        Python executable path inside the environment.
    """

    createVirtualEnv(venvPath, recreate)
    pythonExecutable = getPythonExecutable(venvPath)
    hashFileName = f"{HASH_PREFIX}{requirementsFile.stem}.hash"
    hashFile = venvPath / hashFileName
    desiredHash = computeFileHash(requirementsFile)
    storedHash = readStoredHash(hashFile)
    if recreate or storedHash != desiredHash:
        runCommand(
            [str(pythonExecutable), "-m", "pip", "install", "--upgrade", "pip"],
            "actualizar pip en el entorno virtual",
        )
        runCommand(
            [str(pythonExecutable), "-m", "pip", "install", "-r", str(requirementsFile)],
            f"instalar dependencias desde {requirementsFile.name}",
        )
        writeStoredHash(hashFile, desiredHash)
    return pythonExecutable


def prepareEnvironment(venvPath: Path, mode: str, recreate: bool) -> Path:
    """Prepare the requested environment and return its Python interpreter.

    Parameters
    ----------
    venvPath: Path
        Directory where the virtual environment lives.
    mode: str
        Environment mode to configure, either ``dev`` or ``prod``.
    recreate: bool
        When ``True`` the environment will be re-created from scratch.

    Returns
    -------
    Path
        Python executable that should be used for subsequent commands.
    """

    requirementsFile = REQUIREMENTS_DEV if mode == "dev" else REQUIREMENTS_PROD
    return ensureRequirementsInstalled(venvPath, requirementsFile, recreate)


def runApplication(pythonExecutable: Path) -> None:
    """Run the GUI application using the provided interpreter.

    Parameters
    ----------
    pythonExecutable: Path
        Interpreter inside the managed environment.
    """

    runCommand([str(pythonExecutable), str(REPO_ROOT / "main.py")], "iniciar la aplicacion")


def runTests(pythonExecutable: Path) -> None:
    """Execute the pytest suite inside the managed environment.

    Parameters
    ----------
    pythonExecutable: Path
        Interpreter inside the managed environment.
    """

    runCommand([str(pythonExecutable), "-m", "pytest"], "ejecutar las pruebas")


def buildExecutable(pythonExecutable: Path, name: str, windowed: bool) -> Path:
    """Generate the standalone executable using PyInstaller.

    Parameters
    ----------
    pythonExecutable: Path
        Interpreter inside the managed environment.
    name: str
        Name assigned to the generated executable.
    windowed: bool
        When ``True`` the console window is hidden for GUI applications.

    Returns
    -------
    Path
        Path to the generated executable file.
    """

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    command: list[str] = [
        str(pythonExecutable),
        "-m",
        "PyInstaller",
        str(REPO_ROOT / "main.py"),
        "--name",
        name,
        "--noconfirm",
        "--clean",
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(BUILD_DIR),
        "--onefile",
    ]
    if windowed:
        command.append("--windowed")
    runCommand(command, "generar el ejecutable con PyInstaller")
    executableExtension = ".exe" if os.name == "nt" else ""
    return DIST_DIR / f"{name}{executableExtension}"


def runExecutable(executablePath: Path) -> None:
    """Run a previously generated executable.

    Parameters
    ----------
    executablePath: Path
        Path to the executable file to run.
    """

    if not executablePath.exists():
        raise EnvironmentCommandError(
            f"No se encontro el ejecutable en {executablePath}. Ejecute el comando build primero."
        )
    runCommand([str(executablePath)], "ejecutar el archivo generado")


def parseArguments() -> argparse.Namespace:
    """Parse command line arguments for the environment manager.

    Returns
    -------
    argparse.Namespace
        Parsed arguments with the selected sub-command configuration.
    """

    parser = argparse.ArgumentParser(
        description="Gestor de entorno virtual y empaquetado para WebTest Recorder.",
    )
    parser.add_argument(
        "--venv",
        dest="venv",
        default=str(DEFAULT_VENV),
        help="Ruta al entorno virtual administrado (por defecto .venv en la raiz del repositorio).",
    )
    subParsers = parser.add_subparsers(dest="command", required=True)

    def addCommonFlags(subParser: argparse.ArgumentParser) -> None:
        """Add shared CLI flags for dependency-aware commands.

        Parameters
        ----------
        subParser: argparse.ArgumentParser
            Parser that will receive the shared options.
        """

        subParser.add_argument(
            "--mode",
            choices=("dev", "prod"),
            default="dev",
            help="Modo de ejecucion: dev instala requirements-dev, prod instala requirements.",
        )
        subParser.add_argument(
            "--recreate",
            action="store_true",
            help="Elimina y recrea el entorno virtual antes de instalar dependencias.",
        )

    setupParser = subParsers.add_parser("setup", help="Configura el entorno virtual.")
    addCommonFlags(setupParser)

    runParser = subParsers.add_parser("run", help="Ejecuta la aplicacion en modo grafico.")
    addCommonFlags(runParser)

    testParser = subParsers.add_parser("test", help="Ejecuta el conjunto de pruebas.")
    addCommonFlags(testParser)

    buildParser = subParsers.add_parser("build", help="Genera el ejecutable standalone.")
    addCommonFlags(buildParser)
    buildParser.add_argument(
        "--name",
        default="WebTestRecorder",
        help="Nombre del ejecutable generado (por defecto WebTestRecorder).",
    )
    buildParser.add_argument(
        "--console",
        action="store_true",
        help="Muestra la consola incluso para aplicaciones graficas.",
    )

    runExeParser = subParsers.add_parser(
        "run-exe",
        help="Ejecuta un binario generado previamente.",
    )
    runExeParser.add_argument(
        "--path",
        required=True,
        help="Ruta al ejecutable que se desea iniciar.",
    )

    return parser.parse_args()


def main() -> None:
    """Entry point for the command line interface."""

    arguments = parseArguments()
    venvPath = Path(arguments.venv).resolve()
    if arguments.command == "run-exe":
        runExecutable(Path(arguments.path).resolve())
        return

    recreate = bool(getattr(arguments, "recreate", False))
    mode = getattr(arguments, "mode", "dev")
    requirementsFile = REQUIREMENTS_DEV if mode == "dev" else REQUIREMENTS_PROD
    pythonExecutable = prepareEnvironment(venvPath, mode, recreate)

    if arguments.command == "setup":
        return
    if arguments.command == "run":
        runApplication(pythonExecutable)
    elif arguments.command == "test":
        runTests(pythonExecutable)
    elif arguments.command == "build":
        executablePath = buildExecutable(pythonExecutable, arguments.name, not arguments.console)
        print(f"Ejecutable generado en: {executablePath}")


if __name__ == "__main__":
    main()
