import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const UI = new URL('../../app/research_web/ui/', import.meta.url).pathname;

test('token scale is defined and reachable from the shell', () => {
  const tokens = readFileSync(join(UI, 'tokens.css'), 'utf8');
  for (const group of ['--space-2:', '--radius-md:', '--text-sm:', '--duration-base:']) {
    assert.ok(tokens.includes(group), `tokens.css is missing ${group}`);
  }
  const html = readFileSync(join(UI, 'index.html'), 'utf8');
  const tokenAt = html.indexOf('/static/tokens.css');
  const stylesAt = html.indexOf('/static/styles.css');
  assert.ok(tokenAt > 0, 'index.html must link tokens.css');
  // Tokens define the scale, so they must be evaluated before component sheets.
  assert.ok(tokenAt < stylesAt, 'tokens.css must load before styles.css');
});

test('bare px stays inside the recorded budget', async () => {
  const debt = JSON.parse(readFileSync(join(UI, '.token-debt.json'), 'utf8'));
  const allowed = new Set(['0px', '1px', '2px', '3px']);
  for (const name of readdirSync(UI).filter(n => n.endsWith('.css') && n !== 'tokens.css')) {
    const css = readFileSync(join(UI, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    let count = 0;
    for (const m of css.matchAll(/(?<![-\w.#])(\d*\.?\d+)px\b/g)) {
      if (!allowed.has(m[0])) count++;
    }
    const budget = debt.barePx[name];
    assert.notEqual(budget, undefined, `${name} is new; use var(--space-*) instead of bare px`);
    assert.ok(count <= budget, `${name}: ${count} bare px exceeds budget ${budget}`);
  }
});

test('semantic colour roles are defined for status and direction', () => {
  const tokens = readFileSync(join(UI, 'tokens.css'), 'utf8');
  for (const role of [
    '--color-success:',
    '--color-warning:',
    '--color-danger:',
    '--color-info:',
    '--color-up:',
    '--color-down:',
    '--color-well:',
    '--shadow-md:',
  ]) {
    assert.ok(tokens.includes(role), `tokens.css is missing ${role}`);
  }
  // Direction must be independent of status: a red "up" market stays expressible.
  assert.notEqual(tokens.includes('--color-up: var(--color-danger)'), true);
});

test('bare colour stays inside the recorded budget', async () => {
  const debt = JSON.parse(readFileSync(join(UI, '.token-debt.json'), 'utf8'));
  for (const name of readdirSync(UI).filter(n => n.endsWith('.css') && n !== 'tokens.css')) {
    const css = readFileSync(join(UI, name), 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
    let count = 0;
    for (const block of css.matchAll(/\{([^{}]*)\}/g)) {
      for (const decl of block[1].split(';')) {
        if (/^\s*--[a-z0-9-]+\s*:/.test(decl)) continue;
        if (/var\(/.test(decl)) continue;
        const hits = decl.match(/#[0-9a-fA-F]{3,8}\b/g);
        if (hits) count += hits.length;
      }
    }
    const budget = debt.bareColor[name];
    assert.notEqual(budget, undefined, `${name} is new; use a var(--color-*) role`);
    assert.ok(count <= budget, `${name}: ${count} bare colours exceeds budget ${budget}`);
  }
});
