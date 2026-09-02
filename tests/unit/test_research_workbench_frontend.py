from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_research_workbench_keeps_its_stable_navigation_and_dom_surface():
    index = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    script = (ROOT / "app/web/static/js/research-workbench.js").read_text(encoding="utf-8")

    assert 'data-section="research"' in index
    assert 'id="section-research"' in index
    assert 'id="research-run-form"' in index
    assert 'id="research-run-status"' in index
    assert 'id="research-run-outputs"' in index
    assert ">研究中心</span>" in index
    assert 'id="research-subject-type"' in index
    assert 'id="research-subject-id"' in index
    assert 'id="research-template-list"' in index
    assert 'id="research-run-history"' in index
    assert 'id="asset-start-research"' in index
    assert "research-evidence-json" not in index
    assert '<h2 class="section-title" id="research-workbench-title">A股深度研究</h2>' not in index
    assert "export function initResearchWorkbench" in script
    assert "export function openResearchCenter" in script
    assert "/api/research-templates" in script
    assert "/api/research-runs" in script
    assert "subject_type" in script
    assert "template.available" in script
    assert "result.status === 'completed'" in script
    assert "/downloads/${encodeURIComponent(artifactType)}" in script
    assert "currentSession = null;\n        persistResearchContext();" in script
    assert "if (!currentWorkspace?.workspace_id)" in script
    assert "if (saved.session?.session_id) currentSession = saved.session;" not in script


def test_asset_research_entry_uses_shared_prefill_contract():
    app_script = (ROOT / "app/web/static/js/app.js").read_text(encoding="utf-8")
    asset_script = (ROOT / "app/web/static/js/asset.js").read_text(encoding="utf-8")

    assert "openResearchCenter" in app_script
    assert "buildResearchPrefill" in asset_script
    assert "alphafoundry:open-research-center" in asset_script
    assert "subject_type" in asset_script
