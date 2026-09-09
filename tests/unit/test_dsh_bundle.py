from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path("runtimes/dsh/plugin")


def test_dsh_plugin_is_a_profile_bundle_with_one_bridge_mount():
    package = json.loads((PLUGIN_ROOT / "package.json").read_text())
    patch = (PLUGIN_ROOT / "cordis.patch.yml").read_text()

    assert package["dsh"]["bundle"]["patch"] == "./cordis.patch.yml"
    assert package["main"] == "./lib/index.mjs"
    assert package["scripts"]["build"].startswith("tsdown index.ts")
    assert "@deepseek-ai/dsh-tools" in package["peerDependencies"]
    assert "@deepseek-ai/dsh-skill-filesystem" in package["peerDependencies"]
    assert "id: alphafoundry-runtime-bridge" in patch
    assert "customSkillDirs:" in patch
    assert "name: '@alphafoundry/dsh-runtime-plugin'" in patch


def test_dsh_bridge_exposes_only_loopback_authenticated_runtime_boundaries():
    source = (PLUGIN_ROOT / "index.ts").read_text()

    assert "const BRIDGE_PREFIX = '/alphafoundry/bridge/v1'" in source
    assert "if (!isLoopback(req) || !hasBearer(req, config.bridgeToken))" in source
    assert "alphafoundry_submit_skill_result" in source
    assert "ctx.agents.resume" in source
    assert "sendSse(res, events)" in source
    assert "accepted: { type: 'boolean', required: true }" in source
    assert "DSH supports Skill execution only" not in source


def test_project_bootstrap_uses_an_isolated_web_profile_and_pinned_dsh_checkout():
    bootstrap = Path("scripts/dsh/bootstrap_harness.mjs").read_text()

    assert "dsh-v0.1.1-rc.2" in bootstrap
    assert "@deepseek-ai/dsh-web-app" in bootstrap
    assert "runtimeHome" in bootstrap
