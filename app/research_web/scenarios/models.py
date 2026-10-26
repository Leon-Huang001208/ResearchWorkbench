"""Stable dependency-free errors for the read-only scenario contracts."""


class ScenarioError(ValueError):
    """Public code is stable and never contains private inputs or source contents."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.status = 422 if code != "scenario_catalog_unreadable" else 503
        super().__init__(code)
