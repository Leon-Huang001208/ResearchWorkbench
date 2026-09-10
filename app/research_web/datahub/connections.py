"""Local DataHub connection profiles with OS-owned secret storage."""

from __future__ import annotations

import json
import os
import re
from functools import wraps
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from core.observability import get_logger

log = get_logger(__name__)
MYSQL_SERVICE = "ResearchWorkbench.DataHub"
MYSQL_ACCOUNT = "mysql:default:password"

SOURCE_ALIASES = {
    "zhiqiu_reports": "zhiqiu",
    "zhiqiu_wechat": "zhiqiu",
    "zhiqiu_transcript": "zhiqiu",
}
SUPPORTED_CONFIGURATION_SOURCES = frozenset(
    {"mysql", "ifind", "zhiqiu", "tinysoft", "tushare", "tavily", "bing", "wind"}
)
SINGLE_SECRET_FIELDS = {
    "tinysoft": ("token", "token"),
    "tushare": ("token", "token"),
    "tavily": ("api_key", "api_key"),
    "bing": ("api_key", "api_key"),
}
MIGRATION_VARIABLES = {
    "ifind": {"IFIND_USERNAME", "IFIND_PASSWORD", "IFIND_ACCOUNTS_JSON"},
    "zhiqiu": {"ZQ_ACCOUNTS_JSON", "ZQ_ACCOUNTS"},
    "tushare": {"TUSHARE_TOKEN"},
    "tavily": {"TAVILY_API_KEY"},
    "bing": {"BING_API_KEY"},
    "tinysoft": {"CJ_KEY"},
}


class CredentialStoreError(RuntimeError):
    """Stable, non-secret connection configuration failure."""


def _serialized(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)

    return locked


def _fsync_directory(path: Path) -> None:
    """Persist a directory entry where the host exposes POSIX directory handles."""
    if os.name == "nt":
        log.debug("datahub_directory_fsync_skipped", platform="windows")
        return
    directory_fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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


class AccountConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    username: str = Field(min_length=1, max_length=256)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(char) < 32 for char in value):
            raise ValueError("账号不能为空或包含控制字符")
        return value


class AccountUpdate(AccountConfiguration):
    model_config = ConfigDict(extra="forbid", strict=True)
    password: SecretStr | None = None
    clear_password: bool = False

    @model_validator(mode="after")
    def exclusive_secret_action(self):
        if self.clear_password and self.password is not None and self.password.get_secret_value():
            raise ValueError("不能同时设置并清除密码")
        return self


class IFindConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    backend: Literal["auto", "python_sdk", "http_api"] = "auto"
    http_base_url: str | None = Field(default=None, max_length=2048)
    accounts: list[AccountConfiguration] = Field(min_length=1, max_length=20)

    @field_validator("http_base_url")
    @classmethod
    def valid_http_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().rstrip("/")
        if not re.fullmatch(
            r"https?://[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*)?", value
        ):
            raise ValueError("iFinD HTTP 地址格式非法")
        return value

    @model_validator(mode="after")
    def unique_accounts(self):
        if len({item.id for item in self.accounts}) != len(self.accounts):
            raise ValueError("账号 ID 不能重复")
        if self.backend == "http_api" and not self.http_base_url:
            raise ValueError("http_api 后端必须配置 http_base_url")
        return self


class IFindConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    backend: Literal["auto", "python_sdk", "http_api"] = "auto"
    http_base_url: str | None = Field(default=None, max_length=2048)
    accounts: list[AccountUpdate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_stored_shape(self):
        IFindConfiguration.model_validate(
            {
                "backend": self.backend,
                "http_base_url": self.http_base_url,
                "accounts": [
                    item.model_dump(exclude={"password", "clear_password"})
                    for item in self.accounts
                ],
            }
        )
        return self


class ZhiqiuConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accounts: list[AccountConfiguration] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_accounts(self):
        if len({item.id for item in self.accounts}) != len(self.accounts):
            raise ValueError("账号 ID 不能重复")
        return self


class ZhiqiuConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    accounts: list[AccountUpdate] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_stored_shape(self):
        ZhiqiuConfiguration.model_validate(
            {
                "accounts": [
                    item.model_dump(exclude={"password", "clear_password"})
                    for item in self.accounts
                ]
            }
        )
        return self


class SingleSecretConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SingleSecretConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    secret: SecretStr | None = None
    clear_secret: bool = False

    @model_validator(mode="after")
    def exclusive_secret_action(self):
        if self.clear_secret and self.secret is not None and self.secret.get_secret_value():
            raise ValueError("不能同时设置并清除密钥")
        return self


class WindConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    preferred_adapter: Literal["auto", "client_api", "excel"] = "auto"


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


def canonical_source_id(source_id: str) -> str:
    return SOURCE_ALIASES.get(source_id, source_id)


class MySQLConnectionStore:
    """Local profiles; compatibility methods continue to target MySQL."""

    def __init__(self, root: Path, *, keyring_backend=None, env_path: Path | None = None):
        self.root = Path(root)
        self.directory = self.root / "connections"
        self.path = self.directory / "mysql.json"
        self.env_path = Path(env_path) if env_path is not None else self.root / ".env"
        self.keyring = keyring_backend or _SystemKeyring()
        self._lock = RLock()

    def _path(self, source_id: str) -> Path:
        source = canonical_source_id(source_id)
        if source not in SUPPORTED_CONFIGURATION_SOURCES:
            raise CredentialStoreError("configuration_not_supported")
        return self.directory / f"{source}.json"

    def _read_profile(self, source_id: str, model: type[BaseModel]) -> BaseModel | None:
        path = self._path(source_id)
        if not path.exists():
            return None
        try:
            if path.is_symlink() or path.stat().st_size > 64 * 1024:
                raise ValueError("unsafe configuration file")
            return model.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning(
                "datahub_configuration_read_failed",
                source=canonical_source_id(source_id),
                error_type=type(exc).__name__,
            )
            raise CredentialStoreError("configuration_read_failed") from exc

    def configuration(self) -> MySQLConfiguration | None:
        value = self._read_profile("mysql", MySQLConfiguration)
        return value if isinstance(value, MySQLConfiguration) else None

    def source_configuration(self, source_id: str) -> BaseModel | None:
        source = canonical_source_id(source_id)
        models: dict[str, type[BaseModel]] = {
            "mysql": MySQLConfiguration,
            "ifind": IFindConfiguration,
            "zhiqiu": ZhiqiuConfiguration,
            "tinysoft": SingleSecretConfiguration,
            "tushare": SingleSecretConfiguration,
            "tavily": SingleSecretConfiguration,
            "bing": SingleSecretConfiguration,
            "wind": WindConfiguration,
        }
        if source not in models:
            raise CredentialStoreError("configuration_not_supported")
        return self._read_profile(source, models[source])

    def _secret(self, account: str = MYSQL_ACCOUNT) -> str | None:
        try:
            return self.keyring.get_password(MYSQL_SERVICE, account)
        except Exception as exc:
            log.warning("datahub_credential_store_unavailable", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def _set_secret_account(self, account: str, secret: str) -> None:
        try:
            self.keyring.set_password(MYSQL_SERVICE, account, secret)
            if self.keyring.get_password(MYSQL_SERVICE, account) != secret:
                raise RuntimeError("credential readback mismatch")
        except Exception as exc:
            log.warning("datahub_credential_write_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def _delete_secret_account(self, account: str) -> None:
        try:
            self.keyring.delete_password(MYSQL_SERVICE, account)
            if self.keyring.get_password(MYSQL_SERVICE, account):
                raise RuntimeError("credential delete readback mismatch")
        except Exception as exc:
            log.warning("datahub_credential_delete_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("credential_store_unavailable") from exc

    def _account_name(self, source_id: str, item_id: str, kind: str = "password") -> str:
        return f"{canonical_source_id(source_id)}:{item_id}:{kind}"

    def credentials(self) -> tuple[MySQLConfiguration, str]:
        configuration = self.configuration()
        if configuration is None:
            raise CredentialStoreError("not_configured")
        secret = self._secret()
        if not secret:
            raise CredentialStoreError("credential_missing")
        return configuration, secret

    def read_source_secret(self, source_id: str, item_id: str = "default") -> str:
        source = canonical_source_id(source_id)
        kind = SINGLE_SECRET_FIELDS.get(source, (None, "password"))[1]
        secret = self._secret(self._account_name(source, item_id, kind))
        if not secret:
            raise CredentialStoreError("credential_missing")
        return secret

    @_serialized
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

    @_serialized
    def source_status(self, source_id: str) -> dict:
        source = canonical_source_id(source_id)
        if source == "mysql":
            return self.status()
        try:
            configuration = self.source_configuration(source)
        except CredentialStoreError as exc:
            log.warning("datahub_source_status_failed", source=source, failure_code=str(exc))
            return {
                "configured": False,
                "secret_configured": False,
                "credential_store_available": True,
                "restart_required": False,
                "failure_code": str(exc),
            }
        if configuration is None:
            defaults: dict[str, Any] = {}
            if source == "ifind":
                defaults = {"backend": "auto", "http_base_url": None, "accounts": []}
            elif source == "zhiqiu":
                defaults = {"accounts": []}
            elif source == "wind":
                defaults = {"preferred_adapter": "auto"}
            return {
                **defaults,
                "configured": False,
                "secret_configured": False,
                "credential_store_available": True,
                "restart_required": False,
                "failure_code": None,
            }
        if source == "wind":
            return {
                **configuration.model_dump(),
                "configured": True,
                "secret_configured": False,
                "credential_store_available": True,
                "restart_required": False,
                "failure_code": None,
            }
        try:
            if source in {"ifind", "zhiqiu"}:
                accounts = []
                for item in configuration.accounts:
                    secret = bool(self._secret(self._account_name(source, item.id)))
                    accounts.append({**item.model_dump(), "secret_configured": secret})
                secret_configured = any(item["secret_configured"] for item in accounts)
                data = {**configuration.model_dump(exclude={"accounts"}), "accounts": accounts}
            else:
                kind = SINGLE_SECRET_FIELDS[source][1]
                secret_configured = bool(self._secret(self._account_name(source, "default", kind)))
                data = {}
            return {
                **data,
                "configured": secret_configured,
                "secret_configured": secret_configured,
                "credential_store_available": True,
                "restart_required": secret_configured,
                "failure_code": None,
            }
        except CredentialStoreError:
            data = configuration.model_dump()
            if source in {"ifind", "zhiqiu"}:
                data["accounts"] = [
                    {**item.model_dump(), "secret_configured": False}
                    for item in configuration.accounts
                ]
            return {
                **data,
                "configured": False,
                "secret_configured": False,
                "credential_store_available": False,
                "restart_required": False,
                "failure_code": "credential_store_unavailable",
            }

    @_serialized
    def statuses(self) -> dict[str, dict]:
        result = {source: self.source_status(source) for source in SUPPORTED_CONFIGURATION_SOURCES}
        for alias, source in SOURCE_ALIASES.items():
            result[alias] = result[source]
        return result

    def _write_profile(self, source_id: str, configuration: BaseModel) -> None:
        path = self._path(source_id)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise OSError("connection directory is a symlink")
        raw = configuration.model_dump_json(indent=2).encode("utf-8")
        with NamedTemporaryFile(
            dir=self.directory, prefix=f".{canonical_source_id(source_id)}-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, path)
            _fsync_directory(self.directory)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_configuration(self, configuration: MySQLConfiguration) -> None:
        self._write_profile("mysql", configuration)

    def _delete_profile(self, source_id: str) -> None:
        self._path(source_id).unlink(missing_ok=True)

    def _delete_configuration(self) -> None:
        self._delete_profile("mysql")

    def _set_secret(self, password: str) -> None:
        self._set_secret_account(MYSQL_ACCOUNT, password)

    def _delete_secret(self) -> None:
        self._delete_secret_account(MYSQL_ACCOUNT)

    def _restore_secret_values(self, values: dict[str, str | None]) -> None:
        for account, value in values.items():
            if value:
                self._set_secret_account(account, value)
            elif self._secret(account):
                self._delete_secret_account(account)

    @_serialized
    def save(self, configuration: MySQLConfiguration, *, password: str | None = None) -> dict:
        old_configuration = self.configuration()
        old_secret = self._secret()
        replacement = password if isinstance(password, str) and password else ""
        try:
            if replacement:
                self._set_secret(replacement)
            self._write_configuration(configuration)
        except (CredentialStoreError, OSError) as exc:
            try:
                if replacement:
                    self._set_secret(old_secret) if old_secret else self._delete_secret()
                if old_configuration is not None:
                    self._write_configuration(old_configuration)
                else:
                    self._delete_configuration()
            except (CredentialStoreError, OSError) as rollback_error:
                log.error(
                    "mysql_configuration_rollback_failed", error_type=type(rollback_error).__name__
                )
            if isinstance(exc, CredentialStoreError):
                raise
            log.error("mysql_configuration_write_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("configuration_write_failed") from exc
        log.info("mysql_configuration_saved", secret_updated=bool(replacement))
        return self.status()

    def _models_for_update(self, source: str, payload: dict[str, Any]):
        if source == "ifind":
            update = IFindConfigurationUpdate.model_validate(payload)
            stored = IFindConfiguration.model_validate(
                {
                    "backend": update.backend,
                    "http_base_url": update.http_base_url,
                    "accounts": [
                        item.model_dump(exclude={"password", "clear_password"})
                        for item in update.accounts
                    ],
                }
            )
            return update, stored
        if source == "zhiqiu":
            update = ZhiqiuConfigurationUpdate.model_validate(payload)
            stored = ZhiqiuConfiguration.model_validate(
                {
                    "accounts": [
                        item.model_dump(exclude={"password", "clear_password"})
                        for item in update.accounts
                    ]
                }
            )
            return update, stored
        if source in SINGLE_SECRET_FIELDS:
            field = SINGLE_SECRET_FIELDS[source][0]
            unexpected = set(payload) - {field, "clear_secret"}
            if unexpected:
                raise ValueError(f"unexpected fields: {sorted(unexpected)}")
            update = SingleSecretConfigurationUpdate.model_validate(
                {"secret": payload.get(field), "clear_secret": payload.get("clear_secret", False)}
            )
            return update, SingleSecretConfiguration()
        if source == "wind":
            stored = WindConfiguration.model_validate(payload)
            return stored, stored
        raise CredentialStoreError("configuration_not_supported")

    def _profile_secret_accounts(self, source: str, configuration: BaseModel | None) -> set[str]:
        if source in {"ifind", "zhiqiu"} and configuration is not None:
            return {self._account_name(source, item.id) for item in configuration.accounts}
        if source in SINGLE_SECRET_FIELDS:
            return {self._account_name(source, "default", SINGLE_SECRET_FIELDS[source][1])}
        return set()

    @_serialized
    def save_source(self, source_id: str, payload: dict[str, Any]) -> dict:
        source = canonical_source_id(source_id)
        if source == "mysql":
            raise CredentialStoreError("mysql_schema_required")
        update, stored = self._models_for_update(source, payload)
        old_configuration = self.source_configuration(source)
        accounts = self._profile_secret_accounts(
            source, old_configuration
        ) | self._profile_secret_accounts(source, stored)
        old_secrets = {account: self._secret(account) for account in accounts}
        try:
            if source in {"ifind", "zhiqiu"}:
                new_ids = {item.id for item in update.accounts}
                for account in accounts:
                    item_id = account.split(":", 2)[1]
                    if item_id not in new_ids and old_secrets[account]:
                        self._delete_secret_account(account)
                for item in update.accounts:
                    account = self._account_name(source, item.id)
                    replacement = item.password.get_secret_value() if item.password else ""
                    if item.clear_password and old_secrets.get(account):
                        self._delete_secret_account(account)
                    elif replacement:
                        self._set_secret_account(account, replacement)
            elif source in SINGLE_SECRET_FIELDS:
                account = next(iter(accounts))
                replacement = update.secret.get_secret_value() if update.secret else ""
                if update.clear_secret and old_secrets.get(account):
                    self._delete_secret_account(account)
                elif replacement:
                    self._set_secret_account(account, replacement)
            self._write_profile(source, stored)
        except (CredentialStoreError, OSError) as exc:
            try:
                self._restore_secret_values(old_secrets)
                if old_configuration is None:
                    self._delete_profile(source)
                else:
                    self._write_profile(source, old_configuration)
            except (CredentialStoreError, OSError) as rollback_error:
                log.error(
                    "datahub_configuration_rollback_failed",
                    source=source,
                    error_type=type(rollback_error).__name__,
                )
            if isinstance(exc, CredentialStoreError):
                raise
            raise CredentialStoreError("configuration_write_failed") from exc
        log.info("datahub_configuration_saved", source=source)
        return self.source_status(source_id)

    @_serialized
    def delete(self) -> dict:
        old_configuration = self.configuration()
        old_secret = self._secret()
        if old_configuration is None and not old_secret:
            return {"deleted": True}
        try:
            if old_secret:
                self._delete_secret()
            self._delete_configuration()
        except (CredentialStoreError, OSError) as exc:
            try:
                if old_secret:
                    self._set_secret(old_secret)
                if old_configuration is not None:
                    self._write_configuration(old_configuration)
            except (CredentialStoreError, OSError) as rollback_error:
                log.error("mysql_delete_rollback_failed", error_type=type(rollback_error).__name__)
            if isinstance(exc, CredentialStoreError):
                raise
            log.error("mysql_configuration_delete_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("configuration_delete_failed") from exc
        log.info("mysql_configuration_deleted")
        return {"deleted": True}

    @_serialized
    def delete_source(self, source_id: str) -> dict:
        source = canonical_source_id(source_id)
        if source == "mysql":
            return self.delete()
        old_configuration = self.source_configuration(source)
        accounts = self._profile_secret_accounts(source, old_configuration)
        old_secrets = {account: self._secret(account) for account in accounts}
        if old_configuration is None and not any(old_secrets.values()):
            return {"deleted": True}
        try:
            for account, value in old_secrets.items():
                if value:
                    self._delete_secret_account(account)
            self._delete_profile(source)
        except (CredentialStoreError, OSError) as exc:
            try:
                self._restore_secret_values(old_secrets)
                if old_configuration is not None:
                    self._write_profile(source, old_configuration)
            except (CredentialStoreError, OSError) as rollback_error:
                log.error(
                    "datahub_delete_rollback_failed",
                    source=source,
                    error_type=type(rollback_error).__name__,
                )
            if isinstance(exc, CredentialStoreError):
                raise
            raise CredentialStoreError("configuration_delete_failed") from exc
        log.info("datahub_configuration_deleted", source=source)
        return {"deleted": True}

    def _env_values(self) -> tuple[list[str], dict[str, str]]:
        if not self.env_path.exists():
            return [], {}
        try:
            if self.env_path.is_symlink() or self.env_path.stat().st_size > 256 * 1024:
                raise OSError("unsafe env file")
            lines = self.env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError as exc:
            raise CredentialStoreError("migration_source_unavailable") from exc
        values = {}
        for line in lines:
            match = re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*(?:\r?\n)?$", line)
            if not match:
                continue
            raw = match.group(2)
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
                raw = raw[1:-1]
            values[match.group(1)] = raw
        return lines, values

    @_serialized
    def migration_preview(self) -> dict:
        _lines, values = self._env_values()
        targets = []
        conflicts = []
        for source, variables in MIGRATION_VARIABLES.items():
            present = sorted(key for key in variables if values.get(key, "").strip())
            if not present:
                continue
            target_id = "zhiqiu_reports" if source == "zhiqiu" else source
            conflict = self.source_status(source)["configured"]
            targets.append({"source_id": target_id, "variables": present, "conflict": conflict})
            if conflict:
                conflicts.append(target_id)
        return {"available": bool(targets), "conflicts": conflicts, "targets": targets}

    @staticmethod
    def _parse_accounts(raw: str, *, fallback_id: str = "legacy") -> list[dict[str, str]]:
        try:
            value = json.loads(raw)
        except ValueError:
            value = None
        if isinstance(value, dict):
            value = value.get("accounts", value)
            if isinstance(value, dict):
                value = [
                    {"id": str(index), "username": username, "password": password}
                    for index, (username, password) in enumerate(value.items(), 1)
                ]
        if isinstance(value, list):
            accounts = []
            for index, item in enumerate(value, 1):
                if not isinstance(item, dict):
                    raise CredentialStoreError("migration_source_invalid")
                username = item.get("username") or item.get("user") or item.get("account")
                password = item.get("password") or item.get("token")
                if not isinstance(username, str) or not isinstance(password, str):
                    raise CredentialStoreError("migration_source_invalid")
                accounts.append(
                    {
                        "id": str(item.get("id") or f"legacy-{index}"),
                        "username": username,
                        "password": password,
                    }
                )
            return accounts
        accounts = []
        for index, item in enumerate(re.split(r"[;,]", raw), 1):
            if not item.strip():
                continue
            username, separator, password = item.partition(":")
            if not separator:
                raise CredentialStoreError("migration_source_invalid")
            accounts.append(
                {
                    "id": fallback_id if index == 1 else f"{fallback_id}-{index}",
                    "username": username,
                    "password": password,
                }
            )
        if not accounts:
            raise CredentialStoreError("migration_source_invalid")
        return accounts

    def _migration_payload(self, source: str, values: dict[str, str]) -> dict[str, Any]:
        if source == "ifind":
            if values.get("IFIND_ACCOUNTS_JSON", "").strip():
                accounts = self._parse_accounts(values["IFIND_ACCOUNTS_JSON"])
            elif values.get("IFIND_USERNAME", "").strip() and values.get("IFIND_PASSWORD", ""):
                accounts = [
                    {
                        "id": "legacy",
                        "username": values["IFIND_USERNAME"],
                        "password": values["IFIND_PASSWORD"],
                    }
                ]
            else:
                raise CredentialStoreError("migration_source_invalid")
            return {"backend": "auto", "http_base_url": None, "accounts": accounts}
        if source == "zhiqiu":
            raw = values.get("ZQ_ACCOUNTS_JSON") or values.get("ZQ_ACCOUNTS") or ""
            return {"accounts": self._parse_accounts(raw)}
        variable = next(iter(MIGRATION_VARIABLES[source]))
        field = SINGLE_SECRET_FIELDS[source][0]
        return {field: values.get(variable, "")}

    def _write_env(self, lines: list[str]) -> None:
        self.env_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with NamedTemporaryFile(
            dir=self.env_path.parent, prefix=".env-migration-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write("".join(lines).encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.env_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _restore_env(self, raw: bytes | None, mode: int) -> None:
        if raw is None:
            self.env_path.unlink(missing_ok=True)
            return
        self.env_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with NamedTemporaryFile(
            dir=self.env_path.parent, prefix=".env-rollback-", delete=False
        ) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, mode)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.env_path)
        finally:
            temporary.unlink(missing_ok=True)

    @_serialized
    def apply_migration(self, source_ids: list[str]) -> dict:
        lines, values = self._env_values()
        original_env = self.env_path.read_bytes() if self.env_path.exists() else None
        original_env_mode = (
            self.env_path.stat().st_mode & 0o777 if self.env_path.exists() else 0o600
        )
        requested = []
        for source_id in source_ids:
            source = canonical_source_id(source_id)
            if source not in MIGRATION_VARIABLES or source in requested:
                raise CredentialStoreError("migration_selection_invalid")
            requested.append(source)
        preview = self.migration_preview()
        available = {canonical_source_id(item["source_id"]): item for item in preview["targets"]}
        if any(source not in available for source in requested):
            raise CredentialStoreError("migration_selection_invalid")
        if any(available[source]["conflict"] for source in requested):
            raise CredentialStoreError("migration_conflict")
        old_files = {
            source: self._path(source).read_bytes() if self._path(source).exists() else None
            for source in requested
        }
        payloads = {source: self._migration_payload(source, values) for source in requested}
        secret_accounts: set[str] = set()
        for source, payload in payloads.items():
            if source in {"ifind", "zhiqiu"}:
                secret_accounts.update(
                    self._account_name(source, item["id"]) for item in payload["accounts"]
                )
            else:
                secret_accounts.add(
                    self._account_name(source, "default", SINGLE_SECRET_FIELDS[source][1])
                )
        old_secrets = {account: self._secret(account) for account in secret_accounts}
        removed_variables = set().union(*(MIGRATION_VARIABLES[source] for source in requested))
        remaining = [
            line
            for line in lines
            if not (
                (match := re.match(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=", line))
                and match.group(1) in removed_variables
            )
        ]
        try:
            for source, payload in payloads.items():
                self.save_source(source, payload)
                if not self.source_status(source)["secret_configured"]:
                    raise CredentialStoreError("credential_readback_failed")
            self._write_env(remaining)
        except (CredentialStoreError, OSError, ValueError) as exc:
            try:
                self._restore_env(original_env, original_env_mode)
                self._restore_secret_values(old_secrets)
                for source, raw in old_files.items():
                    if raw is None:
                        self._delete_profile(source)
                    else:
                        path = self._path(source)
                        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                        path.write_bytes(raw)
            except (CredentialStoreError, OSError) as rollback_error:
                log.error(
                    "datahub_migration_rollback_failed", error_type=type(rollback_error).__name__
                )
            log.error("datahub_migration_apply_failed", error_type=type(exc).__name__)
            raise CredentialStoreError("migration_apply_failed") from exc
        migrated = ["zhiqiu_reports" if source == "zhiqiu" else source for source in requested]
        log.info("datahub_environment_migrated", source_count=len(migrated))
        return {"migrated": migrated, "preview": self.migration_preview()}
