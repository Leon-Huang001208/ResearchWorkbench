import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const code = await readFile(new URL('../../app/web/static/js/fingpt.js', import.meta.url), 'utf8');
const template = await readFile(new URL('../../app/web/templates/index.html', import.meta.url), 'utf8');

function page(...responses) {
  const node = () => ({ hidden: false, classList: { toggle() {} }, addEventListener() {} });
  const link = { ...node(), hidden: true, href: '', removeAttribute() { this.href = ''; } };
  const frame = { ...node(), hidden: true, src: '', removeAttribute() { this.src = ''; } };
  const children = [{ ...node(), contains: () => false }, { ...node(), contains: () => true }];
  const shell = { children };
  const copy = node();
  const diagnostic = node();
  const calls = [];
  const api = async (_method, path) => {
    calls.push(path);
    if (!path.endsWith('/health')) return { tasks: [], sessions: [] };
    return responses.shift();
  };
  const document = {
    getElementById(id) {
      return ({ 'fingpt-runtime-state': node(), 'fingpt-dsh-frame': frame,
        'fingpt-host-unavailable': diagnostic, 'fingpt-diagnostic-copy': copy,
        'btn-fingpt-retry': node() })[id];
    },
    querySelector(selector) {
      return ({ '[data-open-research-qa]': link, '.fingpt-page': shell })[selector];
    },
    querySelectorAll: () => [],
  };
  const source = code.replace(/^import[^\n]*\n/, '').replace('export async function', 'async function');
  const init = new Function('apiCall', 'document', 'window', 'esc', `${source}; return initFinGPT;`)(
    api, document, { addEventListener() {} }, String,
  );
  return { init, link, calls, children, copy };
}

test('legacy FinGPT exposes only the configured private replacement and observes rollback', async () => {
  const url = 'https://research.tail123.ts.net/#/qa';
  assert.doesNotMatch(template, /href="http:\/\/127\.0\.0\.1:8088\/#\/qa"/);
  const app = page({ retired: true, research_web_url: url }, { available: false });
  await app.init();
  assert.equal(app.link.href, url);
  assert.equal(app.link.hidden, false);
  assert.deepEqual(app.calls, ['/api/v2/fingpt/health']);
  await app.init();
  assert.equal(app.link.hidden, true);
  assert.equal(app.link.href, '');
  assert.ok(app.children.every(child => !child.hidden));
  assert.deepEqual(app.calls.slice(1).sort(), ['/api/v2/fingpt/health', '/api/v2/fingpt/sessions', '/api/v2/fingpt/tasks']);
});

test('legacy FinGPT suppresses the DSH panel on an invalid replacement URL', async () => {
  const app = page({ retired: true, research_web_url: 'https://untrusted.example/#/qa' });
  await app.init();
  assert.equal(app.link.hidden, true);
  assert.equal(app.link.href, '');
  assert.match(app.copy.textContent, /FinGPT/);
  assert.deepEqual(app.calls, ['/api/v2/fingpt/health']);
});
