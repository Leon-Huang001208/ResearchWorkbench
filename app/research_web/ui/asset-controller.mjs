import { safeLog } from './core.mjs';
import { selectAssetObservation } from './asset-navigation.mjs';

export function createAssetWorkspaceController({ api, onChange = () => {} } = {}) {
  const state = { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [], errors: {}, loading: false };
  let generation = 0; let abort;
  function cancel() { generation++; abort?.abort(); abort = null; state.loading = false; }
  async function load(route = {}) {
    cancel(); const ticket = generation; abort = new AbortController(); const options = { signal: abort.signal };
    Object.assign(state, { observation: null, rows: {}, errors: {}, loading: true }); onChange();
    const requests = [['observations', 'assetObservations'], ['watchlists', 'watchlists'], ['notes', 'assetNotes'], ['alerts', 'assetAlerts'], ['notifications', 'assetNotifications']];
    await Promise.all(requests.map(async ([name, method]) => {
      try { const data = await api[method](options); if (ticket === generation) state[name] = Array.isArray(data.items) ? data.items : []; }
      catch (error) { if (ticket === generation) { state[name] = []; state.errors[name] = error.message; safeLog('asset_workspace_read_failed', { status: name }); } }
    }));
    if (ticket !== generation) return;
    const chosen = selectAssetObservation(state.observations, route);
    if (chosen) {
      state.observation = { ...chosen, blocks: Object.fromEntries(Object.entries(chosen.blocks || {}).map(([key, block]) => [key, { ...block }])) };
      const observation = state.observation;
      await Promise.all(Object.entries(observation.blocks).filter(([name]) => !['news', 'announcements'].includes(name)).map(async ([name, block]) => {
        const dataset = block.dataset; if (!dataset?.dataset_id || !observation.session_id) return;
        const rows = []; const expected = Number(dataset.row_count);
        try {
          for (let offset = 0; offset < 5000; offset += 200) {
            if (ticket !== generation) return;
            const result = await api.datasetRows(observation.session_id, dataset.dataset_id, offset, 200, options);
            if (!Array.isArray(result.items)) throw new Error('快照行格式异常');
            rows.push(...result.items);
            if (rows.length >= expected || result.items.length < 200) break;
          }
          if (Number.isFinite(expected) && rows.length < expected) throw new Error('快照记录未完整读取，请重试。');
          if (ticket === generation) state.rows[name] = rows;
        } catch (error) {
          if (ticket !== generation) return;
          if (rows.length) state.rows[name] = rows;
          block.status = rows.length ? 'partial' : 'error'; block.failure_code = 'snapshot_read_failed';
          state.errors[name] = error.message; safeLog('asset_dataset_rows_failed', { status: name });
        }
      }));
    }
    if (ticket === generation) { state.loading = false; onChange(); }
  }
  return { state, load, cancel };
}
