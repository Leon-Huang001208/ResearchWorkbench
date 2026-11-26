import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createDatasetReference } from '../../app/research_web/ui/dataset-reference.mjs';

/** Minimal DOM stand-in: only the members the reference jump actually touches. */
function fakeCard({ top = 0, scrollTop = 0 } = {}) {
  const classes = new Set();
  const panel = {
    scrollTop,
    scrolledTo: null,
    getBoundingClientRect: () => ({ top: 0 }),
    scrollTo(options) { this.scrolledTo = options; },
  };
  return {
    classList: {
      add: name => classes.add(name),
      remove: name => classes.delete(name),
      has: name => classes.has(name),
    },
    getBoundingClientRect: () => ({ top }),
    closest: selector => (selector === '.context-panel' ? panel : null),
    panel,
  };
}

function harness({ cards = [], compact = false, reducedMotion = false } = {}) {
  const opened = [];
  const timers = [];
  let renders = 0;
  const root = { querySelectorAll: () => cards };

  const original = globalThis.matchMedia;
  globalThis.matchMedia = query => ({
    matches: query.includes('prefers-reduced-motion') ? reducedMotion : compact,
  });

  const api = createDatasetReference({
    openContext: patch => opened.push(patch),
    render: () => { renders += 1; },
    root,
    schedule: (fn, ms) => timers.push([fn, ms]),
  });

  return {
    api, opened, timers, cards,
    get renders() { return renders; },
    flush() { while (timers.length) timers.shift()[0](); },
    restore() { globalThis.matchMedia = original; },
  };
}

test('following a citation opens the datasets tab and renders', () => {
  const h = harness({ cards: [fakeCard()] });
  try {
    assert.equal(h.api.focus('1'), true);
    assert.deepEqual(h.opened, [{ collapsed: false, open: false, tab: 'datasets' }]);
    assert.equal(h.renders, 1);
  } finally { h.restore(); }
});

test('a narrow viewport opens the context panel', () => {
  const h = harness({ cards: [fakeCard()], compact: true });
  try {
    h.api.focus('1');
    assert.equal(h.opened[0].open, true);
  } finally { h.restore(); }
});

test('the cited card is indexed from 1 and flashes', () => {
  const first = fakeCard();
  const second = fakeCard();
  const h = harness({ cards: [first, second] });
  try {
    h.api.focus('2');
    assert.equal(second.classList.has('flash'), true);
    assert.equal(first.classList.has('flash'), false);
    h.flush();
    assert.equal(second.classList.has('flash'), false, 'flash must clear itself');
  } finally { h.restore(); }
});

test('the card scrolls to sit 12px below the panel top', () => {
  const card = fakeCard({ top: 200, scrollTop: 50 });
  const h = harness({ cards: [card] });
  try {
    h.api.focus('1');
    assert.equal(card.panel.scrolledTo.top, 238);   // 200 - 0 + 50 - 12
    assert.equal(card.panel.scrolledTo.behavior, 'smooth');
  } finally { h.restore(); }
});

test('reduced motion scrolls instantly instead of animating', () => {
  const card = fakeCard();
  const h = harness({ cards: [card], reducedMotion: true });
  try {
    h.api.focus('1');
    assert.equal(card.panel.scrolledTo.behavior, 'auto');
  } finally { h.restore(); }
});

test('scroll never goes negative and out-of-range refs are inert', () => {
  const card = fakeCard({ top: 5, scrollTop: 0 });
  const h = harness({ cards: [card] });
  try {
    h.api.focus('1');
    assert.equal(card.panel.scrolledTo.top, 0);
    assert.equal(h.api.focus('9'), false, 'missing card reports no match');
    assert.equal(h.api.focus('0'), false, 'zero and negatives are rejected');
    assert.equal(h.api.focus('not-a-number'), false);
  } finally { h.restore(); }
});
