// UI-only state: never persists tool payloads, approvals, or research contents.
export function createDisclosureState({ limit = 500, logger = () => {} } = {}) {
  const states = new Map();
  let focused = null;
  return {
    capture(root, active) {
      try {
        focused = active?.tagName === 'SUMMARY' ? active.parentElement?.dataset?.disclosureKey : null;
        for (const item of root.querySelectorAll('details[data-disclosure-key]')) {
          const key = item.dataset.disclosureKey;
          states.delete(key); states.set(key, item.open);
        }
        while (states.size > limit) states.delete(states.keys().next().value);
      } catch { logger('disclosure_capture_failed'); }
    },
    restore(root) {
      try {
        for (const item of root.querySelectorAll('details[data-disclosure-key]')) {
          const key = item.dataset.disclosureKey;
          if (states.has(key)) item.open = states.get(key);
          if (focused === key) item.querySelector('summary')?.focus({ preventScroll: true });
        }
      } catch { logger('disclosure_restore_failed'); }
    },
  };
}
