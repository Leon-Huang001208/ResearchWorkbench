/**
 * Clipboard actions for conversation output.
 *
 * These two handlers were two of the ~300 inline branches inside the 919-line
 * click listener in app.mjs. They only touch three things, so they move out
 * cleanly: read state, write the transient "copied" marker, and repaint.
 */

const TRANSIENT_MS = 1600;

/**
 * @param {object} deps
 * @param {() => object} deps.getState        current shell state
 * @param {() => string} deps.getCopied       current transient marker
 * @param {(value: string) => void} deps.setCopied
 * @param {() => void} deps.render
 * @param {(transient: string) => void} [deps.schedule]  timer hook for tests
 * @param {(value: string) => Promise<void>} [deps.writeText]
 */
export function createClipboardActions({
  getState,
  getCopied,
  setCopied,
  render,
  schedule = (fn, ms) => setTimeout(fn, ms),
  writeText = text => navigator.clipboard.writeText(text),
}) {
  const flash = marker => {
    setCopied(marker);
    render();
    schedule(() => {
      // Only clear if nothing newer replaced the marker meanwhile.
      if (getCopied() === marker) {
        setCopied('');
        render();
      }
    }, TRANSIENT_MS);
  };

  return {
    /** Answer body copy; the message must still exist in the open conversation. */
    async copyAnswer(id) {
      const message = (getState().detail?.messages || []).find(item => item.id === id);
      if (!message?.text) return false;
      try {
        await writeText(message.text);
        flash(`answer:${message.id}`);
        return true;
      } catch {
        getState().error = '复制失败，请手动选择正文复制。';
        render();
        return false;
      }
    },

    /** Current URL copy, used by the share affordance. */
    async shareSession() {
      try {
        await writeText(globalThis.location.href);
        flash('share');
        return true;
      } catch {
        getState().error = '复制链接失败，请手动复制地址栏地址。';
        render();
        return false;
      }
    },
  };
}
