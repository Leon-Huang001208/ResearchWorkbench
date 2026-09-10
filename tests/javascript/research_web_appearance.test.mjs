import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import { inflateSync } from 'node:zlib';

const ui = new URL('../../app/research_web/ui/', import.meta.url);
async function factory() {
  const context = { module: { exports: {} } };
  vm.runInNewContext(await readFile(new URL('theme.js', ui), 'utf8'), context);
  return context.module.exports;
}

function decodeRgbaPng(png) {
  assert.deepEqual(png.subarray(0, 8), Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]));
  const chunks = [];
  let cursor = 8;
  while (cursor < png.length) {
    const length = png.readUInt32BE(cursor);
    const type = png.subarray(cursor + 4, cursor + 8).toString('ascii');
    const data = png.subarray(cursor + 8, cursor + 8 + length);
    chunks.push({ type, data });
    cursor += length + 12;
  }
  const header = chunks.find(chunk => chunk.type === 'IHDR')?.data;
  assert.ok(header, 'PNG must contain IHDR');
  const width = header.readUInt32BE(0), height = header.readUInt32BE(4);
  assert.equal(header[8], 8, 'brand mark must use 8-bit channels');
  assert.equal(header[9], 6, 'brand mark must be RGBA');
  const rows = inflateSync(Buffer.concat(chunks.filter(chunk => chunk.type === 'IDAT').map(chunk => chunk.data)));
  const stride = width * 4;
  const rgba = Buffer.alloc(stride * height);
  let source = 0;
  for (let y = 0; y < height; y += 1) {
    const filter = rows[source++];
    for (let x = 0; x < stride; x += 1) {
      const raw = rows[source++];
      const left = x >= 4 ? rgba[y * stride + x - 4] : 0;
      const above = y ? rgba[(y - 1) * stride + x] : 0;
      const upperLeft = y && x >= 4 ? rgba[(y - 1) * stride + x - 4] : 0;
      if (filter === 0) rgba[y * stride + x] = raw;
      else if (filter === 1) rgba[y * stride + x] = (raw + left) & 255;
      else if (filter === 2) rgba[y * stride + x] = (raw + above) & 255;
      else if (filter === 3) rgba[y * stride + x] = (raw + Math.floor((left + above) / 2)) & 255;
      else if (filter === 4) {
        const p = left + above - upperLeft;
        const pa = Math.abs(p - left), pb = Math.abs(p - above), pc = Math.abs(p - upperLeft);
        rgba[y * stride + x] = (raw + (pa <= pb && pa <= pc ? left : pb <= pc ? above : upperLeft)) & 255;
      } else assert.fail(`unsupported PNG filter ${filter}`);
    }
  }
  return { width, height, rgba };
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
  assert.match(renderBrandMark(), /assets\/brand\/brand-mark.png/);
  assert.match(renderBrandMark(), /width="108" height="120"/);
  assert.doesNotMatch(renderBrandMark(), /HUAAN|华安|<svg/);
  assert.doesNotMatch(renderPrimaryRail({ page: 'settings' }), /data-theme-(?:select|option)/);
  const picker = renderAppearancePicker();
  assert.equal((picker.match(/data-theme-option/g) || []).length, 3);
  assert.equal((picker.match(/type="radio"/g) || []).length, 3);
  for (const value of ['system', 'light', 'dark']) assert.match(picker, new RegExp(`value="${value}"`));
  for (const label of ['跟随系统', '浅色', '深色']) assert.match(picker, new RegExp(label));
  const css = await readFile(new URL('appearance.css', ui), 'utf8');
  assert.match(css, /brightness\(0\) invert\(1\)/);
  assert.doesNotMatch(css, /mix-blend-mode/);
});

test('brand mark is a transparent 108×120 RGBA crop while source bytes stay immutable', async () => {
  const source = await readFile(new URL('assets/brand/source-logo.png', ui));
  assert.equal(createHash('sha256').update(source).digest('hex'), 'bcb4aaff2e6c11912389148f11886412c624f585252806887dc057d94c6e78b6');
  const { width, height, rgba } = decodeRgbaPng(await readFile(new URL('assets/brand/brand-mark.png', ui)));
  assert.equal(width, 108); assert.equal(height, 120);
  for (const [x, y] of [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]]) assert.equal(rgba[(y * width + x) * 4 + 3], 0, `corner ${x},${y} must be transparent`);
  const opaqueBluePixels = [...rgba.keys()].filter(index => index % 4 === 0).filter(index => rgba[index + 3] === 255 && rgba[index] < 90 && rgba[index + 1] > 80 && rgba[index + 2] > 100);
  assert.ok(opaqueBluePixels.length > 0, 'brand mark must retain opaque blue logo pixels');
});

test('favicon files are transparent 16px and 32px PNGs and the old tab icon is not referenced', async () => {
  const html = await readFile(new URL('index.html', ui), 'utf8');
  assert.match(html, /assets\/brand\/favicon-16\.png/);
  assert.match(html, /assets\/brand\/favicon-32\.png/);
  assert.doesNotMatch(html, /rel="icon"[^>]*research-workbench-logo\.png/);
  for (const size of [16, 32]) {
    const png = await readFile(new URL(`assets/brand/favicon-${size}.png`, ui));
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

test('closed research panel counts failed activities and abnormal subagents separately', async () => {
  const { renderResearchAttention } = await import(new URL('shell.mjs', ui));
  assert.equal(renderResearchAttention({}), '');
  assert.match(renderResearchAttention({ activities: Array.from({ length: 7 }, () => ({ status: 'failed' })) }), />7 项活动失败。</);
  assert.match(renderResearchAttention({ subagents: [{ error: 'failed' }] }), />1 个子 Agent 异常。</);
  const html = renderResearchAttention({
    activities: [{ status: 'failed' }, { status: 'completed', error: '真实失败' }],
    subagents: [{ status: 'error' }],
    agents: Array.from({ length: 8 }, () => ({ status: 'failed' })),
    delivery: { status: 'incomplete' },
  });
  assert.match(html, /2 项活动失败，1 个子 Agent 异常。/);
  assert.doesNotMatch(html, /8 个|10 项|活动或 Agent/);
  assert.match(html, /文件交付尚未完成/);
  assert.match(html, /data-show-attention/);
});

test('conversation layout right-aligns fluid user bubbles and keeps assistant replies as body text', async () => {
  const css = await readFile(new URL('styles.css', ui), 'utf8');
  assert.match(css, /\.message\.user\s*\{[^}]*justify-content:\s*flex-end/);
  assert.match(css, /\.message\.user \.markdown\s*\{[^}]*width:\s*fit-content[^}]*max-width:\s*78%/);
  assert.match(css, /\.message\.assistant \.markdown\s*\{[^}]*padding-left:\s*0/);
  assert.match(css, /@media \(max-width:\s*760px\)[\s\S]*?\.message\.user \.markdown\s*\{[^}]*max-width:\s*92%/);
});

test('capability workspace has four-to-one responsive density and a full-screen mobile dialog', async () => {
  const css = await readFile(new URL('appearance.css', ui), 'utf8');
  assert.match(css, /@media \(min-width: 1400px\)[\s\S]*?\.capability-workspace-grid \{ grid-template-columns: repeat\(4/);
  assert.match(css, /@media \(min-width: 1400px\)[\s\S]*?\.capability-workspace \.data-grid \{ grid-template-columns: repeat\(4/);
  assert.match(css, /@media \(max-width: 1100px\)[\s\S]*?\.capability-workspace-grid \{ grid-template-columns: repeat\(2/);
  assert.match(css, /@media \(max-width: 600px\)[\s\S]*?\.capability-workspace-grid \{ grid-template-columns: 1fr/);
  assert.match(css, /\.capability-workspace-subnav a\[aria-current='page'\]/);
  assert.match(css, /\.capability-preview-dialog \{[^}]*width: min\(760px/);
  assert.match(css, /@media \(max-width: 760px\)[\s\S]*?\.capability-preview-dialog \{[^}]*width: 100vw[^}]*min-height: 100dvh/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)/);
});

test('approved v2 composition keeps title, sidebar actions and model inside composer', async () => {
  const shell = await import(new URL('shell.mjs', ui));
  const { renderComposer } = await import(new URL('composer.mjs', ui));
  const header = shell.renderTopbar({ page: 'fingpt' });
  assert.match(header, /topbar-title/);
  assert.doesNotMatch(header, /id="model-select"/);
  assert.doesNotMatch(shell.renderPrimaryRail({ page: 'fingpt' }), /data-new/);
  assert.match(shell.renderSidebar({ page: 'fingpt' }), /data-new/);
  const composer = renderComposer({ draft: '', expectedFormats: null });
  assert.match(composer, /id="model-select"/);
  assert.match(composer, /composer-send/);
  assert.ok(composer.indexOf('composer-tools') < composer.indexOf('format-picker'));
});
