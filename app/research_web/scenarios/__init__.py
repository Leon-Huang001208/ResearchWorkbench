"""Pure static parity references and first-eight research scenario contracts."""

from .catalog import get_scenario, read_catalog, read_scenarios, select_scenario
from .models import ScenarioError

__all__ = [
    "ScenarioError",
    "get_scenario",
    "read_catalog",
    "read_scenarios",
    "select_scenario",
]
