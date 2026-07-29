"""Static safety checks for the configuration workbench."""

import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

CONFIGURATION_JS = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "js" / "configuration.js"
)
CONFIGURATION_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "templates" / "index.html"
)
CONFIGURATION_CSS = (
    Path(__file__).resolve().parents[2] / "app" / "web" / "static" / "configuration.css"
)
APP_WEB_DOC = Path(__file__).resolve().parents[2] / "docs" / "modules" / "app_web.md"
CONFIGURATION_LOCK_SPEC = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-07-26-contextual-configuration-locks-design.md"
)


class _MarkupElement:
    def __init__(self, tag: str, attrs: list[tuple[str, str]], parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.content: list[str] = []

    @property
    def markup(self) -> str:
        return "".join(self.content)

    def is_descendant_of(self, ancestor) -> bool:
        current = self.parent
        while current:
            if current is ancestor:
                return True
            current = current.parent
        return False


class _ConfigurationMarkupParser(HTMLParser):
    """Keep parsed attributes plus serializable descendant markup for test queries."""

    _VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements: list[_MarkupElement] = []
        self.elements_by_id: dict[str, _MarkupElement] = {}
        self._open_elements: list[_MarkupElement] = []

    def _append_to_open_elements(self, content: str) -> None:
        for element in self._open_elements:
            element.content.append(content)

    def handle_starttag(self, tag, attrs):
        self._append_to_open_elements(self.get_starttag_text())
        element = _MarkupElement(tag, attrs, self._open_elements[-1] if self._open_elements else None)
        self.elements.append(element)
        element_id = element.attrs.get("id")
        if element_id:
            self.elements_by_id[element_id] = element
        if tag not in self._VOID_ELEMENTS:
            self._open_elements.append(element)

    def handle_startendtag(self, tag, attrs):
        self._append_to_open_elements(self.get_starttag_text())
        element = _MarkupElement(tag, attrs, self._open_elements[-1] if self._open_elements else None)
        self.elements.append(element)
        element_id = element.attrs.get("id")
        if element_id:
            self.elements_by_id[element_id] = element

    def handle_endtag(self, tag):
        self._append_to_open_elements(f"</{tag}>")
        if self._open_elements and self._open_elements[-1].tag == tag:
            self._open_elements.pop()

    def handle_data(self, data):
        self._append_to_open_elements(data)


def _balanced_javascript_end(source: str, opening: int, opener: str, closer: str, context: str) -> int:
    """Locate a balanced JavaScript delimiter while ignoring strings and comments."""
    depth = 0
    index = opening
    quote = None
    line_comment = False
    block_comment = False
    while index < len(source):
        character = source[index]
        next_character = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if character == "\n":
                line_comment = False
        elif block_comment:
            if character == "*" and next_character == "/":
                block_comment = False
                index += 1
        elif quote:
            if character == "\\":
                index += 1
            elif character == quote:
                quote = None
        elif character == "/" and next_character == "/":
            line_comment = True
            index += 1
        elif character == "/" and next_character == "*":
            block_comment = True
            index += 1
        elif character in {"'", '"', "`"}:
            quote = character
        elif character == opener:
            depth += 1
        elif character == closer:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise AssertionError(f"configuration.js has an unclosed {context}")


def _balanced_javascript_region(source: str, opening: int, opener: str, closer: str, context: str) -> str:
    """Extract a balanced JavaScript region while ignoring strings and comments."""
    closing = _balanced_javascript_end(source, opening, opener, closer, context)
    return source[opening + 1:closing]


def _configuration_function(source: str, name: str) -> str:
    """Return one balanced named function, with an actionable failure if it is absent."""
    declaration = re.compile(
        rf"^(?:export\s+)?(?:async\s+)?function\s+{re.escape(name)}\s*\(",
        re.MULTILINE,
    )
    match = declaration.search(source)
    if not match:
        raise AssertionError(f"configuration.js must declare {name}()")
    parameters_opening = match.end() - 1
    parameters_closing = _balanced_javascript_end(
        source, parameters_opening, "(", ")", f"{name}() parameter list"
    )
    opening = source.find("{", parameters_closing + 1)
    if opening < 0:
        raise AssertionError(f"configuration.js must open the {name}() function body")
    return source[match.start():opening + 1] + _balanced_javascript_region(
        source, opening, "{", "}", f"{name}() function body"
    ) + "}"


def _configuration_modal_markup(template: str) -> tuple[_ConfigurationMarkupParser, _MarkupElement]:
    """Return the parsed config modal and all queryable descendants, independent of HTML layout."""
    parser = _ConfigurationMarkupParser()
    parser.feed(template)
    parser.close()
    modal = parser.elements_by_id.get("config-edit-modal")
    if not modal:
        raise AssertionError('index.html must declare the config-edit-modal container')
    return parser, modal


def test_configuration_workbench_never_refills_saved_secrets():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "api_key?.value" not in source
    assert "password?.value" not in source
    assert "account.key?.value" not in source
    assert "database_url?.value" not in source
    assert "environment_locked_fields" in source
    assert "applyEnvironmentLocks" in source
    assert "setSecretState" in source


def test_configuration_modal_event_binder_remains_declared():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "bindModalFormEvents(form, section);" in source
    assert "function bindModalFormEvents(form, section)" in source


def test_database_summary_uses_runtime_readiness_not_saved_url_state():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "databaseRuntimeReadiness" in source
    assert "/api/setup/readiness" in source
    assert "数据库已验证" in source
    assert "数据库待重启" in source
    assert "数据库未就绪" in source
    assert "已配置连接地址" not in source


def test_configuration_locks_are_contextual_not_global():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "data-config-environment-lock-notice" not in template
    assert "renderEnvironmentLockedFields" not in source
    assert "LOCKED_FIELD_MESSAGE" in source
    assert "data-config-lock-message" in source
    assert "aria-describedby" in source
    assert "由当前启动配置管理" in source


def test_configuration_locks_dynamic_configuration_in_context():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    app_web_doc = APP_WEB_DOC.read_text(encoding="utf-8")
    lock_spec = CONFIGURATION_LOCK_SPEC.read_text(encoding="utf-8")

    assert "applyProviderRowLocks" in source
    assert "applyTaskRouteLocks" in source
    assert "setDynamicRowLocked" in source
    assert "setModalLockNote(true)" in source
    assert "LLM_PROVIDER_${index}_" in source
    assert "TASK_${task.toUpperCase()}_PROVIDER" in source
    assert "该组由当前启动配置管理" in source
    assert "原子集合锁定" in app_web_doc
    assert "原子集合锁定" in lock_spec


def test_configuration_collection_lock_message_has_an_accessible_id():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "config-collection-lock-message-${++dynamicLockMessageSequence}" in source


def test_configuration_payload_filter_omits_static_environment_locks():
    script = f"""
import {{ filterEnvironmentLockedPayload }} from {CONFIGURATION_JS.as_uri()!r};

const accounts = [{{ name: 'primary' }}];
const webSearchPayload = {{
    accounts,
    provider: 'tavily',
    rotation_strategy: 'round_robin',
    quota_limit: 1000,
    max_results: 5,
    timeout: 15,
}};
const lockedFields = [
    'LOG_LEVEL', 'LOG_DIR', 'LLM_EXTRACT_MAX_WORKERS', 'LLM_EXTRACT_MAX_RETRIES',
    'LLM_EXTRACT_CHUNK_SIZE', 'LLM_EXTRACT_CHUNK_OVERLAP', 'LLM_EXTRACT_LONG_TEXT_THRESHOLD',
    'DATABASE_URL', 'WEB_SEARCH_PROVIDER', 'WEB_SEARCH_KEY_ROTATION',
    'WEB_SEARCH_KEY_QUOTA_LIMIT', 'WEB_SEARCH_MAX_RESULTS', 'WEB_SEARCH_TIMEOUT',
];
const advancedPayload = {{
    log_level: 'INFO', log_dir: '/tmp/logs', llm_max_workers: 4, llm_max_retries: 2,
    chunk_size: 1000, chunk_overlap: 100, long_text_threshold: 5000,
}};
const databasePayload = {{ database_url: 'postgres://secret' }};

const filtered = {{
    advanced: filterEnvironmentLockedPayload('advanced', advancedPayload, lockedFields),
    database: filterEnvironmentLockedPayload('database', databasePayload, lockedFields),
    web_search: filterEnvironmentLockedPayload('web_search', webSearchPayload, lockedFields),
}};

if (JSON.stringify(filtered) !== JSON.stringify({{
    advanced: {{}},
    database: {{}},
    web_search: {{ accounts }},
}})) {{
    throw new Error(`unexpected filtered payload: ${{JSON.stringify(filtered)}}`);
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_payload_filter_omits_locked_dynamic_collections_only():
    script = f"""
import {{ filterEnvironmentLockedPayload }} from {CONFIGURATION_JS.as_uri()!r};

const providers = [{{ name: 'environment-provider' }}];
const taskRoutes = [{{ task: 'chat', provider: 'environment-provider', model: 'gpt-test' }}];
const accounts = [{{ name: 'environment-account' }}];

const filtered = {{
    providerLocked: filterEnvironmentLockedPayload(
        'llm', {{ providers, task_routes: taskRoutes }}, ['LLM_PROVIDER_1_API_KEY'],
    ),
    routeLocked: filterEnvironmentLockedPayload(
        'llm', {{ providers, task_routes: taskRoutes }}, ['TASK_CHAT_PROVIDER'],
    ),
    zhiqiu: filterEnvironmentLockedPayload(
        'zhiqiu', {{ accounts, rotation_strategy: 'round_robin' }}, ['ZQ_ACCOUNTS_JSON'],
    ),
    ifind: filterEnvironmentLockedPayload(
        'ifind', {{ accounts, backend: 'http_api', http_base_url: 'https://example.test' }}, ['IFIND_PASSWORD'],
    ),
    webSearch: filterEnvironmentLockedPayload(
        'web_search', {{ accounts, provider: 'tavily', timeout: 15 }}, ['TAVILY_API_KEY'],
    ),
}};

const expected = {{
    providerLocked: {{ providers, task_routes: taskRoutes }},
    routeLocked: {{ providers, task_routes: taskRoutes }},
    zhiqiu: {{ rotation_strategy: 'round_robin' }},
    ifind: {{ backend: 'http_api', http_base_url: 'https://example.test' }},
    webSearch: {{ provider: 'tavily', timeout: 15 }},
}};

if (JSON.stringify(filtered) !== JSON.stringify(expected)) {{
    throw new Error(`unexpected filtered payload: ${{JSON.stringify(filtered)}}`);
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_module_parses_with_node():
    result = subprocess.run(
        ["node", "--check", str(CONFIGURATION_JS)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_workbench_keeps_progress_and_hides_diagnostics_by_default():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    health_source = _configuration_function(source, "renderConfigurationHealth")
    parser = _ConfigurationMarkupParser()
    parser.feed(template)
    parser.close()
    environment_disclosure = next(
        (
            element
            for element in parser.elements
            if "config-environment-disclosure" in element.attrs.get("class", "").split()
        ),
        None,
    )

    assert 'data-config-progress-completed' in template
    assert 'data-config-progress-total' in template
    assert 'id="config-refresh"' not in template
    assert 'data-config-connection-summary' not in template
    assert 'data-config-status-filter' not in template
    assert 'data-config-environment-diagnostics' in template
    assert environment_disclosure, 'index.html must contain a .config-environment-disclosure'
    assert 'data-config-environment-diagnostics' in environment_disclosure.markup
    assert '<summary>运行环境</summary>' in environment_disclosure.markup
    assert 'data-config-onboarding' not in template
    assert 'data-config-onboarding' not in health_source
    assert 'function renderEnvironmentDiagnostics(snapshot)' in source
    assert 'snapshot.environment' in source
    assert 'snapshot.catalog' in source


def test_configuration_workbench_removes_unused_refresh_and_filter_behaviour():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindConfigurationEvents")

    assert 'function refreshConfiguration()' not in source
    assert 'function renderConfigurationCardVisibility()' not in source
    assert 'config-refresh' not in events_source
    assert 'data-config-status-filter' not in events_source


def test_configuration_workbench_keeps_card_opening_events_without_filters():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindConfigurationEvents")

    assert 'data-config-onboarding' not in events_source
    assert 'data-config-card' in events_source
    assert 'openConfigModal(section)' in events_source
    assert 'config-refresh' not in events_source
    assert 'data-config-status-filter' not in events_source


def test_configuration_refinement_modal_test_help_tracks_testable_sections_without_saving():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    template_markup, modal = _configuration_modal_markup(template)
    open_modal_source = _configuration_function(source, "openConfigModal")
    test_help = next(
        (
            element
            for element in template_markup.elements
            if "data-config-test-help" in element.attrs and element.is_descendant_of(modal)
        ),
        None,
    )

    assert test_help, 'config edit modal must include a data-config-test-help element'
    assert '测试连接不会保存当前更改' in test_help.markup
    assert 'const testable = Boolean(meta.testable);' in open_modal_source
    assert re.search(r'testBtn\.hidden\s*=\s*!testable\s*;', open_modal_source)
    assert re.search(
        r'const\s+testHelp\s*=\s*modal\?\.querySelector\(\s*[\'\"]\[data-config-test-help\][\'\"]\s*\)\s*;',
        open_modal_source,
    ), 'openConfigModal must look up its test help inside the current modal'
    assert re.search(r'if\s*\(testHelp\)\s*testHelp\.hidden\s*=\s*!testable\s*;', open_modal_source)
    assert "document.querySelector('[data-config-test-help]')" not in open_modal_source


def test_configuration_refinement_modal_save_action_and_collection_layout_hooks():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    template_markup, modal = _configuration_modal_markup(template)
    save_button = template_markup.elements_by_id.get("btn-config-edit-modal-save")

    assert save_button and save_button.is_descendant_of(modal), (
        'config edit modal must include #btn-config-edit-modal-save'
    )
    assert '保存更改' in save_button.markup, (
        'config edit modal must present its primary save action as “保存更改”'
    )
    assert 'config-empty-collection' in source
    assert 'config-field-grid config-field-grid--compact' in source


def test_configuration_modal_hierarchy_uses_compact_collections_and_safe_database_state():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")
    modal_source = _configuration_function(source, "renderModalForm")
    database_state_source = _configuration_function(source, "databaseSecretPresentation")

    assert 'config-collection-table' in modal_source
    assert 'config-collection-table config-provider-table' in modal_source
    assert 'config-collection-table config-zhiqiu-table' in modal_source
    assert 'config-collection-table config-ifind-table' in modal_source
    assert 'placeholder="输入新的连接地址"' in modal_source
    assert '当前连接' in modal_source
    assert 'masked_value' in database_state_source
    assert "form.elements.database_url.value = '';" in modal_source
    assert re.search(
        r'\.config-edit-modal-body\s+\.config-collection-table\s*\{[^}]*border:',
        stylesheet,
        re.DOTALL,
    )
    assert re.search(
        r'\.config-edit-modal-body\s+\.config-collection-table\s+\.config-dynamic-row\s*\{[^}]*box-shadow:\s*none',
        stylesheet,
        re.DOTALL,
    )


def test_configuration_editor_visual_contract_has_tabs_editing_state_and_mobile_rows():
    """Editable modal keeps navigation, changes, labels, and mobile rows explicit."""
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")

    assert 'class="config-tab-list"' in source
    for selector in (
        ".config-tab-list",
        '.config-tab-list [role="tab"][aria-selected="true"]',
        ".config-edit-modal-body .config-dynamic-row:focus-within",
        "@media (max-width: 720px)",
    ):
        assert selector in stylesheet
    assert ".config-edit-modal .config-edit-modal-body .config-dynamic-field > span:first-child" not in stylesheet
    assert re.search(
        r"\.config-edit-modal-body\s+\.config-collection-table\s+\.config-dynamic-field\s*>\s*span:first-child\s*\{\s*display:\s*none\s*;",
        stylesheet,
    )
    mobile_rules = stylesheet[stylesheet.rfind("@media (max-width: 720px)"):]
    assert re.search(
        r"\.config-edit-modal\s+\.config-edit-modal-body\s+\.config-collection-table\s+\.config-dynamic-field\s*>\s*span:first-child\s*\{\s*display:\s*flex\s*;",
        mobile_rules,
    )


def test_configuration_empty_collection_lifecycle_restores_all_account_collections():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    remove_source = _configuration_function(source, "removeButton")
    restore_source = _configuration_function(source, "restoreEmptyCollectionState")
    empty_state_source = _configuration_function(source, "createEmptyCollectionState")

    assert "const form = row?.closest('[data-config-form]');" in remove_source
    assert 'const section = form?.dataset.configForm;' in remove_source
    assert 'restoreEmptyCollectionState(form, section);' in remove_source
    assert "form.querySelector('.config-empty-collection')" in restore_source
    assert "state.setAttribute('role', 'status');" in empty_state_source
    for section, list_id, row_class in (
        ('zhiqiu', 'config-zhiqiu-account-list', 'config-zhiqiu-row'),
        ('ifind', 'config-ifind-account-list', 'config-ifind-row'),
        ('web_search', 'config-web_search-key-list', 'config-web_search-row'),
    ):
        assert section in restore_source
        assert list_id in restore_source
        assert row_class in restore_source


def test_configuration_collection_table_responsive_contract():
    stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")
    tablet_rules = re.search(
        r"@media\s*\(max-width:\s*1040px\)\s*\{(?P<rules>.*?)\n\}",
        stylesheet,
        re.DOTALL,
    )

    assert tablet_rules, "collection tables need a tablet breakpoint"
    rules = tablet_rules.group("rules")
    assert re.search(r"\.config-row-labels\s*\{\s*display:\s*none\s*;", rules)
    assert re.search(
        r"\.config-zhiqiu-row.*?\.config-web_search-row\s*\{\s*grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)",
        rules,
        re.DOTALL,
    )
    breakpoint = stylesheet.rfind("@media (max-width: 720px)")

    assert breakpoint >= 0, "collection tables need a 720px mobile breakpoint"
    rules = stylesheet[breakpoint:]
    assert re.search(r"\.config-row-labels\s*\{\s*display:\s*none\s*;", rules)
    assert re.search(
        r"\.config-collection-table\s+\.config-dynamic-row\s*\{\s*grid-template-columns:\s*1fr\s*;",
        rules,
        re.DOTALL,
    )
    assert re.search(
        r"\.config-collection-table\s+\.config-dynamic-field\s*>\s*span:first-child.*?display:\s*(?:flex|block)\s*;",
        rules,
        re.DOTALL,
    )


def test_configuration_empty_collection_state_is_rendered_inside_its_list():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    render_source = _configuration_function(source, "renderEmptyCollectionState")

    assert "const collection =" in render_source
    assert "listId" in render_source
    assert "form.querySelector(`#${collection.listId}`)" in render_source
    assert "list.append(state);" in render_source
    assert "addButton.after(state);" not in render_source


def test_configuration_refresh_syncs_collection_empty_states_for_open_modals():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    render_section_source = _configuration_function(source, "renderSection")
    sync_source = _configuration_function(source, "syncEmptyCollectionState")

    assert "document.getElementById(`config-${section}-form`)" in sync_source
    assert 'removeEmptyCollectionState(form);' in sync_source
    assert 'renderEmptyCollectionState(form, section, accounts);' in sync_source
    for section in ('zhiqiu', 'ifind', 'web_search'):
        assert f"syncEmptyCollectionState('{section}', values.accounts || []);" in render_section_source


def test_configuration_health_uses_runtime_database_readiness_and_compact_grids_are_grids():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    stylesheet = CONFIGURATION_CSS.read_text(encoding="utf-8")
    health_source = _configuration_function(source, "getConfigurationHealth")

    assert "section === 'database'" in health_source
    assert "databaseReadinessPresentation().state === 'ready'" in health_source
    assert re.search(
        r'\.config-field-grid--compact\s*\{[^}]*display:\s*grid\s*;',
        stylesheet,
        re.DOTALL,
    )


def test_database_runtime_refresh_updates_health_after_card_render_when_snapshot_exists():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    refresh_source = _configuration_function(source, "refreshDatabaseRuntimeReadiness")

    assert re.search(
        r'if\s*\(configurationSnapshot\)\s*\{\s*renderConfigurationHealth\(configurationSnapshot\);\s*\}',
        refresh_source,
    )
    assert refresh_source.index('renderDatabaseRuntimeReadiness();') < refresh_source.index('renderSummaryCards();')
    assert refresh_source.index('renderSummaryCards();') < refresh_source.index('renderConfigurationHealth(configurationSnapshot);')


def test_configuration_refinement_modal_locks_keep_accessible_descriptions():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    environment_lock_source = _configuration_function(source, "setEnvironmentLockState")
    apply_locks_source = _configuration_function(source, "applyEnvironmentLocks")

    assert 'aria-describedby' in environment_lock_source
    assert 'setEnvironmentLockState(control' in apply_locks_source
    assert 'setModalLockNote(hasStaticLock)' in apply_locks_source


def test_capability_presentation_covers_all_supported_statuses():
    script = f"""
import {{ getCapabilityPresentation, getEnvironmentDisplayValue }} from {CONFIGURATION_JS.as_uri()!r};

const presentations = {{
    available: getCapabilityPresentation({{ status: 'available' }}),
    notDetected: getCapabilityPresentation({{ status: 'not_detected' }}),
    notApplicable: getCapabilityPresentation({{ status: 'not_applicable' }}),
    unknown: getCapabilityPresentation({{ status: 'unknown' }}),
}};

const expected = {{
    available: ['ready', '可用'],
    notDetected: ['missing', '未检测到'],
    notApplicable: ['missing', '不适用'],
    unknown: ['error', '未知'],
}};

for (const [key, [state, label]] of Object.entries(expected)) {{
    const presentation = presentations[key];
    if (presentation.state !== state || presentation.label !== label) {{
        throw new Error(`unexpected ${{key}} presentation: ${{JSON.stringify(presentation)}}`);
    }}
    if (!presentation.detail || !presentation.remediation) {{
        throw new Error(`missing Chinese fallback text for ${{key}}`);
    }}
}}

const malformedCapabilities = [
    {{ status: '__proto__', detail: '不应采用', remediation: ['不应采用'] }},
    {{ status: 'constructor', detail: '不应采用', remediation: ['不应采用'] }},
    {{ status: 'toString', detail: '不应采用', remediation: ['不应采用'] }},
    {{ status: {{ value: 'available' }}, detail: '不应采用', remediation: ['不应采用'] }},
    null,
    'malformed capability',
];
const unknownPresentation = {{
    state: 'error',
    label: '未知',
    detail: '暂时无法确定此能力的状态。',
    remediation: ['请刷新检测；若仍未知，请查看应用日志。'],
}};

for (const capability of malformedCapabilities) {{
    const presentation = getCapabilityPresentation(capability);
    if (JSON.stringify(presentation) !== JSON.stringify(unknownPresentation)) {{
        throw new Error(`malformed capability escaped unknown fallback: ${{JSON.stringify(presentation)}}`);
    }}
}}

const environmentLabels = {{ desktop: '桌面端', windows: 'Windows' }};
const unexpectedLabelInputs = ['__proto__', 'constructor', 'toString'];
for (const value of unexpectedLabelInputs) {{
    if (getEnvironmentDisplayValue(value, environmentLabels) !== value) {{
        throw new Error(`unsafe environment label mapping: ${{value}}`);
    }}
}}
for (const value of [null, 42, {{ value: 'desktop' }}]) {{
    if (getEnvironmentDisplayValue(value, environmentLabels) !== '未提供') {{
        throw new Error(`non-string environment label was accepted: ${{JSON.stringify(value)}}`);
    }}
}}
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_configuration_secret_editor_never_offers_saved_secret_copy_or_reveal():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    secret_control_source = _configuration_function(source, "createSecretControl")

    assert "data-secret-replace" in secret_control_source
    assert "data-secret-clear" in secret_control_source
    assert "data-secret-copy" not in secret_control_source
    assert "data-secret-toggle" not in secret_control_source
    assert re.search(r"replace\.addEventListener\(\s*['\"]click['\"]", secret_control_source)
    assert re.search(r"clear\.addEventListener\(\s*['\"]click['\"]", secret_control_source)
    assert re.search(r"control\.append\([^)]*\breplace\b[^)]*\bclear\b[^)]*\)", secret_control_source)
    assert "toggleSecretVisibility" not in secret_control_source
    assert "copySecretValue" not in secret_control_source
    assert "navigator.clipboard" not in secret_control_source


def test_configuration_secret_collection_preserves_replacement_value_verbatim():
    """collectSecretPair is private, so retain its exact-value contract statically."""
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    collector_source = _configuration_function(source, "collectSecretPair")

    assert "const value = secretInput.value;" in collector_source
    assert ".trim()" not in collector_source
    assert "value === ''" in collector_source


def test_configuration_remove_action_is_explicit_and_does_not_persist_immediately():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    remove_source = _configuration_function(source, "removeButton")

    assert "移除" in remove_source
    assert "markSectionDirty(form || row);" in remove_source
    assert "configurationApiCall(" not in remove_source
    assert "fetch(" not in remove_source
    assert "saveSection(" not in remove_source
    assert ".remove()" in remove_source


def test_llm_modal_uses_separate_service_and_route_tabs():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    modal_source = _configuration_function(source, "renderModalForm")
    events_source = _configuration_function(source, "bindModalFormEvents")
    selection_source = _configuration_function(source, "selectConfigurationTab")

    for tab in ("providers", "routes"):
        assert re.search(
            rf'<button\b(?=[^>]*\brole=["\']tab["\'])(?=[^>]*\bdata-config-tab=["\']{tab}["\'])[^>]*>',
            modal_source,
        ), f"{tab} must be a tab button"
        assert re.search(
            rf'<[a-z]+\b(?=[^>]*\brole=["\']tabpanel["\'])(?=[^>]*\bdata-config-tab-panel=["\']{tab}["\'])[^>]*>',
            modal_source,
        ), f"{tab} must have a tab panel"
    assert re.search(
        r'<[a-z]+\b(?=[^>]*\bdata-config-tab-panel=["\'](?:providers|routes)["\'])(?=[^>]*\bhidden\b)[^>]*>',
        modal_source,
    ), "one LLM tab panel must be initially hidden"
    assert re.search(
        r'aria-selected.*?data-config-tab-panel.*?\.hidden\s*=',
        selection_source,
        re.DOTALL,
    ), "tab selection must update selection and the matching panel visibility"
    assert "selectConfigurationTab(form, tab.dataset.configTab)" in events_source


def test_llm_modal_tabs_support_roving_keyboard_navigation():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindModalFormEvents")

    assert "addEventListener('keydown'" in events_source
    for key in ("ArrowLeft", "ArrowRight", "Home", "End"):
        assert key in events_source
    assert "tabIndex" in events_source
    assert ".focus()" in events_source


def test_collection_addition_marks_dirty_and_focuses_first_field():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindModalFormEvents")

    for selector, row_factory in (
        ("data-add-provider", "createProviderRow"),
        ("data-add-task-route", "createTaskRouteRow"),
        ("data-add-zhiqiu-account", "createZhiqiuAccountRow"),
        ("data-add-ifind-account", "createIfindAccountRow"),
        ("data-add-web_search-key", "createWebSearchKeyRow"),
    ):
        handler = re.search(
            rf'form\.querySelector\(["\']\[{selector}\]["\']\)\?\.addEventListener\(\s*["\']click["\']\s*,\s*\(\)\s*=>\s*\{{(?P<body>.*?)\n\s*\}}\s*\);',
            events_source,
            re.DOTALL,
        )
        assert handler, f"{selector} must have a click handler"
        body = handler.group("body")
        assert row_factory in body, f"{selector} must create its collection row"
        assert "append(" in body, f"{selector} must append its collection row"
        assert "focusFirstCollectionField" in body, f"{selector} must focus its first field"
        assert "markSectionDirty(form)" in body, f"{selector} must mark the form dirty"
        assert "modalDirty = true;" in body, f"{selector} must mark the modal dirty"


def test_collection_lock_disables_only_environment_owned_collection():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    collection_lock_source = _configuration_function(source, "applyCollectionLock")

    assert re.search(
        r"const\s+lockedFields\s*=\s*configurationSnapshot\?\.environment_locked_fields\s*\|\|\s*\[\s*\]\s*;",
        collection_lock_source,
    )
    assert "isEnvironmentLocked(key, lockedFields)" in collection_lock_source
    assert "if (!locked) return;" in collection_lock_source


def test_environment_lock_disables_secret_replacement_actions():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    lock_source = _configuration_function(source, "lockControl")

    assert "[data-secret-replace]" in lock_source
    assert "[data-secret-clear]" in lock_source
    assert "disabled = true" in lock_source


def test_secret_actions_mark_their_containing_modal_dirty_immediately():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    secret_control_source = _configuration_function(source, "createSecretControl")
    dirty_source = _configuration_function(source, "markSecretControlDirty")

    assert secret_control_source.count("markSecretControlDirty(secretInput)") >= 2
    assert "markSectionDirty(form);" in dirty_source
    assert "modalDirty = true;" in dirty_source
    assert "syncModalButtons();" in dirty_source


def test_llm_locks_remain_scoped_to_the_matching_dynamic_row():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    provider_locks = _configuration_function(source, "applyProviderRowLocks")
    route_locks = _configuration_function(source, "applyTaskRouteLocks")
    payload_filter = _configuration_function(source, "filterEnvironmentLockedPayload")

    assert "lockedFields.some(key => /^LLM_PROVIDER_" not in provider_locks
    assert "lockedFields.some(key => /^TASK_" not in route_locks
    assert "isEnvironmentLocked(`${prefix}${suffix}`, lockedFields)" in provider_locks
    assert "isEnvironmentLocked(`TASK_${task.toUpperCase()}_PROVIDER`, lockedFields)" in route_locks
    assert "delete filteredPayload.providers" not in payload_filter
    assert "delete filteredPayload.task_routes" not in payload_filter


def test_modal_save_button_requires_unsaved_changes():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    modal_buttons_source = _configuration_function(source, "syncModalButtons")

    assert "|| !modalDirty" in modal_buttons_source
    assert "saveBtn.disabled = saveDisabled" in modal_buttons_source
    assert "testBtn.disabled = disabled || databaseLocked" in modal_buttons_source


def test_modal_save_only_clears_dirty_state_after_a_successful_api_save():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    save_source = _configuration_function(source, "saveSection")
    modal_save_source = _configuration_function(source, "modalSaveSection")

    assert "return !editedWhileSaving;" in save_source
    assert "return false;" in save_source
    assert re.search(
        r"const\s+saved\s*=\s*await\s+saveSection\(currentModalSection\);\s*"
        r"if\s*\(saved\)\s*\{\s*modalDirty\s*=\s*false;",
        modal_save_source,
        re.DOTALL,
    )


def test_provider_row_locks_keep_their_snapshot_index_after_dom_changes():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    row_source = _configuration_function(source, "createProviderRow")
    render_source = _configuration_function(source, "renderProviders")
    locks_source = _configuration_function(source, "applyProviderRowLocks")

    assert "row.dataset.providerIndex" in row_source
    assert "createProviderRow(provider, index + 1)" in render_source
    assert "Number(row.dataset.providerIndex)" in locks_source
    assert "rowIndex + 1" not in locks_source


def test_database_environment_lock_disables_modal_actions_and_skips_requests():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    save_source = _configuration_function(source, "saveSection")
    test_source = _configuration_function(source, "testSection")
    modal_buttons_source = _configuration_function(source, "syncModalButtons")

    assert "function isDatabaseEnvironmentLocked()" in source
    assert re.search(
        r"if\s*\(section\s*===\s*['\"]database['\"]\s*&&\s*isDatabaseEnvironmentLocked\(\)\)\s*\{\s*return false;",
        save_source,
    )
    assert re.search(
        r"if\s*\(section\s*===\s*['\"]database['\"]\s*&&\s*isDatabaseEnvironmentLocked\(\)\)\s*\{\s*return;",
        test_source,
    )
    assert "const databaseLocked = currentModalSection === 'database' && isDatabaseEnvironmentLocked();" in modal_buttons_source
