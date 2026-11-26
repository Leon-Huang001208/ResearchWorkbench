/**
 * Office auto-probe consent, end to end.
 *
 * Turning this on or off has a surprising amount of choreography: confirm the
 * destructive direction, optimistically patch the local items, queue a consent
 * update per integration, then poll every affected probe batch until it settles
 * — all of it abandoned if the user leaves the settings page midway.
 *
 * The dispatcher in app.mjs held this inline and needed nine collaborators to do
 * it. Gathering them behind one factory keeps the click handler to a single call
 * and gives the flow a name that can be tested.
 */

export const OFFICE_INTEGRATION_IDS = Object.freeze([
  'local:excel_app',
  'local:word_app',
  'local:powerpoint_app',
]);

const WAITING_STATUSES = new Set(['queued', 'checking']);

/**
 * Resolve the integrations a request covers.
 *
 * @param {string} requested `all` or a single integration id
 * @returns {string[]} matching ids, empty when the request names something unknown
 */
export function officeConsentTargets(requested) {
  if (requested === 'all') return [...OFFICE_INTEGRATION_IDS];
  return OFFICE_INTEGRATION_IDS.filter(id => id === requested);
}

/**
 * Decide whether a disable request still needs an explicit second confirmation.
 *
 * Enabling is additive and goes through immediately. Disabling is confirmed once
 * per target: the first click records the target and returns "needs confirm",
 * the second click carries `confirmed=true` and proceeds.
 */
export function officeConsentNeedsConfirm({ requested, currentlyEnabled, confirmed, pendingTarget }) {
  // Turning it ON is additive; only turning it OFF is confirmed.
  if (!currentlyEnabled) return false;
  return confirmed !== 'true' || pendingTarget !== requested;
}

/**
 * @param {object} deps
 * @param {object} deps.guard          polling guard from createLocalIntegrationPollingGuard
 * @param {object} deps.queue          queue from createOfficeConsentQueue
 * @param {() => object} deps.getCatalog
 * @param {(names: string[]) => Promise<void>} deps.loadCatalog
 * @param {(id: string) => Promise<object>} deps.fetchBatch
 * @param {(getBatch: Function, id: string) => Promise<object>} deps.waitForBatch
 * @param {(message: string) => void} deps.setSuccess
 * @param {(message: string) => void} deps.setError
 * @param {() => void} deps.render
 * @param {(event: string, detail?: object) => void} [deps.log]
 * @param {() => string} deps.getPendingTarget
 * @param {(value: string) => void} deps.setPendingTarget
 */
export function createOfficeAutoConsent({
  guard,
  queue,
  getCatalog,
  loadCatalog,
  fetchBatch,
  waitForBatch,
  setSuccess,
  setError,
  render,
  log = () => {},
  getPendingTarget,
  setPendingTarget,
}) {
  /** Patch the visible rows so the toggle responds before the server answers. */
  const patchLocalItems = (ids, consent) => {
    for (const item of getCatalog().localIntegrations?.integration_status?.items || []) {
      if (ids.includes(item.id)) item.details = { ...item.details, auto_probe_consent: consent };
    }
  };

  const batchesToWatch = (results, latest) => {
    const seen = new Set(results.map(result => result?.batch?.id).filter(Boolean));
    if (latest?.id && WAITING_STATUSES.has(latest.status)) seen.add(latest.id);
    return [...seen];
  };

  return {
    /**
     * @param {{requested: string, currentlyEnabled: boolean, confirmed: string}} input
     *   currentlyEnabled reflects the toggle's current state: true means this
     *   click turns the feature OFF, which is the direction that needs confirming.
     * @returns {Promise<'ignored'|'needs-confirm'|'done'|'failed'>}
     */
    async apply({ requested, currentlyEnabled, confirmed }) {
      const ids = officeConsentTargets(requested);
      if (!ids.length) return 'ignored';

      if (officeConsentNeedsConfirm({ requested, currentlyEnabled, confirmed, pendingTarget: getPendingTarget() })) {
        setPendingTarget(requested);
        render();
        return 'needs-confirm';
      }

      setPendingTarget('');
      const ticket = guard.begin();
      patchLocalItems(ids, !currentlyEnabled);
      render();

      try {
        const settled = await Promise.allSettled(ids.map(id => queue.set(id, !currentlyEnabled)));
        if (!guard.isCurrent(ticket)) return 'ignored';

        const rejected = settled.find(result => result.status === 'rejected');
        if (rejected) throw rejected.reason;

        const results = settled.map(result => result.value);
        await loadCatalog(['localIntegrations']);
        if (!guard.isCurrent(ticket)) return 'ignored';

        // Turning it off needs no follow-up; keep the message short.
        if (currentlyEnabled) {
          setSuccess('已关闭对应 Office 自动验证。');
          render();
        }

        const latest = getCatalog().localIntegrations?.integration_status?.latest_batch;
        for (const batchId of batchesToWatch(results, latest)) {
          let previous = '';
          await waitForBatch(async id => {
            if (!guard.isCurrent(ticket)) return { status: 'cancelled' };
            const batch = await fetchBatch(id);
            if (!guard.isCurrent(ticket)) return { status: 'cancelled' };
            // Repaint only on real progress, not on every poll tick.
            const progress = JSON.stringify(batch.items || {});
            if (progress !== previous) {
              previous = progress;
              await loadCatalog(['localIntegrations']);
            }
            return batch;
          }, batchId);
        }
        if (!guard.isCurrent(ticket)) return 'ignored';
        await loadCatalog(['localIntegrations']);
        if (!guard.isCurrent(ticket)) return 'ignored';

        setSuccess(currentlyEnabled ? '已关闭对应 Office 自动验证。' : 'Office 自动验证已处理；请查看每项结果。');
        return 'done';
      } catch (error) {
        if (!guard.isCurrent(ticket)) return 'ignored';
        setError(error?.message || 'Office 自动验证设置失败。');
        log('office_auto_consent_failed', { status: error?.code || error?.name || 'unknown' });
        await loadCatalog(['localIntegrations']);
        return 'failed';
      } finally {
        if (guard.isCurrent(ticket)) render();
      }
    },
  };
}
