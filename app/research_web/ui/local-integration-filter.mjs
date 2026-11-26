/**
 * Local-integration category filter and consent-cancel focus restore.
 *
 * Both handlers are pure UI bookkeeping: one swaps the active category and puts
 * focus back on the pressed chip, the other dismisses a pending consent prompt
 * and restores focus to the row that raised it. They sit in the click dispatcher
 * only because that is where all clicks land.
 */

const CATEGORY_PREFIX = 'local-category-';

/**
 * Escape a value for use inside an attribute selector.
 *
 * The DOM provides CSS.escape; the fallback keeps this module usable where it is
 * absent (tests, older engines) without silently producing a broken selector.
 */
const escapeSelectorValue = value =>
  globalThis.CSS?.escape ? globalThis.CSS.escape(value) : String(value).replace(/["\\]/g, '\\$&');

/**
 * @param {object} deps
 * @param {(value: string) => void} deps.setCategory
 * @param {() => string} deps.getConsentTarget
 * @param {(value: string) => void} deps.setConsentTarget
 * @param {() => void} deps.render
 * @param {Document|Element} [deps.root]
 */
export function createLocalIntegrationFilter({
  setCategory,
  getConsentTarget,
  setConsentTarget,
  render,
  root = document,
}) {
  return {
    /** @param {string} raw the pressed chip's data value, or 'all' */
    selectCategory(raw) {
      const value = raw === 'all' ? 'all' : String(raw).replace(CATEGORY_PREFIX, '');
      setCategory(value);
      render();
      // Return focus to the pressed chip; CSS.escape keeps odd ids addressable.
      root.querySelector(`[data-local-category-target="${escapeSelectorValue(raw)}"]`)?.focus();
      return value;
    },

    /** Dismiss the pending Office auto-consent prompt and restore focus. */
    cancelConsent() {
      const target = getConsentTarget();
      setConsentTarget('');
      render();
      root.querySelector(`[data-office-auto-consent="${escapeSelectorValue(target)}"]`)?.focus();
      return target;
    },
  };
}
