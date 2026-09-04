import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const ui = new URL('../../app/research_web/ui/', import.meta.url);
async function factory() {
  const context = { module: { exports: {} } };
  vm.runInNewContext(await readFile(new URL('theme.js', ui), 'utf8'), context);
  return context.module.exports;
}

test('appearance defaults to OS and manual preferences persist independently of research state', async () => {
  const { createThemeController, STORAGE_KEY } = await factory();
  const values = new Map();
  const root = { dataset: {}, style: {} };
  const storage = { getItem: k => values.get(k), setItem: (k, v) => values.set(k, v) };
  const theme = createThemeController({ root, storage, systemDark: true });
  assert.equal(theme.resolved, 'dark');
  theme.setPreference('light'); theme.setSystemDark(true);
  assert.equal(theme.resolved, 'light');
  assert.equal(values.get(STORAGE_KEY), 'light');
  assert.equal(createThemeController({ root, storage, systemDark: true }).resolved, 'light');
  theme.setPreference('system'); theme.setSystemDark(false);
  assert.equal(theme.resolved, 'light');
  assert.equal(root.style.colorScheme, 'light');
});

test('invalid storage and storage failures never prevent appearance initialization', async () => {
  const { createThemeController } = await factory();
  const logs = [];
  const root = { dataset: {}, style: {} };
  const theme = createThemeController({ root, systemDark: true, storage: {
    getItem() { throw Error('private payload'); }, setItem() { throw Error('private payload'); },
  }, log: event => logs.push(event) });
  theme.setPreference('light');
  assert.equal(theme.resolved, 'light');
  theme.setPreference('invalid', { persist: false });
  assert.equal(theme.preference, 'system');
  assert.equal(theme.resolved, 'dark');
  assert.ok(logs.includes('theme_storage_read_failed'));
  assert.ok(logs.includes('theme_storage_write_failed'));
  assert.doesNotMatch(JSON.stringify(logs), /private payload/);
});

test('theme initializes before CSS; navigation has no appearance control and settings owns three radio cards', async () => {
  const html = await readFile(new URL('index.html', ui), 'utf8');
  assert.ok(html.indexOf('/static/theme.js') < html.indexOf('/static/styles.css'));
  const { renderAppearancePicker, renderBrandMark, renderPrimaryRail } = await import(new URL('shell.mjs', ui));
  assert.match(renderBrandMark(), /huaan-brand\/source-logo.png/);
  assert.doesNotMatch(renderBrandMark(), /HUAAN|华安|<svg/);
  assert.doesNotMatch(renderPrimaryRail({ page: 'settings' }), /data-theme-(?:select|option)/);
  const picker = renderAppearancePicker();
  assert.equal((picker.match(/data-theme-option/g) || []).length, 3);
  assert.equal((picker.match(/type="radio"/g) || []).length, 3);
  for (const value of ['system', 'light', 'dark']) assert.match(picker, new RegExp(`value="${value}"`));
  for (const label of ['跟随系统', '浅色', '深色']) assert.match(picker, new RegExp(label));
  const css = await readFile(new URL('appearance.css', ui), 'utf8');
  assert.match(css, /grayscale\(1\) invert\(1\) brightness\(2\)/);
  assert.match(css, /mix-blend-mode: screen/);
});

test('favicon files are transparent 16px and 32px PNGs and the old tab icon is not referenced', async () => {
  const html = await readFile(new URL('index.html', ui), 'utf8');
  assert.match(html, /huaan-brand\/favicon-16\.png/);
  assert.match(html, /huaan-brand\/favicon-32\.png/);
  assert.doesNotMatch(html, /rel="icon"[^>]*alphafoundry-logo\.png/);
  for (const size of [16, 32]) {
    const png = await readFile(new URL(`assets/huaan-brand/favicon-${size}.png`, ui));
    assert.equal(png.subarray(1, 4).toString(), 'PNG');
    assert.equal(png.readUInt32BE(16), size);
    assert.equal(png.readUInt32BE(20), size);
    assert.equal(png[25], 6);
  }
});

test('settings icon uses a bounded symmetric stroke gear and a fixed rail size', async () => {
  const { icon } = await import(new URL('icons.mjs', ui));
  const gear = icon('settings');
  assert.match(gear, /viewBox="0 0 24 24"/);
  assert.match(gear, /<circle cx="12" cy="12" r="3"\/>/);
  assert.match(gear, /M12\.22 2h-\.44/);
  assert.doesNotMatch(gear, /font|glyph/);
  const css = await readFile(new URL('appearance.css', ui), 'utf8');
  assert.match(css, /\.rail-icon \.ui-icon \{ width: 18px; height: 18px; flex: 0 0 18px; \}/);
});

test('closed research panel still exposes actual failures and incomplete delivery', async () => {
  const { renderResearchAttention } = await import(new URL('shell.mjs', ui));
  assert.equal(renderResearchAttention({}), '');
  const html = renderResearchAttention({ activities: [{ status: 'failed' }], agents: [{ error: 'failed' }], delivery: { status: 'incomplete' } });
  assert.match(html, /2 项活动或 Agent 异常/);
  assert.match(html, /文件交付尚未完成/);
  assert.match(html, /data-show-attention/);
});

test('approved v2 composition keeps title, sidebar actions and model inside composer', async () => {
  const shell = await import(new URL('shell.mjs', ui));
  const { renderComposer } = await import(new URL('composer.mjs', ui));
  const header = shell.renderTopbar({ page: 'fingpt' });
  assert.match(header, /topbar-title/);
  assert.doesNotMatch(header, /id="model-select"/);
  assert.match(shell.renderPrimaryRail({ page: 'fingpt' }), /data-new/);
  const composer = renderComposer({ draft: '', expectedFormats: null });
  assert.match(composer, /id="model-select"/);
  assert.match(composer, /composer-send/);
  assert.ok(composer.indexOf('composer-tools') < composer.indexOf('format-picker'));
});
