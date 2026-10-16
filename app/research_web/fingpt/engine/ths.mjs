import { registerPrivate } from './security.mjs';
import { requestSignal } from './network.mjs';
// 同花顺 iFinD QuantAPI（HTTP）客户端：access_token 自动刷新（仅内存缓存，不落盘、不打印）
// 文档：quantapi.51ifind.com/gwstatic/static/ds_web/quantapi-web/example.html
// 权限：免费版不提供 EDB；基础数据/日期序列单次 ≤1 万单元格；历史行情单次 ≤5 万单元格、最近 5 年
const BASE = () => (process.env.THS_BASE_URL || 'https://quantapi.51ifind.com/api/v1').replace(/\/$/, '');
let token = null;       // { value, expires }
let refreshing = null;

export const thsEnabled = () => !!(process.env.THS_REFRESH_TOKEN || process.env.THS_ACCESS_TOKEN);

async function refresh() {
  if (!process.env.THS_REFRESH_TOKEN) throw new Error('未配置 THS_REFRESH_TOKEN');
  refreshing ||= (async () => {
    const r = await fetch(`${BASE()}/get_access_token`, { method: 'POST', headers: { 'Content-Type': 'application/json', refresh_token: process.env.THS_REFRESH_TOKEN }, signal: requestSignal(10000) });
    const j = await r.json();
    if (j.errorcode !== 0 || !j.data?.access_token) throw new Error(`iFinD 取 token 失败：${j.errmsg || j.errorcode}`);
    token = { value: j.data.access_token, expires: Date.parse(String(j.data.expired_time).replace(' ', 'T') + '+08:00') || Date.now() + 6 * 864e5 };
    registerPrivate(token.value);
    process.env.THS_ACCESS_TOKEN = token.value; // 仅更新进程内环境
    return token.value;
  })().finally(() => { refreshing = null; });
  return refreshing;
}

async function getToken() {
  if (token && token.expires - Date.now() > 3600e3) return token.value;
  if (!token && process.env.THS_ACCESS_TOKEN && !process.env.THS_REFRESH_TOKEN) return process.env.THS_ACCESS_TOKEN;
  return refresh();
}

// token 失效类错误码（-1010 token 过期 / -1302 / Device exceed limit 等）→ 刷新后重试一次
const TOKEN_ERR = (j) => /token|device exceed|登录|未登录/i.test(j.errmsg || '') || [-1010, -1001, -1302, -1300].includes(j.errorcode);

export async function thsPost(api, body, { retry = true } = {}) {
  const tk = await getToken();
  const r = await fetch(`${BASE()}/${api}`, { method: 'POST', headers: { 'Content-Type': 'application/json', access_token: tk }, body: JSON.stringify(body), signal: requestSignal(15000) });
  const j = await r.json().catch(() => ({ errorcode: -1, errmsg: `HTTP ${r.status}` }));
  if (j.errorcode !== 0) {
    if (retry && TOKEN_ERR(j)) { token = null; await refresh(); return thsPost(api, body, { retry: false }); }
    throw Object.assign(new Error(`iFinD ${api} 错误 ${j.errorcode}：${j.errmsg}`), { code: j.errorcode });
  }
  return j;
}

const col = (tbl, k) => tbl?.table?.[k];

export async function thsRealtime(codes) {
  const j = await thsPost('real_time_quotation', { codes: codes.join(','), indicators: 'latest,preClose,open,high,low,changeRatio,amount,turnoverRatio,pe_ttm,pbr_lf,totalCapital' });
  return j.tables.map(t => ({ code: t.thscode, time: t.time?.[0], price: col(t, 'latest')?.[0], prevClose: col(t, 'preClose')?.[0], open: col(t, 'open')?.[0], high: col(t, 'high')?.[0], low: col(t, 'low')?.[0],
    chgPct: r2(col(t, 'changeRatio')?.[0]), amountYi: r2(col(t, 'amount')?.[0] / 1e8), turnoverPct: r2(col(t, 'turnoverRatio')?.[0]), peTTM: r2(col(t, 'pe_ttm')?.[0]), pbLF: r2(col(t, 'pbr_lf')?.[0]), totalMvYi: r2(col(t, 'totalCapital')?.[0] / 1e8) }));
}

export async function thsHistory(code, start, end) {
  const j = await thsPost('cmd_history_quotation', { codes: code, indicators: 'open,high,low,close,volume,amount,changeRatio', startdate: start, enddate: end, functionpara: { Fill: 'Blank' } });
  const t = j.tables[0]; const T = t.table;
  return (t.time || []).map((d, i) => [d.replace(/-/g, ''), T.open[i], T.high[i], T.low[i], T.close[i], T.volume[i]]);
}

const FIN = { revenue: 'ths_revenue_stock', revenueYoY: 'ths_or_yoy_stock', netProfit: 'ths_np_atoopc_stock', grossMargin: 'ths_gross_selling_rate_stock', roe: 'ths_roe_stock', debtRatio: 'ths_asset_liab_ratio_stock', eps: 'ths_basic_eps_stock' };
const PNAME = { '0331': '一季报', '0630': '中报', '0930': '三季报', '1231': '年报' };
function recentPeriods(n) {
  const out = []; const d = new Date(); let y = d.getFullYear();
  const ends = ['1231', '0930', '0630', '0331'];
  while (out.length < n + 4) { for (const e of ends) { const p = `${y}${e}`; if (Date.parse(`${y}-${e.slice(0, 2)}-${e.slice(2)}`) < Date.now() - 20 * 864e5) out.push(p); } y--; }
  return out;
}
export async function thsFinancials(code, n = 6) {
  const periods = recentPeriods(n);
  const calls = periods.map(p => thsPost('basic_data_service', { codes: code, indipara: Object.values(FIN).map(i => ({ indicator: i, indiparams: [p] })) }).then(j => [p, j.tables[0]?.table || {}]).catch(() => [p, {}]));
  const res = Object.fromEntries(await Promise.all(calls));
  const rows = [];
  for (const p of periods) {
    const T = res[p]; if (T[FIN.revenue]?.[0] == null && T[FIN.netProfit]?.[0] == null) continue;
    const prev = res[`${+p.slice(0, 4) - 1}${p.slice(4)}`]?.[FIN.netProfit]?.[0];
    const np = T[FIN.netProfit]?.[0];
    rows.push({ period: `${p.slice(0, 4)}${PNAME[p.slice(4)]}`, revenueYi: r2(T[FIN.revenue]?.[0] / 1e8), revenueYoY: r2(T[FIN.revenueYoY]?.[0]), netProfitYi: r2(np / 1e8),
      netProfitYoY: prev ? r2((np / prev - 1) * 100 * Math.sign(prev)) : null, grossMargin: r2(T[FIN.grossMargin]?.[0]), roe: r2(T[FIN.roe]?.[0]), debtRatio: r2(T[FIN.debtRatio]?.[0]), eps: r2(T[FIN.eps]?.[0]) });
    if (rows.length >= n) break;
  }
  return rows;
}

export async function thsAnnouncements(code, days = 30, limit = 15) {
  const end = new Date(); const start = new Date(Date.now() - days * 864e5);
  const f = (d) => d.toLocaleDateString('sv-SE', { timeZone: 'Asia/Shanghai' });
  const j = await thsPost('report_query', { codes: code, functionpara: { reportType: '901' }, beginrDate: f(start), endrDate: f(end), outputpara: 'reportDate:Y,thscode:Y,secName:Y,reportTitle:Y,pdfURL:Y,seq:Y' });
  const T = j.tables?.[0]?.table || {};
  return (T.reportTitle || []).map((title, i) => ({ date: T.reportDate[i], name: T.secName?.[i], title, seq: T.seq?.[i] })).slice(0, limit); // pdfURL 含账号 token，不外发
}

export async function thsEdb(ids, start, end) {
  const j = await thsPost('edb_service', { indicators: ids.join(','), startdate: start, enddate: end });
  return j.tables.map(t => ({ id: t.id || t.thscode, time: t.time, values: t.value || Object.values(t.table || {})[0] }));
}

function r2(v) { return v == null || Number.isNaN(v) ? null : +(+v).toFixed(2); }
