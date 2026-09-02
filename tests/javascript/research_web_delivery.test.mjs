import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import * as views from '../../app/research_web/ui/views.mjs';
import { createController } from '../../app/research_web/ui/core.mjs';

test('delivery is independent from execution and renders missing/corrupt reasons safely', () => {
  assert.equal(typeof views.renderDelivery, 'function');
  const html = views.renderDelivery({ status: 'incomplete', required_formats: ['docx', 'xlsx'], missing_formats: ['xlsx'], files: [{ name: '<bad>.xlsx', valid: false, reason: '空表' }], reasons: ['缺少有效 XLSX'] });
  assert.match(html, /交付未完成/);
  assert.match(html, /DOCX.*XLSX/);
  assert.match(html, /空表/);
  assert.match(html, /&lt;bad&gt;/);
  assert.doesNotMatch(html, /<bad>/);
  assert.equal(views.statusText('completed'), '执行已结束');
});

test('explicit file formats survive navigation and enter the idempotent request body', async () => {
  const bodies = [];
  const controller = createController({ api: { detail: async (id) => ({ id, messages: [] }), message: async (_id, body) => { bodies.push(body); return { accepted: true }; } } });
  assert.equal(typeof controller.setFormats, 'function');
  await controller.open({ page: 'fingpt', sessionId: 'one' });
  controller.setDraft('研究'); controller.setFormats(['docx', 'xlsx']);
  await controller.open({ page: 'history', sessionId: null });
  await controller.open({ page: 'fingpt', sessionId: 'one' });
  await controller.send();
  assert.deepEqual(bodies[0].expected_formats, ['docx', 'xlsx']);
});

test('format picker distinguishes skill defaults from explicit no-file output', () => {
  assert.equal(typeof views.renderFormatPicker, 'function');
  assert.match(views.renderFormatPicker(null, 'fund-evaluation'), /DOCX.*HTML.*XLSX/);
  assert.match(views.renderFormatPicker([], 'fund-evaluation'), /无需文件/);
});

test('rename and native questions use accessible in-app forms instead of window.prompt', async () => {
  const app = await readFile(new URL('../../app/research_web/ui/app.mjs', import.meta.url), 'utf8');
  assert.doesNotMatch(app, /window\.prompt\s*\(/);
  assert.equal(typeof views.renderRename, 'function');
  assert.match(views.renderRename('旧标题'), /id="rename-form"/);
  assert.match(views.renderRename('旧标题'), /maxlength="120"/);
  const html = views.renderConversation({ messages: [], questions: [{ id: 'rpc', text: '期间？', items: [{ id: 'period', question: '期间？', options: [{ label: '2025', description: '去年' }] }] }] });
  assert.match(html, /data-question-form="rpc"/);
  assert.match(html, /name="custom-0"/);
  assert.match(html, /name="selection-0"/);
  assert.match(html, /type="submit"/);
});
