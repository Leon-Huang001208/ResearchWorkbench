"""Static safety checks for the desktop first-run setup wizard."""

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SETUP_WIZARD_JS = ROOT / "app" / "web" / "static" / "js" / "setup-wizard.js"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
CONFIGURATION_JS = ROOT / "app" / "web" / "static" / "js" / "configuration.js"
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"


def test_setup_wizard_reads_safe_readiness_and_renders_api_copy_as_text():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    assert "fetch('/api/setup/readiness'" in source
    assert "runtime_status === 'setup_required'" in source
    assert "textContent" in source
    assert "remediation" in source
    assert "innerHTML" not in source


def test_setup_wizard_can_open_database_configuration_or_skip_without_claiming_ready():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    assert "openDatabaseConfiguration" in source
    assert "setup-wizard-open-database" in source
    assert "setup-wizard-skip" in source
    assert "classList.add('hidden')" in source
    assert "数据库已就绪" not in source


def test_setup_wizard_traps_and_restores_focus_for_modal_accessibility():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    assert "setupWizardRestoreFocus" in source
    assert "document.activeElement" in source
    assert "restoreSetupWizardFocus" in source
    assert "getSetupWizardFocusableControls" in source
    assert "event.key !== 'Tab'" in source
    assert "event.shiftKey" in source
    assert "cycleSetupWizardFocus" in source


def test_focus_cycle_helper_wraps_both_tab_directions():
    module_uri = SETUP_WIZARD_JS.as_uri()
    script = f"""
        import assert from 'node:assert/strict';
        import {{ cycleSetupWizardFocus }} from '{module_uri}';
        const calls = [];
        const first = {{ focus: () => calls.push('first') }};
        const last = {{ focus: () => calls.push('last') }};
        const outside = {{ focus: () => calls.push('outside') }};
        const forward = {{ key: 'Tab', shiftKey: false, preventDefault: () => calls.push('prevent-forward') }};
        const backward = {{ key: 'Tab', shiftKey: true, preventDefault: () => calls.push('prevent-backward') }};
        assert.equal(cycleSetupWizardFocus(forward, [first, last], last), true);
        assert.equal(cycleSetupWizardFocus(backward, [first, last], first), true);
        assert.equal(cycleSetupWizardFocus(forward, [first, last], outside), true);
        assert.deepEqual(calls, ['prevent-forward', 'first', 'prevent-backward', 'last', 'prevent-forward', 'first']);
    """
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_setup_wizard_failure_and_initialization_are_safe_to_repeat():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    assert "setupWizardInitializationPromise" in source
    assert "if (setupWizardInitializationPromise) return setupWizardInitializationPromise;" in source
    assert "readiness request failed" in source


def test_database_configuration_modal_receives_focus_after_wizard_handoff():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    handoff = source[source.index("export async function openDatabaseConfiguration()"):]
    assert "btn-config-edit-modal-close" in handoff
    assert "config-edit-modal" in handoff
    assert "!modal ||" in handoff
    assert "classList.contains('hidden')" in handoff
    assert ".focus()" in handoff


def test_setup_wizard_handoff_keeps_its_focus_boundary_until_modal_is_ready():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    handoff = source[source.index("openDatabase.addEventListener"):source.index("skip.addEventListener")]
    assert "await openDatabaseConfiguration()" in handoff
    assert "hideSetupWizard({ restoreFocus: false })" in handoff
    assert handoff.index("await openDatabaseConfiguration()") < handoff.index("hideSetupWizard({ restoreFocus: false })")
    assert "openDatabase.disabled = true" in handoff


def test_skip_only_hides_wizard_without_releasing_setup_required_gate():
    source = SETUP_WIZARD_JS.read_text(encoding="utf-8")

    skip_handler = source[source.index("skip.addEventListener"):source.index("document.addEventListener('keydown'")]
    assert "hideSetupWizard();" in skip_handler
    assert "setupRequiredNavigationGate" not in skip_handler
    assert "setupWizardHandoffPending" in skip_handler


def test_setup_mode_does_not_start_business_data_requests():
    source = APP_JS.read_text(encoding="utf-8")

    assert "initSetupWizard" in source
    assert "if (setupMode)" in source
    assert "navigateTo('system', { systemTab: 'config' })" in source
    setup_return = source.index("if (setupMode) {")
    assert setup_return < source.index("initAssetSearch();")
    assert setup_return < source.index("connectSSE();")


def test_setup_required_navigation_gate_blocks_data_loads_before_they_start():
    source = APP_JS.read_text(encoding="utf-8")

    assert "setupRequiredNavigationGate" in source
    navigation = source[
        source.index("function navigateTo(section, options = {})"):
        source.index("window.navigateTo = navigateTo;")
    ]
    assert "const targetSection = systemTarget(section, options.systemTab);" in navigation
    assert "targetSection !== 'config'" in navigation
    assert "数据库尚未就绪" in source
    assert navigation.index("targetSection !== 'config'") < navigation.index("loadDashboard();")
    assert "activateSetupRequiredNavigationGate();" in source


def test_setup_wizard_markup_has_accessible_overlay_controls():
    source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="setup-wizard"' in source
    assert 'role="dialog"' in source
    assert 'aria-modal="true"' in source
    assert 'aria-live="polite"' in source
    assert 'id="setup-wizard-open-database"' in source
    assert 'id="setup-wizard-skip"' in source


def test_setup_wizard_module_parses_with_node():
    result = subprocess.run(
        ["node", "--check", str(SETUP_WIZARD_JS)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
