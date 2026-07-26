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


def _config_refresh_markup(template: str) -> tuple[_ConfigurationMarkupParser, _MarkupElement]:
    """Return the parsed refresh button using its true id attribute."""
    parser = _ConfigurationMarkupParser()
    parser.feed(template)
    parser.close()
    refresh = parser.elements_by_id.get("config-refresh")
    if not refresh:
        raise AssertionError('index.html must declare a #config-refresh button')
    return parser, refresh


def _status_filter_change_callback(events_source: str) -> str:
    """Extract the complete status-filter change callback from the event binder."""
    listener = re.search(
        r"querySelector\(\s*['\"]\[data-config-status-filter\]['\"]\s*\)\?\.addEventListener\s*\(",
        events_source,
    )
    if not listener:
        raise AssertionError('bindConfigurationEvents must bind [data-config-status-filter]')
    arguments = _balanced_javascript_region(
        events_source,
        listener.end() - 1,
        "(",
        ")",
        "status-filter addEventListener arguments",
    )
    callback = re.match(r"\s*['\"]change['\"]\s*,(?P<callback>[\s\S]+)\Z", arguments)
    if not callback:
        raise AssertionError('status-filter listener must register a change callback')
    return callback.group("callback")


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
    providerLocked: {{ task_routes: taskRoutes }},
    routeLocked: {{ providers }},
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


def test_configuration_refinement_replaces_onboarding_with_compact_progress_overview():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    health_source = _configuration_function(source, "renderConfigurationHealth")

    assert 'data-config-progress-completed' in template
    assert 'data-config-progress-missing' in template
    assert 'data-config-connection-summary' in template
    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in template
    assert 'data-config-onboarding' not in health_source


def test_configuration_refinement_refresh_status_is_described_and_never_tests_connections():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    template_markup, refresh = _config_refresh_markup(template)
    refresh_source = _configuration_function(source, "refreshConfiguration")
    load_source = _configuration_function(source, "loadConfiguration")
    refresh_path = refresh_source + load_source

    assert '刷新状态' in refresh.markup
    described_by = refresh.attrs.get("aria-describedby")
    assert described_by, '#config-refresh must describe its non-testing refresh behavior'
    help_ids = described_by.split()
    help_text = ''
    for help_id in help_ids:
        help_node = template_markup.elements_by_id.get(help_id)
        if help_node:
            help_text += help_node.markup
    assert '不测试连接或保存配置' in help_text, (
        '#config-refresh aria-describedby must reference help text stating “不测试连接或保存配置”'
    )
    assert 'await loadConfiguration({ discardDirty: true });' in refresh_source
    assert 'connectionStateBySection.clear()' in refresh_path
    assert 'testSection' not in refresh_path
    assert '/test' not in refresh_path
    assert 'modalTestSection' not in refresh_path


def test_configuration_refinement_binds_status_filter_without_onboarding_events():
    template = CONFIGURATION_TEMPLATE.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    events_source = _configuration_function(source, "bindConfigurationEvents")

    assert 'data-config-status-filter' in template
    assert 'data-config-onboarding' not in events_source
    assert 'openNextIncompleteConfiguration' not in events_source
    callback = _status_filter_change_callback(events_source)
    assert re.search(r'\brenderConfigurationCardVisibility\s*\(', callback), (
        'status-filter change callback must call renderConfigurationCardVisibility'
    )


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


def test_configuration_refinement_modal_locks_keep_accessible_descriptions():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")
    environment_lock_source = _configuration_function(source, "setEnvironmentLockState")
    apply_locks_source = _configuration_function(source, "applyEnvironmentLocks")

    assert 'aria-describedby' in environment_lock_source
    assert 'setEnvironmentLockState(control' in apply_locks_source
    assert 'setModalLockNote(hasStaticLock)' in apply_locks_source
