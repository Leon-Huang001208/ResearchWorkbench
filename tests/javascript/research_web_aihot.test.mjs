import test from 'node:test';
import assert from 'node:assert/strict';
import { createAihotController, renderAihot } from '../../app/research_web/ui/aihot.mjs';
import { renderHot, observedRuns, curvePath, sparkline } from '../../app/research_web/ui/aihot-hot.mjs';
import { renderPaper, pagesOf, archiveGroups } from '../../app/research_web/ui/aihot-report.mjs';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';

const citation = (id, title = id) => ({ itemId: id, title, summary: '摘要', sourceName: '发布者', sourceUrl: 'https://example.org/post', available: true, firstParty: true, otherSources: 2 });
const report = () => ({ kind: 'daily', key: '2026-10-15', issueNumber: 177, lead: { title: '头条测试', leadParagraph: '开篇' }, leadItemId: 'lead', sections: [{ label: '模型', items: [citation('lead'), citation('update')] }], highlights: [citation('update')], flashes: [citation('flash', '快讯内容')], metrics: { totalEvents: 2, sourcesCount: 4, firstPartyEvents: 1, modelsReleased: 1 }, readingMinutes: 3, prev: '2026-10-14', next: '2026-10-16' });
const hotEntry = (rank = 1) => ({ rank, story: { publicId: `id-${rank}`, title: '事件标题' }, heat: 123.7, trend: 'up', trendPct: 25, badges: ['surge', 'new'], sourceCount: 4, participantCount: 8, sourceNames: ['甲', '乙'], participants: [{ name: '来源一', kind: 'editorial' }, { name: '讨论者', kind: 'signal' }], summary: '综述', latest: '新进展', spark: [2, 3, null, 4, 8] });
const response = body => ({ ok: true, json: async () => body });

test('independent daily, weekly, monthly, archive and hot routes', () => {
  for (const tab of ['daily','weekly','monthly','archive','hot']) assert.equal(parseRoute(`#/aihot/${tab}`).aihotTab, tab);
  assert.equal(parseRoute('#/aihot/weekly?date=2026-W41').aihotDate, '2026-W41');
  assert.equal(parseRoute('#/aihot/monthly?date=2026-09').aihotDate, '2026-09');
  assert.equal(parseRoute('#/aihot/unknown').aihotTab, 'daily');
  assert.match(renderPrimaryRail({ page: 'aihot' }), /href="#\/aihot\/daily"/);
});

test('latest page uses upstream edition identity and empty page stays empty', async () => {
  const calls = [];
  const controller = createAihotController({ fetcher: async url => { calls.push(url); return response({ index: [{ key: '2026-10-15' }], report: report() }); } });
  await controller.activate({ aihotTab: 'daily' });
  assert.match(calls[0], /reports\/daily\/latest-page$/);
  assert.equal(controller.state.date, '2026-10-15');
  assert.equal(calls.length, 1);
  const empty = createAihotController({ fetcher: async () => response({ index: [], report: null }) });
  await empty.activate({ aihotTab: 'daily' });
  assert.match(renderAihot(empty.state), /暂无.*日报/);
});

test('late responses cannot replace another tab', async () => {
  let resolve;
  const controller = createAihotController({ fetcher: url => url.includes('pages/hot') ? Promise.resolve(response({ entries: [hotEntry()] })) : new Promise(done => { resolve = done; }) });
  const pending = controller.activate({ aihotTab: 'daily' });
  await controller.activate({ aihotTab: 'hot' });
  resolve(response({ index: [], report: report() })); await pending;
  assert.equal(controller.state.tab, 'hot'); assert.equal(controller.state.report, null); assert.equal(controller.state.hot.entries.length, 1);
});

test('specified report fetches exact issue and matching navigation', async () => {
  const calls = [];
  const controller = createAihotController({ fetcher: async url => { calls.push(url); return response(url.includes('/navigation/') ? { items: [] } : report()); } });
  await controller.activate({ aihotTab: 'daily', aihotDate: '2026-10-15' });
  assert.deepEqual(calls.sort(), ['/api/research/aihot/reports/daily/2026-10-15', '/api/research/aihot/reports/daily/navigation/2026-10-15'].sort());
});

test('paper includes all original page regions and removes duplicate lead', () => {
  const r = report();
  r.sections[0].items[1].related = [citation('related', '关联报道')];
  const html = renderPaper(r, [{ key: r.key, issueNumber: 177, title: '本期' }]);
  for (const word of ['第 177 期','件大事','个来源','件一手发布','个新模型','约 3 分钟','头条测试','开篇','今日看点','本期版面','期次日历','一手','另外 2 家','关联报道','快讯内容','本期完','前一日','后一日','日报合订本']) assert.ok(html.includes(word), word);
  assert.equal(pagesOf(r).pages[0].items.length, 1);
  assert.equal((html.match(/id="aihot-r-lead"/g) || []).length, 1);
  assert.match(html, /data-aihot-jump="aihot-r-update"/);
});

test('withdrawn content keeps a clear notice and has no actionable source link', () => {
  const r = report(); r.sections[0].items[1].available = false;
  const html = renderPaper(r, []);
  assert.match(html, /该内容已按来源方要求/); assert.match(html, /aihot-withdrawn/);
});

test('full hot board includes podium, rows, values, badges, participants and method', () => {
  const html = renderHot({ entries: Array.from({ length: 10 }, (_, i) => hotEntry(i + 1)), windowHours: 48, computedAt: '2026-10-16T01:00:00Z' });
  for (const word of ['热度前三','其余热点','NO.01','NO.02','NO.03','No.04–10','热度指数','124','新进展','24 小时走势','来源一','讨论者','氛围组','25%','热度是怎么算的','半衰期']) assert.ok(html.includes(word), word);
  assert.equal((html.match(/class="aihot-hot-row"/g) || []).length, 7);
});

test('untrusted publishers escape HTML and links never inject scripts', () => {
  const entry = hotEntry(); entry.story.title = '<img onerror=evil>'; entry.participants[0].name = '<script>evil</script>';
  const html = renderHot({ entries: [entry] });
  assert.doesNotMatch(html, /<img onerror|<script>/); assert.match(html, /&lt;img/);
  const r = report(); r.sections[0].items[1].sourceUrl = 'javascript:alert(1)';
  assert.doesNotMatch(renderPaper(r, []), /javascript:/);
});

test('heat lines break at missing hours and never invent a short history', () => {
  assert.deepEqual(observedRuns([1,2,null,3,null,4,5]), [[0,1],[3],[5,6]]);
  assert.match(curvePath([[0,0],[1,2],[2,1]]), /^M0 0C/);
  assert.doesNotMatch(sparkline([1,null,2], 'empty'), /<svg/);
  assert.match(sparkline([1,2,null,4], 'gaps'), /部分时段缺少可比数据/);
});

test('archive groups and source monthly expansion preserve dates', async () => {
  assert.equal(archiveGroups('daily', [{ key:'2026-10-01' },{key:'2026-09-30'}]).length, 2);
  const calls = [];
  const controller = createAihotController({ fetcher: async url => { calls.push(url); return response(url.includes('/months/') ? { items: [{ key:'2026-09-30', title:'归档标题' }] } : { index:[{key:'2026-09-30'}], report:null }); } });
  await controller.activate({ aihotTab: 'daily' });
  await controller.loadMonth('2026-09');
  assert.match(calls.at(-1), /months\/2026-09$/);
  assert.equal(controller.state.months['2026-09'].items[0].title, '归档标题');
  const html = renderAihot(controller.state); assert.match(html, /归档标题/); assert.match(html, /切换日报、周报、月报/);
});

test('errors remain visible and explicit refresh recovers', async () => {
  let broken = true;
  const controller = createAihotController({ fetcher: async () => broken ? { ok:false,status:429,json:async()=>({detail:{message:'读取受限'}}) } : response({ entries: [] }) });
  await controller.activate({ aihotTab: 'hot' }); assert.match(renderAihot(controller.state), /role="alert"/);
  broken = false; await controller.refresh(); assert.equal(controller.state.error, ''); assert.match(renderAihot(controller.state), /暂时没有热点/);
});


test('canceled month reads can retry after returning to daily', async () => {
  let monthCalls = 0;
  const controller = createAihotController({ fetcher: async (url, options) => {
    if (!url.includes('/months/')) return response({ index: [{ key:'2026-09-30' }], report: null });
    monthCalls++;
    if (monthCalls === 1) return new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(new DOMException('canceled', 'AbortError')), { once:true }));
    return response({ items: [{ key:'2026-09-30', title:'可恢复' }] });
  } });
  await controller.activate({ aihotTab:'daily' });
  const pending = controller.loadMonth('2026-09');
  await controller.activate({ aihotTab:'daily' });
  await pending; await controller.loadMonth('2026-09');
  assert.equal(monthCalls, 2); assert.equal(controller.state.months['2026-09'].loading, false);
});

test('archive failures wait for an explicit retry rather than disclosure rerenders', async () => {
  let monthCalls = 0;
  const controller = createAihotController({ fetcher: async url => {
    if (!url.includes('/months/')) return response({ index:[{ key:'2026-09-30' }], report:null });
    monthCalls++; return { ok:false,status:503,json:async()=>({detail:{message:'暂不可用'}}) };
  } });
  await controller.activate({ aihotTab:'daily' }); await controller.loadMonth('2026-09');
  controller.toggleMonth('2026-09', true); controller.toggleMonth('2026-09', true);
  assert.equal(monthCalls, 1); assert.match(controller.state.months['2026-09'].error, /暂不可用/);
});

test('periodical earlier navigation stays in current kind history', () => {
  const r = { ...report(), kind:'monthly', key:'2026-09', prev:null, next:null };
  const html = renderAihot({ tab:'monthly',kind:'monthly',date:'2026-09',report:r,editions:[] });
  assert.match(html, /data-aihot-jump="aihot-report-history">更早/);
  assert.doesNotMatch(html, /href="#\/aihot\/archive">更早/);
});

test('highlights outside the printed sections still open their report', () => {
  const r = report(); r.highlights = [citation('outside', '外部看点')];
  const html = renderPaper(r, []);
  assert.match(html, /#\/aihot\/item\/outside/);
  assert.doesNotMatch(html, /data-aihot-jump="aihot-r-outside"/);
});
