import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';

import { parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderFrameworks } from '../../app/research_web/ui/frameworks.mjs';
import { goldFrameworkV0 } from '../../app/research_web/ui/frameworks/fixtures/gold-v0.mjs';

test('framework routes keep the hub, gold slug and seven safe tab states', () => {
  assert.deepEqual(parseRoute('#/frameworks'), { page: 'frameworks', sessionId: null, frameworkSlug: null, frameworkTab: 'overview' });
  assert.deepEqual(parseRoute('#/frameworks/gold'), { page: 'frameworks', sessionId: null, frameworkSlug: 'gold', frameworkTab: 'overview' });
  assert.equal(parseRoute('#/frameworks/gold?tab=positioning').frameworkTab, 'positioning');
  assert.equal(parseRoute('#/frameworks/gold?tab=unknown').frameworkTab, 'overview');
  assert.equal(parseRoute('#/frameworks/gold/unsafe').frameworkSlug, null);
});

test('hub separates frameworks from the asset terminal and only registers gold', () => {
  const html = renderFrameworks();
  assert.match(html, /研究框架/);
  assert.match(html, /框架解释“为什么”/);
  assert.match(html, /href="#\/workbench\/assets"/);
  assert.match(html, /href="#\/frameworks\/gold"/);
  assert.match(html, /已注册框架/);
  assert.doesNotMatch(html, /Dollar 研究框架|基金排行|完整 K 线/);
});

test('gold detail exposes all seven sections and renders each deterministic fixture view', () => {
  const sections = goldFrameworkV0.framework.sections;
  assert.equal(sections.length, 7);
  const overview = renderFrameworks({ slug: 'gold' });
  for (const [, label] of sections) assert.match(overview, new RegExp(label));
  assert.match(overview, /V0 视觉检查点/);
  assert.match(overview, /固定演示数据，不代表当前市场/);
  assert.match(overview, /role="img"/);
  assert.match(overview, /下一项验证/);

  for (const [tab, label] of sections) {
    const html = renderFrameworks({ slug: 'gold', tab });
    assert.match(html, new RegExp(`id="framework-${tab}"`), label);
    assert.match(html, /class="[^"]*active[^"]*" aria-current="page"/);
    assert.doesNotMatch(html, /<iframe|<script|<link|<img/i);
    assert.doesNotMatch(html, /加仓|止盈|买入|卖出/);
  }
});

test('gold renderer includes dedicated Lieflat encodings and honest proxy labels', () => {
  assert.match(renderFrameworks({ slug: 'gold', tab: 'drivers' }), /gold-factor-waterfall-title/);
  assert.match(renderFrameworks({ slug: 'gold', tab: 'supply' }), /gold-demand-rungs-title/);
  assert.match(renderFrameworks({ slug: 'gold', tab: 'cycle' }), /gold-cycle-lineage-title/);
  assert.match(renderFrameworks({ slug: 'gold', tab: 'positioning' }), /gold-option-pressure-title/);
  const allocation = renderFrameworks({ slug: 'gold', tab: 'allocation' });
  assert.match(allocation, /gold-correlation-matrix-title/);
  assert.match(allocation, /不提供个人仓位/);
  assert.match(renderFrameworks({ slug: 'gold', tab: 'positioning' }), /代理指标/);
});

test('framework UI remains self-hosted and responsive styles keep accessible mobile targets', async () => {
  const css = await readFile(new URL('../../app/research_web/ui/appearance.css', import.meta.url), 'utf8');
  const moduleSource = await readFile(new URL('../../app/research_web/ui/frameworks/goldar.mjs', import.meta.url), 'utf8');
  assert.match(css, /\.framework-tabs a[^}]+min-height:\s*44px/s);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]+\.framework-tabs/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)[\s\S]+\.framework-section/);
  assert.doesNotMatch(moduleSource, /font-face|cdn\.|iframe|<img/i);
});
