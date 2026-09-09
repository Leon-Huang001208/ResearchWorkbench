from __future__ import annotations

import json

from runtimes.dsh.deploy import deploy


def test_dsh_deploy_generates_manifest_and_discoverable_skill_files(tmp_path):
    result = deploy(
        deployment_path=tmp_path / "profile" / "alphafoundry",
        dsh_home=tmp_path / "dsh-home",
    )

    manifest = json.loads(
        (tmp_path / "profile" / "alphafoundry" / "alphafoundry-manifest.json").read_text()
    )
    skill_file = tmp_path / "dsh-home" / "skills" / "market-close-review" / "SKILL.md"

    assert manifest["schema_version"] == "alphafoundry-dsh-deployment/v1"
    assert result["skill_ids"] == [
        "market-close-review",
        "market-attribution",
        "counter-evidence-review",
        "report-narrative",
    ]
    assert "name: market-close-review" in skill_file.read_text()
    assert "alphafoundry_submit_skill_result" in skill_file.read_text()
