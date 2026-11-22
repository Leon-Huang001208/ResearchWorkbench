"""Read-only, credential-free Research Bot configuration diagnostics."""

_CONFIGURATION_STATES = frozenset(
    {"available", "disabled_service_only", "disabled_tenant", "disabled_automation"}
)


def configuration_status(*, service_only: bool, tenant_mode: bool, automation_enabled: bool) -> str:
    if service_only:
        return "disabled_service_only"
    if tenant_mode:
        return "disabled_tenant"
    return "available" if automation_enabled else "disabled_automation"


def diagnostic(status: object = None) -> dict[str, str]:
    configuration = (
        status if isinstance(status, str) and status in _CONFIGURATION_STATES else "unknown"
    )
    return {"configuration": configuration, "runtime_verification": "NOT_RUN"}
