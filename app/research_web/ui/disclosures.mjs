// UI-only state: never persists tool payloads, approvals, or research contents.
export function createDisclosureState({ limit = 500, logger = () => {} } = {}) {
  const states = new Map();
  const scrollPositions = new Map();
  let focused = null;
  return {
    capture(root, active) {
      scrollPositions.clear();
      try {
        focused = active?.tagName === 'SUMMARY' ? active.parentElement?.dataset?.disclosureKey : null;
        for (const item of root.querySelectorAll('details[data-disclosure-key]')) {
          const key = item.dataset.disclosureKey;
          states.delete(key); states.set(key, item.open);
        }
        while (states.size > limit) states.delete(states.keys().next().value);
        for (const item of root.querySelectorAll('[data-render-scroll-key]')) {
          const key = item.dataset.renderScrollKey;
          if (key) scrollPositions.set(key, item.scrollLeft);
        }
      } catch { logger('disclosure_capture_failed'); }
    },
    restore(root) {
      try {
        for (const item of root.querySelectorAll('details[data-disclosure-key]')) {
          const key = item.dataset.disclosureKey;
          if (states.has(key)) item.open = states.get(key);
          if (focused === key) item.querySelector('summary')?.focus({ preventScroll: true });
        }
        if (scrollPositions.size) {
          for (const item of root.querySelectorAll('[data-render-scroll-key]')) {
            const left = scrollPositions.get(item.dataset.renderScrollKey);
            if (left !== undefined) item.scrollLeft = left;
          }
        }
      } catch { logger('disclosure_restore_failed'); }
      finally { scrollPositions.clear(); }
    },
  };
}
