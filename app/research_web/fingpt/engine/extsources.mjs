import { requestSignal } from './network.mjs';
// 外部公开数据源（来自 codex-external-data-sources/sources.json，无需密钥）
const UA = { 'User-Agent': 'Mozilla/5.0 (Macintosh) AlphaDesk/1.0' };
const getJSON = async (url, t = 12000) => { const r = await fetch(url, { headers: UA, signal: requestSignal(t) }); if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); };
const fmt = (ms) => new Date(ms).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false });

// 华尔街见闻 7x24 快讯
export async function wscnLives(limit = 20, keyword = '') {
  const j = await getJSON(`https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=${Math.min(limit * (keyword ? 4 : 1), 100)}`);
  let items = (j.data?.items || []).map(x => ({ time: fmt(x.display_time * 1000), title: x.title || '', text: (x.content_text || '').slice(0, 300), url: x.uri, important: x.score > 1 }));
  if (keyword) items = items.filter(x => (x.title + x.text).includes(keyword));
  return items.slice(0, limit);
}

// 东方财富 7x24 快讯（JS 变量包裹）
export async function eastmoneyFlash(limit = 20, keyword = '') {
  const r = await fetch('https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html', { headers: UA, signal: requestSignal(12000) });
  const t = await r.text(); const j = JSON.parse(t.slice(t.indexOf('{'), t.lastIndexOf('}') + 1));
  let items = (j.LivesList || []).map(x => ({ time: x.showtime, title: x.title, text: (x.digest || '').slice(0, 300), url: x.url_w }));
  if (keyword) items = items.filter(x => (x.title + x.text).includes(keyword));
  return items.slice(0, limit);
}

// 指数估值：蛋卷 PE 历史（含分位）→ 兜底中证指数官网 PE
const DJ = (code) => /^\d{6}$/.test(code) ? `${/^(0|5|9)/.test(code) && !/^399/.test(code) ? 'SH' : 'SZ'}${code}` : code.replace('.', '').replace(/^(\d{6})(SH|SZ)$/i, '$2$1').toUpperCase();
export async function indexValuation(code) {
  const raw = String(code).replace(/\.(SH|SZ|CSI)$/i, '');
  try {
    const j = await getJSON(`https://danjuanfunds.com/djapi/index_eva/pe_history/${DJ(raw)}?day=all`);
    const arr = j.data?.index_eva_pe_growths || [];
    if (!arr.length) throw new Error('empty');
    const last = arr.at(-1); const pes = arr.map(x => x.pe).sort((a, b) => a - b);
    const pct = pes.filter(v => v <= last.pe).length / pes.length * 100;
    const y5 = arr.filter(x => x.ts > Date.now() - 5 * 365 * 864e5).map(x => x.pe).sort((a, b) => a - b);
    return { provider: '蛋卷基金', url: `https://danjuanfunds.com/dj-valuation-table-detail/${DJ(raw)}`, data: { code: raw, asof: fmt(last.ts).slice(0, 10), pe: last.pe, pePercentileAll: +pct.toFixed(1), pePercentile5y: +(y5.filter(v => v <= last.pe).length / y5.length * 100).toFixed(1), peMin: pes[0], peMax: pes.at(-1), peMedian: pes[Math.floor(pes.length / 2)], since: fmt(arr[0].ts).slice(0, 10) } };
  } catch {
    const j = await getJSON(`https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=${raw}`);
    const arr = j.data || []; if (!arr.length) throw new Error('中证指数无估值数据');
    const last = arr.at(-1); const pes = arr.map(x => x.peg).sort((a, b) => a - b);
    return { provider: '中证指数官网', url: `https://www.csindex.com.cn/#/indices/family/detail?indexCode=${raw}`, data: { code: raw, name: last.indexName, asof: last.tradeDate, pe: last.peg, pePercentileAll: +(pes.filter(v => v <= last.peg).length / pes.length * 100).toFixed(1), since: arr[0].tradeDate } };
  }
}

// FRED 序列（CSV，无需 key）
export async function fredSeries(series, n = 24) {
  const r = await fetch(`https://fred.stlouisfed.org/graph/fredgraph.csv?id=${encodeURIComponent(series)}`, { headers: UA, signal: requestSignal(15000) });
  if (!r.ok) throw new Error(`FRED HTTP ${r.status}`);
  const rows = (await r.text()).trim().split('\n').slice(1).map(l => l.split(',')).filter(x => x[1] && x[1] !== '.');
  return rows.slice(-n).map(([date, v]) => ({ date, value: +v }));
}
