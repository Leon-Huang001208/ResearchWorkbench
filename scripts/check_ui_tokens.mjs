#!/usr/bin/env node
/**
 * Guard the design-token scale.
 *
 * The UI grew to 214 distinct px values across 5.2k lines of CSS because every
 * declaration picked its own number. tokens.css defines the scale; this check
 * stops new stylesheets from drifting away from it again.
 *
 * Existing files are grandfathered: only their current bare-value count is
 * allowed, so the budget can only shrink as files are migrated.
 */

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const UI = new URL('../app/research_web/ui/', import.meta.url).pathname;
const BASELINE = new URL('../app/research_web/ui/.token-debt.json', import.meta.url).pathname;

// Structural values that have no design meaning in the scale.
const ALLOWED_PX = new Set(['0px', '1px', '2px', '3px']);

function scan(file) {
  const css = readFileSync(file, 'utf8');
  const withoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '');
  const bare = [];
  for (const match of withoutComments.matchAll(/(?<![-\w.#])(\d*\.?\d+)px\b/g)) {
    if (!ALLOWED_PX.has(match[0])) bare.push(match[0]);
  }
  return bare.length;
}

/** Colour literals outside custom-property definitions and outside var() fallbacks. */
function scanColors(file) {
  const css = readFileSync(file, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');
  let count = 0;
  for (const block of css.matchAll(/\{([^{}]*)\}/g)) {
    for (const decl of block[1].split(';')) {
      if (/^\s*--[a-z0-9-]+\s*:/.test(decl)) continue;   // token definition
      if (/var\(/.test(decl)) continue;                    // consumes a token
      const hits = decl.match(/#[0-9a-fA-F]{3,8}\b/g);
      if (hits) count += hits.length;
    }
  }
  return count;
}

const sheets = readdirSync(UI)
  .filter(name => name.endsWith('.css') && name !== 'tokens.css')
  .sort();

let baseline = {};
try {
  baseline = JSON.parse(readFileSync(BASELINE, 'utf8')).barePx ?? {};
} catch {
  baseline = {};
}

const problems = [];
const counts = {};
const colorCounts = {};
const colorBaseline = JSON.parse(
  readFileSync(BASELINE, 'utf8').replace(/^{/, '{'),
).bareColor ?? {};
for (const name of sheets) {
  const count = scan(join(UI, name));
  counts[name] = count;
  const allowed = baseline[name];
  if (allowed === undefined) {
    if (count > 0) {
      problems.push(`${name}: ${count} bare px values in a new file; use var(--space-*)` );
    }
  } else if (count > allowed) {
    problems.push(`${name}: ${count} bare px values, budget is ${allowed}; use var(--space-*)`);
  }

  const colours = scanColors(join(UI, name));
  colorCounts[name] = colours;
  const colorAllowed = colorBaseline[name];
  if (colorAllowed === undefined) {
    if (colours > 0) problems.push(`${name}: ${colours} bare colours in a new file; use var(--color-*)`);
  } else if (colours > colorAllowed) {
    problems.push(`${name}: ${colours} bare colours, budget is ${colorAllowed}; use var(--color-*)`);
  }
}

const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
const budget = Object.values(baseline).reduce((sum, n) => sum + (n ?? 0), 0);

if (problems.length) {
  console.error(JSON.stringify({ status: 'FAIL', code: 'ui_token_budget_exceeded', problems }, null, 2));
  process.exit(1);
}

console.log(
  JSON.stringify(
    {
      status: 'PASS',
      sheets: sheets.length,
      barePx: total,
      budget,
      headroom: budget - total,
      bareColor: Object.values(colorCounts).reduce((sum, n) => sum + n, 0),
      colorBudget: Object.values(colorBaseline).reduce((sum, n) => sum + (n ?? 0), 0),
    },
    null,
    2,
  ),
);
