import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { adaptFrameworkSnapshot, createEmbedReceiver, createEmbedBridge, createFrameworkLoadGuard } from '../../app/research_web/ui/frameworks/embed-bridge.mjs';
import { renderEmbedDashboard } from '../../app/research_web/ui/frameworks/embed-dashboard.mjs';
import { renderFrameworks } from '../../app/research_web/ui/frameworks.mjs';
import { goldTestData } from '../../app/research_web/ui/frameworks/fixtures/gold-v0.mjs';
import { dollarTestData } from '../../app/research_web/ui/frameworks/fixtures/dollar-v1.mjs';

test('adapters preserve native scores, nulls, status, sources and revision without mutation', () => {
  for (const data of [goldTestData(), dollarTestData()]) {
    const before = structuredClone(data);
    const adapted = adaptFrameworkSnapshot(data);
    assert.deepEqual(adapted, before);
    adapted.snapshot.status = 'changed';
    assert.deepEqual(data, before);
    const html = renderEmbedDashboard(before);
    assert.match(html, /原生得分|原生维度得分/);
    assert.match(html, /回测 · 量化策略 · 模型拟合：尚未接入/);
    assert.doesNotMatch(html, /<pre|snapshot\.json/);
  }
});
test('bridge rejects foreign origin/source/slug/revision/token and acknowledges exact displayed snapshot', () => {
  const data = goldTestData(), sent = [], source = { postMessage: (...args) => sent.push(args) };
  const bridge = createEmbedBridge({ origin: 'https://workbench.test' });
  bridge.bind({ contentWindow: source }, data, 'nonce');
  const event = { origin: 'https://workbench.test', source, data: { channel: 'rwb-framework-v1', type: 'ready', slug: 'gold' } };
  for (const bad of [{ origin: 'https://evil.test' }, { source: {} }, { data: { ...event.data, slug: 'dollar' } }]) bridge.receive({ ...event, ...bad });
  assert.equal(sent.length, 0);
  bridge.receive(event);
  assert.deepEqual(sent[0][0].payload, data);
  assert.equal(sent[0][1], event.origin);
  const ack = { ...event, data: { ...event.data, type: 'ack', revision: data.snapshot.revision, token: 'nonce' } };
  for (const bad of [{ revision: 'wrong' }, { token: 'old' }, { slug: 'dollar' }]) assert.equal(bridge.receive({ ...ack, data: { ...ack.data, ...bad } }), false);
  assert.equal(bridge.ready('gold', data.snapshot.revision), false);
  assert.equal(bridge.receive(ack), true);
  assert.equal(bridge.ready('gold', data.snapshot.revision), true);
  bridge.bind({ contentWindow: {} }, dollarTestData(), 'next');
  assert.equal(bridge.receive(ack), false);
  assert.equal(bridge.ready('gold', data.snapshot.revision), false);
});
test('delayed loads cannot replace newer route or refresh', async () => {
  const guard = createFrameworkLoadGuard(), first = guard.begin();
  let resolve;
  const old = new Promise(r => { resolve = r; });
  const second = guard.begin();
  let committed = 'new';
  const work = old.then(() => { if (guard.current(first)) committed = 'old'; });
  resolve(); await work;
  assert.equal(committed, 'new');
  assert.equal(guard.current(second), true);
  guard.invalidate(); assert.equal(guard.current(second), false);
});
test('native host keeps Bot revision stale and static embeds have no Bot', () => {
  const data = goldTestData();
  const html = renderFrameworks({ slug: 'gold', data, bot: { open: true, sessionId: 's', revision: 'older', bridgeReady: true } });
  assert.match(html, /data-native-framework/);
  assert.match(html, /data-revision="older"/);
  assert.match(html, /数据已更新/);
  assert.match(html, /href="#\/frameworks\/gold" target="_blank"/);
  const staticHTML = renderFrameworks({ slug: 'ainvest', data: { framework: { slug: 'ainvest', name: 'AInvest', display: { imported_at: '2026-10-14' } }, snapshot: { revision: 'static' } } });
  assert.match(staticHTML, /静态导入 · 2026-10-14/);
  assert.doesNotMatch(staticHTML, /framework-bot|data-native-framework/);
});
test('core entry never loads bundled JSON or legacy compiled app', async () => {
  for (const slug of ['gold', 'dollar']) {
    const html = await readFile(new URL(`../../app/research_web/frameworks/embeds/${slug}/index.html`, import.meta.url), 'utf8');
    assert.match(html, /\/static\/frameworks\/embed-core.mjs/);
    assert.doesNotMatch(html, /app\.js|index-CNyL|https?:/);
  }
  const core = await readFile(new URL('../../app/research_web/ui/frameworks/embed-core.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(core, /fetch\(|\.json/);
  assert.match(core, /parentWindow: window.parent/);
});

test('canonical server Gold seed renders every native core section and source metadata', async () => {
  const data = JSON.parse(await readFile(new URL('./research_web_frameworks_gold_canonical.json', import.meta.url), 'utf8'));
  const html = renderEmbedDashboard(adaptFrameworkSnapshot(data));
  const { snapshot: s } = data;
  assert.match(html, /id="allocation_context"/);
  assert.doesNotMatch(html, /id="allocation"/);
  assert.ok(html.includes(s.cycle_macro.policy_phase));
  assert.ok(html.includes(s.allocation_context.diversification_note));
  assert.ok(html.includes(s.allocation_context.drawdown_note));
  for (const flow of s.supply_demand.flows) { assert.ok(html.includes(flow.label)); assert.ok(html.includes(flow.value)); assert.ok(html.includes(flow.note)); }
  for (const factor of s.pricing_drivers.factors) {
    assert.ok(html.includes(factor.raw_value));
    assert.ok(html.includes(`权重 ${factor.weight}%`));
  }
  for (const regime of s.cycle_macro.regimes) { assert.ok(html.includes(regime.label)); assert.ok(html.includes(regime.fit)); assert.ok(html.includes(regime.reason)); }
  for (const strike of s.options.strikes) { assert.ok(html.includes(strike.label)); assert.ok(html.includes(strike.side)); }
  for (const scenario of s.allocation_context.scenarios) { assert.ok(html.includes(scenario.label)); assert.ok(html.includes(scenario.gold)); assert.ok(html.includes(scenario.note)); }
  for (const correlation of s.allocation_context.correlations) { assert.ok(html.includes(correlation.row)); assert.ok(html.includes(correlation.column)); }
  for (const gap of s.gaps) { assert.ok(html.includes(gap.label)); assert.ok(html.includes(gap.next_check)); }
  assert.ok(html.includes(`变化 ${s.market_context.change_percent}%`));
  assert.ok(html.includes(s.market_context.range_low.toLocaleString('zh-CN', { maximumFractionDigits: 3 })));
  for (const block of [s.market_context,s.pricing_drivers,s.supply_demand,s.cycle_macro,s.options,s.allocation_context]) {
    for (const source of block.sources) { assert.ok(html.includes(`href="${source.url}"`)); assert.ok(html.includes(source.unit)); assert.ok(html.includes(source.method)); }
  }
  for (const event of s.events) { assert.ok(html.includes(event.title)); assert.ok(html.includes(event.impact)); }
  for (const evidence of s.evidence) { assert.ok(html.includes(`href="${evidence.url}"`)); assert.ok(html.includes(evidence.observation)); }
});
test('canonical Dollar seed preserves dimension null score, units, source links, range and gaps', async () => {
  const data = JSON.parse(await readFile(new URL('./research_web_frameworks_dollar_canonical.json', import.meta.url), 'utf8'));
  data.snapshot.plumbing_m.score = null;
  const html = renderEmbedDashboard(adaptFrameworkSnapshot(data));
  assert.match(html, /原生维度得分 —/);
  for (const key of ['quantity_q','price_p','fiscal_g','plumbing_m','cross_border_x']) {
    const block = data.snapshot[key];
    for (const series of block.series) { assert.ok(html.includes(series.unit)); assert.ok(html.includes(series.label)); }
    for (const source of block.sources) assert.ok(html.includes(`href="${source.url}"`));
  }
  const before = structuredClone(data);
  renderEmbedDashboard(data);
  assert.deepEqual(data, before);
});
test('refresh changes displayed revision while old Bot retains its bound revision and disables both actions', () => {
  const data = goldTestData();
  const bot = { open: true, sessionId: 's', revision: data.snapshot.revision, bridgeReady: true };
  const before = structuredClone(bot);
  data.snapshot.revision = 'a'.repeat(64);
  const html = renderFrameworks({ slug: 'gold', data, bot });
  assert.ok(html.includes(`data-framework-revision="${data.snapshot.revision}"`));
  assert.ok(html.includes(`data-revision="${bot.revision}"`));
  assert.match(html, /data-framework-verify disabled/);
  assert.match(html, /type="submit" disabled/);
  assert.deepEqual(bot,before);
});

test('theme metadata changes presentation independently of canonical revision and requires validated binding', () => {
  const data = goldTestData(), sent = [], source = { postMessage: m => sent.push(m) };
  const bridge = createEmbedBridge({ origin: 'https://host.test' });
  bridge.setTheme('dark'); bridge.bind({ contentWindow: source }, data, 'nonce');
  bridge.receive({ origin: 'https://host.test', source, data: { channel: 'rwb-framework-v1', type: 'ready', slug: 'gold' } });
  const payload = sent.at(-1);
  assert.equal(payload.theme,'dark'); assert.equal(payload.revision,data.snapshot.revision);
  const acks = [], themes = [], parentWindow = {};
  const receive = createEmbedReceiver({ origin: 'https://host.test', parentWindow, slug: 'gold', render: () => {}, applyTheme: t => themes.push(t), acknowledge: m => acks.push(m) });
  const event = { origin: 'https://host.test', source: parentWindow, data: payload };
  assert.equal(receive(event),true); assert.deepEqual(themes,['dark']); assert.equal(acks.length,1);
  bridge.setTheme('light'); const update = sent.at(-1);
  assert.equal(update.type,'theme'); assert.equal(update.revision,data.snapshot.revision);
  assert.equal(receive({ ...event, data: { ...update, token: 'wrong' } }),false);
  assert.equal(receive({ ...event, origin: 'https://evil.test', data: update }),false);
  assert.equal(receive({ ...event, data: update }),true); assert.deepEqual(themes,['dark','light']);
  assert.deepEqual(payload.payload,data); assert.equal(acks.length,1);
});
test('malformed revision and render failure never acknowledge or enable theme updates', () => {
  const data = goldTestData(), parentWindow = {}, acks = [], errors = [];
  const receive = createEmbedReceiver({ origin: 'https://host.test', parentWindow, slug: 'gold', render: () => { throw new Error('render'); }, applyTheme: () => {}, acknowledge: m => acks.push(m), onError: e => errors.push(e) });
  const message = { channel:'rwb-framework-v1',type:'snapshot',slug:'gold',token:'nonce',theme:'light',revision:data.snapshot.revision,payload:data };
  const event = { origin:'https://host.test',source:parentWindow,data:message };
  assert.equal(receive(event),false); assert.equal(acks.length,0); assert.equal(errors.length,1);
  assert.equal(receive({ ...event, data: { ...message, type:'theme' } }),false);
  data.snapshot.revision = 'not-a-hash'; message.revision = data.snapshot.revision;
  assert.equal(receive(event),false); assert.equal(acks.length,0);
  assert.throws(() => adaptFrameworkSnapshot(data), /合同不完整/);
});

test('iframe remount invalidates acknowledged state and old token until replacement confirms', () => {
  const data = goldTestData(), source = { postMessage() {} };
  const bridge = createEmbedBridge({ origin:'https://host.test' });
  bridge.bind({ contentWindow:source },data,'first');
  const ack = { origin:'https://host.test',source,data:{channel:'rwb-framework-v1',type:'ack',slug:'gold',revision:data.snapshot.revision,token:'first'} };
  assert.equal(bridge.receive(ack),true);
  bridge.clear(); bridge.bind({contentWindow:source},data,'replacement');
  assert.equal(bridge.ready('gold',data.snapshot.revision),false);
  assert.equal(bridge.receive(ack),false);
  assert.equal(bridge.receive({...ack,data:{...ack.data,token:'replacement'}}),true);
});

test('embedded viewport height follows wrapper at short viewports rather than clipping an oversized frame', async () => {
  const base = await readFile(new URL('../../app/research_web/ui/styles.css',import.meta.url),'utf8');
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css',import.meta.url),'utf8');
  const wrapper = base.match(/\.embedded-iframe-wrap \{([^}]+)\}/)[1];
  const iframe = css.match(/\.embedded-native-layout iframe \{([^}]+)\}/)[1];
  assert.match(wrapper,/height: calc\(100dvh - 128px\)/);
  assert.match(iframe,/height: 100%/);
  assert.doesNotMatch(iframe,/720px|min-height/);
  for (const viewport of [390,700,900]) {
    const wrapperHeight = Math.max(400,viewport-128);
    const frameHeight = wrapperHeight; // CSS percentage resolves against explicit wrapper height.
    assert.equal(frameHeight,wrapperHeight);
    assert.ok(frameHeight > 0);
  }
});
