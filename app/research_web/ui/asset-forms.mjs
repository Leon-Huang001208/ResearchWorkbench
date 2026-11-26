/**
 * Asset workspace form submissions.
 *
 * Five forms share the same lifecycle: read the form, guard against a stale page,
 * call the API, refresh the workspace, report a message. They lived inline in the
 * 434-line submit listener. The wind-range rule and the "still running" wording
 * are load-bearing business statements, so they move verbatim.
 */

const WIND_MAX_DAYS = 60;
const DAY_MS = 86400000;

/**
 * Wind only serves daily stock bars up to 60 calendar days inclusive.
 * Returns an error string when the request violates that, otherwise null.
 */
export function windRangeError(payload) {
  if (payload?.source !== 'wind') return null;
  if (payload.frequency !== 'daily') {
    return 'Wind 当前仅支持不超过 60 个日历日的股票日线，请修改区间或来源。';
  }
  const span = (Date.parse(payload.end_date) - Date.parse(payload.start_date)) / DAY_MS + 1;
  if (!Number.isFinite(span)) return 'Wind 当前仅支持不超过 60 个日历日的股票日线，请修改区间或来源。';
  return span > WIND_MAX_DAYS
    ? 'Wind 当前仅支持不超过 60 个日历日的股票日线，请修改区间或来源。'
    : null;
}

/**
 * @param {object} deps
 * @param {object} deps.api
 * @param {object} deps.assetState
 * @param {object} deps.assetWorkspace
 * @param {object} deps.assetNews
 * @param {() => object} deps.getState
 * @param {() => boolean} deps.isBusy
 * @param {(busy: boolean) => void} deps.setBusy
 * @param {() => () => boolean} deps.owner        returns a "still current" probe
 * @param {() => number} deps.generation          page generation counter
 * @param {(record: object, ticket: number) => Promise<object>} deps.pollObservation
 * @param {() => Promise<void>} deps.loadWorkspace
 * @param {() => void} deps.render
 * @param {(message: string) => void} deps.setSuccess
 * @param {(message: string) => void} deps.setError
 * @param {(url: string) => void} deps.replaceUrl
 * @param {(asset: string, type: string, view: string) => string} deps.assetHref
 * @param {(form: HTMLFormElement) => object} deps.readObservation
 * @param {() => string} deps.newId
 * @param {(event: string, detail?: object) => void} [deps.log]
 */
export function createAssetForms({
  api,
  assetState,
  assetWorkspace,
  assetNews,
  getState,
  isBusy,
  setBusy,
  owner,
  generation,
  pollObservation,
  loadWorkspace,
  render,
  setSuccess,
  setError,
  replaceUrl,
  assetHref,
  readObservation,
  newId,
  log = () => {},
}) {
  const formValues = form => new FormData(form);

  /** Shared shape for the three simple "post a record, refresh" forms. */
  async function postAndRefresh({ form, send, okMessage, logEvent }) {
    const current = owner();
    try {
      await send(formValues(form));
      if (!current()) return 'stale';
      form.reset();
      setSuccess(okMessage);
      await loadWorkspace();
      render();
      return 'saved';
    } catch (error) {
      if (current()) {
        setError(error.message);
        render();
      }
      log(logEvent, { code: error.code || 'request_failed' });
      return 'failed';
    }
  }

  return {
    /** Start an observation run and follow it to completion. */
    async createObservation(form) {
      if (isBusy()) return 'busy';
      const current = owner();
      const payload = readObservation(form);
      const ticket = generation();
      const state = getState();

      const rangeError = windRangeError(payload);
      if (rangeError) {
        setError(rangeError);
        render();
        return 'rejected';
      }

      assetWorkspace.cancel();
      setBusy(true);
      setError('');
      render();
      try {
        let record = await api.createAssetObservation(payload, newId());
        if (ticket !== generation() || !current()) return 'stale';

        Object.assign(state.route, { asset: payload.asset, assetType: payload.asset_type });
        // replaceState does not dispatch hashchange; the topic read below stays bound to this asset.
        replaceUrl(assetHref(payload.asset, payload.asset_type, state.route.assetView || 'overview'));
        assetState.observation = record;
        assetState.rows = {};
        render();
        void assetNews.activate(state.route);

        record = await pollObservation(record, ticket);
        if (ticket !== generation() || !current()) return 'stale';
        await loadWorkspace();

        if (ticket === generation() && current() && record.status !== 'running'
            && assetState.observation?.id === record.id) {
          void assetWorkspace.startHistory(
            'recent',
            payload.adjustment,
            undefined,
            payload.adjustment === 'none' ? payload.source : 'tinysoft',
          );
        }

        setSuccess(
          record.status === 'complete'
            ? '资产数据查询已结束，请查看各区块的来源与覆盖。'
            : record.status === 'running'
              ? '查询仍在运行，刷新本地状态可继续查看；未重新提交。'
              : '查询已结束，部分区块有缺失或失败，请查看对应状态。',
        );
        return record.status;
      } catch (error) {
        if (ticket === generation()) setError(error.message);
        log('asset_observation_create_failed');
        return 'failed';
      } finally {
        if (current()) {
          setBusy(false);
          render();
        }
      }
    },

    /** Add the current asset to a local watchlist. */
    addWatchlistItem(form) {
      return postAndRefresh({
        form,
        send: values => api.addWatchlistItem(String(values.get('watchlist_id')), {
          asset: String(values.get('asset')),
          asset_type: assetState.observation?.asset_type || 'stock',
          name: String(assetState.rows?.overview?.[0]?.name || values.get('asset')),
        }),
        okMessage: '已加入本地自选列表。',
        logEvent: 'asset_watchlist_update_failed',
      });
    },

    /** Save a free-text observation note. */
    saveNote(form) {
      return postAndRefresh({
        form,
        send: values => api.createAssetNote({
          asset: String(values.get('asset')),
          text: String(values.get('text')).trim(),
        }),
        okMessage: '观察笔记已保存。',
        logEvent: 'asset_note_update_failed',
      });
    },

    /** Save an alert rule; evaluation happens when a new snapshot arrives. */
    saveAlert(form) {
      return postAndRefresh({
        form,
        send: values => api.createAssetAlert({
          asset: String(values.get('asset')),
          field: String(values.get('field')),
          operator: String(values.get('operator')),
          threshold: Number(values.get('threshold')),
          cooldown_minutes: 60,
        }),
        okMessage: '提醒规则已保存，将在新快照到达时评估。',
        logEvent: 'asset_alert_update_failed',
      });
    },
  };
}
