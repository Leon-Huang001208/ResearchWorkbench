import test from 'node:test';
import assert from 'node:assert/strict';
import { createDisclosureState } from '../../app/research_web/ui/disclosures.mjs';

function item(key, open = false) {
  const summary = { tagName: 'SUMMARY', focus(options) { this.focused = options; } };
  const details = { dataset: { disclosureKey: key }, open, querySelector() { return summary; }, summary };
  summary.parentElement = details;
  return details;
}
const root = items => ({ querySelectorAll() { return items; } });
test('SSE replacement preserves explicit open/closed choices and summary keyboard focus', () => {
  const state = createDisclosureState();
  const old = [item('s:process:assistant:2', false), item('s:tool:t', true), item('claw:project:p', true)];
  state.capture(root(old), old[1].summary);
  const fresh = [item('s:process:assistant:2', true), item('s:tool:t'), item('claw:project:p'), item('s:tool:new')];
  state.restore(root(fresh));
  assert.deepEqual(fresh.map(row => row.open), [false, true, true, false]);
  assert.deepEqual(fresh[1].summary.focused, { preventScroll: true });
});
test('different sessions never inherit tool disclosure state, and retention is bounded', () => {
  const state = createDisclosureState({ limit: 2 });
  state.capture(root([item('one:tool:t', true), item('one:tool:x', true), item('one:tool:y', true)]));
  const fresh = [item('two:tool:t'), item('one:tool:t'), item('one:tool:y')];
  state.restore(root(fresh));
  assert.deepEqual(fresh.map(row => row.open), [false, false, true]);
});
test('disclosure failures are logged and never prevent a research render', () => {
  const events = [], state = createDisclosureState({ logger: name => events.push(name) });
  const broken = { querySelectorAll() { throw new Error('detached'); } };
  state.capture(broken); state.restore(broken);
  assert.deepEqual(events, ['disclosure_capture_failed', 'disclosure_restore_failed']);
});
