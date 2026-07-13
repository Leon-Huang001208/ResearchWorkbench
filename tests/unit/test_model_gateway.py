from types import SimpleNamespace

from core.model_gateway.gateway import ModelGatewayImpl
from core.settings.config import TaskRoute


def test_unconfigured_task_inherits_default_route_model():
    """A task without its own route must not fall back to an SDK placeholder model."""
    gateway = ModelGatewayImpl.__new__(ModelGatewayImpl)
    provider = SimpleNamespace()
    gateway._providers = {"deepseek": provider}
    gateway._task_routes = {
        "default": TaskRoute(provider="deepseek", model="deepseek-v4-flash")
    }
    gateway._default_provider = provider

    resolved_provider, resolved_model = gateway._resolve("reporting", None)

    assert resolved_provider is provider
    assert resolved_model == "deepseek-v4-flash"
