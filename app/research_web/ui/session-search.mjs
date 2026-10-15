// One native read at a time; superseded/closed queries cannot replace current UI.
// Holds only this explicit search's snippets, never a second conversation store.
export function createSessionSearch({ search, notify = () => {}, logger = () => {}, delay = 250, schedule = setTimeout, cancel = clearTimeout }) {
  const state = { query: '', mode: '', items: [], pending: false, error: '', has_more: false };
  let generation = 0, timer = null, active = false, ready = false;
  function reset() {
    generation++; if (timer !== null) cancel(timer); timer = null; ready = false;
    Object.assign(state, { query: '', mode: '', items: [], pending: false, error: '', has_more: false });
  }
  async function execute() {
    if (active || !ready) return;
    ready = false; active = true;
    const ticket = generation, query = state.query, mode = state.mode;
    try {
      const result = await search(query, mode);
      if (ticket !== generation) return;
      if (result?.source !== 'native_dsh' || !Array.isArray(result.items) || result.items.length > 20 || typeof result.has_more !== 'boolean' || result.items.some(row => typeof row?.id !== 'string' || !row.id || row.mode !== mode || typeof row.title !== 'string' || typeof row.snippet !== 'string' || [...row.snippet].length > 240)) throw new Error('invalid_search_response');
      Object.assign(state, { items: result.items, has_more: result.has_more });
      logger('native_session_search_finished');
    } catch {
      if (ticket === generation) { state.error = '正文搜索暂不可用，请重试；标题和能力搜索仍可用。'; state.items = []; state.has_more = false; logger('native_session_search_failed'); }
    } finally {
      active = false;
      if (ticket === generation) { state.pending = false; notify(); }
      if (ready) void execute();
    }
  }
  return {
    state,
    update(value, mode) {
      reset(); state.query = String(value || '').trim(); state.mode = mode === 'claw' ? mode : '';
      if (state.query && state.mode) {
        if (state.query.length > 500 || state.query.includes('\0')) state.error = '正文搜索关键词须为不含空字符的500字符以内文本。';
        else { state.pending = true; timer = schedule(() => { timer = null; ready = true; void execute(); }, delay); }
      }
      notify();
    },
    close() { reset(); notify(); },
  };
}
