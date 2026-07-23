/* ============================================================
   AlphaFoundry — Commentary Production Center
   ============================================================ */

import { apiCall, esc, toast } from './core.js';

export const COMMENTARY_RECIPES = [
    {
        id: 'daily-close',
        title: '每日收盘点评',
        tag: '市场点评',
        tone: '克制、归因清晰、适合收盘后发布',
        sections: ['今日市场表现', '行业与风格变化', '资金与情绪', '核心归因', '后续观察'],
    },
    {
        id: 'market-drawdown',
        title: '市场大跌归因',
        tag: '异动复盘',
        tone: '先解释冲击，再判断是否改变中期逻辑',
        sections: ['发生了什么', '主要拖累方向', '直接触发因素', '深层原因判断', '明日观察变量'],
    },
    {
        id: 'sector-review',
        title: '行业板块点评',
        tag: '行业观点',
        tone: '研究员口径，强调景气、估值、催化和配置含义',
        sections: ['核心观点', '行情表现', '景气度证据', '估值与预期差', '配置建议与风险'],
    },
    {
        id: 'theme-event',
        title: '主题事件点评',
        tag: '主题研究',
        tone: '围绕事件传导链和受益方向展开',
        sections: ['事件概述', '产业链传导', '受益与受损方向', '市场分歧', '跟踪指标'],
    },
    {
        id: 'global-shock',
        title: '海外扰动点评',
        tag: '全球映射',
        tone: '区分海外事实、A股映射和情绪外溢',
        sections: ['海外市场表现', '触发因素', '跨市场传导', 'A股映射方向', '风险边界'],
    },
    {
        id: 'etf-allocation',
        title: '产品/ETF配置点评',
        tag: '产品转化',
        tone: '观点先行，产品承接，风险提示完整',
        sections: ['配置结论', '板块表现', '基本面与估值', '催化因素', '产品映射与风险提示'],
    },
];

export const COMMENTARY_CONFIDENCE_LEVELS = [
    { key: 'confirmed', attribute: 'data-confidence="confirmed"', label: '已确认数据' },
    { key: 'reported', attribute: 'data-confidence="reported"', label: '媒体报道' },
    { key: 'interpretation', attribute: 'data-confidence="interpretation"', label: '市场解释' },
    { key: 'judgement', attribute: 'data-confidence="judgement"', label: '主观判断' },
];

let initialized = false;
let activeRecipeId = COMMENTARY_RECIPES[0].id;
let latestContextRecipeId = '';
let latestContextPack = null;
let isLoadingContext = false;
let currentContextPromise = null;
let backendRecipes = [];
let currentEvidenceItems = [];
let selectedEvidenceKeys = new Set();
let currentDraftSections = [];
let autoRefreshInterval = null;
let versionHistory = [];

function bindCommentaryActions() {
    document
        .getElementById('btn-commentary-refresh-context')
        ?.addEventListener('click', () => loadCommentaryContext({ force: true }));
    document
        .getElementById('btn-commentary-generate-draft')
        ?.addEventListener('click', generateCommentaryDraft);
    document
        .getElementById('btn-commentary-copy-draft')
        ?.addEventListener('click', copyCommentaryDraft);
    document
        .getElementById('btn-commentary-export-md')
        ?.addEventListener('click', exportCommentaryMarkdown);
    document
        .getElementById('btn-commentary-auto-refresh')
        ?.addEventListener('click', toggleAutoRefresh);
    document
        .querySelector('.commentary-workspace-tabs')
        ?.addEventListener('click', event => {
            const tab = event.target?.closest?.('[data-commentary-workspace]');
            if (!tab) return;
            switchCommentaryWorkspace(tab.dataset.commentaryWorkspace);
        });
    document
        .getElementById('commentary-evidence-list')
        ?.addEventListener('change', event => {
            const checkbox = event.target?.closest?.('[data-commentary-evidence-key]');
            if (!checkbox) return;
            toggleCommentaryEvidence(checkbox.dataset.commentaryEvidenceKey, checkbox.checked);
        });
    document
        .getElementById('commentary-content-checklist')
        ?.addEventListener('change', renderGenerationLogic);
    document
        .getElementById('commentary-draft-sections')
        ?.addEventListener('click', event => {
            const action = event.target?.closest?.('[data-section-action]');
            if (!action) return;
            applySectionAction(
                Number(action.dataset.sectionIndex),
                action.dataset.sectionAction
            );
        });
    document
        .getElementById('commentary-history-list')
        ?.addEventListener('click', event => {
            const btn = event.target?.closest?.('[data-run-action]');
            if (!btn) return;
            const runId = btn.dataset.runId;
            const action = btn.dataset.runAction;
            if (action === 'view') viewRunDraft(runId);
            if (action === 'restore') restoreRunDraft(runId);
        });
}

function activeRecipe() {
    const recipes = commentaryRecipes();
    return recipes.find(recipe => recipe.id === activeRecipeId) || recipes[0] || COMMENTARY_RECIPES[0];
}

function commentaryRecipes() {
    return backendRecipes.length ? backendRecipes : COMMENTARY_RECIPES;
}

function readField(id) {
    return document.getElementById(id)?.value?.trim() || '';
}

function splitSignals(text) {
    return text
        .split(/[\n；;。]+/)
        .map(item => item.trim())
        .filter(Boolean)
        .slice(0, 6);
}

function renderTemplateList() {
    const list = document.getElementById('commentary-template-list');
    const count = document.getElementById('commentary-template-count');
    if (!list) return;

    const recipes = commentaryRecipes();
    if (count) count.textContent = `${recipes.length} 类`;
    list.innerHTML = recipes.map(recipe => `
        <button class="commentary-template-card ${recipe.id === activeRecipeId ? 'active' : ''}" type="button" onclick="selectCommentaryTemplate('${recipe.id}')">
            <span>${esc(recipe.tag)}</span>
            <strong>${esc(recipe.title)}</strong>
            <small>${esc(recipe.tone)}</small>
        </button>
    `).join('');
}

function renderActiveRecipe() {
    const recipe = activeRecipe();
    const title = document.getElementById('commentary-active-title');
    const tag = document.getElementById('commentary-active-tag');
    if (title) title.textContent = recipe.title;
    if (tag) tag.textContent = recipe.tag;
    renderTemplateList();
    renderGenerationLogic();
}

export function selectCommentaryTemplate(recipeId) {
    const recipes = commentaryRecipes();
    activeRecipeId = recipes.some(recipe => recipe.id === recipeId) ? recipeId : recipes[0].id;
    renderActiveRecipe();
    updateCommentaryWorkflow({ template: 'done', subject: 'active' });
    loadCommentaryContext({ force: true });
}

export async function loadCommentaryRecipes() {
    try {
        const catalog = await apiCall('GET', '/api/commentary/recipes');
        const recipes = Array.isArray(catalog?.recipes) ? catalog.recipes : [];
        if (!recipes.length) return commentaryRecipes();
        backendRecipes = recipes;
        if (!backendRecipes.some(recipe => recipe.id === activeRecipeId)) {
            activeRecipeId = catalog.default_recipe_id || backendRecipes[0].id;
        }
        renderActiveRecipe();
        latestContextRecipeId = '';
        return backendRecipes;
    } catch (error) {
        console.warn('commentary_recipes_load_failed', error);
        backendRecipes = [];
        renderActiveRecipe();
        return COMMENTARY_RECIPES;
    }
}

function setContextStatus(text, state = 'idle') {
    const el = document.getElementById('commentary-context-status');
    if (!el) return;
    el.textContent = text;
    el.dataset.state = state;
}

function setTextareaValue(id, value) {
    const el = document.getElementById(id);
    if (!el || !value) return;
    el.value = value;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function inferCommentaryTarget() {
    const news = currentEvidenceItems.find(item => item.source_type === 'news' && item.title);
    if (news?.title) return compactText(news.title, 28);
    const attribution = latestContextPack?.attribution_signals?.find?.(item => item.label || item.tag);
    if (attribution) return attribution.label || attribution.tag;
    const market = currentEvidenceItems.find(item =>
        item.source_type === 'market_data'
        && /领涨方向|拖累方向|领跌方向/.test(item.title || '')
    );
    return market?.title?.replace(/^领涨方向：|^拖累方向：|^领跌方向：/, '') || '';
}

function renderCommentaryTargetCandidate() {
    const candidate = inferCommentaryTarget();
    const el = document.getElementById('commentary-target-candidate');
    if (el) el.textContent = candidate ? `自动候选：${candidate}` : '自动候选：等待上下文';
    return candidate;
}

function readSelectedContentSections() {
    const selected = Array.from(
        document.querySelectorAll('[data-commentary-content-section]:checked')
    )
        .map(input => input.dataset.commentaryContentSection || '')
        .filter(Boolean);
    return selected.join(' / ');
}

function renderLogicList(id, items = [], emptyText = '等待上下文。') {
    const el = document.getElementById(id);
    if (!el) return;
    const visibleItems = items.map(item => String(item || '').trim()).filter(Boolean);
    if (!visibleItems.length) {
        el.innerHTML = `<p class="empty-state compact">${esc(emptyText)}</p>`;
        return;
    }
    el.innerHTML = visibleItems.map((item, index) => `
        <article class="commentary-logic-row">
            <span>${index + 1}</span>
            <p>${esc(item)}</p>
        </article>
    `).join('');
}

function buildGenerationLogicSnapshot(recipe = activeRecipe()) {
    const request = buildDraftRequest(recipe);
    const selected = selectedEvidenceItems();
    const preferences = request.writing_preferences || {};
    const attribution = Array.isArray(request.attribution_signals)
        ? request.attribution_signals
        : [];
    const verifiedCount = selected.filter(item => item.verification_status === 'verified').length;
    const reportedCount = selected.filter(
        item => item.source_type === 'news' || item.source_type === 'research'
    ).length;
    return {
        recipe: [
            `recipe_id=${recipe.id}；标题=${recipe.title}；口径=${recipe.tone}`,
            `段落结构：${(recipe.sections || []).join(' / ') || '等待 recipe'}`,
            `点评对象：${formatTargetMode(preferences.target_mode)} - ${preferences.target_name || '等待确认'}`,
            `内容清单：${preferences.content_sections || '等待确认'}`,
            `写作偏好：受众=${preferences.audience || 'internal'}；长度=${preferences.length || 'medium'}；风格=${preferences.tone || 'balanced'}`,
        ],
        evidence: [
            `选中证据 ${selected.length} 条；已核验 ${verifiedCount} 条；新闻/研报 ${reportedCount} 条`,
            ...selected.slice(0, 7).map(item => (
                `${formatEvidenceLabel(item)}｜${item.source_type || item.kind || 'source'}｜${formatVerificationStatus(item.verification_status)}｜${item.title || '未命名证据'}`
            )),
        ],
        attribution: attribution.length
            ? attribution.slice(0, 6).map(item => (
                `${item.rank || '-'}｜${formatAttributionStrength(item.strength)}｜${Math.round(Number(item.score || 0))}｜${item.label || item.tag || '归因项'}：${item.rationale || '等待归因说明'}`
            ))
            : ['暂无归因排序；生成时会退回数据快照和证据包做谨慎归因。'],
        prompt: [
            'prompt 顺序：证据包 -> 数据快照 -> 结构化证据与核验状态 -> 归因排序 -> 主观判断 -> 写作偏好',
            `证据包摘要：${compactText(request.evidence_pack_text || '暂无证据包', 140)}`,
            `数据快照摘要：${compactText(request.data_snapshot_text || '暂无数据快照', 140)}`,
            `主观判断：${compactText(request.subjective_judgement || '暂无，请保持中性', 140)}`,
            '模型约束：先写消息面主线，再用行情数据验证；未核验证据必须谨慎措辞。',
        ],
        quality: [
            'quality gate: 未核验证据不能写成确定事实。',
            'quality gate: 必须包含风险提示或后续观察变量。',
            'quality gate: 禁止一定会、稳赚、无风险等承诺式表达。',
            'guardrail: 返回前会尝试修正内联标题、软化确定性语言并补风险提示。',
        ],
        run: [
            '1. GET /api/commentary/context：生成 data_snapshot、evidence_items、attribution_signals。',
            '2. 前端勾选证据并读取写作设置，组装 CommentaryDraftRequest。',
            '3. POST /api/commentary/draft：LLM 优先，本地规则兜底。',
            '4. POST /api/commentary/quality-check：发布门禁检查事实边界和风险表达。',
            '5. POST /api/commentary/runs：记录模型、证据数量、质检状态和草稿。',
        ],
    };
}

function renderGenerationLogic() {
    const snapshot = buildGenerationLogicSnapshot(activeRecipe());
    renderLogicList('commentary-logic-recipe', snapshot.recipe);
    renderLogicList('commentary-logic-evidence', snapshot.evidence, '等待证据入选。');
    renderLogicList('commentary-logic-attribution', snapshot.attribution, '等待归因排序。');
    renderLogicList('commentary-logic-prompt', snapshot.prompt);
    renderLogicList('commentary-logic-quality', snapshot.quality);
    renderLogicList('commentary-logic-run', snapshot.run);
}

export function switchCommentaryWorkspace(mode = 'template') {
    const targetMode = mode || 'template';
    document.querySelectorAll('[data-commentary-workspace]').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.commentaryWorkspace === targetMode);
    });
    document.querySelectorAll('[data-commentary-workspace-panel]').forEach(panel => {
        panel.classList.toggle('active', panel.dataset.commentaryWorkspacePanel === targetMode);
    });
    if (targetMode === 'content') renderGenerationLogic();
}

function updateCommentaryWorkflow(overrides = {}) {
    const selectedCount = selectedEvidenceItems().length;
    const hasContext = Boolean(latestContextPack && latestContextRecipeId === activeRecipe().id);
    const hasEvidence = currentEvidenceItems.length > 0;
    const draftText = document.getElementById('commentary-draft-output')?.innerText?.trim() || '';
    const hasDraft = currentDraftSections.length > 0 || draftText.length > 20;
    const qualityText = document.getElementById('commentary-quality-panel')?.innerText || '';
    const hasQuality = hasDraft && !qualityText.includes('等待生成后质检');
    const normalizedOverrides = { ...overrides };
    if (normalizedOverrides.context) normalizedOverrides.content = normalizedOverrides.context;
    if (normalizedOverrides.evidence) normalizedOverrides.content = normalizedOverrides.evidence;
    if (normalizedOverrides.quality) normalizedOverrides.draft = normalizedOverrides.quality;
    const states = {
        template: hasContext ? 'done' : 'active',
        subject: hasContext ? 'done' : (normalizedOverrides.template === 'done' ? 'active' : 'pending'),
        content: hasEvidence && selectedCount > 0 ? 'done' : (hasContext ? 'active' : 'pending'),
        draft: hasDraft ? 'done' : (hasEvidence ? 'active' : 'pending'),
        ...normalizedOverrides,
    };
    if (hasQuality) states.draft = 'done';
    const labels = {
        done: '完成',
        active: '当前',
        pending: '等待',
        error: '异常',
    };
    document.querySelectorAll('.commentary-workflow-step[data-commentary-step]').forEach(step => {
        const state = states[step.dataset.commentaryStep] || 'pending';
        step.setAttribute('data-step-state', state);
        const badge = step.querySelector('em');
        if (badge) badge.textContent = labels[state] || state;
    });
}

function formatTargetMode(mode) {
    if (mode === 'manual') return '手动指定';
    if (mode === 'auto') return '自动补充';
    return '模板默认';
}

function evidenceKey(item, index = 0) {
    return [
        item.source_type || item.kind || 'source',
        item.source || '',
        item.title || '',
        item.url || '',
        index,
    ].join('::');
}

function formatEvidenceLabel(item) {
    if (item.display_label) return item.display_label;
    const labels = {
        confirmed: '已确认数据',
        reported: '媒体报道',
        interpretation: '市场解释',
        judgement: '主观判断',
    };
    return labels[item.kind] || item.kind || '证据';
}

function compactText(text, maxLength = 150) {
    const compacted = String(text || '').replace(/\s+/g, ' ').trim();
    if (compacted.length <= maxLength) return compacted;
    return `${compacted.slice(0, maxLength).trim()}...`;
}

function formatEvidenceTerms(item) {
    const terms = Array.isArray(item?.metadata?.matched_terms)
        ? item.metadata.matched_terms
        : [];
    return terms
        .map(term => String(term || '').trim())
        .filter(Boolean)
        .slice(0, 4);
}

function formatEvidenceImpact(item) {
    const summary = compactText(item?.summary || '', 120);
    if (!summary) return '';
    const sentence = summary.match(/^(.{1,72}?[。！？；])/);
    return sentence ? sentence[1] : compactText(summary, 78);
}

function evidenceGroupKey(item) {
    if (item.source_type === 'market_data') return 'market';
    if (item.source_type === 'research') return 'research';
    if (item.source_type === 'news') return 'news';
    if (item.kind === 'judgement' || item.source_type === 'system') return 'judgement';
    return 'judgement';
}

function groupEvidenceItems(items = []) {
    const groups = [
        { key: 'news', title: '消息主线', subtitle: '新闻、公告和事件触发', items: [] },
        { key: 'market', title: '行情验证', subtitle: '指数、板块、资金和广度', items: [] },
        { key: 'research', title: '研报材料', subtitle: '研报、纪要和研究观点', items: [] },
        { key: 'judgement', title: '判断补充', subtitle: '系统提示和主观解释', items: [] },
    ];
    const lookup = new Map(groups.map(group => [group.key, group]));
    items.forEach((item, index) => {
        const group = lookup.get(evidenceGroupKey(item)) || lookup.get('judgement');
        group.items.push({ item, index });
    });
    return groups.filter(group => group.items.length);
}

function renderEvidenceGroup(group) {
    return `
        <section class="commentary-evidence-group" data-evidence-group="${esc(group.key)}">
            <header>
                <div>
                    <h4>${esc(group.title)}</h4>
                    <small>${esc(group.subtitle)}</small>
                </div>
                <span>${group.items.length} 条</span>
            </header>
            <div class="commentary-evidence-group-list">
                ${group.items.map(({ item, index }) => renderEvidenceItem(item, index)).join('')}
            </div>
        </section>
    `;
}

function renderEvidenceItem(item, index) {
    const key = evidenceKey(item, index);
    const status = formatVerificationStatus(item.verification_status);
    const confidence = typeof item.confidence_score === 'number'
        ? `${Math.round(item.confidence_score * 100)}%`
        : '--';
    const terms = formatEvidenceTerms(item);
    const impact = formatEvidenceImpact(item);
    const fullSummary = compactText(item.summary || '', 360);
    return `
        <label class="commentary-evidence-item" data-source-type="${esc(item.source_type || 'other')}">
            <input type="checkbox" data-commentary-evidence-key="${esc(key)}" checked>
            <span class="commentary-evidence-body">
                <span class="commentary-evidence-meta">
                    <strong>${esc(formatEvidenceLabel(item))}</strong>
                    <small>${esc(status)} · ${esc(confidence)} · ${esc(item.source || item.source_type || 'source')}</small>
                </span>
                <b>${esc(item.title || '未命名证据')}</b>
                ${terms.length ? `<span class="commentary-evidence-terms">${terms.map(term => `<em>${esc(term)}</em>`).join('')}</span>` : ''}
                ${impact ? `<small class="commentary-evidence-impact">${esc(impact)}</small>` : ''}
                ${fullSummary && fullSummary !== impact ? `
                    <details class="commentary-evidence-detail">
                        <summary>查看原始摘要</summary>
                        <small>${esc(fullSummary)}</small>
                    </details>
                ` : ''}
            </span>
        </label>
    `;
}

function renderOverviewEvidence(items = []) {
    const list = document.getElementById('commentary-overview-evidence-list');
    if (!list) return;
    const ranked = [...(Array.isArray(items) ? items : [])].sort((left, right) => {
        const leftNews = left.source_type === 'news' ? 1 : 0;
        const rightNews = right.source_type === 'news' ? 1 : 0;
        return rightNews - leftNews || Number(right.confidence_score || 0) - Number(left.confidence_score || 0);
    }).slice(0, 5);
    if (!ranked.length) {
        list.innerHTML = '<p class="empty-state compact">等待上下文证据。</p>';
        return;
    }
    list.innerHTML = ranked.map((item, index) => `
        <article class="commentary-overview-evidence-item">
            <span>${index + 1}</span>
            <div>
                <strong>${esc(item.title || '未命名证据')}</strong>
                <small>${esc(formatEvidenceLabel(item))} · ${esc(formatVerificationStatus(item.verification_status))}</small>
            </div>
        </article>
    `).join('');
}

function renderOverviewAttribution(signals = []) {
    const list = document.getElementById('commentary-overview-attribution-list');
    if (!list) return;
    const items = Array.isArray(signals) ? signals.slice(0, 3) : [];
    if (!items.length) {
        list.innerHTML = '<p class="empty-state compact">等待上下文归因。</p>';
        return;
    }
    list.innerHTML = items.map(item => `
        <article class="commentary-overview-attribution-item" data-strength="${esc(item.strength || 'watch')}">
            <span>${esc(formatAttributionStrength(item.strength))}</span>
            <strong>${esc(item.label || item.tag || '归因项')}</strong>
            <small>${esc(item.rationale || '')}</small>
        </article>
    `).join('');
}

function updateProductionMetrics() {
    const selectedCount = selectedEvidenceItems().length;
    const verifiedCount = currentEvidenceItems.filter(
        item => item.verification_status === 'verified'
    ).length;
    setText('commentary-evidence-count', currentEvidenceItems.length ? `${currentEvidenceItems.length}` : '--');
    setText('commentary-selected-evidence-count', currentEvidenceItems.length ? `${selectedCount}` : '--');
    setText('commentary-verified-count', currentEvidenceItems.length ? `${verifiedCount}` : '--');
    updateCommentaryWorkflow();
}

function renderQualityPanel(response = null) {
    const panel = document.getElementById('commentary-quality-panel');
    if (!panel) return;
    if (!response) {
        panel.innerHTML = '<span data-quality="ready">等待生成后质检</span>';
        updateCommentaryWorkflow({ quality: 'pending' });
        return;
    }
    if (Array.isArray(response.issues)) {
        renderQualityIssues(response);
        return;
    }
    const warnings = Array.isArray(response.warnings) ? response.warnings : [];
    const citations = Array.isArray(response.citations) ? response.citations : [];
    const unverified = citations.filter(item => item.verification_status !== 'verified').length;
    panel.innerHTML = [
        `<span data-quality="${warnings.length ? 'warn' : 'ready'}">警告 ${warnings.length}</span>`,
        `<span data-quality="${unverified ? 'watch' : 'ready'}">待核验证据 ${unverified}</span>`,
        `<span data-quality="ready">引用 ${citations.length}</span>`,
    ].join('');
    updateCommentaryWorkflow();
}

function renderQualityIssues(result = {}) {
    const panel = document.getElementById('commentary-quality-panel');
    if (!panel) return;
    const issues = Array.isArray(result.issues) ? result.issues : [];
    const summary = result.summary || {};
    if (!issues.length) {
        panel.innerHTML = '<span data-quality="ready">质检通过</span>';
        updateCommentaryWorkflow({ quality: 'done' });
        return;
    }
    const state = result.status === 'blocked' ? 'warn' : 'watch';
    panel.innerHTML = `
        <span data-quality="${state}">阻断 ${Number(summary.blocked || 0)}</span>
        <span data-quality="watch">提醒 ${Number(summary.warning || 0)}</span>
        ${issues.slice(0, 4).map(issue => `
            <span data-quality="${issue.severity === 'blocker' ? 'warn' : 'watch'}" title="${esc(issue.detail || '')}">
                ${esc(issue.title || issue.code)}
            </span>
        `).join('')}
    `;
    updateCommentaryWorkflow({ quality: 'done' });
}

function formatAttributionStrength(strength) {
    const labels = {
        primary: '主因',
        secondary: '次因',
        watch: '待观察',
        noise: '低相关',
    };
    return labels[strength] || '待观察';
}

function renderAttributionSignals(signals = []) {
    const list = document.getElementById('commentary-attribution-list');
    const count = document.getElementById('commentary-attribution-count');
    renderOverviewAttribution(signals);
    if (!list) return;

    const items = Array.isArray(signals) ? signals.slice(0, 6) : [];
    if (count) count.textContent = items.length ? `${items.length} 项` : '--';
    if (!items.length) {
        list.innerHTML = '<p class="empty-state compact">等待上下文归因。</p>';
        return;
    }

    list.innerHTML = items.map(item => `
        <article class="commentary-attribution-item" data-strength="${esc(item.strength || 'watch')}">
            <div>
                <span>${esc(formatAttributionStrength(item.strength))}</span>
                <strong>${esc(item.label || item.tag || '归因项')}</strong>
                <small>${esc(item.rationale || '')}</small>
            </div>
            <div class="commentary-attribution-score">
                <strong>${Math.round(Number(item.score || 0))}</strong>
                <small>${esc(item.verification_status || 'derived')}</small>
            </div>
        </article>
    `).join('');
}

function renderEvidenceItems(items = []) {
    const list = document.getElementById('commentary-evidence-list');
    if (!list) return;

    currentEvidenceItems = Array.isArray(items) ? items : [];
    selectedEvidenceKeys = new Set(
        currentEvidenceItems.map((item, index) => evidenceKey(item, index))
    );
    updateProductionMetrics();
    renderOverviewEvidence(currentEvidenceItems);
    renderCommentaryTargetCandidate();
    renderGenerationLogic();

    if (!currentEvidenceItems.length) {
        list.innerHTML = '<p class="empty-state compact">等待上下文证据。</p>';
        return;
    }

    list.innerHTML = groupEvidenceItems(currentEvidenceItems)
        .map(group => renderEvidenceGroup(group))
        .join('');
}

export function toggleCommentaryEvidence(key, checked) {
    if (!key) return;
    if (checked) {
        selectedEvidenceKeys.add(key);
    } else {
        selectedEvidenceKeys.delete(key);
    }
    updateProductionMetrics();
    renderGenerationLogic();
}

function selectedEvidenceItems() {
    return currentEvidenceItems.filter((item, index) =>
        selectedEvidenceKeys.has(evidenceKey(item, index))
    );
}

export async function loadCommentaryContext(options = {}) {
    const recipe = activeRecipe();
    if (!options.force && latestContextRecipeId === recipe.id) return;
    if (isLoadingContext) return currentContextPromise;

    isLoadingContext = true;
    setContextStatus('加载上下文...', 'loading');
    updateCommentaryWorkflow({ context: 'active', evidence: 'pending' });
    currentContextPromise = (async () => {
        let context = null;
        try {
            context = await apiCall(
                'GET',
                `/api/commentary/context?recipe_id=${encodeURIComponent(recipe.id)}`
            );
        } catch (error) {
            console.error('commentary_context_fetch_failed', error);
            setContextStatus('上下文加载失败', 'error');
            updateCommentaryWorkflow({ context: 'error' });
            if (options.force) toast(`点评上下文加载失败：${error.message || error}`, 'error');
            return null;
        }

        try {
            latestContextPack = context;
            setTextareaValue('commentary-data-snapshot', context.data_snapshot_text);
            setTextareaValue('commentary-evidence-pack', context.evidence_pack_text);
            renderAttributionSignals(context.attribution_signals);
            renderEvidenceItems(context.evidence_items);
            renderQualityPanel();
            renderGenerationLogic();
            updateContextTimestamp(context);
            latestContextRecipeId = recipe.id;
            setContextStatus('上下文已更新', 'ready');
            updateCommentaryWorkflow();
            if (options.force) toast('点评上下文已更新', 'success');
            return context;
        } catch (error) {
            console.error('commentary_context_render_failed', error);
            setContextStatus('上下文渲染失败', 'error');
            updateCommentaryWorkflow({ context: 'error' });
            if (options.force) toast(`点评上下文渲染失败：${error.message || error}`, 'error');
            return null;
        }
    })();

    try {
        return await currentContextPromise;
    } finally {
        isLoadingContext = false;
        currentContextPromise = null;
    }
}

function pickSignal(signals, index, fallback) {
    if (!signals.length) return fallback;
    return signals[index % signals.length];
}

function buildSectionParagraph(section, dataSignals, evidenceSignals, judgement, index) {
    const dataPoint = pickSignal(dataSignals, index, '市场数据仍需补充');
    const evidencePoint = pickSignal(evidenceSignals, index, '相关证据仍需继续核验');

    if (section.includes('核心') || section.includes('结论') || section.includes('判断')) {
        return `${section}：${judgement || '当前更适合把行情理解为多因素共振下的风险偏好重估，而不是单一事件驱动。'}`;
    }
    if (section.includes('风险')) {
        return `${section}：需要警惕高拥挤交易继续降温、海外变量反复、以及后续数据无法验证当前预期的风险。`;
    }
    if (section.includes('观察') || section.includes('跟踪')) {
        return `${section}：重点观察成交额和资金流能否企稳，强势主题是否继续扩散，以及新增新闻是否从情绪扰动转为基本面压力。`;
    }
    return `${section}：${dataPoint}。证据层面，${evidencePoint}。`;
}

export function buildCommentaryDraft(recipe, dataSnapshot, evidencePack, judgement) {
    const dataSignals = splitSignals(dataSnapshot);
    const evidenceSignals = splitSignals(evidencePack);
    const sectionParagraphs = recipe.sections.map((section, index) =>
        buildSectionParagraph(section, dataSignals, evidenceSignals, judgement, index)
    );

    return {
        title: `${recipe.title}：从数据、证据和判断三层拆解`,
        summary: judgement || '当前点评需要在行情事实、媒体报道和主观归因之间保持清晰边界。',
        paragraphs: sectionParagraphs,
        confidence: [
            ['已确认数据', dataSignals[0] || '等待接入宽基、行业、资金、估值等实时数据'],
            ['媒体报道', evidenceSignals[0] || '等待接入新闻、公告、研报证据'],
            ['市场解释', recipe.tone],
            ['主观判断', judgement || '等待补充投资观点'],
        ],
    };
}

function renderDraft(draft) {
    const output = document.getElementById('commentary-draft-output');
    if (!output) return;

    output.innerHTML = `
        <h3>${esc(draft.title)}</h3>
        <p class="commentary-draft-lead">${esc(draft.summary)}</p>
        ${draft.paragraphs.map(paragraph => `<p>${esc(paragraph)}</p>`).join('')}
        <div class="commentary-draft-confidence">
            ${draft.confidence.map(([label, value]) => `
                <span><strong>${esc(label)}</strong><small>${esc(value)}</small></span>
            `).join('')}
        </div>
    `;
    renderDraftSections({
        sections: draft.paragraphs.map(paragraph => {
            const [heading, ...rest] = paragraph.split('：');
            return {
                heading: heading || '草稿段落',
                content: rest.join('：') || paragraph,
            };
        }),
    });
    updateCommentaryWorkflow({ draft: 'done', quality: 'active' });
    setText('commentary-overview-draft-state', '已生成');
    switchCommentaryWorkspace('draft');
}

function markdownToHtml(markdown) {
    const lines = String(markdown || '').split(/\r?\n/);
    return lines.map(line => {
        const trimmed = line.trim();
        if (!trimmed) return '';
        if (trimmed.startsWith('# ')) return `<h3>${esc(trimmed.slice(2))}</h3>`;
        if (trimmed.startsWith('## ')) return `<h4>${esc(trimmed.slice(3))}</h4>`;
        return `<p>${esc(trimmed)}</p>`;
    }).join('');
}

function parseMarkdownSections(markdown) {
    const sections = [];
    let currentHeading = '';
    let currentLines = [];
    String(markdown || '').split(/\r?\n/).forEach(line => {
        const trimmed = line.trim();
        if (trimmed.startsWith('## ')) {
            if (currentHeading) {
                sections.push({
                    heading: currentHeading,
                    content: currentLines.join('\n').trim(),
                });
            }
            currentHeading = trimmed.slice(3).trim();
            currentLines = [];
            return;
        }
        if (currentHeading && !trimmed.startsWith('# ')) currentLines.push(line);
    });
    if (currentHeading) {
        sections.push({
            heading: currentHeading,
            content: currentLines.join('\n').trim(),
        });
    }
    return sections;
}

function formatVerificationStatus(status) {
    const labels = {
        verified: '已核验',
        source_published: '来源已发布',
        derived: '推导',
        unverified: '待核验',
    };
    return labels[status] || '待核验';
}

function formatCitationMeta(item) {
    const parts = [
        item.source_type || item.kind || 'source',
        formatVerificationStatus(item.verification_status),
    ];
    if (typeof item.confidence_score === 'number') {
        parts.push(`置信度 ${Math.round(item.confidence_score * 100)}%`);
    }
    if (item.source) parts.push(item.source);
    return parts.filter(Boolean).join(' · ');
}

function renderBackendDraft(response) {
    const output = document.getElementById('commentary-draft-output');
    if (!output) return;
    const warnings = Array.isArray(response.warnings) ? response.warnings : [];
    const citations = Array.isArray(response.citations) ? response.citations.slice(0, 6) : [];
    renderAttributionSignals(response.attribution_signals || latestContextPack?.attribution_signals);
    renderQualityPanel(response);
    setText('commentary-run-meta', response.model ? `${response.model}` : '已生成');
    output.innerHTML = `
        ${markdownToHtml(response.draft_markdown)}
        ${warnings.length ? `
            <div class="commentary-draft-warning">
                ${warnings.map(warning => `<span>${esc(warning)}</span>`).join('')}
            </div>
        ` : ''}
        ${citations.length ? `
            <div class="commentary-draft-confidence">
                ${citations.map(item => `
                    <span><strong>${esc(item.display_label || item.kind || 'source')}</strong><small>${esc(item.title || item.source || '')}<br>${esc(formatCitationMeta(item))}</small></span>
                `).join('')}
            </div>
        ` : ''}
    `;
    renderDraftSections(response);
    updateCommentaryWorkflow({ draft: 'done', quality: 'active' });
    setText('commentary-overview-draft-state', '已生成');
    switchCommentaryWorkspace('draft');
}

async function runCommentaryQualityCheck(draftResponse) {
    try {
        const recipe = activeRecipe();
        const result = await apiCall(
            'POST',
            '/api/commentary/quality-check',
            {
                ...buildDraftRequest(recipe),
                draft_markdown: draftResponse?.draft_markdown || '',
            }
        );
        renderQualityPanel(result);
        renderGenerationLogic();
        recordCommentaryRun(draftResponse, result);
        return result;
    } catch (error) {
        console.warn('commentary_quality_check_failed', error);
        const panel = document.getElementById('commentary-quality-panel');
        if (panel) {
            panel.innerHTML = '<span data-quality="watch">质检暂不可用</span>';
        }
        renderGenerationLogic();
        recordCommentaryRun(draftResponse, null);
        return null;
    }
}

async function recordCommentaryRun(draftResponse, qualityResult) {
    try {
        const recipe = activeRecipe();
        await apiCall(
            'POST',
            '/api/commentary/runs',
            {
                recipe_id: recipe.id,
                recipe_title: recipe.title,
                draft_markdown: draftResponse?.draft_markdown || '',
                model: draftResponse?.model || '',
                provider: draftResponse?.provider || '',
                warnings: Array.isArray(draftResponse?.warnings) ? draftResponse.warnings : [],
                evidence_count: currentEvidenceItems.length,
                selected_evidence_count: selectedEvidenceItems().length,
                quality_status: qualityResult?.status || 'unknown',
                quality_summary: qualityResult?.summary || {},
            }
        );
    } catch (error) {
        console.warn('commentary_run_record_failed', error);
    }
}

function renderDraftSections(response = {}) {
    const container = document.getElementById('commentary-draft-sections');
    if (!container) return;
    const sections = Array.isArray(response.sections) && response.sections.length
        ? response.sections
        : parseMarkdownSections(response.draft_markdown);
    currentDraftSections = sections.map((section, index) => ({
        heading: section.heading || `段落 ${index + 1}`,
        content: section.content || '',
    }));

    if (!currentDraftSections.length) {
        container.innerHTML = '<p class="empty-state compact">生成后显示分段编辑器。</p>';
        return;
    }

    container.innerHTML = currentDraftSections.map((section, index) => `
        <article class="commentary-section-card">
            <header>
                <strong>${esc(section.heading)}</strong>
                <span>${section.content.length} 字</span>
            </header>
            <textarea data-section-text="${index}" rows="5">${esc(section.content)}</textarea>
            <div class="commentary-section-actions">
                <button class="btn-secondary" type="button" data-section-index="${index}" data-section-action="shorten"><i class="codicon codicon-fold"></i> 缩短</button>
                <button class="btn-secondary" type="button" data-section-index="${index}" data-section-action="soften"><i class="codicon codicon-shield"></i> 降判断</button>
                <button class="btn-secondary" type="button" data-section-index="${index}" data-section-action="risk"><i class="codicon codicon-warning"></i> 补风险</button>
                <button class="btn-secondary" type="button" data-section-index="${index}" data-section-action="copy"><i class="codicon codicon-copy"></i> 复制</button>
            </div>
        </article>
    `).join('');
}

export async function applySectionAction(index, action) {
    const textarea = document.querySelector(`[data-section-text="${index}"]`);
    if (!textarea) return;
    let text = textarea.value.trim();
    if (action === 'copy') {
        await navigator.clipboard.writeText(text);
        toast('段落已复制', 'success');
        return;
    }
    try {
        text = await rewriteCommentarySection(index, action, text);
    } catch (error) {
        console.warn('commentary_section_rewrite_failed', error);
        text = applyLocalSectionAction(text, action);
        toast('段落已用本地规则处理', 'error');
    }
    textarea.value = text;
    currentDraftSections[index] = {
        ...currentDraftSections[index],
        content: text,
    };
}

async function rewriteCommentarySection(index, action, text) {
    const response = await apiCall(
        'POST',
        '/api/commentary/section-rewrite',
        buildSectionRewriteRequest(index, action, text)
    );
    const rewritten = response?.rewritten_content?.trim();
    if (!rewritten) throw new Error('empty section rewrite response');
    return rewritten;
}

function buildSectionRewriteRequest(index, action, text) {
    const recipe = activeRecipe();
    return {
        ...buildDraftRequest(recipe),
        section_heading: currentDraftSections[index]?.heading || `段落 ${index + 1}`,
        section_content: text,
        action,
    };
}

function applyLocalSectionAction(text, action) {
    if (action === 'shorten') {
        const sentences = text.split(/(?<=[。！？；])/).map(item => item.trim()).filter(Boolean);
        return sentences.slice(0, 2).join('') || text.slice(0, 120);
    }
    if (action === 'soften') {
        return text
            .replace(/必然/g, '更可能')
            .replace(/一定/g, '需要观察')
            .replace(/确定/g, '相对明确')
            .replace(/不会/g, '短期不易');
    }
    if (action === 'risk') {
        const riskText = '需要提示的是，若后续成交额、资金流或新增证据不能验证当前判断，相关归因仍需下修。';
        if (!text.includes(riskText)) return `${text}${text.endsWith('。') ? '' : '。'}${riskText}`;
    }
    return text;
}

function readWritingPreferences() {
    const targetMode = readField('commentary-target-mode-control') || 'template_default';
    const manualTarget = readField('commentary-target-input');
    const inferredTarget = renderCommentaryTargetCandidate();
    const templateTarget = activeRecipe().title;
    return {
        audience: readField('commentary-audience-control') || 'internal',
        length: readField('commentary-length-control') || 'medium',
        tone: readField('commentary-tone-control') || 'balanced',
        target_mode: targetMode,
        target_name: targetMode === 'manual'
            ? manualTarget
            : (targetMode === 'auto' ? inferredTarget : templateTarget),
        content_sections: readSelectedContentSections(),
    };
}

function buildDraftRequest(recipe) {
    return {
        recipe_id: recipe.id,
        data_snapshot_text: readField('commentary-data-snapshot'),
        evidence_pack_text: readField('commentary-evidence-pack'),
        subjective_judgement: readField('commentary-subjective-judgement'),
        evidence_items: selectedEvidenceItems(),
        attribution_signals: Array.isArray(latestContextPack?.attribution_signals) ? latestContextPack.attribution_signals : [],
        writing_preferences: readWritingPreferences(),
    };
}

export async function generateCommentaryDraft() {
    const recipe = activeRecipe();
    try {
        updateCommentaryWorkflow({ draft: 'active', quality: 'pending' });
        setText('commentary-overview-draft-state', '生成中');
        showGenerationOverlay('正在检索上下文...');
        if (isLoadingContext) await currentContextPromise;
        if (!latestContextPack || latestContextRecipeId !== recipe.id) {
            await loadCommentaryContext();
        }
        showGenerationOverlay('正在调用模型生成草稿...');
        const response = await apiCall(
            'POST',
            '/api/commentary/draft',
            buildDraftRequest(recipe)
        );
        hideGenerationOverlay();
        renderBackendDraft(response);
        runCommentaryQualityCheck(response);
        saveToVersionHistory(response);
        loadCommentaryRuns();
        toast('点评草稿已生成', 'success');
    } catch (error) {
        hideGenerationOverlay();
        console.error('[commentary] failed to generate draft', error);
        setText('commentary-overview-draft-state', '本地兜底');
        const draft = buildCommentaryDraft(
            recipe,
            readField('commentary-data-snapshot'),
            readField('commentary-evidence-pack'),
            readField('commentary-subjective-judgement')
        );
        renderDraft(draft);
        saveToVersionHistory({ draft_markdown: draft.paragraphs.join('\n\n'), model: 'rule_based_fallback' });
        toast('本地兜底草稿已生成', 'error');
    }
}

export async function copyCommentaryDraft() {
    try {
        const output = document.getElementById('commentary-draft-output');
        const text = output?.innerText?.trim();
        if (!text) {
            toast('暂无可复制内容', 'error');
            return;
        }
        await navigator.clipboard.writeText(text);
        toast('点评草稿已复制', 'success');
    } catch (error) {
        console.error('[commentary] failed to copy draft', error);
        toast('复制失败，请手动选择文本', 'error');
    }
}

/* ============================================================
   Phase 1 — 导出 Markdown
   ============================================================ */

export function exportCommentaryMarkdown() {
    try {
        const output = document.getElementById('commentary-draft-output');
        const markdown = buildExportMarkdown();
        if (!markdown || markdown.length < 20) {
            toast('暂无可导出内容', 'error');
            return;
        }
        const recipe = activeRecipe();
        const dateStr = new Date().toISOString().slice(0, 10);
        const filename = `${recipe.title}_${dateStr}.md`;
        const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        URL.revokeObjectURL(url);
        toast(`已导出 ${filename}`, 'success');
    } catch (error) {
        console.error('[commentary] failed to export markdown', error);
        toast('导出失败', 'error');
    }
}

function buildExportMarkdown() {
    const recipe = activeRecipe();
    const contextTime = document.getElementById('commentary-context-time')?.textContent || '';
    const lines = [
        `# ${recipe.title}`,
        '',
        `> 生成时间：${new Date().toLocaleString()}`,
        contextTime ? `> 数据时间：${contextTime}` : '',
        `> 模板口径：${recipe.tone}`,
        '',
        '---',
        '',
    ].filter(Boolean);

    const draftOutput = document.getElementById('commentary-draft-output');
    if (draftOutput) {
        const text = draftOutput.innerText?.trim() || '';
        if (text) lines.push(text, '');
    }

    if (currentDraftSections.length) {
        lines.push('---', '', '## 分段内容', '');
        currentDraftSections.forEach((section, i) => {
            lines.push(`### ${section.heading}`);
            lines.push('');
            lines.push(section.content || '');
            lines.push('');
        });
    }

    const selected = selectedEvidenceItems();
    if (selected.length) {
        lines.push('---', '', '## 引用证据', '');
        selected.forEach((item, i) => {
            lines.push(`${i + 1}. **[${formatEvidenceLabel(item)}]** ${item.title || '未命名证据'}`);
            if (item.source) lines.push(`   - 来源：${item.source}`);
            if (item.verification_status) lines.push(`   - 核验状态：${formatVerificationStatus(item.verification_status)}`);
        });
    }

    return lines.join('\n');
}

/* ============================================================
   Phase 1 — 运行历史
   ============================================================ */

async function loadCommentaryRuns() {
    try {
        const runs = await apiCall('GET', '/api/commentary/runs?limit=30');
        renderRunsList(Array.isArray(runs) ? runs : []);
    } catch (error) {
        console.warn('commentary_runs_load_failed', error);
    }
}

function renderRunsList(runs = []) {
    const list = document.getElementById('commentary-history-list');
    if (!list) return;
    if (!runs.length) {
        list.innerHTML = '<p class="empty-state compact">暂无历史记录。</p>';
        return;
    }
    list.innerHTML = runs.map(run => {
        const time = run.created_at ? new Date(run.created_at).toLocaleString() : '--';
        const qualityLabel = {
            passed: '通过', warning: '提醒', blocked: '阻断', unknown: '未知',
        }[run.quality_status] || run.quality_status || '未知';
        const qualityClass = run.quality_status === 'passed' ? 'ready'
            : run.quality_status === 'warning' ? 'watch' : 'warn';
        return `
            <article class="commentary-history-item">
                <div class="commentary-history-meta">
                    <strong>${esc(run.recipe_title || run.recipe_id)}</strong>
                    <span data-quality="${qualityClass}">${esc(qualityLabel)}</span>
                    <small>${esc(run.model || '--')}</small>
                    <small>${esc(time)}</small>
                </div>
                <div class="commentary-history-stats">
                    <span>证据 ${run.evidence_count || 0} / 纳入 ${run.selected_evidence_count || 0}</span>
                    ${run.warnings?.length ? `<span>⚠ ${run.warnings.length} 条警告</span>` : ''}
                </div>
                <div class="commentary-history-actions">
                    <button class="btn-secondary" type="button" data-run-id="${esc(run.run_id)}" data-run-action="view"><i class="codicon codicon-eye"></i> 查看</button>
                    <button class="btn-secondary" type="button" data-run-id="${esc(run.run_id)}" data-run-action="restore"><i class="codicon codicon-history"></i> 恢复</button>
                </div>
            </article>
        `;
    }).join('');
}

async function viewRunDraft(runId) {
    try {
        const runs = await apiCall('GET', '/api/commentary/runs?limit=50');
        const run = Array.isArray(runs) ? runs.find(r => r.run_id === runId) : null;
        if (!run) {
            toast('未找到该记录', 'error');
            return;
        }
        const output = document.getElementById('commentary-draft-output');
        if (output) {
            output.innerHTML = markdownToHtml(run.draft_markdown || '');
        }
        setText('commentary-run-meta', run.model || '历史记录');
        setText('commentary-overview-draft-state', `历史 · ${new Date(run.created_at).toLocaleString()}`);
        switchCommentaryWorkspace('draft');
        toast('已加载历史草稿（只读）', 'success');
    } catch (error) {
        console.error('[commentary] failed to view run', error);
        toast('加载历史记录失败', 'error');
    }
}

async function restoreRunDraft(runId) {
    try {
        const runs = await apiCall('GET', '/api/commentary/runs?limit=50');
        const run = Array.isArray(runs) ? runs.find(r => r.run_id === runId) : null;
        if (!run) {
            toast('未找到该记录', 'error');
            return;
        }
        const sections = parseMarkdownSections(run.draft_markdown || '');
        currentDraftSections = sections.map((section, index) => ({
            heading: section.heading || `段落 ${index + 1}`,
            content: section.content || '',
        }));
        renderDraftSections({ sections: currentDraftSections, draft_markdown: run.draft_markdown });
        const output = document.getElementById('commentary-draft-output');
        if (output) {
            output.innerHTML = markdownToHtml(run.draft_markdown || '');
        }
        setText('commentary-run-meta', `恢复 · ${run.model || '--'}`);
        updateCommentaryWorkflow({ draft: 'done', quality: 'active' });
        switchCommentaryWorkspace('draft');
        toast('已恢复草稿，可以继续编辑', 'success');
    } catch (error) {
        console.error('[commentary] failed to restore run', error);
        toast('恢复历史记录失败', 'error');
    }
}

/* ============================================================
   Phase 1 — 上下文时间戳 + 自动刷新
   ============================================================ */

function updateContextTimestamp(pack) {
    const el = document.getElementById('commentary-context-time');
    if (!el) return;
    if (pack?.generated_at) {
        el.textContent = new Date(pack.generated_at).toLocaleTimeString();
        el.title = `完整时间：${new Date(pack.generated_at).toLocaleString()}`;
    } else if (pack) {
        el.textContent = new Date().toLocaleTimeString();
    }
}

export function toggleAutoRefresh() {
    const btn = document.getElementById('btn-commentary-auto-refresh');
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
        if (btn) {
            btn.classList.remove('active');
            btn.title = '每5分钟自动刷新上下文';
        }
        toast('自动刷新已关闭', 'success');
    } else {
        autoRefreshInterval = setInterval(() => {
            loadCommentaryContext({ force: true, silent: true });
        }, 5 * 60 * 1000);
        if (btn) {
            btn.classList.add('active');
            btn.title = '自动刷新已开启（每5分钟）';
        }
        toast('自动刷新已开启（每5分钟）', 'success');
    }
}

/* ============================================================
   Phase 1 — 生成进度指示
   ============================================================ */

function showGenerationOverlay(step = '正在生成草稿...') {
    const overlay = document.getElementById('commentary-generation-overlay');
    const stepEl = document.getElementById('commentary-generation-step');
    if (overlay) overlay.hidden = false;
    if (stepEl) stepEl.textContent = step;
}

function hideGenerationOverlay() {
    const overlay = document.getElementById('commentary-generation-overlay');
    if (overlay) overlay.hidden = true;
}

function saveToVersionHistory(response) {
    versionHistory.push({
        time: new Date().toISOString(),
        model: response?.model || 'rule_based_fallback',
        draftMarkdown: response?.draft_markdown || '',
        sections: currentDraftSections.map(s => ({ heading: s.heading, content: s.content })),
    });
    if (versionHistory.length > 20) versionHistory.shift();
}

export function initCommentaryCenter() {
    if (initialized) return;
    initialized = true;
    bindCommentaryActions();
    renderActiveRecipe();
    updateCommentaryWorkflow();
    loadCommentaryRecipes().finally(() => loadCommentaryContext());
    loadCommentaryRuns();
}
