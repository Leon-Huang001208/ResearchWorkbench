/**
 * Keep Tab focus inside an open dialog.
 *
 * Both the capability preview and the MCP server dialog carried a byte-identical
 * copy of this trap. Two copies means two places to get the wrap-around wrong,
 * and the subtle case -- focus escaping to the page behind an open modal -- only
 * shows up on the exact first/last element.
 */

/** Elements a user can reach with Tab, in document order. */
export const FOCUSABLE_SELECTOR = [
  'button:not(:disabled)',
  'a[href]',
  'input:not(:disabled)',
  'select:not(:disabled)',
  'textarea:not(:disabled)',
].join(', ');

/**
 * Compute where Tab should land, or null when the browser default is correct.
 *
 * Wraps when focus is on the last element (forward), the first (backward), or
 * has escaped the dialog entirely — the last case is what pulls a stray Tab
 * back inside an open modal.
 *
 * @returns {{index: number, wrap: boolean} | null}
 */
export function nextTrapIndex({ count, currentIndex, shiftKey }) {
  if (count <= 0) return null;
  if (currentIndex < 0) {
    // Focus is outside the dialog: send it to the entry edge.
    return { index: shiftKey ? count - 1 : 0, wrap: true };
  }
  if (shiftKey && currentIndex === 0) return { index: count - 1, wrap: true };
  if (!shiftKey && currentIndex === count - 1) return { index: 0, wrap: true };
  return null;
}

/**
 * Trap Tab within `root` for one keydown event.
 *
 * @param {KeyboardEvent} event
 * @param {Element|null} root           the dialog container
 * @param {Document|Element} [doc]      element used for activeElement lookup
 * @returns {boolean} true when the event was handled and default prevented
 */
export function trapTabFocus(event, root, doc = document) {
  if (event.key !== 'Tab' || !root) return false;
  const focusable = [...(root.querySelectorAll?.(FOCUSABLE_SELECTOR) || [])];
  const currentIndex = focusable.indexOf(doc.activeElement);
  const next = nextTrapIndex({
    count: focusable.length,
    currentIndex,
    shiftKey: Boolean(event.shiftKey),
  });
  if (!next) return false;

  event.preventDefault();
  focusable[next.index]?.focus({ preventScroll: true });
  return true;
}
