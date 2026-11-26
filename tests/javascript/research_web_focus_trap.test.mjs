import { test } from 'node:test';
import assert from 'node:assert/strict';
import { FOCUSABLE_SELECTOR, nextTrapIndex, trapTabFocus } from '../../app/research_web/ui/focus-trap.mjs';

test('the trap selector excludes disabled controls but keeps links', () => {
  assert.match(FOCUSABLE_SELECTOR, /button:not\(:disabled\)/);
  assert.match(FOCUSABLE_SELECTOR, /input:not\(:disabled\)/);
  assert.match(FOCUSABLE_SELECTOR, /a\[href\]/);
});

test('mid-list Tab is left to the browser', () => {
  assert.equal(nextTrapIndex({ count: 3, currentIndex: 1, shiftKey: false }), null);
  assert.equal(nextTrapIndex({ count: 3, currentIndex: 1, shiftKey: true }), null);
});

test('forward Tab on the last element wraps to the first', () => {
  assert.deepEqual(nextTrapIndex({ count: 3, currentIndex: 2, shiftKey: false }), { index: 0, wrap: true });
});

test('backward Tab on the first element wraps to the last', () => {
  assert.deepEqual(nextTrapIndex({ count: 3, currentIndex: 0, shiftKey: true }), { index: 2, wrap: true });
});

test('focus outside the dialog is pulled back inside', () => {
  assert.deepEqual(nextTrapIndex({ count: 3, currentIndex: -1, shiftKey: false }), { index: 0, wrap: true });
  assert.deepEqual(nextTrapIndex({ count: 3, currentIndex: -1, shiftKey: true }), { index: 2, wrap: true });
});

test('an empty dialog traps nothing', () => {
  assert.equal(nextTrapIndex({ count: 0, currentIndex: -1, shiftKey: false }), null);
});

function fakeDialog(elements, activeIndex) {
  const focused = [];
  const nodes = elements.map((_, i) => ({ i, focus: () => focused.push(i) }));
  return {
    focused,
    nodes,
    dialog: { querySelectorAll: () => nodes },
    doc: { activeElement: activeIndex >= 0 ? nodes[activeIndex] : { outside: true } },
  };
}

test('trapTabFocus wraps and prevents the default Tab', () => {
  const { dialog, doc, focused } = fakeDialog(['a', 'b', 'c'], 2);
  const event = { key: 'Tab', shiftKey: false, prevented: false, preventDefault() { this.prevented = true; } };
  assert.equal(trapTabFocus(event, dialog, doc), true);
  assert.equal(event.prevented, true);
  assert.deepEqual(focused, [0]);
});

test('trapTabFocus leaves non-Tab keys alone', () => {
  const { dialog, doc } = fakeDialog(['a'], 0);
  const event = { key: 'Enter', shiftKey: false, preventDefault() { throw new Error('must not prevent'); } };
  assert.equal(trapTabFocus(event, dialog, doc), false);
});

test('a missing dialog is a no-op rather than a crash', () => {
  const event = { key: 'Tab', shiftKey: false, preventDefault() { throw new Error('must not prevent'); } };
  assert.equal(trapTabFocus(event, null, { activeElement: null }), false);
});

test('shift-Tab from outside lands on the last element', () => {
  const { dialog, doc, focused } = fakeDialog(['a', 'b'], -1);
  const event = { key: 'Tab', shiftKey: true, preventDefault() {} };
  trapTabFocus(event, dialog, doc);
  assert.deepEqual(focused, [1]);
});
