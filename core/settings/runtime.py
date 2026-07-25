"""Single runtime source for platform-aware configuration decisions."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Mapping

from dotenv import load_dotenv

from core.settings.paths import app_data_dir

RuntimeMode = Literal["desktop", "web-dev", "web-prod"]

DEFAULT_WEB_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_DESKTOP_BACKEND_URL = "http://127.0.0.1:8765"


class RuntimeConfigurationError(ValueError):
    """Raised when runtime bootstrap configuration is invalid."""


@dataclass(frozen=True)
class RuntimeContext:
    """Resolved runtime configuration before application services are imported."""

    mode: RuntimeMode
    project_root: Path
    data_dir: Path | None
    env_path: Path | None
    backend_url: str
    can_write_config: bool
    environment_override_keys: frozenset[str] = frozenset()


def resolve_runtime_context(
    *,
    environ: Mapping[str, str] | None = None,
    project_root: Path | None = None,
) -> RuntimeContext:
    """Resolve config location and service URL without mutating process state."""
    values = os.environ if environ is None else environ
    root = Path(
        values.get("ALPHAFOUNDRY_PROJECT_ROOT", project_root or Path(__file__).parents[2])
    ).expanduser()
    mode = _resolve_mode(values)
    explicit_config = values.get("ALPHAFOUNDRY_CONFIG_FILE")
    desktop_data_dir = values.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR")
    data_dir = (
        Path(desktop_data_dir).expanduser()
        if mode == "desktop" and desktop_data_dir
        else app_data_dir()
        if mode == "desktop"
        else None
    )
    env_path = _resolve_env_path(mode, root, data_dir, explicit_config)
    backend_url = values.get(
        "ALPHAFOUNDRY_BACKEND_URL",
        DEFAULT_DESKTOP_BACKEND_URL if mode == "desktop" else DEFAULT_WEB_BACKEND_URL,
    ).rstrip("/")

    if not backend_url.startswith(("http://", "https://")):
        raise RuntimeConfigurationError("ALPHAFOUNDRY_BACKEND_URL 必须使用 http 或 https 协议")

    return RuntimeContext(
        mode=mode,
        project_root=root,
        data_dir=data_dir,
        env_path=env_path,
        backend_url=backend_url,
        can_write_config=mode != "web-prod",
        environment_override_keys=frozenset(values),
    )


def initialize_runtime_environment() -> RuntimeContext:
    """Load the selected config file once before settings and repositories initialize."""
    context = resolve_runtime_context()
    environment_override_keys = frozenset(os.environ)
    if context.data_dir is not None:
        os.environ.setdefault("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(context.data_dir))
    if context.env_path is not None and context.env_path.exists():
        load_dotenv(context.env_path, override=False)
    return replace(resolve_runtime_context(), environment_override_keys=environment_override_keys)


def _resolve_mode(values: Mapping[str, str]) -> RuntimeMode:
    raw_mode = values.get("ALPHAFOUNDRY_RUN_MODE")
    if raw_mode is None:
        raw_mode = "desktop" if values.get("ALPHAFOUNDRY_DESKTOP") else "web-dev"
    if raw_mode not in {"desktop", "web-dev", "web-prod"}:
        raise RuntimeConfigurationError("ALPHAFOUNDRY_RUN_MODE 必须是 desktop、web-dev 或 web-prod")
    return raw_mode  # type: ignore[return-value]


def _resolve_env_path(
    mode: RuntimeMode,
    project_root: Path,
    data_dir: Path | None,
    explicit_config: str | None,
) -> Path | None:
    if explicit_config:
        return Path(explicit_config).expanduser()
    if mode == "desktop":
        assert data_dir is not None
        return data_dir / ".env"
    if mode == "web-dev":
        return project_root / ".env"
    return None
