/**
 * Data-source connection actions: remove, consent, probe and auth check.
 *
 * These four lived inline in the click dispatcher and each repeated the same
 * shape: resolve the source label, confirm the risky direction, call the API
 * through the shared action wrapper, refresh whatever the panel shows, and
 * report a stable message. Gathering them here also gives the busy flag and the
 * selected-configuration reset a single owner.
 */

import { confirmAutoProbeConsent } from './connections.mjs';

const ZHIQIU_SHARED_NOTE =
  '该账号池由知丘研报、公众号与纪要共享，三项授权都会被移除。';

/**
 * Label lookup shared by every action here.
 * Falls back to the raw id so a stale button still names something identifiable.
 */
export function sourceLabel(catalog, sourceId) {
  const sources = catalog?.connections?.sources || [];
  return sources.find(item => item.id === sourceId)?.label || sourceId;
}

/** Zhiqiu sources share one credential pool; removing one removes all three. */
export function sharedImpactNote(sourceId) {
  return String(sourceId).startsWith('zhiqiu_') ? ZHIQIU_SHARED_NOTE : '';
}

/**
 * @param {object} deps
 * @param {() => object} deps.getCatalog
 * @param {object} deps.api
 * @param {object} deps.controller   the shared action wrapper
 * @param {(names: string[]) => Promise<void>} deps.loadCatalog
 * @param {(sourceId: string) => Promise<void>} deps.loadConnectionConfiguration
 * @param {(message: string) => void} deps.setSuccess
 * @param {(message: string) => void} deps.setError
 * @param {() => void} deps.clearError
 * @param {() => void} deps.clearSuccess
 * @param {(busy: boolean) => void} deps.setProbeBusy
 * @param {() => void} deps.clearSelectedConfiguration
 * @param {() => void} deps.render
 * @param {(id: string) => Promise<object>} deps.waitForProbe
 * @param {(fn: Function, id: string) => Promise<object>} deps.waitForBatch
 * @param {() => string} deps.newId
 * @param {(fn: Function) => boolean} [deps.confirm]
 * @param {(event: string, detail?: object) => void} [deps.log]
 */
export function createSourceConnections({
  getCatalog,
  api,
  controller,
  loadCatalog,
  loadConnectionConfiguration,
  setSuccess,
  setError,
  clearError,
  clearSuccess,
  setProbeBusy,
  clearSelectedConfiguration,
  render,
  waitForProbe,
  waitForBatch,
  newId,
  confirm = fn => fn(),
  log = () => {},
}) {
  const label = sourceId => sourceLabel(getCatalog(), sourceId);

  return {
    /** Remove local configuration and credentials; historical snapshots stay readable. */
    async remove(sourceId) {
      const name = label(sourceId);
      const message = `移除 ${name} 的本机配置与凭据？${sharedImpactNote(sourceId)}历史快照不会删除。`;
      if (confirm(() => globalThis.confirm?.(message)) !== true) return 'cancelled';

      const result = await controller.action(
        () => api.deleteSourceConfiguration(sourceId),
        { refreshAfter: false },
      );
      if (!result) return 'failed';

      setSuccess('本机配置和系统凭据已移除；历史快照保持可读。');
      clearSelectedConfiguration();
      await loadCatalog(['connections', 'dataCatalog', 'tools']);
      // Clearing the selection means the detail panel reloads against a gone source;
      // this refresh keeps the panel from showing the removed configuration.
      await loadConnectionConfiguration(sourceId);
      return 'removed';
    },

    /**
     * Toggle automatic probing for one source.
     * @param {{sourceId: string, currentlyEnabled: boolean}} input
     */
    async setConsent({ sourceId, currentlyEnabled }) {
      const next = !currentlyEnabled;
      const name = label(sourceId);
      if (!confirmAutoProbeConsent(message => globalThis.confirm?.(message) === true, name, next)) {
        return 'cancelled';
      }

      const result = await controller.action(
        () => api.setIntegrationConsent(`data:${sourceId}`, next),
        { refreshAfter: false },
      );
      if (!result) return 'failed';

      setSuccess(next ? `已允许自动检测 ${name}。` : `已停用 ${name} 的自动检测。`);
      await loadCatalog(['connections', 'integrations']);
      return 'updated';
    },

    /** Run one probe and report its health. */
    async probe(sourceId) {
      const name = label(sourceId);
      clearError();
      clearSuccess();
      setProbeBusy(true);
      render();
      try {
        const accepted = await controller.action(
          () => api.probeDataSource(sourceId, `probe-${sourceId}-${newId()}`),
          { refreshAfter: false },
        );
        if (!accepted) return 'failed';
        if (typeof accepted.id !== 'string' || !accepted.id) {
          throw new Error('服务未返回有效的探测任务，请刷新后重试。');
        }
        const current = await waitForProbe(probeId => api.dataProbe(probeId), accepted.id);
        setSuccess(
          current.health === 'healthy'
            ? `${name}检测通过。`
            : `${name}检测完成，请根据状态说明处理。`,
        );
        await loadCatalog(['connections', 'dataCatalog']);
        await loadConnectionConfiguration(sourceId);
        return 'done';
      } catch (error) {
        setError(error?.message || '检测失败，请重试。');
        log('connection_probe_failed', { status: error?.code || error?.name || 'unknown' });
        return 'failed';
      } finally {
        setProbeBusy(false);
        render();
      }
    },

    /** Verify an HTTP auth exchange. Data permissions remain unverified. */
    async verifyAuth(sourceId) {
      setProbeBusy(true);
      clearError();
      clearSuccess();
      render();
      try {
        const result = await api.verifySourceAuthorization(sourceId);
        setSuccess(
          result.status === 'authenticated'
            ? 'HTTP 授权交换成功；具体数据权限尚未验证。'
            : '授权尚未验证。',
        );
        await loadConnectionConfiguration(sourceId);
        return 'verified';
      } catch (error) {
        setError(error.message || '授权未验证');
        log('source_authorization_unverified');
        return 'failed';
      } finally {
        setProbeBusy(false);
        render();
      }
    },
  };
}
