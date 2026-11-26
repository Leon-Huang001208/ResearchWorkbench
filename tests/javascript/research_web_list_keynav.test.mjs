import { test } from 'node:test';
import assert from 'node:assert/strict';
import { LIST_NAV_KEYS, listNavTarget, nextListIndex } from '../../app/research_web/ui/list-keynav.mjs';
import { capabilityTabKey } from '../../app/research_web/ui/capabilities.mjs';
import { mcpMarketplaceTabKey } from '../../app/research_web/ui/mcp-marketplace.mjs';

test('Home and End jump to the edges', () => {
  assert.equal(nextListIndex({ key: 'Home', count: 5, current: 3 }), 0);
  assert.equal(nextListIndex({ key: 'End', count: 5, current: 1 }), 4);
});

test('arrows step and wrap in both directions', () => {
  assert.equal(nextListIndex({ key: 'ArrowRight', count: 4, current: 0 }), 1);
  assert.equal(nextListIndex({ key: 'ArrowRight', count: 4, current: 3 }), 0, 'wraps past the end');
  assert.equal(nextListIndex({ key: 'ArrowLeft', count: 4, current: 0 }), 3, 'wraps before the start');
  assert.equal(nextListIndex({ key: 'ArrowLeft', count: 4, current: 2 }), 1);
});

test('vertical lists use up/down and ignore left/right', () => {
  assert.equal(nextListIndex({ key: 'ArrowDown', count: 3, current: 0, axis: 'vertical' }), 1);
  assert.equal(nextListIndex({ key: 'ArrowUp', count: 3, current: 0, axis: 'vertical' }), 2);
  assert.equal(nextListIndex({ key: 'ArrowRight', count: 3, current: 0, axis: 'vertical' }), null);
});

test('an unselected list enters from the matching edge', () => {
  assert.equal(nextListIndex({ key: 'ArrowRight', count: 4, current: -1 }), 0);
  assert.equal(nextListIndex({ key: 'ArrowLeft', count: 4, current: -1 }), 3);
  assert.equal(nextListIndex({ key: 'ArrowDown', count: 4, current: -1, axis: 'vertical' }), 0);
  assert.equal(nextListIndex({ key: 'ArrowUp', count: 4, current: -1, axis: 'vertical' }), 3);
});

test('an unselected list can opt out of edge entry', () => {
  assert.equal(nextListIndex({ key: 'ArrowLeft', count: 4, current: -1, wrapFromNone: false }), 0);
});

test('unrelated keys and empty lists return null', () => {
  assert.equal(nextListIndex({ key: 'Enter', count: 3, current: 0 }), null);
  assert.equal(nextListIndex({ key: 'Tab', count: 3, current: 0 }), null);
  assert.equal(nextListIndex({ key: 'Home', count: 0, current: 0 }), null);
});

test('listNavTarget rejects non-navigation keys before computing', () => {
  assert.equal(listNavTarget({ key: 'a', count: 3, current: 0 }), null);
  // LIST_NAV_KEYS is the union of both axes; each axis only honours its own pair.
  assert.ok(LIST_NAV_KEYS.includes('ArrowUp') && LIST_NAV_KEYS.includes('ArrowRight'));
  for (const key of ['ArrowLeft', 'ArrowRight', 'Home', 'End']) {
    assert.notEqual(listNavTarget({ key, count: 3, current: 0 }), null, `${key} should navigate a horizontal list`);
  }
  for (const key of ['ArrowUp', 'ArrowDown']) {
    assert.equal(listNavTarget({ key, count: 3, current: 0 }), null, `${key} must not move a horizontal list`);
    assert.notEqual(listNavTarget({ key, count: 3, current: 0, axis: 'vertical' }), null, `${key} should move a vertical list`);
  }
});

test('capabilityTabKey preserves the original edge behaviour for unknown kinds', () => {
  // Math.max(0, -1) pins the index at 0, so ArrowLeft wraps to the LAST tab.
  // Verified against the pre-refactor implementation before changing it.
  assert.deepEqual(capabilityTabKey('ArrowLeft', 'nonexistent-kind'), { handled: true, kind: 'plugin' });
  assert.deepEqual(capabilityTabKey('ArrowRight', 'nonexistent-kind'), { handled: true, kind: 'connector' });
  assert.deepEqual(capabilityTabKey('Home', 'nonexistent-kind'), { handled: true, kind: 'skill' });
  assert.deepEqual(capabilityTabKey('Tab', 'skill'), { handled: false });
});

test('mcpMarketplaceTabKey cycles the three subviews', () => {
  assert.deepEqual(mcpMarketplaceTabKey('ArrowRight', 'library'), { handled: true, view: 'market' });
  assert.deepEqual(mcpMarketplaceTabKey('End', 'library'), { handled: true, view: 'connections' });
  assert.deepEqual(mcpMarketplaceTabKey('ArrowLeft', 'library'), { handled: true, view: 'connections' });
  assert.deepEqual(mcpMarketplaceTabKey('x', 'library'), { handled: false });
});
