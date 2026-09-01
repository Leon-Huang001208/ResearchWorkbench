import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../../outputs/merged-platform-product-prototype/', import.meta.url);
const text = (file) => readFile(new URL(file, root), 'utf8');
const requiredFiles = [
  'index.html', 'brand-spec.md', 'assets/alphafoundry-logo.png',
  'styles/tokens.css', 'styles/base.css', 'styles/shell.css',
  'styles/components.css', 'styles/pages.css', 'styles/responsive.css',
  'scripts/store.js', 'scripts/router.js', 'scripts/data-adapter.js',
  'scripts/shell.js', 'scripts/tweaks.js',
  'scripts/pages/market-home.js', 'scripts/pages/theme-research.js',
  'scripts/pages/asset-observation.js', 'scripts/pages/fingpt.js',
  'scripts/pages/claw.js', 'scripts/pages/watchlists.js',
  'scripts/pages/research-library.js', 'scripts/pages/capability-center.js',
  'scripts/journeys.js', 'scripts/app.js',
];

test('prototype contains every focused artifact file', async () => {
  await Promise.all(requiredFiles.map((file) => access(new URL(file, root))));
});

test('prototype loads assets in deterministic order', async () => {
  const html = await text('index.html');
  let cursor = -1;
  for (const file of requiredFiles.filter((item) => item.endsWith('.css') || item.endsWith('.js'))) {
    const next = html.indexOf(file);
    assert.ok(next > cursor, `${file} is missing or loaded out of order`);
    cursor = next;
  }
  assert.doesNotMatch(html, /TODO|TBD|FIXME|待定/);
});

test('shell defines responsive, focus and reduced-motion contracts', async () => {
  const responsive = await text('styles/responsive.css');
  const base = await text('styles/base.css');
  for (const query of ['1440px', '1024px', '768px', '767px']) assert.match(responsive, new RegExp(query));
  assert.match(responsive, /prefers-reduced-motion/);
  assert.match(base, /:focus-visible/);
});

test('all eight routes, demo states and trace links are authored', async () => {
  const sources = await Promise.all(requiredFiles.filter((item) => item.endsWith('.js')).map(text));
  const combined = sources.join('\n');
  for (const route of ['/market-home', '/themes', '/assets/:assetId', '/fingpt', '/claw', '/watchlists', '/research-library', '/capabilities']) {
    assert.ok(combined.includes(route), `missing route ${route}`);
  }
  for (const state of ['default', 'loading', 'empty', 'partial', 'stale', 'unavailable', 'quarantined', 'error', 'permission_denied', 'blocked_runtime']) {
    assert.ok(combined.includes(state), `missing demo state ${state}`);
  }
  assert.match(combined, /API-MKT-001/);
  assert.match(combined, /API-RES-016/);
  assert.match(combined, /CAP-AGT-001/);
});

test('five journeys are complete and runtime recovery is explicit', async () => {
  const journeys = await text('scripts/journeys.js');
  for (const id of ['J01', 'J02', 'J03', 'J04', 'J05']) assert.match(journeys, new RegExp(id));
  assert.match(journeys, /blocked_runtime/);
  assert.match(journeys, /state=running/);
  assert.doesNotMatch(journeys, /scrollIntoView/);
});
