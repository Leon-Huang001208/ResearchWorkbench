import { summarizeTech } from './indicators.mjs';
import { publicData } from './security.mjs';
import { withSignal } from './network.mjs';
import { marketCapCheck, extremePercentile, totalCapYi } from './integrity.mjs';
import { requestSignal } from './network.mjs';
// 真实数据工具：腾讯行情 / 腾讯前复权K线 / 东方财富主要财务指标 / 本地知识库与新闻 / 技术指标
// 每个工具返回 { data, sources:[{title,url,provider,asof}] }
import * as THS from './ths.mjs';
import { ifindCall, ifindMcpEnabled } from './ifind_mcp.mjs';
import * as EXT from './extsources.mjs';
let L = { summarizeTech, STOCKS: [ {name:'宁德时代',code:'300750.SZ'}, {name:'比亚迪',code:'002594.SZ'}, {name:'贵州茅台',code:'600519.SH'}, {name:'中芯国际',code:'688981.SH'}, {name:'招商银行',code:'600036.SH'}, {name:'东方财富',code:'300059.SZ'} ] }; // 本地数据（esbuild 打包自 src/data）
export function setLocalData(mod) { L = mod; }

const UA = { 'User-Agent': 'Mozilla/5.0 (Macintosh) AlphaDesk/1.0', Referer: 'https://gu.qq.com/' };
async function get(url, { gbk = false, timeout = 10000 } = {}) {
  const r = await fetch(url, { headers: UA, signal: requestSignal(timeout) });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const buf = await r.arrayBuffer();
  return new TextDecoder(gbk ? 'gbk' : 'utf-8').decode(buf);
}

// "300750" / "300750.SZ" / "sz300750" / "宁德时代" → { tx:"sz300750", code:"300750.SZ", name }
export async function resolveCode(input) {
  let s = String(input || '').trim();
  let m = s.match(/^(sh|sz|bj)(\d{6})$/i);
  if (m) return mk(m[1].toLowerCase(), m[2]);
  m = s.match(/^(\d{6})(?:\.(SH|SZ|BJ))?$/i);
  if (m) return mk(m[2] ? m[2].toLowerCase() : guess(m[1]), m[1]);
  const local = L?.STOCKS?.find(x => x.name === s || s.includes(x.name));
  if (local) { const [c, ex] = local.code.split('.'); return mk(ex.toLowerCase(), c, local.name); }
  const t = await get(`https://smartbox.gtimg.cn/s3/?v=2&q=${encodeURIComponent(s)}&t=gp`);
  const hint = JSON.parse(`"${(t.match(/v_hint="([^"]*)"/) || [])[1] || ''}"`);
  const first = hint.split('^').map(x => x.split('~')).find(a => /^(sh|sz|bj)$/.test(a[0]) && /^\d{6}$/.test(a[1]));
  if (!first) throw new Error(`无法识别证券：${s}`);
  return mk(first[0], first[1], first[2]);
  function guess(c) { return /^[69]/.test(c) ? 'sh' : /^[48]/.test(c) ? 'bj' : 'sz'; }
  function mk(ex, c, name) { return { tx: ex + c, code: `${c}.${ex.toUpperCase()}`, name }; }
}

async function realtimeQuote({ codes }) {
  const list = await Promise.all((Array.isArray(codes) ? codes : [codes]).slice(0, 10).map(resolveCode));
  const text = await get(`https://qt.gtimg.cn/q=${list.map(x => x.tx).join(',')}`, { gbk: true });
  const out = [];
  for (const part of text.split(';')) {
    const m = part.match(/v_(\w+)="([^"]+)"/); if (!m) continue;
    const f = m[2].split('~'); if (f.length < 47 || !(Number(f[3]) > 0)) continue;
    const code = list.find(x => x.tx === m[1])?.code || m[1];
    out.push({ code, name: f[1], price: +f[3], prevClose: +f[4], open: +f[5], chgPct: +f[32], high: +f[33], low: +f[34],
      amountWan: +f[37], turnoverPct: +f[38], pe: +f[39], totalMvYi: +f[45], pb: +f[46],
      time: f[30]?.replace(/^(\d{4})(\d\d)(\d\d)(\d\d)(\d\d)(\d\d)$/, '$1-$2-$3 $4:$5:$6') });
  }
  if (!out.length) throw new Error('未返回有效实时行情');
  return { data: out, sources: [{ title: `腾讯证券实时行情 ${out.map(x => x.name).join('、')}`, url: `https://gu.qq.com/${list[0]?.tx}`, provider: '腾讯证券', asof: out[0]?.time }] };
}

async function fetchKline(code, days) {
  const s = await resolveCode(code);
  const j = JSON.parse(await get(`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=${s.tx},day,,,${Math.min(Math.max(days, 30), 320)},qfq`));
  const d = j.data?.[s.tx]; const raw = d?.qfqday || d?.day || [];
  // 腾讯：[日期, 开, 收, 高, 低, 量] → KRow：[日期, 开, 高, 低, 收, 量]
  const rows = raw.map(r => [r[0].replace(/-/g, ''), +r[1], +r[3], +r[4], +r[2], +r[5]]);
  return { s, rows, name: d?.qt?.[s.tx]?.[1] || s.name };
}

async function historicalKline({ code, days = 60 }) {
  const { s, rows, name } = await fetchKline(code, Math.max(days, 60));
  const last = rows.slice(-Math.min(days, 60));
  const closes = rows.map(r => r[4]);
  const hi = Math.max(...last.map(r => r[2])), lo = Math.min(...last.map(r => r[3]));
  return {
    data: { code: s.code, name, period: `${last[0]?.[0]}~${last.at(-1)?.[0]}`, columns: ['date', 'open', 'high', 'low', 'close', 'volume'],
      rows: last.slice(-30), rangeHigh: hi, rangeLow: lo, chgPctInRange: +((closes.at(-1) / last[0][4] - 1) * 100).toFixed(2) },
    sources: [{ title: `${name || s.code} 日K线（前复权）`, url: `https://gu.qq.com/${s.tx}`, provider: '腾讯证券', asof: last.at(-1)?.[0] }],
  };
}

async function tencentIndicators({ code }) {
  const { s, rows, name } = await fetchKline(code, 200);
  if (rows.length < 61) throw new Error('K线数据不足 60 根，无法计算');
  const t = L.summarizeTech(rows);
  const r2 = (x) => typeof x === 'number' ? +x.toFixed(2) : x;
  return { data: { code: s.code, name, asof: rows.at(-1)[0], ...Object.fromEntries(Object.entries(t).map(([k, v]) => [k, r2(v)])) },
    sources: [{ title: `${name || s.code} 技术指标（MA/MACD/RSI，基于腾讯前复权日K计算）`, url: `https://gu.qq.com/${s.tx}`, provider: 'AlphaDesk 指标引擎 · 腾讯证券', asof: rows.at(-1)[0] }] };
}

async function technicalIndicators({ code }) {
  const s = await resolveCode(code);
  return chain([
    ['iFinD QuantAPI', async () => {
      if (!THS.thsEnabled()) throw new Error('未配置');
      const rows = await THS.thsHistory(s.code, daysAgo(400), today());
      if (rows.length < 61) throw new Error('历史行情不足');
      return { data: { code: s.code, asof: rows.at(-1)[0], adjust: '不复权', ...L.summarizeTech(rows) },
        sources: [{ title: `${s.name || s.code} 技术指标（iFinD不复权行情计算）`, url: ifindUrl, provider: '同花顺 iFinD QuantAPI', asof: rows.at(-1)[0] }] };
    }],
    ['腾讯证券', () => tencentIndicators({ code })],
  ]);
}

async function financials({ code, periods = 6 }) {
  const s = await resolveCode(code);
  const cols = 'REPORT_DATE_NAME,REPORT_DATE,TOTALOPERATEREVE,TOTALOPERATEREVETZ,PARENTNETPROFIT,PARENTNETPROFITTZ,KCFJCXSYJLR,XSMLL,XSJLL,ROEJQ,ZCFZL,EPSJB,BPS,MGJYXJJE';
  const url = `https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_FINANCE_MAINFINADATA&columns=${cols}&filter=(SECUCODE%3D%22${s.code}%22)&pageSize=${Math.min(periods, 12)}&sortColumns=REPORT_DATE&sortTypes=-1`;
  const j = JSON.parse(await get(url));
  const yi = (v) => v == null ? null : +(v / 1e8).toFixed(2), p = (v) => v == null ? null : +(+v).toFixed(2);
  const data = (j.result?.data || []).map(r => ({ period: r.REPORT_DATE_NAME, revenueYi: yi(r.TOTALOPERATEREVE), revenueYoY: p(r.TOTALOPERATEREVETZ),
    netProfitYi: yi(r.PARENTNETPROFIT), netProfitYoY: p(r.PARENTNETPROFITTZ), deductNetProfitYi: yi(r.KCFJCXSYJLR), grossMargin: p(r.XSMLL),
    netMargin: p(r.XSJLL), roe: p(r.ROEJQ), debtRatio: p(r.ZCFZL), eps: p(r.EPSJB), bps: p(r.BPS), ocfps: p(r.MGJYXJJE) }));
  if (!data.length) throw new Error(`未查到 ${s.code} 的财务数据`);
  return { data: { code: s.code, unit: '金额：亿元；比率：%', rows: data },
    sources: [{ title: `${s.code} 主要财务指标（${data[0].period} 起）`, url: `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=${s.tx.toUpperCase()}#/cwfx`, provider: '东方财富 F10', asof: data[0].period }] };
}

// ===== 多源取数：按优先级依次尝试，记录实际命中的提供方与失败原因 =====
async function chain(steps) {
  const errs = [];
  for (const [name, fn] of steps) {
    try { const r = await fn(); if (r && r.data != null && (!Array.isArray(r.data) || r.data.length)) { if (errs.length) r.data = { ...(typeof r.data === 'object' && !Array.isArray(r.data) ? r.data : { rows: r.data }), _fallback: errs }; return r; } throw new Error('返回空数据'); }
    catch (e) { errs.push(`${name}: ${e.message}`.slice(0, 160)); }
  }
  throw new Error(`全部数据源失败（${errs.join('；')}）`);
}
const ifindUrl = 'https://www.51ifind.com';
const today = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
const daysAgo = (n) => new Date(Date.now() - n * 864e5).toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
const mcpRes = (title, text) => ({ data: { markdown: clipText(text, 6000) }, sources: [{ title, url: ifindUrl, provider: '同花顺 iFinD MCP', asof: today() }] });
const clipText = (s, n) => (s.length > n ? s.slice(0, n) + '…' : s);

async function rtQuote({ codes }) {
  const list = await Promise.all((Array.isArray(codes) ? codes : [codes]).slice(0, 10).map(resolveCode));
  return chain([
    ['iFinD QuantAPI', async () => { if (!THS.thsEnabled()) throw new Error('未配置'); const d = await THS.thsRealtime(list.map(x => x.code));
      if (!d.length || !d.some(x => x.price > 0)) throw new Error('无有效报价');
      return { data: d.map(x => ({ ...x, name: list.find(l => l.code === x.code)?.name })), sources: [{ title: `iFinD 实时行情 ${list.map(x => x.name || x.code).join('、')}`, url: ifindUrl, provider: '同花顺 iFinD QuantAPI', asof: d[0]?.time }] }; }],
    ['腾讯证券', () => realtimeQuote({ codes: list.map(x => x.code) })],
  ]);
}

async function histK({ code, days = 60 }) {
  const s = await resolveCode(code); const n = Math.min(days, 60);
  return chain([
    ['iFinD QuantAPI', async () => { if (!THS.thsEnabled()) throw new Error('未配置'); const rows = (await THS.thsHistory(s.code, daysAgo(Math.ceil(n * 1.6) + 10), today())).slice(-n);
      if (!rows.length) throw new Error('无数据');
      return { data: { code: s.code, name: s.name, adjust: '不复权', period: `${rows[0][0]}~${rows.at(-1)[0]}`, columns: ['date', 'open', 'high', 'low', 'close', 'volume'], rows: rows.slice(-30),
        rangeHigh: Math.max(...rows.map(r => r[2])), rangeLow: Math.min(...rows.map(r => r[3])), chgPctInRange: +((rows.at(-1)[4] / rows[0][4] - 1) * 100).toFixed(2) },
        sources: [{ title: `${s.name || s.code} 日K线（iFinD 历史行情）`, url: ifindUrl, provider: '同花顺 iFinD QuantAPI', asof: rows.at(-1)[0] }] }; }],
    ['腾讯证券', () => historicalKline({ code: s.code, days })],
  ]);
}

async function fin({ code, periods = 6 }) {
  const s = await resolveCode(code);
  return chain([
    ['iFinD QuantAPI', async () => { if (!THS.thsEnabled()) throw new Error('未配置'); const rows = await THS.thsFinancials(s.code, Math.min(periods, 8));
      if (!rows.length) throw new Error('无数据');
      return { data: { code: s.code, unit: '金额：亿元；比率：%', rows }, sources: [{ title: `${s.name || s.code} 主要财务指标（iFinD 基础数据，${rows[0].period} 起）`, url: ifindUrl, provider: '同花顺 iFinD QuantAPI', asof: rows[0].period }] }; }],
    ['东方财富', () => financials({ code: s.code, periods })],
  ]);
}

async function notices({ code, days = 30, keyword }) {
  const s = await resolveCode(code);
  return chain([
    ['iFinD QuantAPI 公告', async () => { if (!THS.thsEnabled()) throw new Error('未配置'); let rows = await THS.thsAnnouncements(s.code, Math.min(days, 180), 30);
      if (keyword) rows = rows.filter(r => r.title.includes(keyword)); rows = rows.slice(0, 15);
      return { data: rows, sources: [{ title: `${s.name || s.code} 近 ${days} 日公告（${rows.length} 条）`, url: ifindUrl, provider: '同花顺 iFinD 公告查询', asof: rows[0]?.date }] }; }],
    ['iFinD MCP 公告', async () => mcpRes(`${s.name || s.code} 公告检索`, await ifindCall('news', 'search_notice', { query: `${s.name || s.code} ${keyword || '最新公告'}`, time_start: daysAgo(days), time_end: today(), size: 8 }))],
  ]);
}

async function mcpStock({ tool = 'get_stock_summary', query }) {
  if (!ifindMcpEnabled()) throw new Error('iFinD MCP 未安装');
  const ok = ['get_stock_summary', 'search_stocks', 'get_stock_performance', 'get_stock_info', 'get_stock_shareholders', 'get_stock_financials', 'get_risk_indicators', 'get_stock_events', 'get_esg_data'];
  if (!ok.includes(tool)) tool = 'get_stock_summary';
  const txt = await ifindCall('stock', tool, { query });
  return checkedMcp(`iFinD ${tool}：${query}`, txt, query);
}
async function mcpNews({ query, type = 'news', days = 30, size = 8 }) {
  const tool = type === 'notice' ? 'search_notice' : type === 'trending' ? 'search_trending_news' : 'search_news';
  const params = tool === 'search_trending_news' ? { query } : { query, time_start: daysAgo(days), time_end: today(), size: Math.min(size, 10) };
  return chain([
    ['iFinD MCP', async () => mcpRes(`iFinD ${tool === 'search_notice' ? '公告' : '资讯'}检索：${query}`, await ifindCall('news', tool, params))],
    ['东方财富快讯', async () => { const d = await EXT.eastmoneyFlash(10, query.split(/\s+/)[0]); if (!d.length) throw new Error('无匹配'); return { data: d, sources: [{ title: `东方财富 7x24：${query}`, url: 'https://kuaixun.eastmoney.com/', provider: '东方财富', asof: d[0]?.time }] }; }],
    ['华尔街见闻快讯', async () => { const d = await EXT.wscnLives(10, query.split(/\s+/)[0]); if (!d.length) throw new Error('无匹配'); return { data: d, sources: [{ title: `华尔街见闻 7x24：${query}`, url: 'https://wallstreetcn.com/live/global', provider: '华尔街见闻', asof: d[0]?.time }] }; }],
  ]);
}
async function macro({ query, fred_series }) {
  const steps = [
    ['iFinD MCP EDB', async () => mcpRes(`iFinD 宏观/行业指标：${query}`, await ifindCall('edb', 'get_edb_data', { query }))],
    ['iFinD MCP EDB 搜索', async () => mcpRes(`iFinD 指标搜索：${query}`, await ifindCall('edb', 'search_edb', { query }))],
  ];
  if (fred_series) steps.push(['FRED', async () => { const d = await EXT.fredSeries(fred_series); return { data: { series: fred_series, rows: d }, sources: [{ title: `FRED ${fred_series}`, url: `https://fred.stlouisfed.org/series/${fred_series}`, provider: '圣路易斯联储 FRED', asof: d.at(-1)?.date }] }; }]);
  return chain(steps);
}
async function idxVal({ code }) {
  return chain([
    ['iFinD MCP', async () => checkedMcp(`iFinD 指数估值：${code}`, await ifindCall('index', 'index_data', { query: `${code}指数最新PE、PB与历史估值分位数，注明样本区间及日期` }), `${code}指数`)],
    ['公开指数估值', async () => {
      const r = await EXT.indexValuation(code);
      return { data: r.data, sources: [{ title: `${r.data.name || r.data.code} 指数估值（PE 及历史分位）`, url: r.url, provider: r.provider, asof: r.data.asof }] };
    }],
  ]);
}
async function idxData({ query }) {
  return checkedMcp(`iFinD 指数/板块：${query}`, await ifindCall('index', /板块|行业|概念/.test(query) ? 'sector_data' : 'index_data', { query }), query);
}
async function flash({ keyword = '', limit = 15 }) {
  return chain([
    ['iFinD MCP', async () => mcpRes(`iFinD 最新资讯：${keyword || '市场'}`, await ifindCall('news', 'search_news', { query: keyword || '最新财经市场快讯', size: Math.min(limit, 10), time_start: daysAgo(1), time_end: today() }))],
    ['东方财富', async () => { const d = await EXT.eastmoneyFlash(limit, keyword); return { data: d, sources: [{ title: `东方财富 7x24 快讯${keyword ? `：${keyword}` : ''}`, url: 'https://kuaixun.eastmoney.com/', provider: '东方财富', asof: d[0]?.time }] }; }],
    ['华尔街见闻', async () => { const d = await EXT.wscnLives(limit, keyword); if (!d.length) throw new Error('无匹配'); return { data: d, sources: [{ title: `华尔街见闻 7x24 快讯${keyword ? `：${keyword}` : ''}`, url: 'https://wallstreetcn.com/live/global', provider: '华尔街见闻', asof: d[0]?.time }] }; }],
  ]);
}

const S = (props, req) => ({ type: 'object', properties: props, required: req });
const code = { type: 'string', description: '证券代码或名称，如 300750 / 宁德时代 / 600519.SH' };
export const TOOL_META = {
  get_realtime_quote: { title: '获取实时行情', group: '金融数据库', run: rtQuote, schema: S({ codes: { type: 'array', items: { type: 'string' }, description: '证券代码或名称列表（≤10）' } }, ['codes']),
    desc: '实时行情：现价、涨跌幅、成交额、换手率、PE(TTM)、PB、总市值。源：iFinD QuantAPI → 腾讯证券。' },
  get_historical_k_data: { title: '获取历史K线数据', group: '金融数据库', run: histK, schema: S({ code, days: { type: 'integer', description: '最近交易日数，≤60' } }, ['code']),
    desc: '日K线（开高低收量）与区间高低点、涨跌幅。源：iFinD 历史行情 → 腾讯前复权K线。' },
  get_technical_indicators: { title: '计算技术指标', group: '金融数据库', run: technicalIndicators, schema: S({ code }, ['code']),
    desc: '优先用 iFinD 不复权日K，腾讯前复权兜底，注明复权口径，计算 MA5/20/60、MACD、RSI14。' },
  get_financial_data: { title: '获取主要财务指标', group: '金融数据库', run: fin, schema: S({ code, periods: { type: 'integer', description: '报告期数，默认6' } }, ['code']),
    desc: '最近报告期营收、归母净利及同比、毛利率、ROE、资产负债率、EPS。源：iFinD 基础数据 → 东方财富 F10。' },
  get_stock_announcements: { title: '获取公司公告', group: '公告资讯', run: notices, schema: S({ code, days: { type: 'integer', description: '回溯天数，默认30' }, keyword: { type: 'string', description: '公告标题关键词，可选' } }, ['code']),
    desc: '上市公司公告标题、日期与 PDF 链接。源：iFinD 公告查询 → iFinD MCP 公告语义检索。' },
  ifind_stock_query: { title: 'iFinD 股票数据查询', group: '金融数据库', run: mcpStock,
    schema: S({ tool: { type: 'string', enum: ['get_stock_summary', 'search_stocks', 'get_stock_performance', 'get_stock_info', 'get_stock_shareholders', 'get_stock_financials', 'get_risk_indicators', 'get_stock_events', 'get_esg_data'], description: 'summary=信息摘要/估值；search_stocks=智能选股；performance=行情与技术指标；info=基本资料；shareholders=股东；financials=指定财务指标；risk=风险指标；events=重大事件指标；esg=ESG' },
      query: { type: 'string', description: '自然语言问句，含证券与指标与时间，如“宁德时代2025年三季度ROE与净利润增速”；最多5只股票' } }, ['tool', 'query']),
    desc: '同花顺 iFinD 自然语言取数（A股）：估值(PE/PB/PS/PEG/EV-EBITDA)、任意财务指标、股东、风险指标、ESG、智能选股、行业板块股票。指标较冷门或需跨公司对比时优先用它。' },
  search_news_notices: { title: '搜索新闻与公告', group: '公告资讯', run: mcpNews,
    schema: S({ query: { type: 'string', description: '检索语句，如“宁德时代 储能 订单”' }, type: { type: 'string', enum: ['news', 'notice', 'trending'], description: 'news=财经新闻，notice=公告原文段落，trending=热点' }, days: { type: 'integer' }, size: { type: 'integer' } }, ['query']),
    desc: '财经新闻/公告段落/热点检索。源：iFinD MCP → 华尔街见闻 → 东方财富快讯。' },
  get_macro_data: { title: '获取宏观与行业经济数据', group: '宏观数据库', run: macro,
    schema: S({ query: { type: 'string', description: '指标描述，如“中国CPI当月同比（202401-202609）”“新能源汽车产量当月值”' }, fred_series: { type: 'string', description: '可选：美国宏观用 FRED 序列ID，如 DGS10、CPIAUCSL、FEDFUNDS' } }, ['query']),
    desc: '宏观（GDP/CPI/PPI/社融/利率）、行业经济与大宗商品数据。源：iFinD EDB → FRED（美国序列兜底）。' },
  get_index_valuation: { title: '获取指数估值分位', group: '金融数据库', run: idxVal, schema: S({ code: { type: 'string', description: '指数代码，如 000300（沪深300）、000905、399006' } }, ['code']),
    desc: '指数 PE 及全历史/近5年分位。源：iFinD MCP → 蛋卷基金 → 中证指数官网。' },
  get_index_sector_data: { title: '获取指数板块数据', group: '金融数据库', run: idxData, schema: S({ query: { type: 'string', description: '如“沪深300近20日涨跌幅”“半导体板块今日涨跌幅与成交额”' } }, ['query']),
    desc: '指数与行业/概念板块行情、成分。源：iFinD MCP。' },
  get_news_flash: { title: '获取7x24快讯', group: '互联网', run: flash, schema: S({ keyword: { type: 'string', description: '关键词过滤，可空' }, limit: { type: 'integer' } }, []),
    desc: '市场 7x24 实时快讯。源：iFinD MCP → 东方财富 → 华尔街见闻。' },

};
if (!ifindMcpEnabled()) for (const k of ['ifind_stock_query', 'get_index_sector_data']) delete TOOL_META[k];

export const TOOL_SCHEMAS = Object.entries(TOOL_META).map(([name, t]) => ({ type: 'function', function: { name, description: t.desc, parameters: t.schema } }));

export async function runTool(name, args, { signal } = {}) {
  const t = TOOL_META[name];
  if (!t) throw new Error(`未知工具 ${name}`);
  return withSignal(signal, async () => {
    signal?.throwIfAborted();
    const result = await t.run(args || {});
    signal?.throwIfAborted();
    return publicData(result);
  });
}

// 极端分位数和市值必须附验证状态；无法匹配口径时不作自动采信。
async function checkedMcp(title, text, query) {
  const result = mcpRes(title, text);
  const checks = [];
  const extreme = extremePercentile(text);
  if (extreme) {
    const c = String(query).match(/\b(?:000\d{3}|399\d{3}|9\d{5})\b/)?.[0];
    if (/指数|沪深300|中证|创业板指/.test(query) && c) {
      try {
        const verified = await EXT.indexValuation(c);
        result.data.independentValuation = verified.data;
        result.sources.push({ title: `${c} 指数估值交叉验证`, provider: verified.provider, url: verified.url, asof: verified.data.asof });
        checks.push({ metric: '历史分位', status: '口径存疑', reason: '已取得独立估值历史，但未确认双方样本区间一致；采用独立历史并注明区间' });
      } catch { checks.push({ metric: '历史分位', status: '口径存疑', reason: '独立历史估值源不可用，禁止采信0/100分位' }); }
    } else checks.push({ metric: '历史分位', status: '口径存疑', reason: '未取得同样本区间的历史PE，禁止采信0/100分位' });
  }
  if (/市值/.test(text)) {
    const local = L?.STOCKS?.filter(x => String(query).includes(x.name) || String(query).includes(x.code.slice(0, 6))) || [];
    const inputs = [...local.map(x => x.code), ...(String(query).match(/\b\d{6}(?:\.(?:SH|SZ|BJ))?\b/gi) || [])];
    const codes = [...new Set((await Promise.all(inputs.map(resolveCode))).map(s => s.code))];
    try {
      if (codes.length !== 1) throw new Error('无法确定唯一标的');
      const quote = await rtQuote({ codes });
      const rows = Array.isArray(quote.data) ? quote.data : quote.data.rows;
      const current = rows?.[0];
      checks.push({ metric: '总市值', ...marketCapCheck(totalCapYi(text), current?.totalMvYi) });
      result.data.realtimeCrossCheck = quote.data;
      result.sources.push(...quote.sources);
    } catch { checks.push({ metric: '总市值', status: '口径存疑', reason: '无法取得同标的实时总市值，禁止直接采信冲突值' }); }
  }
  if (checks.length) {
    result.data.validation = checks;
    result.data.markdown += '\n\n[数据校验警告]\n' + checks.map(x => `${x.metric}：${x.status}；${x.reason}`).join('\n');
  }
  return result;
}
