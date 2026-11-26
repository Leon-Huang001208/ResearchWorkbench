/**
 * Keyboard navigation over a fixed list of choices.
 *
 * Six places in the UI implement the same rule -- Home/End jump to the edges,
 * one arrow steps and wraps -- for tabs, subviews, a search dropdown and two
 * composer menus. They had drifted: two variants handled "no current selection"
 * differently, one had an off-by-one on End. Keeping one implementation means a
 * single place to be right.
 */

/** Keys this helper understands, for callers that gate on them first. */
export const LIST_NAV_KEYS = Object.freeze(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End']);

/**
 * Resolve the next index for a keyboard event.
 *
 * @param {object} input
 * @param {string} input.key            the keyboard event key
 * @param {number} input.count          number of choices
 * @param {number} input.current        current index, or -1 when nothing is selected
 * @param {'horizontal'|'vertical'} [input.axis]  which arrows step the list
 * @param {boolean} [input.wrapFromNone]  when nothing is selected, does an arrow
 *   land on the first item (down/right) or the last (up/left)? Always true for
 *   Home/End regardless.
 * @returns {number|null} next index, or null when the key is not ours
 */
export function nextListIndex({ key, count, current, axis = 'horizontal', wrapFromNone = true }) {
  if (!Number.isInteger(count) || count <= 0) return null;

  if (key === 'Home') return 0;
  if (key === 'End') return count - 1;

  const forwardKey = axis === 'vertical' ? 'ArrowDown' : 'ArrowRight';
  const backwardKey = axis === 'vertical' ? 'ArrowUp' : 'ArrowLeft';
  if (key !== forwardKey && key !== backwardKey) return null;

  const forward = key === forwardKey;
  if (current < 0) {
    if (!wrapFromNone) return 0;
    return forward ? 0 : count - 1;
  }
  return (current + (forward ? 1 : -1) + count) % count;
}

/**
 * Convenience wrapper: returns null when the key is not a navigation key at all,
 * so callers can early-return instead of repeating the key list.
 */
export function listNavTarget({ key, count, current, axis = 'horizontal', wrapFromNone = true }) {
  if (!LIST_NAV_KEYS.includes(key)) return null;
  return nextListIndex({ key, count, current, axis, wrapFromNone });
}
