"""Local DataHub connection profiles with OS-owned secret storage."""

from __future__ import annotations

import os
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.observability import get_logger

log = get_logger(__name__)
MYSQL_SERVICE = "ResearchWorkbench.DataHub"
MYSQL_ACCOUNT = "mysql:default:password"


class CredentialStoreError(RuntimeError):
    """Stable, non-secret connection configuration failure."""


class MySQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=3306, ge=1, le=65535)
    user: str = Field(min_length=1, max_length=128)
    charset: Literal["utf8mb4", "utf8", "gbk"] = "utf8mb4"
    tls_mode: Literal["required_no_verify"] = "required_no_verify"

    @field_validator("label", "host", "user")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("连接字段不能为空或包含控制字符")
        return value

    @field_validator("host")
    @classmethod
    def validate_host(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9._:-]+", value) or ".." in value:
            raise ValueError("主机名格式非法")
        return value


class _SystemKeyring:
    def _module(self):
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("keyring unavailable") from exc
        return keyring

    def get_password(self, service: str, account: str):
        return self._module().get_password(service, account)

    def set_password(self, service: str, account: str, password: str):
        return self._module().set_password(service, account, password)

    def delete_password(self, service: str, account: str):
        return self._module().delete_password(service, account)


class MySQLConnectionStore:
    """One local MySQL profile; secrets never enter the JSON profile."""

    def __init__(self, root: Path, *, keyring_backend=None):
        self.root = Path(root)
        self.directory = self.root / "connections"
        self.path = self.directory / "mysql.json"
        self.keyring = keyring_backend or _SystemKeyring()

    def configuration(self) -> MySQLConfiguration | None:
        if not self.path.exists():
            return None
        try:
            if self.path.is_symlink() or self.path.stat().st_size > 16 * 1024:
                raise ValueError("unsafe configuration file")
            return MySQLConfiguration.model_validate_json(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("mysql_configuration_read_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("configuration_read_failed") from exc

    def _secret(self) -> str | None:
        try:
            return self.keyring.get_password(MYSQL_SERVICE, MYSQL_ACCOUNT)
        except Exception as exc:
            log.warning("mysql_credential_store_unavailable", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def credentials(self) -> tuple[MySQLConfiguration, str]:
        configuration = self.configuration()
        if configuration is None:
            raise CredentialStoreError("not_configured")
        secret = self._secret()
        if not secret:
            raise CredentialStoreError("credential_missing")
        return configuration, secret

    def status(self) -> dict:
        try:
            configuration = self.configuration()
        except CredentialStoreError as exc:
            return self._status(None, False, False, str(exc))
        try:
            secret = self._secret()
            return self._status(configuration, bool(secret), True, None)
        except CredentialStoreError:
            return self._status(configuration, False, False, "credential_store_unavailable")

    @staticmethod
    def _status(configuration, secret_configured, available, failure_code):
        data = configuration.model_dump() if configuration else {}
        return {
            **data,
            "configured": configuration is not None,
            "secret_configured": secret_configured,
            "credential_store_available": available,
            "restart_required": bool(configuration and secret_configured),
            "failure_code": failure_code,
        }

    def _write_configuration(self, configuration: MySQLConfiguration) -> None:
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise OSError("connection directory is a symlink")
        raw = configuration.model_dump_json(indent=2).encode("utf-8")
        with NamedTemporaryFile(dir=self.directory, prefix=".mysql-", delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.path)
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(missing_ok=True)

    def _delete_configuration(self) -> None:
        self.path.unlink(missing_ok=True)

    def _set_secret(self, password: str) -> None:
        try:
            self.keyring.set_password(MYSQL_SERVICE, MYSQL_ACCOUNT, password)
        except Exception as exc:
            log.warning("mysql_credential_write_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def _delete_secret(self) -> None:
        try:
            self.keyring.delete_password(MYSQL_SERVICE, MYSQL_ACCOUNT)
        except Exception as exc:
            log.warning("mysql_credential_delete_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def save(self, configuration: MySQLConfiguration, *, password: str | None = None) -> dict:
        old_configuration = self.configuration()
        old_secret = self._secret()
        replacement = password if isinstance(password, str) and password else ""
        if replacement:
            self._set_secret(replacement)
        try:
            self._write_configuration(configuration)
        except OSError as exc:
            try:
                if replacement:
                    self._set_secret(old_secret) if old_secret else self._delete_secret()
                if old_configuration is not None:
                    self._write_configuration(old_configuration)
                else:
                    self._delete_configuration()
            except (CredentialStoreError, OSError) as rollback_error:
                log.error(
                    "mysql_configuration_rollback_failed",
                    error_type=type(rollback_error).__name__,
                )
            log.error("mysql_configuration_write_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("configuration_write_failed") from exc
        log.info("mysql_configuration_saved", secret_updated=bool(replacement))
        return self.status()

    def delete(self) -> dict:
        old_configuration = self.configuration()
        old_secret = self._secret()
        if old_configuration is None and not old_secret:
            return {"deleted": True}
        if old_secret:
            self._delete_secret()
        try:
            self._delete_configuration()
        except OSError as exc:
            try:
                if old_secret:
                    self._set_secret(old_secret)
                if old_configuration is not None:
                    self._write_configuration(old_configuration)
            except (CredentialStoreError, OSError) as rollback_error:
                log.error("mysql_delete_rollback_failed", error_type=type(rollback_error).__name__)
            log.error("mysql_configuration_delete_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("configuration_delete_failed") from exc
        log.info("mysql_configuration_deleted")
        return {"deleted": True}
