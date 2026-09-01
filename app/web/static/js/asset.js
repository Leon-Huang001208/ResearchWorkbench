/* ============================================================
   AlphaFoundry — Asset Analysis Module
   ============================================================ */

import { apiCall, toast, esc, getChartColors, fmtVolume, fmtAmount, fmtMarketCap, fmtRevenue, fmtNetProfit } from './core.js';

// ─── Chart Instances ───────────────────────────────────────
let chartKLine = null;
let chartCapitalFlow = null;
let chartChipDist = null;
let chartTopicTrend = null;
const DEFAULT_TIME_RANGE = '1Y';
let currentTimeRange = DEFAULT_TIME_RANGE;
let currentCanonicalId = null;
let currentAssetAnalysisData = null;
let currentAssetObserveMode = 'equity';
let currentTopicObservation = null;
let currentKLineBars = [];
let currentDisplayKLineBars = [];
let currentKLinePeriod = 'D';
let showAllKLineBars = false;
let currentOverlayMode = 'ma';
let currentMainPriceRange = null;
let lastChipUpdateIndex = null;
let chipUpdateFrame = null;
const visibleMA = { ma5: true, ma10: true, ma20: true, ma60: true, ma120: true, ma250: true, boll: true };

// ─── Search State ──────────────────────────────────────────
let assetSearchDebounceTimer = null;
let selectedAssetIndex = -1;
let assetSearchResults = [];
let assetSearchRequestSeq = 0;

const ASSET_SEARCH_SEEDS = [
    {
        canonical_id: '600519.SH',
        symbol: '600519.SH',
        raw_code: '600519',
        name: '贵州茅台',
        display_name: '贵州茅台',
        asset_type: 'equity',
        exchange: 'SH',
        market: 'A-share',
        industry: '食品饮料',
        pinyin_abbr: 'gzmt',
        source: 'client_seed',
    },
    {
        canonical_id: '399436.SZ',
        symbol: '399436.SZ',
        raw_code: '399436',
        name: '绿色煤炭',
        display_name: '绿色煤炭',
        asset_type: 'index',
        exchange: 'SZ',
        market: 'A-share',
        industry: '煤炭',
        pinyin_abbr: 'lsmt',
        source: 'client_seed',
    },
];

const THEME_OBSERVATION_PRESETS = {
    robot: {
        aliases: ['宇树机器人', '人形机器人', '机器人', '减速器', '工业母机'],
        tags: ['机器人', '人形机器人', '智能制造', 'AI+硬件'],
        index: { name: '宇树机器人指数', code: '8841946.WI', value: 1842.56 },
        heat: 86.7,
        attention: 234512,
        summary: '机器人链由整机、执行器、减速器、传感器和控制系统共同驱动，适合从指数、ETF 与核心成分股三层拆解。',
        relatedAssets: [
            { name: '机器人ETF南方', code: '159258.SZ', type: 'ETF', price: 1.234, change_pct: 2.64, meta: '规模 65.21亿' },
            { name: '机器人ETF', code: '562500.SH', type: 'ETF', price: 1.201, change_pct: 2.58, meta: '规模 38.47亿' },
            { name: '中证机器人指数', code: 'H30590.CSI', type: '指数', price: 4123.45, change_pct: 7.32, meta: '主题基准' },
            { name: '国证机器人产业指数', code: '980022.CNI', type: '指数', price: 3876.21, change_pct: 7.18, meta: '产业链映射' },
        ],
        components: [
            { name: '机器人ETF南方', code: '159258.SZ', change_pct: 2.64, amount: '40.22亿', contribution: 1.23, segment: 'ETF' },
            { name: '三花智控', code: '002050.SZ', change_pct: 4.18, amount: '28.76亿', contribution: 0.98, segment: '执行器' },
            { name: '拓普集团', code: '601689.SH', change_pct: 3.35, amount: '25.13亿', contribution: 0.86, segment: '执行器' },
            { name: '绿的谐波', code: '688017.SH', change_pct: 6.72, amount: '18.65亿', contribution: 0.74, segment: '减速器' },
            { name: '中大力德', code: '002896.SZ', change_pct: 4.36, amount: '12.64亿', contribution: 0.56, segment: '减速器' },
            { name: '鸣志电器', code: '603728.SH', change_pct: 2.81, amount: '11.23亿', contribution: 0.49, segment: '电机' },
        ],
        news: [
            { title: '宇树科技发布第三代人形机器人 H3，运动能力与交互体验双升级', source: '财联社', time: '10:45' },
            { title: '特斯拉 Optimus 量产计划提前至 2026Q4，供应链订单加速释放', source: '券商中国', time: '09:58' },
            { title: '工信部：加快推动人形机器人创新发展，支持关键技术攻关', source: '工信部网站', time: '07-03 06:32' },
        ],
        notes: [
            '板块今日强势上攻，受新品发布与量产预期共同驱动。',
            '核心标的成交活跃，机器人ETF资金持续净流入。',
            '关注减速器、执行器等核心零部件环节的业绩兑现节奏。',
            '短期波动加大，留意高位回落风险与主题轮动节奏。',
        ],
    },
    default: {
        aliases: [],
        tags: ['主题', 'Wind热门概念', '实时异动'],
        index: { name: '主题指数', code: '--', value: 1000 },
        heat: 72.4,
        attention: 98620,
        summary: '该主题来自 Wind 热门概念矩阵，适合继续拆解相关 ETF、指数、成分股贡献和新闻催化。',
        relatedAssets: [
            { name: '相关主题ETF', code: '--', type: 'ETF', price: 1.000, change_pct: 1.28, meta: '等待映射' },
            { name: '相关概念指数', code: '--', type: '指数', price: 1000.00, change_pct: 1.12, meta: '等待映射' },
        ],
        components: [
            { name: '核心成分一', code: '--', change_pct: 2.18, amount: '--', contribution: 0.72, segment: '核心资产' },
            { name: '核心成分二', code: '--', change_pct: 1.67, amount: '--', contribution: 0.54, segment: '产业链' },
            { name: '核心成分三', code: '--', change_pct: 1.12, amount: '--', contribution: 0.39, segment: '弹性标的' },
        ],
        news: [
            { title: '主题热度上升，资金关注相关产业链方向', source: '市场监控', time: '实时' },
            { title: '相关 ETF 与指数同步异动，等待进一步拆解成分贡献', source: 'AlphaFoundry', time: '实时' },
        ],
        notes: [
            '该主题来自市场矩阵实时异动。',
            '需要进一步确认成分股贡献和资金流向。',
            '若进入观察池，可生成信号并跟踪后续催化。',
        ],
    },
};

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const toFiniteNumber = (value) => {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
};
const fmtFixed = (value, digits = 2, suffix = '') =>
    isFiniteNumber(value) ? `${value.toFixed(digits)}${suffix}` : '--';
const normalizeSearchText = (value) => String(value || '').trim().toLowerCase().replace(/\s+/g, '');
const KLINE_MA_CONFIGS = [
    { key: 'ma5', name: 'MA5', color: '#ed8936' },
    { key: 'ma10', name: 'MA10', color: '#3182ce' },
    { key: 'ma20', name: 'MA20', color: '#805ad5' },
    { key: 'ma60', name: 'MA60', color: '#10b981' },
    { key: 'ma120', name: 'MA120', color: '#22d3ee' },
    { key: 'ma250', name: 'MA250', color: '#a3a3a3' },
];
const BOLL_CONFIGS = [
    { key: 'boll_upper', name: 'BOLL上轨', label: 'UPPER', color: '#ffff00', lineColor: '#ffff00' },
    { key: 'boll_middle', name: 'BOLL中轨', label: 'MID', color: '#d9d9d9', lineColor: '#d9d9d9' },
    { key: 'boll_lower', name: 'BOLL下轨', label: 'LOWER', color: '#ff00ff', lineColor: '#ff00ff' },
];

function movingAverageAt(bars, index, period, key = 'close') {
    const start = Math.max(0, index - period + 1);
    const values = bars
        .slice(start, index + 1)
        .map(bar => toFiniteNumber(bar[key]))
        .filter(value => value !== null);
    if (!values.length) return null;
    return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function formatDateKey(dateValue, period) {
    const date = new Date(`${String(dateValue).slice(0, 10)}T00:00:00`);
    if (Number.isNaN(date.getTime())) return String(dateValue);
    const year = date.getFullYear();
    if (period === 'M') return `${year}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    const day = new Date(Date.UTC(year, date.getMonth(), date.getDate()));
    const dayNum = day.getUTCDay() || 7;
    day.setUTCDate(day.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(day.getUTCFullYear(), 0, 1));
    const week = Math.ceil((((day - yearStart) / 86400000) + 1) / 7);
    return `${day.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function aggregatePriceBars(priceBars, period) {
    if (period === 'D') return priceBars;
    const groups = [];
    let currentKey = null;
    let current = null;

    priceBars.forEach(bar => {
        const key = formatDateKey(bar.date, period);
        if (key !== currentKey) {
            currentKey = key;
            current = {
                ...bar,
                date: key,
                source_end_date: bar.date,
                open: bar.open,
                high: bar.high,
                low: bar.low,
                close: bar.close,
                volume: bar.volume || 0,
                amount: bar.amount || 0,
            };
            groups.push(current);
            return;
        }

        current.source_end_date = bar.date;
        current.high = Math.max(toFiniteNumber(current.high) ?? -Infinity, toFiniteNumber(bar.high) ?? -Infinity);
        current.low = Math.min(toFiniteNumber(current.low) ?? Infinity, toFiniteNumber(bar.low) ?? Infinity);
        current.close = bar.close;
        current.volume = (toFiniteNumber(current.volume) || 0) + (toFiniteNumber(bar.volume) || 0);
        current.amount = (toFiniteNumber(current.amount) || 0) + (toFiniteNumber(bar.amount) || 0);
        current.turnover = toFiniteNumber(bar.turnover);
    });

    return groups.map((bar, index, bars) => ({
        ...bar,
        ma5: movingAverageAt(bars, index, 5),
        ma10: movingAverageAt(bars, index, 10),
        ma20: movingAverageAt(bars, index, 20),
        ma60: movingAverageAt(bars, index, 60),
        ma120: movingAverageAt(bars, index, 120),
        ma250: movingAverageAt(bars, index, 250),
    }));
}

function prepareKLineBars(priceBars) {
    const sortedBars = [...(priceBars || [])].sort((a, b) => String(a.date).localeCompare(String(b.date)));
    const periodBars = aggregatePriceBars(sortedBars, currentKLinePeriod);
    return periodBars.map((bar, index, bars) => ({
        ...bar,
        ma5: toFiniteNumber(bar.ma5) ?? movingAverageAt(bars, index, 5),
        ma10: toFiniteNumber(bar.ma10) ?? movingAverageAt(bars, index, 10),
        ma20: toFiniteNumber(bar.ma20) ?? movingAverageAt(bars, index, 20),
        ma60: toFiniteNumber(bar.ma60) ?? movingAverageAt(bars, index, 60),
        ma120: toFiniteNumber(bar.ma120) ?? movingAverageAt(bars, index, 120),
        ma250: toFiniteNumber(bar.ma250) ?? movingAverageAt(bars, index, 250),
    }));
}

function getInitialZoomStart(count) {
    return showAllKLineBars || count <= 120 ? 0 : Math.max(0, ((count - 120) / count) * 100);
}

function getVisibleBarsForInitialRange(bars) {
    if (showAllKLineBars || bars.length <= 120) return bars;
    return bars.slice(-120);
}

function calculatePriceRangeForBars(bars) {
    const values = [];
    bars.forEach(bar => {
        [bar.high, bar.low].forEach(value => {
            const number = toFiniteNumber(value);
            if (number !== null) values.push(number);
        });
        if (currentOverlayMode === 'ma') {
            ['ma5', 'ma10', 'ma20', 'ma60', 'ma120', 'ma250'].forEach(key => {
                const number = toFiniteNumber(bar[key]);
                if (number !== null) values.push(number);
            });
        }
        if (currentOverlayMode === 'boll') {
            ['boll_upper', 'boll_middle', 'boll_lower'].forEach(key => {
                const number = toFiniteNumber(bar[key]);
                if (number !== null) values.push(number);
            });
        }
    });
    if (!values.length) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max((max - min) * 0.08, Math.max(max * 0.005, 0.01));
    return {
        min: Number((min - padding).toFixed(2)),
        max: Number((max + padding).toFixed(2)),
    };
}

function getZoomIndexRange(count, startPercent = 0, endPercent = 100) {
    if (count <= 0) return [0, 0];
    const parsedStart = Number(startPercent);
    const parsedEnd = Number(endPercent);
    const start = Math.max(0, Math.min(100, Number.isFinite(parsedStart) ? parsedStart : 0));
    const end = Math.max(start, Math.min(100, Number.isFinite(parsedEnd) ? parsedEnd : 100));
    const startIndex = Math.max(0, Math.floor((start / 100) * count));
    const endIndex = Math.min(count - 1, Math.ceil((end / 100) * count) - 1);
    return [startIndex, Math.max(startIndex, endIndex)];
}

function getKLineVisibleRightIndex(count, zoomState = {}) {
    if (count <= 0) return 0;
    const endPercent = Number(zoomState.end);
    if (Number.isFinite(endPercent)) {
        return getZoomIndexRange(count, zoomState.start, endPercent)[1];
    }
    const endValue = Number(zoomState.endValue);
    if (Number.isFinite(endValue)) {
        return Math.min(Math.max(Math.round(endValue), 0), count - 1);
    }
    return count - 1;
}

function applyVisiblePriceRange(startPercent, endPercent, updateCharts = true) {
    const bars = currentDisplayKLineBars || [];
    if (!bars.length) return null;
    const [startIndex, endIndex] = getZoomIndexRange(bars.length, startPercent, endPercent);
    const range = calculatePriceRangeForBars(bars.slice(startIndex, endIndex + 1));
    if (!range) return null;
    currentMainPriceRange = range;
    if (updateCharts && chartKLine) {
        chartKLine.setOption({
            yAxis: [
                { min: range.min, max: range.max },
                {},
                {},
                {},
                {},
            ],
        }, false);
    }
    if (updateCharts && chartChipDist) {
        chartChipDist.setOption({ yAxis: { min: range.min, max: range.max } }, false);
    }
    return range;
}

function ensureMainOverlayLabel(container) {
    let label = container.querySelector('.kline-main-overlay-label');
    if (!label) {
        label = document.createElement('div');
        label.className = 'kline-main-overlay-label';
        container.appendChild(label);
    }
    return label;
}

function renderMainOverlayLabel(container, bar) {
    const label = ensureMainOverlayLabel(container);
    if (!bar) {
        label.textContent = '';
        return;
    }
    const parts = [];
    const add = (text, color = '#d1d5db') => {
        parts.push(`<span style="color:${color}">${esc(text)}</span>`);
    };

    if (currentOverlayMode === 'ma') {
        KLINE_MA_CONFIGS.forEach(cfg => {
            add(`${cfg.name} ${fmtFixed(toFiniteNumber(bar[cfg.key]))}`, cfg.color);
        });
    } else if (currentOverlayMode === 'boll') {
        add('BOLL(20)', '#d1d5db');
        BOLL_CONFIGS.forEach(cfg => {
            add(`${cfg.label} ${fmtFixed(toFiniteNumber(bar[cfg.key]))}`, cfg.color);
        });
    } else {
        add('K线', '#d1d5db');
    }
    label.innerHTML = parts.join('');
}

function formatKLineDate(dateValue) {
    const text = String(dateValue || '--');
    return /^\d{4}-\d{2}-\d{2}$/.test(text) ? text.replaceAll('-', '/') : text;
}

function calculateBarAveragePrice(bar) {
    const amount = toFiniteNumber(bar?.amount);
    const volume = toFiniteNumber(bar?.volume);
    const low = toFiniteNumber(bar?.low);
    const high = toFiniteNumber(bar?.high);
    if (amount !== null && volume > 0) {
        const average = amount / volume;
        const lowerBound = low !== null ? low * 0.5 : 0;
        const upperBound = high !== null ? high * 1.5 : Infinity;
        if (average > lowerBound && average < upperBound) return average;
    }
    return toFiniteNumber(bar?.vwap)
        ?? toFiniteNumber(bar?.avg_price)
        ?? toFiniteNumber(bar?.average_price)
        ?? toFiniteNumber(bar?.close);
}

function calculateBarChange(bar, index, bars) {
    const close = toFiniteNumber(bar?.close);
    const open = toFiniteNumber(bar?.open);
    const prevClose = index > 0 ? toFiniteNumber(bars[index - 1]?.close) : null;
    const base = prevClose ?? open;
    if (close === null || base === null || base === 0) {
        return { change: null, pct: null, className: '' };
    }
    const change = close - base;
    return {
        change,
        pct: (change / base) * 100,
        className: change >= 0 ? 'price-up' : 'price-down',
    };
}

function getQuotePriceClass(value, reference) {
    const price = toFiniteNumber(value);
    const base = toFiniteNumber(reference);
    if (price === null || base === null) return '';
    return price >= base ? 'price-up' : 'price-down';
}

function calculateBarAmplitude(bar, index, bars) {
    const amplitude = toFiniteNumber(bar?.amplitude)
        ?? toFiniteNumber(bar?.amplitude_pct);
    if (amplitude !== null) return amplitude;
    const high = toFiniteNumber(bar?.high);
    const low = toFiniteNumber(bar?.low);
    const open = toFiniteNumber(bar?.open);
    const prevClose = index > 0 ? toFiniteNumber(bars[index - 1]?.close) : null;
    const base = prevClose ?? open;
    if (high === null || low === null || base === null || base === 0) return null;
    return ((high - low) / base) * 100;
}

function renderKLineQuoteForBar(bar, index, bars) {
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    const setClass = (id, className) => {
        const el = document.getElementById(id);
        if (el) el.className = className || '';
    };
    const basic = currentAssetAnalysisData?.basic_info || {};
    const quoteBars = bars || [];
    const safeIndex = Math.min(Math.max(Number(index) || 0, 0), Math.max(quoteBars.length - 1, 0));
    const activeBar = bar || quoteBars[safeIndex] || {};
    const change = calculateBarChange(activeBar, safeIndex, quoteBars);
    const avgPrice = calculateBarAveragePrice(activeBar);
    const amplitude = calculateBarAmplitude(activeBar, safeIndex, quoteBars);
    const changeSign = change.change !== null && change.change >= 0 ? '+' : '';
    const priceReference = safeIndex > 0 ? toFiniteNumber(quoteBars[safeIndex - 1]?.close) : toFiniteNumber(activeBar.open);

    setText('kline-quote-code', basic.symbol || currentAssetAnalysisData?.canonical_id || '--');
    setText('kline-quote-name', basic.name || '--');
    setText('kline-quote-date', formatKLineDate(activeBar.date));
    setText('kline-quote-close', fmtFixed(toFiniteNumber(activeBar.close)));
    setText('kline-quote-change-pct', change.pct !== null ? `${changeSign}${change.pct.toFixed(2)}%` : '--');
    setText('kline-quote-change', change.change !== null ? `(${changeSign}${change.change.toFixed(2)})` : '(--)');
    setText('kline-quote-open', fmtFixed(toFiniteNumber(activeBar.open)));
    setText('kline-quote-high', fmtFixed(toFiniteNumber(activeBar.high)));
    setText('kline-quote-low', fmtFixed(toFiniteNumber(activeBar.low)));
    setText('kline-quote-avg', fmtFixed(avgPrice));
    setText('kline-quote-volume', fmtVolume(activeBar.volume));
    setText('kline-quote-turnover', fmtFixed(toFiniteNumber(activeBar.turnover), 2, '%'));
    setText('kline-quote-amplitude', fmtFixed(amplitude, 2, '%'));
    setText('kline-quote-amount', fmtAmount(activeBar.amount));

    ['kline-quote-close', 'kline-quote-change-pct', 'kline-quote-change'].forEach(id => {
        setClass(id, change.className);
    });
    setClass('kline-quote-open', getQuotePriceClass(activeBar.open, priceReference));
    setClass('kline-quote-high', getQuotePriceClass(activeBar.high, priceReference));
    setClass('kline-quote-low', getQuotePriceClass(activeBar.low, priceReference));
    setClass('kline-quote-avg', getQuotePriceClass(avgPrice, priceReference));
}

function switchAssetObserveMode(mode = 'equity') {
    const normalizedMode = ['equity', 'etf', 'index', 'theme'].includes(mode) ? mode : 'equity';
    currentAssetObserveMode = normalizedMode;
    document.querySelectorAll('[data-asset-mode]').forEach(button => {
        button.classList.toggle('active', button.dataset.assetMode === normalizedMode);
    });
    const topicResult = document.getElementById('asset-topic-result');
    const assetResult = document.getElementById('asset-result');
    if (topicResult) topicResult.classList.toggle('hidden', normalizedMode !== 'theme');
    if (assetResult) {
        const hasAssetData = Boolean(currentAssetAnalysisData);
        assetResult.classList.toggle('hidden', normalizedMode === 'theme' || !hasAssetData);
    }
    if (normalizedMode === 'theme' && currentTopicObservation) {
        setTimeout(() => {
            if (chartTopicTrend) chartTopicTrend.resize();
        }, 40);
    }
}

function openThemeObservation(topic = {}) {
    const observation = buildThemeObservation(topic);
    currentTopicObservation = observation;
    const input = document.getElementById('asset-code');
    if (input) {
        input.value = observation.name;
        delete input.dataset.selectedSymbol;
    }
    hideAssetSearchDropdown();
    switchAssetObserveMode('theme');
    renderThemeObservation(observation);
}

function findThemePreset(name = '') {
    const normalizedName = normalizeSearchText(name);
    return Object.values(THEME_OBSERVATION_PRESETS).find(preset =>
        (preset.aliases || []).some(alias => normalizedName.includes(normalizeSearchText(alias)))
    ) || THEME_OBSERVATION_PRESETS.default;
}

function buildThemeObservation(topic = {}) {
    const name = topic.name || topic.theme_name || '主题观察';
    const preset = findThemePreset(name);
    const changePct = toFiniteNumber(topic.change_pct) ?? toFiniteNumber(topic.changePct) ?? 0;
    const sign = changePct >= 0 ? 1 : -1;
    const value = toFiniteNumber(preset.index?.value) || 1000;
    const indexCode = topic.wind_code || windCodeFromSectorId(topic.sector_id) || preset.index?.code || '--';
    return {
        ...preset,
        name,
        change_pct: changePct,
        view_label: topic.view_label || topic.viewLabel || 'Wind热门概念',
        sector_id: topic.sector_id || '',
        rank: topic.rank || '--',
        updated_at: topic.updated_at || topic.fetched_at || new Date().toISOString(),
        index: {
            ...(preset.index || {}),
            code: indexCode,
            value: Number((value * (1 + Math.abs(changePct) / 900)).toFixed(2)),
        },
        intraday: buildThemeIntradaySeries(value, changePct || sign * 1.2),
    };
}

function windCodeFromSectorId(sectorId = '') {
    const text = String(sectorId || '');
    if (!text.startsWith('wind-')) return '';
    return text.slice('wind-'.length).replace(/-/g, '.');
}

function buildThemeIntradaySeries(baseValue, changePct) {
    const points = [];
    const start = baseValue / (1 + changePct / 100);
    for (let i = 0; i < 36; i += 1) {
        const progress = i / 35;
        const wave = Math.sin(progress * Math.PI * 3) * 0.16 + Math.cos(progress * Math.PI * 7) * 0.07;
        const drift = changePct * progress;
        const value = start * (1 + (drift + wave) / 100);
        points.push({
            time: i < 24
                ? `${String(9 + Math.floor((30 + i * 5) / 60)).padStart(2, '0')}:${String((30 + i * 5) % 60).padStart(2, '0')}`
                : `${String(13 + Math.floor((i - 24) * 5 / 60)).padStart(2, '0')}:${String(((i - 24) * 5) % 60).padStart(2, '0')}`,
            value: Number(value.toFixed(2)),
            volume: Math.round(5 + Math.abs(Math.sin(i * 0.7)) * 16 + progress * 8),
        });
    }
    return points;
}

function renderThemeObservation(topic) {
    const setText = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };
    const change = toFiniteNumber(topic.change_pct) || 0;
    const changeClass = change >= 0 ? 'price-up' : 'price-down';
    const sign = change > 0 ? '+' : '';
    setText('asset-topic-name', topic.name);
    setText('asset-topic-badge', topic.view_label);
    setText('asset-topic-rank', topic.rank === '--' ? '--' : `#${topic.rank}`);
    setText('asset-topic-updated', formatTopicUpdatedAt(topic.updated_at));
    setText('asset-topic-heat', fmtFixed(toFiniteNumber(topic.heat), 1));
    setText('asset-topic-attention', formatInteger(topic.attention));
    setText('asset-topic-summary', topic.summary);
    setText('asset-topic-index-label', `${topic.index?.name || '概念指数'} ${topic.index?.code || '--'}`);
    setText('asset-topic-component-count', `${(topic.components || []).length} 个核心样本`);
    const changeEl = document.getElementById('asset-topic-change');
    if (changeEl) {
        changeEl.className = `asset-topic-change ${changeClass}`;
        changeEl.textContent = `${sign}${change.toFixed(2)}%`;
    }
    renderTopicTags(topic.tags || []);
    renderTopicRelatedAssets(topic.relatedAssets || [], change);
    renderTopicComponents(topic.components || []);
    renderTopicNews(topic.news || []);
    renderTopicNotes(topic.notes || []);
    renderTopicTrendChart(topic);
}

function formatTopicUpdatedAt(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function formatInteger(value) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return Math.round(num).toLocaleString();
}

function renderTopicTags(tags) {
    const container = document.getElementById('asset-topic-tags');
    if (!container) return;
    container.innerHTML = tags.map(tag => `<span>${esc(tag)}</span>`).join('');
}

function renderTopicRelatedAssets(items, themeChangePct) {
    const container = document.getElementById('asset-topic-related-assets');
    if (!container) return;
    container.innerHTML = items.map(item => {
        const change = toFiniteNumber(item.change_pct) ?? themeChangePct;
        const changeClass = change >= 0 ? 'price-up' : 'price-down';
        const sign = change > 0 ? '+' : '';
        return `
            <button type="button" class="asset-topic-related-item" onclick="analyzeAssetByCode('${esc(item.code || '')}')">
                <span>
                    <strong>${esc(item.name || '--')}</strong>
                    <small>${esc(item.code || '--')} · ${esc(item.type || '资产')}</small>
                    <em>${esc(item.meta || '')}</em>
                </span>
                <span class="asset-topic-related-price">
                    <strong>${fmtFixed(toFiniteNumber(item.price))}</strong>
                    <small class="${changeClass}">${sign}${change.toFixed(2)}%</small>
                </span>
            </button>
        `;
    }).join('');
}

function renderTopicComponents(items) {
    const tbody = document.getElementById('asset-topic-components');
    if (!tbody) return;
    const maxContribution = Math.max(...items.map(item => toFiniteNumber(item.contribution) || 0), 1);
    tbody.innerHTML = items.map((item, index) => {
        const change = toFiniteNumber(item.change_pct) || 0;
        const contribution = toFiniteNumber(item.contribution) || 0;
        const sign = change > 0 ? '+' : '';
        return `
            <tr>
                <td>${index + 1}</td>
                <td><button type="button" onclick="analyzeAssetByCode('${esc(item.code || '')}')">${esc(item.name || '--')}</button></td>
                <td>${esc(item.code || '--')}</td>
                <td class="${change >= 0 ? 'price-up' : 'price-down'}">${sign}${change.toFixed(2)}%</td>
                <td>${esc(item.amount || '--')}</td>
                <td>
                    <span class="asset-topic-contribution">
                        <strong>${contribution.toFixed(2)}</strong>
                        <i style="width:${Math.max(8, contribution / maxContribution * 100).toFixed(0)}%"></i>
                    </span>
                </td>
                <td>${esc(item.segment || '--')}</td>
            </tr>
        `;
    }).join('');
}

function renderTopicNews(items) {
    const container = document.getElementById('asset-topic-news');
    if (!container) return;
    container.innerHTML = items.map((item, index) => `
        <article class="asset-topic-news-item">
            <span>${index + 1}</span>
            <div>
                <strong>${esc(item.title || '--')}</strong>
                <small>${esc(item.source || '新闻')} · ${esc(item.time || '--')}</small>
            </div>
        </article>
    `).join('');
}

function renderTopicNotes(items) {
    const container = document.getElementById('asset-topic-notes');
    if (!container) return;
    container.innerHTML = items.map(item => `<li>${esc(item)}</li>`).join('');
}

function renderTopicTrendChart(topic, attempt = 0) {
    const container = document.getElementById('asset-topic-trend-chart');
    if (!container) return;
    if (typeof echarts === 'undefined') {
        container.innerHTML = '<div class="empty-state compact">走势组件加载中...</div>';
        if (attempt < 20) {
            setTimeout(() => {
                if (currentTopicObservation?.name === topic.name) {
                    renderTopicTrendChart(topic, attempt + 1);
                }
            }, 250);
        }
        return;
    }
    container.innerHTML = '';
    if (chartTopicTrend) {
        chartTopicTrend.dispose();
        chartTopicTrend = null;
    }
    const series = topic.intraday || [];
    const change = toFiniteNumber(topic.change_pct) || 0;
    const lineColor = change >= 0 ? '#ff453a' : '#30d158';
    chartTopicTrend = echarts.init(container, null, { devicePixelRatio: window.devicePixelRatio || 1 });
    chartTopicTrend.setOption({
        backgroundColor: 'transparent',
        grid: [{ left: 52, right: 44, top: 28, height: 190 }, { left: 52, right: 44, top: 235, height: 58 }],
        xAxis: [
            { type: 'category', data: series.map(item => item.time), axisLine: { lineStyle: { color: 'rgba(255,255,255,0.16)' } }, axisLabel: { color: '#8e8e93' } },
            { type: 'category', gridIndex: 1, data: series.map(item => item.time), axisLabel: { show: false }, axisTick: { show: false }, axisLine: { lineStyle: { color: 'rgba(255,255,255,0.12)' } } },
        ],
        yAxis: [
            { type: 'value', scale: true, axisLabel: { color: '#8e8e93' }, splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)' } } },
            { type: 'value', gridIndex: 1, axisLabel: { color: '#8e8e93' }, splitLine: { show: false } },
        ],
        tooltip: { trigger: 'axis', backgroundColor: 'rgba(28,28,30,0.94)', borderColor: 'rgba(255,255,255,0.14)', textStyle: { color: '#f5f5f7' } },
        series: [
            {
                type: 'line',
                data: series.map(item => item.value),
                symbol: 'none',
                smooth: true,
                lineStyle: { color: lineColor, width: 2 },
                areaStyle: { color: `${lineColor}33` },
            },
            {
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: series.map(item => item.volume),
                itemStyle: { color: lineColor },
                barWidth: '58%',
            },
        ],
    });
    setTimeout(() => chartTopicTrend?.resize(), 50);
}

async function searchAssets(query) {
    if (!query || query.length < 1) {
        assetSearchRequestSeq++;
        assetSearchResults = [];
        selectedAssetIndex = -1;
        hideAssetSearchDropdown();
        return;
    }
    const requestSeq = ++assetSearchRequestSeq;
    renderAssetSearchLoading(query);
    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}&types=symbol&_=${Date.now()}`);
        if (requestSeq !== assetSearchRequestSeq) return;
        assetSearchResults = mergeAssetSearchResults(results.symbols || [], getClientSeedAssetMatches(query));
        renderAssetSearchDropdown(assetSearchResults, query, results.symbol_search_status || {});
    } catch (e) {
        if (requestSeq !== assetSearchRequestSeq) return;
        console.error('Asset search failed:', e);
        const fallbackResults = getClientSeedAssetMatches(query);
        if (fallbackResults.length) {
            assetSearchResults = fallbackResults;
            renderAssetSearchDropdown(assetSearchResults, query, {
                stock_master_empty: true,
                search_error: e?.message || '搜索服务暂不可用',
            });
            return;
        }
        renderAssetSearchError(e);
    }
}

function mergeAssetSearchResults(apiResults, fallbackResults) {
    const merged = [];
    const seen = new Set();
    [...apiResults, ...fallbackResults].forEach(item => {
        const key = item.canonical_id || item.symbol;
        if (!key || seen.has(key)) return;
        seen.add(key);
        merged.push(item);
    });
    return merged;
}

function getClientSeedAssetMatches(query) {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) return [];
    return ASSET_SEARCH_SEEDS
        .map(item => {
            const match = scoreClientSeedAsset(item, normalizedQuery);
            return match.score > 0 ? { ...item, match_type: match.match_type, score: match.score } : null;
        })
        .filter(Boolean)
        .sort((a, b) => b.score - a.score || String(a.symbol).localeCompare(String(b.symbol)))
        .slice(0, 10);
}

function scoreClientSeedAsset(item, query) {
    const symbol = normalizeSearchText(item.symbol);
    const rawCode = normalizeSearchText(item.raw_code);
    const name = normalizeSearchText(item.name || item.display_name);
    const abbr = normalizeSearchText(item.pinyin_abbr);
    if (query === symbol || query === rawCode) return { match_type: 'exact_code', score: 1000 };
    if (symbol.startsWith(query) || rawCode.startsWith(query)) return { match_type: 'code_prefix', score: 900 };
    if (query === abbr) return { match_type: 'pinyin_exact', score: 850 };
    if (abbr.startsWith(query)) return { match_type: 'pinyin_prefix', score: 800 };
    if (name.includes(query)) return { match_type: 'name_contains', score: 700 };
    if (symbol.includes(query) || rawCode.includes(query)) return { match_type: 'code_contains', score: 600 };
    if (abbr.includes(query)) return { match_type: 'pinyin_contains', score: 500 };
    return { match_type: 'none', score: 0 };
}

function renderAssetSearchLoading(query) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    selectedAssetIndex = -1;
    dropdown.innerHTML = `
        <div class="search-result-group">
            <div class="group-title">标的</div>
            <div class="asset-search-status">正在搜索：${esc(query)}</div>
        </div>
    `;
    dropdown.classList.remove('hidden');
}

function renderAssetSearchError(error) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    selectedAssetIndex = -1;
    dropdown.innerHTML = `
        <div class="search-result-group">
            <div class="group-title">标的</div>
            <div class="asset-search-status is-error">搜索失败：${esc(error?.message || '请稍后重试')}</div>
        </div>
    `;
    dropdown.classList.remove('hidden');
}

function renderAssetSearchDropdown(results, query, status = {}) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;

    // 构建状态提示
    let statusHtml = '';
    if (status.search_error) {
        statusHtml += `<div class="asset-search-status is-error">搜索服务异常，已启用本地候选：${esc(status.search_error)}</div>`;
    } else if (status.stock_master_empty) {
        if (status.using_live_fallback) {
            statusHtml += '<div class="asset-search-status is-info">数据库未同步，已启用实时搜索（AKShare）。运行 <code>python scripts/bootstrap_market_data.py</code> 可导入全量 A 股数据。</div>';
        } else {
            statusHtml += '<div class="asset-search-status is-warning">标的词典未同步，仅显示内置候选。运行 <code>python scripts/bootstrap_market_data.py</code> 可导入全量 A 股数据。实时搜索暂不可用。</div>';
        }
    }
    if (!results || !results.length) {
        selectedAssetIndex = -1;
        dropdown.innerHTML = `
            <div class="search-result-group">
                <div class="group-title">标的</div>
                ${statusHtml}
                <div class="asset-search-status">没有匹配：${esc(query)}</div>
            </div>
        `;
        dropdown.classList.remove('hidden');
        return;
    }
    selectedAssetIndex = 0;
    let html = `<div class="search-result-group"><div class="group-title">标的</div>${statusHtml}`;
    results.forEach((item, index) => {
        const name = item.name || item.display_name || '';
        const industry = item.industry || item.asset_type || '';
        const canonicalId = item.canonical_id || item.symbol || '';
        const symbol = item.symbol || canonicalId;
        html += `
            <div class="search-result-item asset-result-item ${index === selectedAssetIndex ? 'selected' : ''}"
                 data-index="${index}"
                 data-canonical-id="${esc(canonicalId)}"
                 data-symbol="${esc(symbol)}"
                 data-name="${esc(name)}">
                <span class="asset-result-rank">${index + 1}</span>
                <div class="result-title">
                    <span class="asset-symbol">${esc(symbol)}</span>
                    <span class="asset-name">${esc(name)}</span>
                </div>
                ${industry ? `<div class="result-subtitle">${esc(industry)}</div>` : ''}
            </div>
        `;
    });
    html += '</div>';
    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
    dropdown.querySelectorAll('.asset-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const index = Number.parseInt(item.dataset.index, 10);
            selectAssetCandidate(assetSearchResults[index], item);
        });
        item.addEventListener('mouseenter', () => {
            dropdown.querySelectorAll('.asset-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            selectedAssetIndex = parseInt(item.dataset.index);
        });
    });
}

function selectAsset(symbol, element) {
    const candidate = assetSearchResults.find(item => (item.canonical_id || item.symbol) === symbol);
    if (candidate) return selectAssetCandidate(candidate, element);
    selectAssetCandidate({
        canonical_id: symbol,
        symbol: element?.dataset?.symbol || symbol,
        name: element?.dataset?.name || '',
    }, element);
}

function selectAssetCandidate(candidate, element) {
    if (!candidate) return;
    const input = document.getElementById('asset-code');
    const canonicalId = candidate.canonical_id || candidate.symbol || element?.dataset?.canonicalId;
    const name = candidate.name || candidate.display_name || element?.dataset?.name || '';
    const displaySymbol = candidate.symbol || element?.dataset?.symbol || canonicalId;
    if (input) {
        input.value = name ? `${displaySymbol} ${name}` : displaySymbol;
        input.dataset.selectedSymbol = canonicalId;
    }
    const candidateMode = String(candidate.asset_type || '').toLowerCase();
    if (['equity', 'etf', 'index'].includes(candidateMode)) {
        switchAssetObserveMode(candidateMode);
    }
    hideAssetSearchDropdown();
    analyzeAssetByCode(canonicalId);
}

function hideAssetSearchDropdown() {
    clearTimeout(assetSearchDebounceTimer);
    assetSearchRequestSeq++;
    selectedAssetIndex = -1;
    const dropdown = document.getElementById('asset-search-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
}

function handleAssetSearchKeydown(e) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    const items = dropdown.querySelectorAll('.asset-result-item');
    if (dropdown.classList.contains('hidden')) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const code = e.target.dataset.selectedSymbol || normalizeAssetInput(e.target.value);
            if (code) analyzeAssetByCode(code);
        }
        return;
    }
    if (e.key === 'ArrowDown') { e.preventDefault(); selectedAssetIndex = Math.min(selectedAssetIndex + 1, items.length - 1); updateSelectedItem(items); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selectedAssetIndex = Math.max(selectedAssetIndex - 1, 0); updateSelectedItem(items); }
    else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedAssetIndex >= 0 && items[selectedAssetIndex]) { items[selectedAssetIndex].click(); }
        else if (items.length > 0) { items[0].click(); }
        else {
            const fallbackCandidate = getClientSeedAssetMatches(e.target.value.trim())[0];
            if (fallbackCandidate) {
                selectAssetCandidate(fallbackCandidate);
                return;
            }
            const code = e.target.dataset.selectedSymbol || normalizeAssetInput(e.target.value);
            if (code) { hideAssetSearchDropdown(); analyzeAssetByCode(code); }
        }
    } else if (e.key === 'Escape') { hideAssetSearchDropdown(); }
}

function normalizeAssetInput(value) {
    return (value || '').trim().split(/\s+/)[0];
}

function updateSelectedItem(items) {
    items.forEach((item, index) => {
        item.classList.toggle('selected', index === selectedAssetIndex);
        if (index === selectedAssetIndex) item.scrollIntoView({ block: 'nearest' });
    });
}

async function analyzeAssetByCode(code, timeRange = null) {
    if (!code) return toast('请输入资产代码', 'error');
    hideAssetSearchDropdown();
    if (String(code).trim() === '--') return toast('该资产暂未映射代码', 'error');
    if (currentAssetObserveMode === 'theme') switchAssetObserveMode('equity');
    const range = timeRange || currentTimeRange || DEFAULT_TIME_RANGE;
    currentCanonicalId = code;
    currentTimeRange = range;
    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    if (result) result.classList.add('hidden');
    if (loading) loading.classList.remove('hidden');
    try {
        const snapshot = await apiCall(
            'GET',
            `/api/asset-observation/assets/${encodeURIComponent(code)}`
        );
        renderAssetAnalysisCard(normalizeAssetObservationSnapshot(snapshot));
        if (result) result.classList.remove('hidden');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        if (loading) loading.classList.add('hidden');
    }
}

function normalizeAssetObservationSnapshot(snapshot = {}) {
    const asset = snapshot.asset || {};
    const market = snapshot.market_data || {};
    const details = snapshot.type_payload || {};
    const currentPrice = market.last ?? market.close ?? market.nav ?? market.unit_nav ?? null;
    return {
        canonical_id: asset.asset_id,
        basic_info: {
            ...details,
            name: asset.display_name || asset.asset_id,
            symbol: snapshot.identifiers?.[0] || asset.asset_id,
            asset_type: asset.asset_type,
        },
        current_price: currentPrice,
        price_change: market.change ?? null,
        price_change_pct: market.change_pct ?? market.daily_return ?? null,
        volume: market.volume ?? null,
        amount: market.amount ?? null,
        turnover: market.turnover ?? null,
        price_bars: (snapshot.history || []).map(point => ({
            ...point,
            date: point.date || point.as_of,
        })),
        recent_events: snapshot.events || [],
        financial: {
            pe_ttm: market.pe ?? null,
            pb_mrq: market.pb ?? null,
        },
        themes: snapshot.themes || [],
        freshness_status: snapshot.freshness_status,
        quality_flags: snapshot.quality_flags || [],
        source_refs: snapshot.source_refs || [],
    };
}

async function analyzeAsset() {
    const input = document.getElementById('asset-code');
    const code = input?.dataset?.selectedSymbol || normalizeAssetInput(input?.value);
    if (!code) return toast('请输入资产代码', 'error');
    return analyzeAssetByCode(code);
}

function buildResearchPrefill() {
    const basic = currentAssetAnalysisData?.basic_info || {};
    const rawAssetType = String(basic.asset_type || currentAssetObserveMode || 'equity').toLowerCase();
    const typeMap = {
        stock: 'security',
        equity: 'security',
        etf: 'etf',
        index: 'index',
        theme: 'industry',
    };
    const subject_type = typeMap[rawAssetType] || typeMap[currentAssetObserveMode] || 'security';
    const input = document.getElementById('asset-code');
    const topic = currentAssetObserveMode === 'theme' ? currentTopicObservation : null;
    const subjectId = topic?.sector_id
        || topic?.index?.code
        || currentAssetAnalysisData?.canonical_id
        || input?.dataset?.selectedSymbol
        || normalizeAssetInput(input?.value);
    const displayName = topic?.name
        || basic.name
        || input?.value?.replace(subjectId || '', '').trim()
        || subjectId;
    const latestBar = currentAssetAnalysisData?.price_bars?.at?.(-1);
    const asOf = String(latestBar?.date || new Date().toISOString()).slice(0, 10);
    const templateMap = {
        security: 'a_share_deep_research',
        etf: 'index_research',
        index: 'index_research',
        industry: 'industry_research',
    };
    return {
        subject_type,
        subject_id: subjectId,
        display_name: displayName,
        as_of: asOf,
        template_key: templateMap[subject_type],
        question: displayName
            ? `请对${displayName}进行完整研究，验证核心驱动、估值、风险与失效条件。`
            : '',
        source_section: 'asset-analysis',
    };
}

function startResearchFromAsset() {
    const prefill = buildResearchPrefill();
    if (!prefill.subject_id) {
        toast('请先选择一个资产或主题', 'warning');
        return;
    }
    document.dispatchEvent(new CustomEvent('alphafoundry:open-research-center', {
        detail: prefill,
    }));
}

function renderAssetAnalysisCard(data) {
    currentAssetAnalysisData = data;
    currentKLineBars = data.price_bars || [];
    lastChipUpdateIndex = null;
    const basic = data.basic_info || {};
    const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    setText('asset-name', basic.name || data.canonical_id || '--');
    setText('asset-code-display', basic.symbol || data.canonical_id || '--');

    const priceClass = (data.price_change_pct || 0) >= 0 ? 'price-up' : 'price-down';
    const changePrefix = (data.price_change_pct || 0) >= 0 ? '+' : '';
    setText('asset-price', fmtFixed(data.current_price));
    const priceEl = document.getElementById('asset-price'); if (priceEl) priceEl.className = `asset-price ${priceClass}`;
    setText('asset-change', isFiniteNumber(data.price_change) ? `${changePrefix}${data.price_change.toFixed(2)}` : '--');
    const changeEl = document.getElementById('asset-change'); if (changeEl) changeEl.className = `asset-change ${priceClass}`;
    setText('asset-change-pct', isFiniteNumber(data.price_change_pct) ? `(${changePrefix}${data.price_change_pct.toFixed(2)}%)` : '--');
    const pctEl = document.getElementById('asset-change-pct'); if (pctEl) pctEl.className = `asset-change-pct ${priceClass}`;

    setText('asset-volume', fmtVolume(data.volume));
    setText('asset-amount', fmtAmount(data.amount));
    setText('asset-turnover', fmtFixed(data.turnover, 2, '%'));
    setText('asset-market-cap', fmtMarketCap(basic.market_cap));
    setText('asset-high-52w', fmtFixed(data.high_52w));
    setText('asset-low-52w', fmtFixed(data.low_52w));
    setText('kline-quote-code', basic.symbol || data.canonical_id || '--');
    setText('kline-quote-name', basic.name || '--');

    const fin = data.financial || {};
    setText('fin-pe', fmtFixed(fin.pe_ttm));
    setText('fin-pb', fmtFixed(fin.pb_mrq));
    setText('fin-roe', fmtFixed(fin.roe, 2, '%'));
    setText('fin-revenue', fmtRevenue(fin.revenue));
    setText('fin-net-profit', fmtNetProfit(fin.net_profit));
    setText('fin-gross-margin', fmtFixed(fin.gross_margin, 2, '%'));

    currentDisplayKLineBars = prepareKLineBars(currentKLineBars);
    renderKLineChart(currentDisplayKLineBars);
    renderCapitalFlowChart(data.capital_flow);
    renderShareholderList(data.top_10_shareholders || []);
    renderIndustryInfo(data.industry);
    renderEventListPanel(data.recent_events || []);
    renderMacroSensitivity(data.macro_sensitivity);
}

function setAssetAgentCommitteeStatus(text, state = 'idle') {
    const status = document.getElementById('asset-agent-committee-status');
    if (!status) return;
    status.textContent = text;
    status.className = `agent-committee-status ${state}`;
}

function resetAssetAgentCommittee() {
    const summary = document.getElementById('asset-agent-committee-summary');
    const views = document.getElementById('asset-agent-committee-views');
    setAssetAgentCommitteeStatus('分析中', 'loading');
    if (summary) summary.innerHTML = '<div class="empty-state">正在运行宏观、基本面、技术面 Agent...</div>';
    if (views) views.innerHTML = '';
}

function renderAssetAgentCommitteeError(message) {
    const summary = document.getElementById('asset-agent-committee-summary');
    const views = document.getElementById('asset-agent-committee-views');
    setAssetAgentCommitteeStatus('失败', 'error');
    if (summary) {
        summary.innerHTML = `<div class="agent-committee-error">${esc(message || '委员会分析失败')}</div>`;
    }
    if (views) views.innerHTML = '';
}

function renderAssetAgentCommittee(data) {
    const synthesis = data?.synthesis || {};
    const views = Array.isArray(data?.views) ? data.views : [];
    const summary = document.getElementById('asset-agent-committee-summary');
    const viewGrid = document.getElementById('asset-agent-committee-views');
    const finalView = synthesis.final_view || 'unknown';
    const confidence = isFiniteNumber(synthesis.confidence) ? `${Math.round(synthesis.confidence * 100)}%` : '--';

    setAssetAgentCommitteeStatus(directionLabel(finalView), finalView);
    if (summary) {
        const rationale = (synthesis.rationale || []).slice(0, 2).map(item => `<li>${esc(item)}</li>`).join('');
        const risks = (synthesis.risks || []).slice(0, 3).map(item => `<li>${esc(item)}</li>`).join('');
        const nextChecks = (synthesis.recommended_next_checks || []).slice(0, 3).map(item => `<li>${esc(item)}</li>`).join('');
        summary.innerHTML = `
            <div class="agent-committee-final">
                <div>
                    <span class="agent-committee-label">委员会结论</span>
                    <strong class="agent-committee-view ${directionClass(finalView)}">${esc(directionLabel(finalView))}</strong>
                </div>
                <div>
                    <span class="agent-committee-label">置信度</span>
                    <strong>${esc(confidence)}</strong>
                </div>
            </div>
            <p class="agent-committee-thesis">${esc(synthesis.thesis || '暂无委员会论点')}</p>
            <div class="agent-committee-lists">
                <div><span>依据</span><ul>${rationale || '<li>暂无</li>'}</ul></div>
                <div><span>风险</span><ul>${risks || '<li>暂无</li>'}</ul></div>
                <div><span>下一步</span><ul>${nextChecks || '<li>暂无</li>'}</ul></div>
            </div>
        `;
    }
    if (viewGrid) {
        viewGrid.innerHTML = views.map(renderAgentViewCard).join('') || '<div class="empty-state">暂无 Agent 观点</div>';
    }
}

function renderAgentViewCard(view) {
    const role = agentRoleLabel(view.agent_role);
    const confidence = isFiniteNumber(view.confidence) ? `${Math.round(view.confidence * 100)}%` : '--';
    const reasoning = (view.reasoning || []).slice(0, 3).map(item => `<li>${esc(item)}</li>`).join('');
    return `
        <div class="agent-view-card">
            <div class="agent-view-card-header">
                <strong>${esc(role)}</strong>
                <span class="agent-view-badge ${directionClass(view.view)}">${esc(directionLabel(view.view))} ${esc(confidence)}</span>
            </div>
            <p>${esc(view.thesis || '暂无论点')}</p>
            <ul>${reasoning || '<li>暂无推理</li>'}</ul>
        </div>
    `;
}

function directionLabel(direction) {
    return {
        bullish: '积极',
        bearish: '谨慎',
        neutral: '中性',
        mixed: '分歧',
        unknown: '未知',
    }[direction] || '未知';
}

function directionClass(direction) {
    return ['bullish', 'bearish', 'neutral', 'mixed', 'unknown'].includes(direction) ? direction : 'unknown';
}

function agentRoleLabel(role) {
    return {
        macro: '宏观 Agent',
        fundamental: '基本面 Agent',
        technical: '技术面 Agent',
    }[role] || `${role || '未知'} Agent`;
}

function buildDailyChipPriceWeights(bar, priceMin, bucketWidth, buckets) {
    const weights = Array.from({ length: buckets }, () => 0);
    const low = toFiniteNumber(bar.low);
    const high = toFiniteNumber(bar.high);
    const close = toFiniteNumber(bar.close);
    if (low === null || high === null || close === null) return weights;

    const barLow = Math.min(low, high);
    const barHigh = Math.max(low, high);
    const closeIndex = Math.min(Math.max(Math.floor((close - priceMin) / bucketWidth), 0), buckets - 1);

    if (!(barHigh > barLow)) {
        weights[closeIndex] = 1;
        return weights;
    }

    const lowIndex = Math.max(0, Math.floor((barLow - priceMin) / bucketWidth));
    const highIndex = Math.min(buckets - 1, Math.floor((barHigh - priceMin) / bucketWidth));
    for (let idx = lowIndex; idx <= highIndex; idx += 1) {
        const bucketLow = priceMin + idx * bucketWidth;
        const bucketHigh = bucketLow + bucketWidth;
        const overlapLow = Math.max(barLow, bucketLow);
        const overlapHigh = Math.min(barHigh, bucketHigh);
        if (overlapHigh > overlapLow) {
            weights[idx] = overlapHigh - overlapLow;
        }
    }

    const total = weights.reduce((sum, value) => sum + value, 0);
    if (total <= 0) {
        weights[closeIndex] = 1;
        return weights;
    }
    return weights.map(value => value / total);
}

function calculateVisibleChipDistributionFromBars(priceBars, startIndex, endIndex, buckets = 180) {
    const safeStart = Math.min(Math.max(Number(startIndex) || 0, 0), Math.max(priceBars.length - 1, 0));
    const safeEnd = Math.min(Math.max(Number(endIndex) || 0, safeStart), priceBars.length - 1);
    const bars = priceBars
        .slice(safeStart, safeEnd + 1)
        .map(bar => ({
            high: toFiniteNumber(bar.high),
            low: toFiniteNumber(bar.low),
            close: toFiniteNumber(bar.close),
            volume: toFiniteNumber(bar.volume),
        }))
        .filter(bar => bar.high > 0 && bar.low > 0 && bar.close > 0 && bar.volume > 0);

    if (bars.length < 5) return [];

    const priceMin = Math.min(...bars.map(bar => bar.low));
    const priceMax = Math.max(...bars.map(bar => bar.high));
    if (!(priceMax > priceMin)) return [];

    const bucketWidth = (priceMax - priceMin) / buckets;
    const bucketVolumes = Array.from({ length: buckets }, () => 0);

    bars.forEach(bar => {
        const dailyWeights = buildDailyChipPriceWeights(bar, priceMin, bucketWidth, buckets);
        if (!dailyWeights.some(value => value > 0)) return;
        dailyWeights.forEach((weight, idx) => {
            bucketVolumes[idx] += weight * bar.volume;
        });
    });

    const totalVolume = bucketVolumes.reduce((sum, value) => sum + value, 0);
    if (totalVolume <= 0) return [];

    return bucketVolumes.map((volume, idx) => ({
        price: Number((priceMin + (idx + 0.5) * bucketWidth).toFixed(2)),
        volume: Number(volume.toFixed(2)),
        concentration_pct: Number((volume / totalVolume * 100).toFixed(2)),
    }));
}

function calculateChipAverageCost(chipData) {
    const totalVolume = chipData.reduce((sum, item) => sum + (toFiniteNumber(item.volume) || 0), 0);
    if (totalVolume <= 0) return null;
    const weightedSum = chipData.reduce((sum, item) => {
        return sum + (toFiniteNumber(item.price) || 0) * (toFiniteNumber(item.volume) || 0);
    }, 0);
    return Number((weightedSum / totalVolume).toFixed(2));
}

function calculateChipPeakBoundaries(chipData) {
    if (!chipData || chipData.length < 2) return { upper: null, lower: null };

    const sorted = [...chipData]
        .map(item => ({
            price: toFiniteNumber(item.price),
            concentration_pct: toFiniteNumber(item.concentration_pct),
        }))
        .filter(item => item.price !== null && item.concentration_pct !== null)
        .sort((a, b) => a.price - b.price);

    if (sorted.length < 2) return { upper: null, lower: null };

    const peakPoint = sorted.reduce((best, item) =>
        item.concentration_pct > best.concentration_pct ? item : best
    , sorted[0]);
    const peakIndex = sorted.findIndex(item => item.price === peakPoint.price);
    const halfMax = peakPoint.concentration_pct / 2;
    if (halfMax <= 0) return { upper: null, lower: null };

    let upper = null;
    for (let i = peakIndex; i < sorted.length - 1; i += 1) {
        const curr = sorted[i];
        const next = sorted[i + 1];
        if (curr.concentration_pct >= halfMax && next.concentration_pct <= halfMax) {
            const span = curr.concentration_pct - next.concentration_pct;
            const ratio = Math.abs(span) > 1e-10 ? (halfMax - next.concentration_pct) / span : 0;
            upper = Number((next.price + ratio * (curr.price - next.price)).toFixed(2));
            break;
        }
    }

    let lower = null;
    for (let i = peakIndex; i > 0; i -= 1) {
        const curr = sorted[i];
        const prev = sorted[i - 1];
        if (curr.concentration_pct >= halfMax && prev.concentration_pct <= halfMax) {
            const span = curr.concentration_pct - prev.concentration_pct;
            const ratio = Math.abs(span) > 1e-10 ? (halfMax - prev.concentration_pct) / span : 0;
            lower = Number((prev.price + ratio * (curr.price - prev.price)).toFixed(2));
            break;
        }
    }

    return {
        upper: upper ?? sorted[sorted.length - 1].price,
        lower: lower ?? sorted[0].price,
    };
}

function formatChipWindowLabel(sourceBars, startIndex, endIndex) {
    const startBar = sourceBars[startIndex];
    const endBar = sourceBars[endIndex];
    if (!startBar || !endBar) return '普通筹码';
    const count = Math.max(0, endIndex - startIndex + 1);
    return `${startBar.date}-${endBar.date}(${count}日)`;
}

function buildChipDistributionSnapshot(baseData, priceBars, startIndex, endIndex) {
    const sourceBars = priceBars || [];
    const safeStart = sourceBars.length
        ? Math.min(Math.max(Number(startIndex) || 0, 0), sourceBars.length - 1)
        : -1;
    const safeEnd = sourceBars.length && safeStart >= 0
        ? Math.min(Math.max(Number(endIndex) || safeStart, safeStart), sourceBars.length - 1)
        : -1;
    const computedChipData = safeStart >= 0 && safeEnd >= safeStart
        ? calculateVisibleChipDistributionFromBars(sourceBars, safeStart, safeEnd)
        : [];
    const usingComputedChipData = computedChipData.length > 0;
    const chipData = computedChipData.length ? computedChipData : (baseData.chip_distribution || []);
    const peakPoint = chipData.length
        ? chipData.reduce((best, item) =>
            (toFiniteNumber(item.concentration_pct) || 0) > (toFiniteNumber(best.concentration_pct) || 0)
                ? item
                : best
        , chipData[0])
        : null;
    const boundaries = calculateChipPeakBoundaries(chipData);
    const barAtIndex = safeEnd >= 0 ? sourceBars[safeEnd] : null;

    return {
        ...baseData,
        chip_distribution: chipData,
        avg_cost: calculateChipAverageCost(chipData) ?? toFiniteNumber(baseData.avg_cost),
        chip_peak_price: toFiniteNumber(peakPoint?.price) ?? toFiniteNumber(baseData.chip_peak_price),
        chip_peak_upper: usingComputedChipData
            ? boundaries.upper
            : (toFiniteNumber(baseData.chip_peak_upper)
                ?? toFiniteNumber(baseData.chip_peak_upper_price)
                ?? toFiniteNumber(baseData.chip_peak_range?.upper)
                ?? boundaries.upper),
        chip_peak_lower: usingComputedChipData
            ? boundaries.lower
            : (toFiniteNumber(baseData.chip_peak_lower)
                ?? toFiniteNumber(baseData.chip_peak_lower_price)
                ?? toFiniteNumber(baseData.chip_peak_range?.lower)
                ?? boundaries.lower),
        current_price: toFiniteNumber(barAtIndex?.close) ?? toFiniteNumber(baseData.current_price),
        chip_window_label: formatChipWindowLabel(sourceBars, safeStart, safeEnd),
    };
}

function syncChipDistributionHeight() {
    const layout = document.querySelector('.kline-terminal-layout');
    const chartArea = document.getElementById('chart-kline');
    if (!layout || !chartArea) return;
    const chartHeight = chartArea.clientHeight || 690;
    const mainPanelHeight = Math.max(220, Math.round(chartHeight * 0.44));
    layout.style.setProperty('--chip-chart-height', `${mainPanelHeight}px`);
    if (chartChipDist) chartChipDist.resize();
}

function scheduleVisibleChipDistributionUpdate(startIndex, endIndex) {
    if (!currentAssetAnalysisData || !currentDisplayKLineBars.length) return;
    const safeStart = Math.min(Math.max(Number(startIndex) || 0, 0), currentDisplayKLineBars.length - 1);
    const safeEnd = Math.min(Math.max(Number(endIndex) || safeStart, safeStart), currentDisplayKLineBars.length - 1);
    const rangeKey = `${safeStart}:${safeEnd}`;
    if (rangeKey === lastChipUpdateIndex) return;
    const runUpdate = () => {
        chipUpdateFrame = null;
        lastChipUpdateIndex = rangeKey;
        try {
            renderChipDistributionChart(
                buildChipDistributionSnapshot(currentAssetAnalysisData, currentDisplayKLineBars, safeStart, safeEnd)
            );
        } catch (error) {
            console.warn('Failed to update chip distribution for visible K-line range:', error);
        }
    };
    if (chipUpdateFrame !== null && typeof cancelAnimationFrame === 'function') {
        cancelAnimationFrame(chipUpdateFrame);
    }
    chipUpdateFrame = typeof requestAnimationFrame === 'function'
        ? requestAnimationFrame(runUpdate)
        : (runUpdate(), null);
}

function renderKLineChart(priceBars) {
    const container = document.getElementById('chart-kline');
    if (!container || !priceBars.length) return;

    // Guard: echarts CDN not loaded
    if (typeof echarts === 'undefined') {
        console.warn('ECharts not loaded, skipping K-line render');
        container.innerHTML = '<p class="empty-state" style="padding:40px 12px;text-align:center;">图表资源仍在加载，基础数据已显示</p>';
        return;
    }

    // Dispose existing chart + observer before re-creating
    if (chartKLine) {
        if (chartKLine._resizeObserver) {
            chartKLine._resizeObserver.disconnect();
            chartKLine._resizeObserver = null;
        }
        if (chartKLine._mouseleaveHandler) {
            container.removeEventListener('mouseleave', chartKLine._mouseleaveHandler);
            chartKLine._mouseleaveHandler = null;
        }
        if (chartKLine._documentMouseMoveHandler) {
            document.removeEventListener('mousemove', chartKLine._documentMouseMoveHandler);
            chartKLine._documentMouseMoveHandler = null;
        }
        chartKLine.dispose();
        chartKLine = null;
    }

    const colors = getChartColors();
    const upColor = '#ff4d4f';
    const downColor = '#00c896';
    const textColor = '#9ca3af';
    const gridColor = 'rgba(148,163,184,.18)';
    const bgColor = '#090c12';

    const bars = priceBars.filter(b => [b.open, b.high, b.low, b.close].every(isFiniteNumber));
    if (!bars.length) return;

    const dates = bars.map(b => String(b.date));
    const initialZoomStart = getInitialZoomStart(dates.length);
    currentMainPriceRange = calculatePriceRangeForBars(getVisibleBarsForInitialRange(bars));
    const ohlc = bars.map(b => [b.open, b.close, b.low, b.high]);
    const volumes = bars.map((b, i) => {
        const isUp = bars[i].close >= bars[i].open;
        return [i, b.volume || 0, isUp ? 1 : -1];
    });

    const series = [
        {
            name: 'K线',
            type: 'candlestick',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: ohlc,
            itemStyle: {
                color: upColor,
                color0: downColor,
                borderColor: upColor,
                borderColor0: downColor,
            },
        },
        {
            name: '成交量',
            type: 'bar',
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volumes,
            barWidth: '60%',
            itemStyle: {
                color: function (params) {
                    return params.data[2] > 0 ? upColor : downColor;
                },
            },
        },
    ];

    // MA lines
    KLINE_MA_CONFIGS.forEach(cfg => {
        const data = bars.map((b, i) => [i, b[cfg.key]]);
        series.push({
            name: cfg.name,
            type: 'line',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: data,
            smooth: false,
            lineStyle: { width: 1, color: cfg.color },
            itemStyle: { color: cfg.color },
            symbol: 'none',
            showSymbol: false,
        });
    });

    // Bollinger Bands
    BOLL_CONFIGS.forEach(cfg => {
        const data = bars.map((b, i) => [i, b[cfg.key]]);
        series.push({
            name: cfg.name,
            type: 'line',
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: data,
            smooth: false,
            lineStyle: { width: 1, color: cfg.lineColor },
            itemStyle: { color: cfg.lineColor },
            symbol: 'none',
            showSymbol: false,
        });
    });

    // MACD panel
    const macdDIF = bars.map((b, i) => [i, b.macd_dif]);
    const macdDEA = bars.map((b, i) => [i, b.macd_dea]);
    const macdHist = bars.map((b, i) => {
        const val = b.macd_hist;
        return [i, val, val >= 0 ? 1 : -1];
    });

    // KDJ panel
    const kdjK = bars.map((b, i) => [i, b.kdj_k]);
    const kdjD = bars.map((b, i) => [i, b.kdj_d]);
    const kdjJ = bars.map((b, i) => [i, b.kdj_j]);

    // RSI panel
    const rsiData = bars.map((b, i) => [i, b.rsi]);
    const latestBar = bars[bars.length - 1] || {};
    const indicatorValue = (value, digits = 2) =>
        isFiniteNumber(value) ? value.toFixed(digits) : '--';
    const averageVolumeAt = (index, period) => {
        const endIndex = Math.min(Math.max(Number(index) || 0, 0), bars.length - 1);
        const recent = bars.slice(Math.max(0, endIndex - period + 1), endIndex + 1);
        const validVolumes = recent.map(bar => toFiniteNumber(bar.volume)).filter(value => value !== null);
        if (!validVolumes.length) return null;
        return validVolumes.reduce((sum, value) => sum + value, 0) / validVolumes.length;
    };
    const panelLabelStyle = {
        fill: '#d1d5db',
        font: '12px JetBrains Mono, SF Mono, Consolas, monospace',
        textAlign: 'left',
        textVerticalAlign: 'top',
    };
    const buildPanelLabels = (bar, index) => {
        const safeIndex = Math.min(Math.max(Number(index) || 0, 0), bars.length - 1);
        const activeBar = bar || bars[safeIndex] || {};
        return [
            {
                id: 'kline-panel-label-vol',
                type: 'text',
                left: 50,
                top: '53.5%',
                silent: true,
                style: {
                    ...panelLabelStyle,
                    text: `VOL:${fmtVolume(activeBar.volume)} MA5:${fmtVolume(averageVolumeAt(safeIndex, 5))} MA10:${fmtVolume(averageVolumeAt(safeIndex, 10))}`,
                },
            },
            {
                id: 'kline-panel-label-macd',
                type: 'text',
                left: 50,
                top: '64.5%',
                silent: true,
                style: {
                    ...panelLabelStyle,
                    text: `MACD(12,26,9) DIF:${indicatorValue(activeBar.macd_dif, 4)} DEA:${indicatorValue(activeBar.macd_dea, 4)} MACD:${indicatorValue(activeBar.macd_hist, 4)}`,
                },
            },
            {
                id: 'kline-panel-label-kdj',
                type: 'text',
                left: 50,
                top: '77.5%',
                silent: true,
                style: {
                    ...panelLabelStyle,
                    text: `KDJ(9,3,3) K:${indicatorValue(activeBar.kdj_k)} D:${indicatorValue(activeBar.kdj_d)} J:${indicatorValue(activeBar.kdj_j)}`,
                },
            },
            {
                id: 'kline-panel-label-rsi',
                type: 'text',
                left: 50,
                top: '89.5%',
                silent: true,
                style: {
                    ...panelLabelStyle,
                    text: `RSI(14):${indicatorValue(activeBar.rsi)}`,
                },
            },
        ];
    };

    series.push(
        {
            name: 'MACD柱',
            type: 'bar',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdHist,
            barWidth: '60%',
            itemStyle: {
                color: function (params) {
                    return params.data[2] > 0 ? upColor : downColor;
                },
            },
        },
        {
            name: 'DIF',
            type: 'line',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdDIF,
            lineStyle: { width: 1, color: colors.orange },
            itemStyle: { color: colors.orange },
            symbol: 'none',
        },
        {
            name: 'DEA',
            type: 'line',
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: macdDEA,
            lineStyle: { width: 1, color: colors.blue },
            itemStyle: { color: colors.blue },
            symbol: 'none',
        },
        // KDJ
        {
            name: 'K',
            type: 'line',
            xAxisIndex: 3,
            yAxisIndex: 3,
            data: kdjK,
            lineStyle: { width: 1, color: colors.orange },
            itemStyle: { color: colors.orange },
            symbol: 'none',
        },
        {
            name: 'D',
            type: 'line',
            xAxisIndex: 3,
            yAxisIndex: 3,
            data: kdjD,
            lineStyle: { width: 1, color: colors.blue },
            itemStyle: { color: colors.blue },
            symbol: 'none',
        },
        {
            name: 'J',
            type: 'line',
            xAxisIndex: 3,
            yAxisIndex: 3,
            data: kdjJ,
            lineStyle: { width: 1, color: colors.purple },
            itemStyle: { color: colors.purple },
            symbol: 'none',
        },
        // RSI
        {
            name: 'RSI',
            type: 'line',
            xAxisIndex: 4,
            yAxisIndex: 4,
            data: rsiData,
            lineStyle: { width: 1.5, color: colors.purple },
            itemStyle: { color: colors.purple },
            symbol: 'none',
            markLine: {
                silent: true,
                symbol: 'none',
                lineStyle: { type: 'dashed', width: 1, color: gridColor },
                data: [
                    { yAxis: 70, label: { formatter: '70', fontSize: 10, color: textColor } },
                    { yAxis: 30, label: { formatter: '30', fontSize: 10, color: textColor } },
                ],
            },
        }
    );

    const option = {
        backgroundColor: bgColor,
        animation: false,
        legend: {
            show: false,
            top: 2,
            left: 10,
            data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', 'MA120', 'MA250', 'BOLL中轨', 'DIF', 'DEA', 'K', 'D', 'J', 'RSI'],
            itemWidth: 14,
            itemHeight: 8,
            textStyle: { color: textColor, fontSize: 11 },
            selected: {
                'MA5': currentOverlayMode === 'ma',
                'MA10': currentOverlayMode === 'ma',
                'MA20': currentOverlayMode === 'ma',
                'MA60': currentOverlayMode === 'ma',
                'MA120': currentOverlayMode === 'ma',
                'MA250': currentOverlayMode === 'ma',
                'BOLL上轨': currentOverlayMode === 'boll',
                'BOLL中轨': currentOverlayMode === 'boll',
                'BOLL下轨': currentOverlayMode === 'boll',
            },
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: { color: textColor },
            },
            backgroundColor: 'rgba(9,12,18,.94)',
            borderColor: gridColor,
            textStyle: { color: '#d1d5db', fontSize: 12 },
            formatter: function (params) {
                const idx = params[0]?.dataIndex;
                if (idx == null) return '';
                const bar = bars[idx];
                const change = bar.close - bar.open;
                const changePct = bar.open ? ((change / bar.open) * 100).toFixed(2) : '--';
                const sign = change >= 0 ? '+' : '';
                let html = `<div style="font-weight:bold;margin-bottom:4px;">${bar.date}</div>`;
                html += `<div>开盘: ${bar.open.toFixed(2)}</div>`;
                html += `<div>最高: <span style="color:${upColor}">${bar.high.toFixed(2)}</span></div>`;
                html += `<div>最低: <span style="color:${downColor}">${bar.low.toFixed(2)}</span></div>`;
                html += `<div>收盘: ${bar.close.toFixed(2)}</div>`;
                html += `<div>涨跌: <span style="color:${change>=0?upColor:downColor}">${sign}${change.toFixed(2)} (${sign}${changePct}%)</span></div>`;
                if (bar.volume) html += `<div>成交量: ${fmtVolume(bar.volume)}</div>`;
                if (bar.amount) html += `<div>成交额: ${fmtAmount(bar.amount)}</div>`;
                if (isFiniteNumber(bar.turnover)) html += `<div>换手率: ${bar.turnover.toFixed(2)}%</div>`;
                KLINE_MA_CONFIGS.forEach(cfg => {
                    if (isFiniteNumber(bar[cfg.key])) {
                        html += `<div style="color:${cfg.color}">${cfg.name}: ${bar[cfg.key].toFixed(2)}</div>`;
                    }
                });
                if (isFiniteNumber(bar.macd_dif)) html += `<div>DIF: ${bar.macd_dif.toFixed(4)} DEA: ${bar.macd_dea?.toFixed(4)||'--'} MACD: ${bar.macd_hist?.toFixed(4)||'--'}</div>`;
                if (isFiniteNumber(bar.kdj_k)) html += `<div style="color:${colors.orange}">KDJ K: ${bar.kdj_k.toFixed(2)} D: ${bar.kdj_d?.toFixed(2)||'--'} <span style="color:${colors.purple}">J: ${bar.kdj_j?.toFixed(2)||'--'}</span></div>`;
                if (isFiniteNumber(bar.rsi)) html += `<div style="color:${colors.purple}">RSI(14): ${bar.rsi.toFixed(2)}</div>`;
                return html;
            },
        },
        axisPointer: {
            link: [
                { xAxisIndex: 'all' },
            ],
        },
        graphic: buildPanelLabels(latestBar, bars.length - 1),
        grid: [
            { left: 46, right: 8, top: 28, height: '44%' },
            { left: 46, right: 8, top: '53%', height: '8%' },
            { left: 46, right: 8, top: '64%', height: '10%' },
            { left: 46, right: 8, top: '77%', height: '9%' },
            { left: 46, right: 8, top: '89%', height: '6%' },
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                boundaryGap: true,
                axisLine: { onZero: false, lineStyle: { color: gridColor } },
                axisTick: { show: false },
                axisLabel: { color: textColor, fontSize: 10 },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
            },
            {
                type: 'category',
                gridIndex: 1,
                data: dates,
                boundaryGap: true,
                axisLine: { onZero: false, lineStyle: { color: gridColor } },
                axisTick: { show: false },
                axisLabel: { show: false },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
            },
            {
                type: 'category',
                gridIndex: 2,
                data: dates,
                boundaryGap: true,
                axisLine: { onZero: false, lineStyle: { color: gridColor } },
                axisTick: { show: false },
                axisLabel: { color: textColor, fontSize: 10 },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
            },
            {
                type: 'category',
                gridIndex: 3,
                data: dates,
                boundaryGap: true,
                axisLine: { onZero: false, lineStyle: { color: gridColor } },
                axisTick: { show: false },
                axisLabel: { show: false },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
            },
            {
                type: 'category',
                gridIndex: 4,
                data: dates,
                boundaryGap: true,
                axisLine: { onZero: false, lineStyle: { color: gridColor } },
                axisTick: { show: false },
                axisLabel: { color: textColor, fontSize: 10 },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax',
            },
        ],
        yAxis: [
            {
                scale: true,
                min: currentMainPriceRange?.min,
                max: currentMainPriceRange?.max,
                splitArea: { show: false },
                splitLine: { lineStyle: { color: gridColor } },
                axisLabel: { color: textColor, fontSize: 10 },
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { color: textColor, fontSize: 9 },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { show: false },
            },
            {
                scale: true,
                gridIndex: 2,
                splitNumber: 3,
                axisLabel: { color: textColor, fontSize: 9 },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { lineStyle: { color: gridColor } },
            },
            {
                scale: false,
                gridIndex: 3,
                min: 0,
                max: 100,
                splitNumber: 3,
                interval: 50,
                axisLabel: { color: textColor, fontSize: 9 },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { lineStyle: { color: gridColor } },
            },
            {
                scale: false,
                gridIndex: 4,
                min: 0,
                max: 100,
                splitNumber: 2,
                axisLabel: { color: textColor, fontSize: 9 },
                axisLine: { show: false },
                axisTick: { show: false },
                splitLine: { lineStyle: { color: gridColor } },
            },
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1, 2, 3, 4],
                start: initialZoomStart,
                end: 100,
                zoomOnMouseWheel: true,
                moveOnMouseMove: true,
                moveOnMouseWheel: false,
            },
            {
                type: 'slider',
                xAxisIndex: [0, 1, 2, 3, 4],
                start: initialZoomStart,
                end: 100,
                height: 18,
                bottom: 2,
                borderColor: gridColor,
                backgroundColor: 'rgba(15,23,42,.7)',
                fillerColor: 'rgba(148,163,184,.18)',
                handleStyle: { color: '#64748b' },
                textStyle: { color: textColor, fontSize: 10 },
            },
        ],
        series: series,
    };

    // Dispose existing chart + observer before re-creating
    if (chartKLine) {
        if (chartKLine._resizeObserver) {
            chartKLine._resizeObserver.disconnect();
            chartKLine._resizeObserver = null;
        }
        chartKLine.dispose();
        chartKLine = null;
    }

    chartKLine = echarts.init(container, null, { devicePixelRatio: window.devicePixelRatio || 1 });
    chartKLine.setOption(option);
    renderMainOverlayLabel(container, latestBar);
    renderKLineQuoteForBar(latestBar, bars.length - 1, bars);
    const visibleZoomState = { start: initialZoomStart, end: 100, endValue: null };
    const updateVisibleChipDistribution = () => {
        const [startIndex, endIndex] = getZoomIndexRange(
            bars.length,
            visibleZoomState.start,
            visibleZoomState.end
        );
        scheduleVisibleChipDistributionUpdate(startIndex, endIndex);
    };
    const updateActiveKLineIndex = (index) => {
        const safeIndex = Math.min(Math.max(Number(index) || 0, 0), bars.length - 1);
        renderMainOverlayLabel(container, bars[safeIndex]);
        renderKLineQuoteForBar(bars[safeIndex], safeIndex, bars);
        chartKLine.setOption({ graphic: buildPanelLabels(bars[safeIndex], safeIndex) }, false);
        const [startIndex] = getZoomIndexRange(
            bars.length,
            visibleZoomState.start,
            visibleZoomState.end
        );
        scheduleVisibleChipDistributionUpdate(startIndex, safeIndex);
    };
    updateVisibleChipDistribution();
    const resetKLineQuoteToVisibleRight = () => {
        const zoomState = chartKLine.getOption()?.dataZoom?.[0] || visibleZoomState;
        updateActiveKLineIndex(getKLineVisibleRightIndex(bars.length, zoomState));
    };
    let pointerInsideKLine = false;
    const documentMouseMoveHandler = (event) => {
        if (!pointerInsideKLine) return;
        const rect = container.getBoundingClientRect();
        const isInside = event.clientX >= rect.left
            && event.clientX <= rect.right
            && event.clientY >= rect.top
            && event.clientY <= rect.bottom;
        if (isInside) return;
        pointerInsideKLine = false;
        resetKLineQuoteToVisibleRight();
    };
    chartKLine.on('updateAxisPointer', (event) => {
        const axesInfo = event?.axesInfo || [];
        const axisInfo = axesInfo.find(info => info.axisDim === 'x' && info.axisIndex === 0) || axesInfo[0];
        if (!axisInfo) return;
        const rawValue = axisInfo.value;
        const numericValue = Number(rawValue);
        const index = Number.isInteger(numericValue) ? numericValue : dates.indexOf(String(rawValue));
        if (index >= 0) updateActiveKLineIndex(index);
    });
    chartKLine.getZr().on('mousemove', (event) => {
        pointerInsideKLine = true;
        const point = [event.offsetX, event.offsetY];
        if (!chartKLine.containPixel({ gridIndex: 0 }, point)) return;
        const value = chartKLine.convertFromPixel({ xAxisIndex: 0 }, point);
        const index = Array.isArray(value) ? value[0] : value;
        if (Number.isFinite(index)) updateActiveKLineIndex(Math.round(index));
    });
    container.addEventListener('mouseleave', resetKLineQuoteToVisibleRight);
    chartKLine._mouseleaveHandler = resetKLineQuoteToVisibleRight;
    document.addEventListener('mousemove', documentMouseMoveHandler);
    chartKLine._documentMouseMoveHandler = documentMouseMoveHandler;
    chartKLine.on('dataZoom', (event) => {
        const zoom = event?.batch?.[0] || event || {};
        if (Number.isFinite(Number(zoom.start))) visibleZoomState.start = Number(zoom.start);
        if (Number.isFinite(Number(zoom.end))) visibleZoomState.end = Number(zoom.end);
        visibleZoomState.endValue = Number.isFinite(Number(zoom.endValue)) ? Number(zoom.endValue) : null;
        applyVisiblePriceRange(visibleZoomState.start, visibleZoomState.end, true);
        updateVisibleChipDistribution();
    });
    syncChipDistributionHeight();

    // Resize handling
    const ro = new ResizeObserver(() => {
        if (chartKLine) chartKLine.resize();
        syncChipDistributionHeight();
    });
    ro.observe(container);
    chartKLine._resizeObserver = ro;
}

function updateMAToggleButtons() {
    const group = document.getElementById('kline-ma-toggle-group');
    if (!group) return;
    group.querySelectorAll('.kline-btn').forEach(btn => {
        const mode = btn.dataset.overlay;
        const isActive = mode === currentOverlayMode;
        btn.classList.toggle('active', Boolean(isActive));
    });
}

function updateKLinePeriodButtons() {
    const group = document.querySelector('.kline-period-group');
    if (!group) return;
    group.querySelectorAll('.kline-period-item').forEach(btn => {
        const period = btn.dataset.period;
        const isActive = period === currentKLinePeriod || (period === 'ALL' && showAllKLineBars);
        btn.classList.toggle('active', Boolean(isActive));
    });
}

function rerenderCurrentKLinePanel() {
    if (!currentAssetAnalysisData || !currentKLineBars.length) return;
    currentDisplayKLineBars = prepareKLineBars(currentKLineBars);
    lastChipUpdateIndex = null;
    renderKLineChart(currentDisplayKLineBars);
}

function setKLinePeriod(period) {
    if (!period) return;
    if (period === 'ALL') {
        showAllKLineBars = true;
    } else {
        currentKLinePeriod = period;
        showAllKLineBars = false;
    }
    updateKLinePeriodButtons();
    rerenderCurrentKLinePanel();
}

function setKLineTimeRange(range) {
    currentTimeRange = range;
    // Update button active states
    const group = document.getElementById('kline-time-range-group');
    if (group) {
        group.querySelectorAll('.kline-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.range === range);
        });
    }
    // Re-fetch with new time range
    if (currentCanonicalId) {
        analyzeAssetByCode(currentCanonicalId, range);
    }
}

function setKLineOverlayMode(mode) {
    if (!['ma', 'boll', 'none'].includes(mode)) return;
    currentOverlayMode = mode;
    updateMAToggleButtons();
    rerenderCurrentKLinePanel();
}

function toggleMA(maKey) {
    setKLineOverlayMode(maKey === 'boll' ? 'boll' : 'ma');
}

function initKLineToolbar() {
    const periodGroup = document.querySelector('.kline-period-group');
    if (periodGroup) {
        periodGroup.addEventListener('click', (e) => {
            const btn = e.target.closest('.kline-period-item');
            if (!btn || !btn.dataset.period || btn.disabled) return;
            setKLinePeriod(btn.dataset.period);
        });
    }

    // MA toggle buttons
    const maGroup = document.getElementById('kline-ma-toggle-group');
    if (maGroup) {
        maGroup.addEventListener('click', (e) => {
            const btn = e.target.closest('.kline-btn');
            if (!btn || !btn.dataset.overlay) return;
            setKLineOverlayMode(btn.dataset.overlay);
        });
    }
}

function renderChipDistributionChart(data) {
    const container = document.getElementById('chart-chip-distribution');
    if (!container) return;

    const chipData = data.chip_distribution || [];
    const avgCost = toFiniteNumber(data.avg_cost);
    const peakPrice = toFiniteNumber(data.chip_peak_price);
    const peakUpper = toFiniteNumber(data.chip_peak_upper)
        ?? toFiniteNumber(data.chip_peak_upper_price)
        ?? toFiniteNumber(data.chip_peak_range?.upper);
    const peakLower = toFiniteNumber(data.chip_peak_lower)
        ?? toFiniteNumber(data.chip_peak_lower_price)
        ?? toFiniteNumber(data.chip_peak_range?.lower);
    const currentPrice = toFiniteNumber(data.current_price);
    const windowLabel = document.querySelector('.chip-window-label');
    if (windowLabel) windowLabel.textContent = data.chip_window_label || '普通筹码';

    // Update stats display
    const setChipStat = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    setChipStat('chip-peak-price', isFiniteNumber(peakPrice) ? peakPrice.toFixed(2) : '--');
    setChipStat('chip-peak-upper', isFiniteNumber(peakUpper) ? peakUpper.toFixed(2) : '--');
    setChipStat('chip-peak-lower', isFiniteNumber(peakLower) ? peakLower.toFixed(2) : '--');
    setChipStat('chip-avg-cost', isFiniteNumber(avgCost) ? avgCost.toFixed(2) : '--');

    if (!chipData.length || !isFiniteNumber(currentPrice)) {
        setChipStat('chip-profit-ratio', '--');
        setChipStat('chip-loss-ratio', '--');
        if (chartChipDist) { chartChipDist.dispose(); chartChipDist = null; }
        if (container) container.innerHTML = '<p class="empty-state" style="padding:40px 12px;text-align:center;font-size:11px;">暂无筹码分布数据</p>';
        return;
    }

    // Calculate profit/loss ratios
    let profitVol = 0, lossVol = 0;
    chipData.forEach(c => {
        const price = toFiniteNumber(c.price);
        const volume = toFiniteNumber(c.volume) || 0;
        if (price !== null && price < currentPrice) profitVol += volume;
        else lossVol += volume;
    });
    const totalChipVol = profitVol + lossVol;
    const profitRatio = totalChipVol > 0 ? (profitVol / totalChipVol * 100) : 0;
    const lossRatio = totalChipVol > 0 ? (lossVol / totalChipVol * 100) : 0;
    setChipStat('chip-profit-ratio', `${profitRatio.toFixed(1)}%`);
    setChipStat('chip-loss-ratio', `${lossRatio.toFixed(1)}%`);

    if (typeof echarts === 'undefined') return;

    // Dispose existing chart
    if (chartChipDist) {
        if (chartChipDist._resizeObserver) {
            chartChipDist._resizeObserver.disconnect();
            chartChipDist._resizeObserver = null;
        }
        chartChipDist.dispose();
        chartChipDist = null;
    }

    const colors = getChartColors();
    const textColor = '#9ca3af';
    const gridColor = 'rgba(148,163,184,.18)';
    const bgColor = '#11151c';

    // Sort by price ascending
    const sorted = [...chipData]
        .map(c => ({
            ...c,
            price: toFiniteNumber(c.price),
            volume: toFiniteNumber(c.volume),
            concentration_pct: toFiniteNumber(c.concentration_pct),
        }))
        .filter(c => c.price !== null && c.concentration_pct !== null)
        .sort((a, b) => a.price - b.price);
    if (!sorted.length) return;
    const chipPriceMin = Math.min(...sorted.map(c => c.price));
    const chipPriceMax = Math.max(...sorted.map(c => c.price));
    const chipPadding = Math.max((chipPriceMax - chipPriceMin) * 0.08, 0.01);
    const priceAxisRange = currentMainPriceRange || {
        min: Number((chipPriceMin - chipPadding).toFixed(2)),
        max: Number((chipPriceMax + chipPadding).toFixed(2)),
    };
    const bucketHeight = sorted.length > 1
        ? Math.max(0.01, Math.abs(sorted[1].price - sorted[0].price) * 0.72)
        : Math.max(0.02, (priceAxisRange.max - priceAxisRange.min) * 0.02);

    // Build markLine data
    const markLineData = [];

    // Chip peak line (thick solid)
    if (isFiniteNumber(peakPrice)) {
        markLineData.push({
            yAxis: peakPrice.toFixed(2),
            name: '筹码峰 ' + peakPrice.toFixed(2),
            lineStyle: { color: '#eab308', width: 2, type: 'solid' },
            label: { color: '#eab308', fontWeight: 'bold', fontSize: 10, formatter: '筹码峰' },
        });
    }

    // Upper boundary (dashed amber)
    if (peakUpper !== null) {
        markLineData.push({
            yAxis: peakUpper.toFixed(2),
            name: '上边界 ' + peakUpper.toFixed(2),
            lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' },
            label: { color: '#f59e0b', fontSize: 10, formatter: '上边界' },
        });
    }

    // Lower boundary (dashed amber)
    if (peakLower !== null) {
        markLineData.push({
            yAxis: peakLower.toFixed(2),
            name: '下边界 ' + peakLower.toFixed(2),
            lineStyle: { color: '#f59e0b', width: 1.5, type: 'dashed' },
            label: { color: '#f59e0b', fontSize: 10, formatter: '下边界' },
        });
    }

    // Current price line
    if (currentPrice !== null) {
        markLineData.push({
            yAxis: currentPrice.toFixed(2),
            name: '现价 ' + currentPrice.toFixed(2),
            lineStyle: { color: colors.orange, type: 'dashed', width: 1.5 },
            label: { color: colors.orange, fontWeight: 'bold', fontSize: 10, formatter: '现价' },
        });
    }

    // Average cost line
    if (avgCost !== null) {
        markLineData.push({
            yAxis: avgCost.toFixed(2),
            name: '均本 ' + avgCost.toFixed(2),
            lineStyle: { color: colors.blue, type: 'dashed', width: 1.5 },
            label: { color: colors.blue, fontSize: 10, formatter: '均本' },
        });
    }

    chartChipDist = echarts.init(container, null, { devicePixelRatio: window.devicePixelRatio || 1 });

    const option = {
        backgroundColor: bgColor,
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            backgroundColor: 'rgba(9,12,18,.94)',
            borderColor: gridColor,
            textStyle: { color: '#d1d5db', fontSize: 11 },
            formatter: function (params) {
                const p = params[0];
                return `<div style="font-weight:bold;">价格: ${p.data[1].toFixed(2)}</div>
                        <div>筹码占比: ${p.data[0].toFixed(2)}%</div>`;
            },
        },
        grid: { left: 4, right: 36, top: 8, bottom: 12, containLabel: false },
        xAxis: {
            type: 'value',
            axisLabel: { color: textColor, fontSize: 9, formatter: '{value}' },
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { lineStyle: { color: gridColor } },
            max: function (value) { return value.max * 1.25; },
        },
        yAxis: {
            type: 'value',
            min: priceAxisRange.min,
            max: priceAxisRange.max,
            axisLabel: { color: textColor, fontSize: 9, formatter: value => Number(value).toFixed(2) },
            axisLine: { lineStyle: { color: gridColor } },
            axisTick: { show: false },
            splitLine: { show: false },
        },
        series: [
            {
                name: '筹码分布',
                type: 'custom',
                data: sorted.map(c => [c.concentration_pct, c.price]),
                renderItem: function (params, api) {
                    const concentration = api.value(0);
                    const price = api.value(1);
                    const start = api.coord([0, price]);
                    const end = api.coord([concentration, price]);
                    const size = api.size([0, bucketHeight]);
                    const height = Math.max(1, Math.min(3, size[1]));
                    const rect = {
                        x: start[0],
                        y: start[1] - height / 2,
                        width: Math.max(1, end[0] - start[0]),
                        height,
                    };
                    const clipped = echarts.graphic.clipRectByRect(rect, {
                        x: params.coordSys.x,
                        y: params.coordSys.y,
                        width: params.coordSys.width,
                        height: params.coordSys.height,
                    });
                    if (!clipped) return null;
                    return {
                        type: 'rect',
                        shape: clipped,
                        style: api.style({
                            fill: price > currentPrice ? '#22c55e' : '#ff4d4f',
                        }),
                    };
                },
                markLine: {
                    silent: true,
                    symbol: 'none',
                    label: {
                        position: 'end',
                        fontSize: 9,
                        color: textColor,
                    },
                    lineStyle: { type: 'dashed', width: 1.2 },
                    data: markLineData,
                },
            },
        ],
    };

    chartChipDist.setOption(option);

    // Resize handling
    const ro = new ResizeObserver(() => { if (chartChipDist) chartChipDist.resize(); });
    ro.observe(container);
    chartChipDist._resizeObserver = ro;
}

function renderCapitalFlowChart(capitalFlow) {
    const detailsEl = document.getElementById('capital-flow-details');
    if (!capitalFlow) { if (detailsEl) detailsEl.innerHTML = '<p class="empty-state">暂无资金流向数据</p>'; return; }
    if (typeof Chart === 'undefined') return;
    const colors = getChartColors();
    if (chartCapitalFlow) chartCapitalFlow.destroy();
    const labels = ['主力净流入', '超大单', '大单', '中单', '小单'];
    const values = [capitalFlow.main_net || 0, capitalFlow.super_net || 0, capitalFlow.large_net || 0, capitalFlow.medium_net || 0, capitalFlow.small_net || 0];
    const validData = labels.map((l, i) => ({ label: l, value: values[i] })).filter(d => d.value !== 0);
    const ctx = document.getElementById('chart-capital-flow')?.getContext('2d');
    if (ctx) {
        chartCapitalFlow = new Chart(ctx, {
            type: 'pie',
            data: { labels: validData.map(d => d.label), datasets: [{ data: validData.map(d => Math.abs(d.value)), backgroundColor: validData.map(d => d.value >= 0 ? colors.green : colors.red) }] },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }
    if (detailsEl) {
        detailsEl.innerHTML = `
            <div class="flow-detail-item"><span class="flow-label">主力流入</span><span class="flow-value inflow">${fmtAmount(capitalFlow.main_inflow)}</span></div>
            <div class="flow-detail-item"><span class="flow-label">主力流出</span><span class="flow-value outflow">${fmtAmount(capitalFlow.main_outflow)}</span></div>
            <div class="flow-detail-item"><span class="flow-label">主力净流入</span><span class="flow-value ${(capitalFlow.main_net || 0) >= 0 ? 'inflow' : 'outflow'}">${(capitalFlow.main_net || 0) >= 0 ? '+' : ''}${fmtAmount(capitalFlow.main_net)}</span></div>
            ${capitalFlow.northbound_flow !== undefined ? `<div class="flow-detail-item"><span class="flow-label">北向资金</span><span class="flow-value ${capitalFlow.northbound_flow >= 0 ? 'inflow' : 'outflow'}">${capitalFlow.northbound_flow >= 0 ? '+' : ''}${fmtAmount(capitalFlow.northbound_flow)}</span></div>` : ''}
        `;
    }
}

function renderShareholderList(shareholders) {
    const container = document.getElementById('shareholder-list');
    if (!container) return;
    if (!shareholders || !shareholders.length) { container.innerHTML = '<p class="empty-state">暂无股东数据</p>'; return; }
    container.innerHTML = shareholders.map(sh => `
        <div class="shareholder-item">
            <div class="shareholder-name">${esc(sh.name)}</div>
            <div class="shareholder-meta">
                <span class="shareholder-ratio">${fmtFixed(sh.share_ratio, 2, '%')}</span>
                ${isFiniteNumber(sh.change_ratio) ? `<span class="shareholder-change ${sh.change_ratio >= 0 ? 'change-up' : 'change-down'}">${sh.change_ratio >= 0 ? '+' : ''}${sh.change_ratio.toFixed(2)}%</span>` : ''}
                ${sh.is_state_owned ? '<span class="soe-badge">国资</span>' : ''}
            </div>
        </div>
    `).join('');
}

function renderIndustryInfo(industry) {
    const container = document.getElementById('industry-info-detail');
    if (!container) return;
    if (!industry) { container.innerHTML = '<p class="empty-state">暂无行业数据</p>'; return; }
    container.innerHTML = `
        <div class="industry-class"><div class="industry-label">申万一级</div><div class="industry-value">${esc(industry.sw_level_1 || '--')}</div></div>
        <div class="industry-class"><div class="industry-label">申万二级</div><div class="industry-value">${esc(industry.sw_level_2 || '--')}</div></div>
        <div class="industry-metrics">
            <div class="metric-row"><span class="metric-label">行业PE</span><span class="metric-value">${fmtFixed(industry.industry_pe)}</span></div>
            <div class="metric-row"><span class="metric-label">行业PB</span><span class="metric-value">${fmtFixed(industry.industry_pb)}</span></div>
        </div>
    `;
}

function renderEventListPanel(events) {
    const panel = document.getElementById('event-list-panel');
    if (!panel) return;
    if (!events || !events.length) { panel.innerHTML = '<p class="empty-state">暂无相关事件</p>'; return; }
    panel.innerHTML = events.map(e => `
        <div class="event-list-item">
            <div class="item-title">${esc(e.summary || e.title || '')}</div>
            <div class="item-meta">${esc(e.event_type || '')} &bull; ${new Date(e.publish_date || e.created_at).toLocaleString()}</div>
        </div>
    `).join('');
}

function renderMacroSensitivity(macro) {
    const container =
        document.getElementById('macro-sensitivity-detail') ||
        document.getElementById('macro-sensitivity');
    if (!container) return;
    if (!macro || !macro.sensitivities || !macro.sensitivities.length) { container.innerHTML = '<p class="empty-state">暂无宏观敏感性数据</p>'; return; }
    container.innerHTML = macro.sensitivities.map(s => `
        <div class="macro-item">
            <span class="macro-factor">${esc(s.factor)}</span>
            <span class="macro-direction ${s.direction === 'positive' ? 'positive' : s.direction === 'negative' ? 'negative' : ''}">${s.direction === 'positive' ? '↑' : s.direction === 'negative' ? '↓' : '—'}</span>
            <span class="macro-strength">${fmtFixed(s.strength)}</span>
        </div>
    `).join('');
}

function initAssetSearch() {
    const assetInput = document.getElementById('asset-code');
    if (assetInput) {
        assetInput.addEventListener('input', (e) => {
            delete e.target.dataset.selectedSymbol;
            clearTimeout(assetSearchDebounceTimer);
            assetSearchDebounceTimer = setTimeout(() => searchAssets(e.target.value.trim()), 200);
        });
        assetInput.addEventListener('keydown', handleAssetSearchKeydown);
        assetInput.addEventListener('focus', (e) => { if (e.target.value.trim()) searchAssets(e.target.value.trim()); });
    }
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('asset-search-dropdown');
        const input = document.getElementById('asset-code');
        if (dropdown && !dropdown.contains(e.target) && e.target !== input) dropdown.classList.add('hidden');
    });
    document.getElementById('asset-start-research')?.addEventListener('click', startResearchFromAsset);
}

export {
    searchAssets,
    selectAsset,
    analyzeAssetByCode,
    analyzeAsset,
    handleAssetSearchKeydown,
    initAssetSearch,
    setKLineTimeRange,
    toggleMA,
    initKLineToolbar,
    switchAssetObserveMode,
    openThemeObservation,
    buildResearchPrefill,
};
