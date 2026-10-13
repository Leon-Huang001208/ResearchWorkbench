import test from 'node:test';
import assert from 'node:assert/strict';
import { renderResearchPanel, renderResearchRecipes } from '../../app/research_web/ui/research-report.mjs';
import { renderComposer } from '../../app/research_web/ui/composer.mjs';

test('native plan is explicit about incomplete history and escapes task content', () => {
  const html = renderResearchPanel({ research_plan: { status: 'available', turn: 2, seq: 4, history_complete: false,
    items: [{ content: '<img src=x onerror=alert(1)>', status: 'completed' }] } }, 'plan');
  assert.match(html, /历史不完整/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img/);
  assert.match(html, /不代表研究或文件交付完成/);
});

test('invalid or stale report cannot show a checked quality state', () => {
  for (const quality of ['invalid', 'stale', 'incomplete']) {
    const html = renderResearchPanel({ research_report: { quality, issues: ['source_unverified:bad'] } }, 'report');
    assert.doesNotMatch(html, /质量检查已通过/);
    assert.match(html, /source_unverified/);
  }
});

test('old or invalid report notes are hidden with an explicit warning', () => {
  for (const quality of ['stale', 'invalid']) {
    const html = renderResearchPanel({ research_report: { quality, notes: [{ text: 'old-private-note' }] } }, 'notes');
    assert.doesNotMatch(html, /old-private-note/);
    assert.match(html, /旧任务|无效/);
  }
});

test('recipes are disabled while session creation is busy', () => {
  assert.match(renderResearchRecipes({ busy: true }), /disabled/);
  assert.doesNotMatch(renderResearchRecipes({ busy: false }), /disabled/);
});

test('depth selection and recipes prepare a draft without an implicit submission', () => {
  const composer = renderComposer({ page: 'fingpt', researchDepth: 'deep' });
  assert.match(composer, /value="deep" selected/);
  assert.match(composer, /data-format="pdf"/);
  const html = renderResearchRecipes();
  for (const label of ['一页纸', '主题选股', '画图', '调研清单']) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /type="submit"/);
});
