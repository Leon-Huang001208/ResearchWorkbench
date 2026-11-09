import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { createDisclosureState } from '../../app/research_web/ui/disclosures.mjs';
import { createMarketWorkspace, renderMarketWorkspace } from '../../app/research_web/ui/market-dashboard.mjs';
import { renderModuleSidebar } from '../../app/research_web/ui/module-navigation.mjs';

const clock = () => new Date('2026-11-07T16:30:00Z');
const calendarModule = () => import('../../app/research_web/ui/market-calendar.mjs');
const unpack = url => Object.fromEntries(new URL(url, 'http://localhost').searchParams);
const envelope = (days = [], snapshot_id = 'snapshot-1') => ({ snapshot_id, days, sources: [] });

test('financial calendar is a direct market subpage and leaves existing market links intact', () => {
  const route = parseRoute('#/market?view=calendar');
  assert.equal(route.marketView, 'calendar');
  assert.equal(parseRoute('#/market?view=quotes&board_id=BK1234').marketBoardId, 'BK1234');
  assert.match(renderModuleSidebar({ route }), /view=calendar" aria-current="page">财经日历/);
  const html = renderMarketWorkspace({ calendar: { state: {} } }, route);
  assert.match(html, /<h1[^>]*>财经日历<\/h1>/);
  assert.doesNotMatch(html, /data-market-action="(?:pause|refresh)"/);
});

test('market workspace starts only same-origin calendar reads for the calendar route', async () => {
  const calls = [];
  const controller = createMarketWorkspace({ api: { request: async (path, options) => { calls.push([new URL(path, 'http://localhost').pathname, options.method]); return envelope(); } }, now: clock, storage: null });
  await controller.activate({ marketView: 'calendar' });
  controller.cancel();
  assert.deepEqual(calls, [['/market/financial-calendar', undefined], ['/market/financial-calendar', undefined]]);
});

test('Shanghai week, month date selection and category parameters stay independent', async () => {
  const { createFinancialCalendarController } = await calendarModule();
  const calls = [];
  const controller = createFinancialCalendarController({ now: clock, api: { request: async path => { calls.push(unpack(path)); return envelope(); } } });
  await controller.activate();
  assert.deepEqual(calls.splice(0), [
    { view: 'summary', start: '2026-11-02', end: '2026-11-08' },
    { view: 'events', start: '2026-11-02', end: '2026-11-08', category: 'economic' },
  ]);
  await controller.setMode('month');
  assert.deepEqual(calls.splice(0), [
    { view: 'summary', start: '2026-11-01', end: '2026-11-30' },
    { view: 'events', start: '2026-11-08', end: '2026-11-08', category: 'economic' },
  ]);
  await controller.shiftPeriod(1);
  assert.deepEqual(calls.splice(0).map(({ start, end }) => [start, end]), [
    ['2026-12-01', '2026-12-31'], ['2026-12-01', '2026-12-01'],
  ]);
  await controller.setDay('2026-12-04');
  assert.deepEqual(calls.splice(0), [{ view: 'events', start: '2026-12-04', end: '2026-12-04', category: 'economic' }]);
  await controller.setCategory('ipo');
  await controller.setMarket('hk');
  await controller.setSubtype('ipo_lottery');
  await controller.setCategory('inst');
  await controller.setHoldingType('inc');
  await controller.setFilterSet('topAum');
  await controller.setCategory('economic');
  assert.equal(calls[2].market, 'hk');
  assert.equal(calls[2].subtype, 'ipo_lottery');
  assert.equal(calls[5].holding_type, 'inc');
  assert.equal(calls[5].filter_set, 'topAum');
  assert.equal(calls[5].subtype, undefined);
  assert.deepEqual(calls[6], { view: 'events', start: '2026-12-04', end: '2026-12-04', category: 'economic' });
});

test('daily pagination uses the original snapshot and discarded responses cannot overwrite new categories', async () => {
  const { createFinancialCalendarController } = await calendarModule();
  const pending = [];
  const day = '2026-11-08';
  const controller = createFinancialCalendarController({ now: clock, api: { request(path, { signal }) {
    const query = unpack(path);
    if (query.view === 'summary') return Promise.resolve(envelope());
    return new Promise(resolve => pending.push({ query, resolve, signal }));
  } } });
  const first = controller.activate();
  pending[0].resolve(envelope([{ date: day, items: [{ id: 'first' }], total: 21, has_more: true, status: 'partial' }]));
  await first;
  const next = controller.loadMore(day);
  assert.deepEqual(pending[1].query, { view: 'events', start: day, end: day, category: 'economic', page: '1', snapshot_id: 'snapshot-1' });
  const changed = controller.setCategory('report');
  assert.equal(pending[1].signal.aborted, true);
  pending[2].resolve(envelope([{ date: day, items: [], total: null, has_more: false, status: 'not_connected' }], null));
  pending[1].resolve(envelope([{ date: day, items: [{ id: 'late' }], total: 21, has_more: false, status: 'partial' }]));
  await Promise.all([next, changed]);
  assert.deepEqual(controller.state.events.days[0].items, []);
});

test('pagination keeps immutable first-page rows and requires explicit reread after snapshot expiry', async () => {
  const { createFinancialCalendarController } = await calendarModule();
  const day = '2026-11-08';
  let attempts = 0;
  const first = { id: 'first', title: '原记录' };
  const controller = createFinancialCalendarController({ now: clock, logger() {}, api: { async request(path) {
    const query = unpack(path);
    if (query.view === 'summary') return envelope();
    attempts++;
    if (query.page === '2') throw Object.assign(new Error('expired'), { status: 409 });
    return envelope([{ date: day, items: query.page ? [{ id: 'first', title: '重复覆盖' }, { id: 'next' }] : [first], total: 41, has_more: true, status: 'partial' }]);
  } } });
  await controller.activate();
  await controller.loadMore(day);
  assert.deepEqual(controller.state.events.days[0].items, [first, { id: 'next' }]);
  await controller.loadMore(day);
  assert.equal(controller.state.pageErrors.get(day).reload, true);
  await controller.loadMore(day);
  assert.equal(attempts, 3);
  assert.deepEqual(controller.state.events.days[0].items, [first, { id: 'next' }]);
});

test('unknown and partially observed counts, exact fields and links retain their meaning', async () => {
  const { renderFinancialCalendar } = await calendarModule();
  const date = '2026-11-08';
  const state = { mode: 'week', date, today: date, category: 'economic',
    summary: envelope([{ date, status: 'partial', counts: { economic: 2, ipo: null, notify: null, report: null } }]),
    events: { ...envelope([{ date, status: 'partial', items: [{ id: '1', date, title: '<img onerror=alert(1)>', date_precision: 'date_range', end_date: '2026-11-09', source_id: 'fomc', source_url: 'https://www.federalreserve.gov/calendar.htm', observed_at: '2026-11-07T19:00:00Z', actual: 0 }, { id: '2', date, title: '无可用来源链接', source_url: 'javascript:alert(1)' }], total: 2, has_more: false }]), sources: [{ id: 'fomc', label: '美联储', url: 'https://www.federalreserve.gov/calendar.htm', status: 'partial', observed_at: '2026-11-07T19:00:00Z' }] },
  };
  const html = renderFinancialCalendar(state);
  assert.match(html, /≥2/);
  assert.match(html, /未覆盖/);
  assert.match(html, /部分覆盖/);
  assert.match(html, /11月9日/);
  assert.match(html, /美联储/);
  assert.match(html, /href="https:\/\/www\.federalreserve\.gov\/calendar\.htm"/);
  assert.match(html, />0<\/td>/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img|href="javascript:/);
});

test('disconnected categories retain their table schema and distinguish an empty covered date', async () => {
  const { renderFinancialCalendar } = await calendarModule();
  const date = '2026-11-08';
  const base = { mode: 'month', date, today: date };
  const missing = renderFinancialCalendar({ ...base, category: 'notify', subtype: 'notify_contract',
    events: envelope([{ date, status: 'not_connected', items: [], total: null, has_more: false }], null),
  });
  assert.match(missing, /<th scope="col">合同标的<\/th>/);
  assert.match(missing, /colspan="4">尚未接入<\/td>/);
  const empty = renderFinancialCalendar({ ...base, category: 'economic',
    events: envelope([{ date, status: 'covered', items: [], total: 0, has_more: false }]),
  });
  assert.match(empty, /colspan="6">当天没有事件<\/td>/);
  assert.doesNotMatch(empty, /尚未接入/);
});

test('shell restores scoped horizontal scroll for replaced calendar and table elements', async () => {
  const { renderFinancialCalendar } = await calendarModule();
  const date = '2026-11-08';
  const html = renderFinancialCalendar({ mode: 'month', date, today: date, category: 'economic' });
  const [monthKey, tableKey] = [...html.matchAll(/data-render-scroll-key="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual([monthKey, tableKey], ['financial-calendar:month:2026-11-01', 'financial-calendar:table:economic::all:2026-11-08']);
  const element = (key, left = 0) => ({ dataset: { renderScrollKey: key }, scrollLeft: left });
  const root = elements => ({ querySelectorAll: selector => selector === '[data-render-scroll-key]' ? elements : [] });
  const state = createDisclosureState();
  state.capture(root([element(monthKey, 321), element(tableKey, 102)]));
  const elements = [element(monthKey), element(tableKey), element('financial-calendar:table:ipo:ipo_listed:all:2026-11-08')];
  state.restore(root(elements));
  assert.deepEqual(elements.map(node => node.scrollLeft), [321, 102, 0]);
});

test('macro summary availability remains visible while another category is selected', async () => {
  const { renderFinancialCalendar } = await calendarModule();
  const date = '2026-11-08';
  const html = renderFinancialCalendar({ mode: 'month', date, today: date, category: 'report',
    summary: { ...envelope([{ date, status: 'stale', counts: { economic: 1 } }]), sources: [{ id: 'bls', status: 'unavailable' }] },
    events: envelope([{ date, status: 'not_connected', items: [], total: null }], null),
  });
  assert.match(html, /role="status"[^>]*>经济数据：部分来源已陈旧；部分来源暂不可用/);
  assert.match(html, /title="经济数据：≥1 · 数据已陈旧/);
  assert.match(html, /colspan="3">尚未接入/);
});
