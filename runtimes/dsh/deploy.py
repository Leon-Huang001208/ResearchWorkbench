"""Generate DSH deployment artifacts from AlphaFoundry's canonical contracts.

The command never installs DSH or starts a host. Users install the bundle into
their own DSH profile, then point the bundle at this generated directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.observability import get_logger
from services.market_commentary_workflow import (
    daily_market_commentary_skills,
    daily_market_commentary_tools,
)

logger = get_logger(__name__)


def render_skill_markdown(*, capability_id: str, description: str, input_schema: dict) -> str:
    """Render the small DSH-facing instruction wrapper; contracts stay in the manifest."""
    payload = json.dumps(input_schema, ensure_ascii=False, indent=2)
    return (
        f"---\nname: {capability_id}\ndescription: {description}\n---\n\n"
        "# AlphaFoundry Skill\n\n"
        "Read the task payload, use only the approved AlphaFoundry tools when needed, "
        "and finish by calling `alphafoundry_submit_skill_result`. Do not place the "
        "final structured result in ordinary chat text.\n\n"
        "## Input contract\n\n```json\n"
        f"{payload}\n```\n"
    )


def deploy(*, deployment_path: Path, dsh_home: Path) -> dict[str, object]:
    """Write manifest and DSH-discoverable skill files from canonical contracts."""
    deployment_path = deployment_path.expanduser().resolve()
    dsh_home = dsh_home.expanduser().resolve()
    deployment_path.mkdir(parents=True, exist_ok=True)
    skills_root = dsh_home / "skills"
    skills_root.mkdir(parents=True, exist_ok=True)
    tools = daily_market_commentary_tools()
    skills = daily_market_commentary_skills()
    manifest = {
        "schema_version": "alphafoundry-dsh-deployment/v1",
        "tools": [item.model_dump(mode="json") for item in tools],
        "skills": [item.model_dump(mode="json") for item in skills],
    }
    manifest_path = deployment_path / "alphafoundry-manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for skill in skills:
        skill_path = skills_root / skill.capability_id
        skill_path.mkdir(exist_ok=True)
        (skill_path / "SKILL.md").write_text(
            render_skill_markdown(
                capability_id=skill.capability_id,
                description=skill.description,
                input_schema=skill.input_schema,
            ),
            encoding="utf-8",
        )
    logger.info(
        "DSH deployment artifacts generated",
        deployment_path=str(deployment_path),
        skills_root=str(skills_root),
        tool_count=len(tools),
        skill_count=len(skills),
    )
    return {
        "manifest_path": str(manifest_path),
        "skills_root": str(skills_root),
        "tool_ids": [item.capability_id for item in tools],
        "skill_ids": [item.capability_id for item in skills],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AlphaFoundry DSH deployment artifacts")
    parser.add_argument("--deployment-path", required=True, type=Path)
    parser.add_argument("--dsh-home", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            deploy(deployment_path=args.deployment_path, dsh_home=args.dsh_home), ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
