/**
 * Jump to a cited dataset card from a rendered answer.
 *
 * An answer cites datasets by ordinal ("ref 3"). Following the citation has to
 * open the context panel, switch to the datasets tab, then scroll the matching
 * card into view and flash it. That is DOM work plus three pieces of shell
 * state, so it lives here instead of inside the click dispatcher.
 */

const FLASH_MS = 2400;
const COMPACT_QUERY = '(max-width: 1050px)';
const REDUCED_MOTION_QUERY = '(prefers-reduced-motion: reduce)';

/**
 * @param {object} deps
 * @param {(patch: {collapsed: boolean, open: boolean, tab: string}) => void} deps.openContext
 * @param {() => void} deps.render
 * @param {Document|Element} [deps.root]
 * @param {(fn: () => void, ms: number) => void} [deps.schedule]
 */
export function createDatasetReference({ openContext, render, root = document, schedule = (fn, ms) => setTimeout(fn, ms) }) {
  return {
    /** @returns {boolean} whether a matching card was found and flashed */
    focus(reference) {
      openContext({
        collapsed: false,
        open: globalThis.matchMedia?.(COMPACT_QUERY).matches ?? false,
        tab: 'datasets',
      });
      render();

      const index = Number.parseInt(reference, 10) - 1;
      const card = index >= 0 ? root.querySelectorAll('.context-panel .dataset-card')[index] : null;
      if (!card) return false;

      card.classList.add('flash');
      const panel = card.closest('.context-panel');
      if (panel) {
        // 12 is the breathing room above the card, matching the panel's own inset.
        const top = card.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop - 12;
        panel.scrollTo({
          top: Math.max(0, top),
          behavior: globalThis.matchMedia?.(REDUCED_MOTION_QUERY).matches ? 'auto' : 'smooth',
        });
      }
      schedule(() => card.classList.remove('flash'), FLASH_MS);
      return true;
    },
  };
}
