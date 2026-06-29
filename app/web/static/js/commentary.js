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
}

function activeRecipe() {
    return COMMENTARY_RECIPES.find(recipe => recipe.id === activeRecipeId) || COMMENTARY_RECIPES[0];
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

    if (count) count.textContent = `${COMMENTARY_RECIPES.length} 类`;
    list.innerHTML = COMMENTARY_RECIPES.map(recipe => `
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
}

export function selectCommentaryTemplate(recipeId) {
    activeRecipeId = COMMENTARY_RECIPES.some(recipe => recipe.id === recipeId) ? recipeId : COMMENTARY_RECIPES[0].id;
    renderActiveRecipe();
    loadCommentaryContext({ force: true });
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

export async function loadCommentaryContext(options = {}) {
    const recipe = activeRecipe();
    if (!options.force && latestContextRecipeId === recipe.id) return;
    if (isLoadingContext) return currentContextPromise;

    isLoadingContext = true;
    setContextStatus('加载上下文...', 'loading');
    currentContextPromise = (async () => {
        const context = await apiCall(
            'GET',
            `/api/commentary/context?recipe_id=${encodeURIComponent(recipe.id)}`
        );
        latestContextPack = context;
        setTextareaValue('commentary-data-snapshot', context.data_snapshot_text);
        setTextareaValue('commentary-evidence-pack', context.evidence_pack_text);
        renderAttributionSignals(context.attribution_signals);
        latestContextRecipeId = recipe.id;
        setContextStatus('上下文已更新', 'ready');
        if (options.force) toast('点评上下文已更新', 'success');
        return context;
    })();

    try {
        return await currentContextPromise;
    } catch (error) {
        console.error('[commentary] failed to load context', error);
        setContextStatus('上下文加载失败', 'error');
        if (options.force) toast(`点评上下文加载失败：${error.message || error}`, 'error');
        return null;
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
}

function buildDraftRequest(recipe) {
    return {
        recipe_id: recipe.id,
        data_snapshot_text: readField('commentary-data-snapshot'),
        evidence_pack_text: readField('commentary-evidence-pack'),
        subjective_judgement: readField('commentary-subjective-judgement'),
        evidence_items: Array.isArray(latestContextPack?.evidence_items) ? latestContextPack.evidence_items : [],
        attribution_signals: Array.isArray(latestContextPack?.attribution_signals) ? latestContextPack.attribution_signals : [],
    };
}

export async function generateCommentaryDraft() {
    const recipe = activeRecipe();
    try {
        if (isLoadingContext) await currentContextPromise;
        if (!latestContextPack || latestContextRecipeId !== recipe.id) {
            await loadCommentaryContext();
        }
        const response = await apiCall(
            'POST',
            '/api/commentary/draft',
            buildDraftRequest(recipe)
        );
        renderBackendDraft(response);
        toast('点评草稿已生成', 'success');
    } catch (error) {
        console.error('[commentary] failed to generate draft', error);
        const draft = buildCommentaryDraft(
            recipe,
            readField('commentary-data-snapshot'),
            readField('commentary-evidence-pack'),
            readField('commentary-subjective-judgement')
        );
        renderDraft(draft);
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

export function initCommentaryCenter() {
    if (initialized) return;
    initialized = true;
    bindCommentaryActions();
    renderActiveRecipe();
    loadCommentaryContext();
}
