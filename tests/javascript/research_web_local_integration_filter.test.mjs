import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createLocalIntegrationFilter } from '../../app/research_web/ui/local-integration-filter.mjs';

function harness({ consent = '' , foundSelector = true } = {}) {
  const categories = [];
  const focused = [];
  let renders = 0;
  let consentTarget = consent;

  const root = {
    querySelector: selector => {
      if (!foundSelector) return null;
      return { focus: () => focused.push(selector) };
    },
  };

  const api = createLocalIntegrationFilter({
    setCategory: value => categories.push(value),
    getConsentTarget: () => consentTarget,
    setConsentTarget: value => { consentTarget = value; },
    render: () => { renders += 1; },
    root,
  });

  return {
    api, categories, focused,
    get renders() { return renders; },
    get consent() { return consentTarget; },
  };
}

test('selecting "all" sets the all category', () => {
  const h = harness();
  assert.equal(h.api.selectCategory('all'), 'all');
  assert.deepEqual(h.categories, ['all']);
  assert.equal(h.renders, 1);
});

test('the local-category- prefix is stripped from the stored value', () => {
  const h = harness();
  assert.equal(h.api.selectCategory('local-category-office'), 'office');
  assert.deepEqual(h.categories, ['office']);
});

test('focus returns to the chip using the raw value, not the stripped one', () => {
  const h = harness();
  h.api.selectCategory('local-category-office');
  assert.deepEqual(h.focused, ['[data-local-category-target="local-category-office"]']);
});

test('values without the prefix pass through unchanged', () => {
  const h = harness();
  assert.equal(h.api.selectCategory('browser'), 'browser');
  assert.deepEqual(h.categories, ['browser']);
});

test('cancelling consent clears the target and focuses the originating row', () => {
  const h = harness({ consent: 'local:excel_app' });
  assert.equal(h.api.cancelConsent(), 'local:excel_app');
  assert.equal(h.consent, '');
  assert.equal(h.renders, 1);
  assert.deepEqual(h.focused, ['[data-office-auto-consent="local:excel_app"]']);
});

test('a missing focus target does not throw', () => {
  const h = harness({ consent: 'local:word_app', foundSelector: false });
  assert.equal(h.api.cancelConsent(), 'local:word_app');
  assert.equal(h.renders, 1);
  assert.deepEqual(h.focused, []);
});

test('cancelling with no pending consent is still safe', () => {
  const h = harness();
  assert.equal(h.api.cancelConsent(), '');
  assert.equal(h.consent, '');
});
