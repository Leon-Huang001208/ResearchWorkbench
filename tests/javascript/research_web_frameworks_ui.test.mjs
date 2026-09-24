import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderFrameworks } from '../../app/research_web/ui/frameworks.mjs';
import { dollarTestData } from '../../app/research_web/ui/frameworks/fixtures/dollar-v1.mjs';
import { goldTestData } from '../../app/research_web/ui/frameworks/fixtures/gold-v0.mjs';

test('legacy tab query remains a safe anchor into the continuous canvas', () => {
  assert.deepEqual(parseRoute('#/frameworks'), { page: 'frameworks', sessionId: null, frameworkSlug: null, frameworkTab: 'overview' });
  assert.equal(parseRoute('#/frameworks/gold?tab=positioning').frameworkTab, 'positioning');
  assert.equal(parseRoute('#/frameworks/dollar?tab=cross-border').frameworkTab, 'cross-border');
  assert.equal(parseRoute('#/frameworks/gold?tab=unknown').frameworkTab, 'overview');
  assert.equal(parseRoute('#/frameworks/gold/unsafe').frameworkSlug, null);
});

test('hub separates framework reasoning from every asset detail class', () => {
  const html = renderFrameworks();
  assert.match(html, /框架解释“为什么”/);
  assert.match(html, /个股、基金、债券、外汇和商品详情/);
  assert.match(html, /href="#\/workbench\/assets"/);
  assert.match(html, /data-framework-card="gold"/);
  assert.match(html, /data-framework-card="dollar"/);
  assert.match(html, /美元流动性框架/);
  assert.doesNotMatch(html, /基金排行|完整 K 线/);
});

test('gold is one continuous canvas with seven anchors and five charts', () => {
  const data = goldTestData();
  const html = renderFrameworks({ slug: 'gold', data, anchor: 'positioning' });
  for (const section of data.framework.sections) {
    assert.match(html, new RegExp(`id="framework-${section.id}"`));
    assert.match(html, new RegExp(`data-framework-anchor="${section.id}"`));
  }
  assert.match(html, /data-framework-anchor="positioning" class="active"/);
  assert.equal((html.match(/data-lieflat-basics=/g) || []).length, 5);
  for (const skeleton of ['F2', 'F9', 'F6', 'F5', 'L4']) assert.match(html, new RegExp(`data-lieflat-basics="${skeleton}"`));
  assert.doesNotMatch(html, /<iframe|<script|<link|<img/i);
  assert.doesNotMatch(html, /加仓|止盈|买入|卖出|减仓/);
});

test('framework renderers expose one named canvas region without nesting a main landmark', () => {
  const cases = [
    ['gold', goldTestData(), '黄金研究画布'],
    ['dollar', dollarTestData(), '美元流动性研究画布'],
  ];
  for (const [slug, data, label] of cases) {
    const html = renderFrameworks({ slug, data });
    assert.match(html, new RegExp(`<section class="framework-canvas" aria-label="${label}">`));
    assert.doesNotMatch(html, /<main class="framework-canvas">/);
  }
});

test('each Lieflat chart states a conclusion, source and encoding', () => {
  const html = renderFrameworks({ slug: 'gold', data: goldTestData() });
  assert.match(html, /最新值/);
  assert.match(html, /已知贡献合计/);
  assert.match(html, /投资与央行需求抵消珠宝需求回落/);
  assert.match(html, /235 执行价的代理压力最集中/);
  assert.match(html, /黄金与美元的负相关最显著/);
  assert.equal((html.match(/来源：/g) || []).length, 5);
  assert.match(html, /代理指标/);
  assert.match(html, /不给出个人仓位/);
});

test('framework bot exposes explain, verify, busy and stale states', () => {
  const data = goldTestData();
  const closed = renderFrameworks({ slug: 'gold', data, bot: { open: false } });
  assert.match(closed, /data-framework-bot-open aria-label="问当前框架"/);
  assert.match(closed, /<\/section><button class="framework-bot-launch"[\s\S]*<\/button><\/div>\s*<\/article>$/);
  const open = renderFrameworks({ slug: 'gold', data, bot: { open: true, mode: 'explain', sessionId: 's', busy: true, draft: '' } });
  assert.match(open, /无工具解释/);
  assert.match(open, /DSH 正在处理/);
  assert.match(open, /data-framework-verify/);
  const stale = renderFrameworks({ slug: 'gold', data, bot: { open: true, mode: 'verify', sessionId: 's', errorCode: 'framework_snapshot_changed', error: 'stale' } });
  assert.match(stale, /数据已更新/);
  assert.match(stale, /只读检索已启用/);
});

test('dollar is one continuous Q-P-g-M-X canvas with six non-repeated charts', () => {
  const data = dollarTestData();
  const html = renderFrameworks({ slug: 'dollar', data, anchor: 'cross-border' });
  for (const section of data.framework.sections) {
    assert.match(html, new RegExp(`id="framework-${section.id}"`));
    assert.match(html, new RegExp(`data-framework-anchor="${section.id}"`));
  }
  const charts = [...html.matchAll(/data-lieflat-basics="([A-Z0-9]+)"/g)].map((match) => match[1]);
  assert.deepEqual(charts, ['F9', 'F3', 'F12', 'F6', 'F2', 'F8']);
  assert.equal(new Set(charts).size, 6);
  assert.match(html, /净流动性代理/);
  assert.match(html, /非会计恒等式/);
  assert.match(html, /跨币种基差缺失必须明示/);
  assert.doesNotMatch(html, /<iframe|<script|<link|<img/i);
  assert.doesNotMatch(html, /加仓|止盈|买入|卖出|减仓/);
});

test('production renderer never substitutes browser fixture after an API failure', () => {
  const html = renderFrameworks({ slug: 'gold', status: 'error', error: 'offline' });
  assert.match(html, /框架数据暂时不可用/);
  assert.doesNotMatch(html, /离线确定性样例|data-framework="gold"/);
});

test('route transition never renders a snapshot from another framework', () => {
  const html = renderFrameworks({ slug: 'dollar', status: 'ready', data: goldTestData() });
  assert.match(html, /正在读取美元流动性框架/);
  assert.doesNotMatch(html, /data-framework="gold"|data-framework="dollar"/);
});

test('dollar F2 chart bounds the live sixty-point plumbing series', () => {
  const data = dollarTestData();
  data.snapshot.plumbing_m.series[0].points = Array.from({ length: 60 }, (_, index) => ({ date: `day-${index + 1}`, value: index - 30 }));
  const html = renderFrameworks({ slug: 'dollar', data });
  assert.match(html, /data-lieflat-basics="F2"/);
  assert.doesNotMatch(html, /价格背景暂时无法显示/);
});

test('framework API keeps snapshot binding and idempotency headers', async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, status: 202, json: async () => ({ accepted: true }) };
  };
  const api = createAPI({ fetcher, EventSourceClass: null });
  await api.frameworkMessage('gold', 'session-id', { text: '解释', expected_snapshot_revision: 'a'.repeat(64), mode: 'explain' }, 'framework-key');
  assert.equal(calls[0].url, '/api/research/frameworks/gold/sessions/session-id/messages');
  assert.equal(calls[0].options.headers['Idempotency-Key'], 'framework-key');
});

test('responsive and reduced-motion contracts cover anchor rail, charts and bot', async () => {
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  assert.match(css, /\.framework-anchor-rail a[^}]+min-height:\s*44px/s);
  assert.match(css, /@media \(max-width: 900px\)[\s\S]+\.framework-hero\s*\{[^}]*grid-template-columns:\s*1fr/s);
  assert.match(css, /@media \(max-width: 900px\)[\s\S]+\.framework-bot-launch\s*\{[^}]*width:\s*44px[^}]*min-width:\s*44px[^}]*height:\s*44px/s);
  assert.match(css, /@media \(max-width: 900px\)[\s\S]+\.framework-bot-launch\s*\{[^}]*position:\s*sticky[^}]*grid-column:\s*2/s);
  assert.match(css, /@media \(max-width: 900px\)[\s\S]+\.framework-bot-launch strong[^}]+display:\s*none/s);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]+\.framework-bot/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]+\.lf-draw/);
});
