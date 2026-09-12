import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import { goldFallbackData, renderFrameworks } from '../../app/research_web/ui/frameworks.mjs';

test('legacy tab query remains a safe anchor into the continuous canvas', () => {
  assert.deepEqual(parseRoute('#/frameworks'), { page: 'frameworks', sessionId: null, frameworkSlug: null, frameworkTab: 'overview' });
  assert.equal(parseRoute('#/frameworks/gold?tab=positioning').frameworkTab, 'positioning');
  assert.equal(parseRoute('#/frameworks/gold?tab=unknown').frameworkTab, 'overview');
  assert.equal(parseRoute('#/frameworks/gold/unsafe').frameworkSlug, null);
});

test('hub separates framework reasoning from every asset detail class', () => {
  const html = renderFrameworks();
  assert.match(html, /框架解释“为什么”/);
  assert.match(html, /个股、基金、债券、外汇和商品详情/);
  assert.match(html, /href="#\/workbench\/assets"/);
  assert.doesNotMatch(html, /Dollar 研究框架|基金排行|完整 K 线/);
});

test('gold is one continuous canvas with seven anchors and four charts', () => {
  const data = goldFallbackData();
  const html = renderFrameworks({ slug: 'gold', data, anchor: 'positioning' });
  for (const section of data.framework.sections) {
    assert.match(html, new RegExp(`id="framework-${section.id}"`));
    assert.match(html, new RegExp(`data-framework-anchor="${section.id}"`));
  }
  assert.match(html, /data-framework-anchor="positioning" class="active"/);
  assert.equal((html.match(/data-lieflat-basics=/g) || []).length, 4);
  for (const skeleton of ['F2', 'F9', 'F6', 'F5']) assert.match(html, new RegExp(`data-lieflat-basics="${skeleton}"`));
  assert.doesNotMatch(html, /data-lieflat-basics="(?:F3|L3|F12|L16|G20)"/);
  assert.doesNotMatch(html, /<iframe|<script|<link|<img/i);
  assert.doesNotMatch(html, /加仓|止盈|买入|卖出|减仓/);
});

test('each Lieflat chart states a conclusion, source and encoding', () => {
  const html = renderFrameworks({ slug: 'gold', data: goldFallbackData() });
  assert.match(html, /样例价格接近区间上沿/);
  assert.match(html, /美元构成主要拖累/);
  assert.match(html, /投资与央行需求抵消珠宝需求回落/);
  assert.match(html, /235 执行价的代理压力最集中/);
  assert.equal((html.match(/来源：/g) || []).length, 4);
  assert.match(html, /代理指标/);
  assert.match(html, /不给出个人仓位/);
});

test('framework bot exposes explain, verify, busy and stale states', () => {
  const data = goldFallbackData();
  const closed = renderFrameworks({ slug: 'gold', data, bot: { open: false } });
  assert.match(closed, /data-framework-bot-open/);
  const open = renderFrameworks({ slug: 'gold', data, bot: { open: true, mode: 'explain', sessionId: 's', busy: true, draft: '' } });
  assert.match(open, /无工具解释/);
  assert.match(open, /DSH 正在处理/);
  assert.match(open, /data-framework-verify/);
  const stale = renderFrameworks({ slug: 'gold', data, bot: { open: true, mode: 'verify', sessionId: 's', errorCode: 'framework_snapshot_changed', error: 'stale' } });
  assert.match(stale, /数据已更新/);
  assert.match(stale, /只读检索已启用/);
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
  assert.match(css, /@media \(max-width: 760px\)[\s\S]+\.framework-bot/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]+\.lf-draw/);
});
