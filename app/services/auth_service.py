"""Business logic for authenticating desktop application users."""

import base64
import binascii
import hashlib
import hmac
from typing import List, Optional

from app.daos.user_dao import UserDAO, UserDAOError, UserRecord
from app.dtos.auth_result import AuthenticationResult, AuthenticationStatus


class AuthService:
    """Validate credentials against the SQL Server users table."""

    DEFAULT_ITERATIONS = 480_000

    def __init__(self, user_dao: UserDAO) -> None:
        """Store the DAO dependency for further operations."""
        self._user_dao = user_dao

    def authenticate(self, username: str, password: str) -> AuthenticationResult:
        """Authenticate the provided credentials returning a structured response."""
        try:
            record = self._user_dao.get_by_username(username)
        except UserDAOError as exc:
            return AuthenticationResult(
                status=AuthenticationStatus.ERROR,
                message=str(exc),
            )

        if record is None:
            return AuthenticationResult(
                status=AuthenticationStatus.INVALID_CREDENTIALS,
                message="Usuario o contraseña incorrectos.",
            )

        if not record.active:
            return AuthenticationResult(
                status=AuthenticationStatus.INACTIVE,
                message="La cuenta está desactivada, contacte al administrador.",
            )

        if not record.passwordHash or not record.passwordSalt:
            return AuthenticationResult(
                status=AuthenticationStatus.PASSWORD_REQUIRED,
                message="El usuario no tiene una contraseña definida en el sistema central.",
            )

        iterations = self._parse_iterations(record.passwordAlgo)
        stored_hash = self._decode_base64(record.passwordHash)
        salt = self._decode_base64(record.passwordSalt)
        if stored_hash is None or salt is None:
            return AuthenticationResult(
                status=AuthenticationStatus.ERROR,
                message="Las credenciales almacenadas están corruptas o incompletas.",
            )

        computed_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )

        if not hmac.compare_digest(stored_hash, computed_hash):
            return AuthenticationResult(
                status=AuthenticationStatus.INVALID_CREDENTIALS,
                message="Usuario o contraseña incorrectos.",
            )

        if record.requirePasswordReset:
            return AuthenticationResult(
                status=AuthenticationStatus.RESET_REQUIRED,
                message="El sistema principal solicita un cambio de contraseña antes de continuar.",
            )

        return AuthenticationResult(
            status=AuthenticationStatus.AUTHENTICATED,
            message="Inicio de sesión exitoso.",
            username=record.username,
            displayName=record.displayName,
        )

    def list_active_users(self) -> List[UserRecord]:
        """Retrieve the set of active users allowed to access the application."""

        return self._user_dao.list_active_users()

    def _parse_iterations(self, password_algo: Optional[str]) -> int:
        """Parse the iteration count encoded in the password algorithm string."""
        if not password_algo:
            return self.DEFAULT_ITERATIONS
        try:
            algo, iterations = password_algo.split(":", 1)
            if algo != "pbkdf2_sha256":
                return self.DEFAULT_ITERATIONS
            return int(iterations)
        except (ValueError, TypeError):
            return self.DEFAULT_ITERATIONS

    def _decode_base64(self, value: Optional[str]) -> Optional[bytes]:
        """Decode a Base64 string defensively, returning ``None`` on failure."""
        if not value:
            return None
        try:
            return base64.b64decode(value, validate=True)
        except (ValueError, binascii.Error):  # pragma: no cover - ruta de error
            return None
