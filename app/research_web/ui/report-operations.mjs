import { reportHref } from './report-workspace.mjs';
import { safeLog } from './core.mjs';

const ACTIONS = ['prepareWeeklyProduction', 'publishWeeklyProduction', 'runReportWorkflow', 'runHistoricalReportWorkflow', 'probeReportProvider', 'cancelReportRun', 'retryReportRun'];

// UI request coordination only: the original Host remains the execution/quality authority.
export function createReportOperations({ api, scope, detail, setDetail, allowed, busy, setBusy, feedback, navigate, refreshCatalog, delay = ms => new Promise(resolve => setTimeout(resolve, ms)), logger = safeLog }) {
  const current = captured => {
    const now = scope();
    return now.generation === captured.generation && now.page === captured.page && now.projectId === captured.projectId;
  };
  async function refresh(captured, workflowId) {
    if (!current(captured)) return false;
    if (!workflowId) return true;
    const next = await api.reportWorkflow(workflowId);
    if (!current(captured) || detail()?.id !== workflowId || next?.id !== workflowId) return false;
    setDetail(next); return true;
  }
  async function perform(operation) {
    if (!allowed() || busy()) return;
    const captured = { ...scope() }; const workflowId = detail()?.id;
    feedback({ error: '', success: '' }); setBusy(true);
    try { await operation(captured, workflowId); }
    catch (error) {
      if (current(captured)) feedback({ error: error.message || '报告操作未完成，请核对原运行状态。', success: '' });
      logger('report_operation_failed', { code: error.code || 'request_failed' });
    } finally { setBusy(false); }
  }
  async function submit(data, captured) {
    let run = 'runHistoricalReportWorkflow' in data
      ? await api.runHistoricalReportWorkflow(data.runHistoricalReportWorkflow)
      : await api.runReportWorkflow(data.runReportWorkflow);
    if (!current(captured)) return;
    for (let attempt = 0; attempt < 12 && !run.session_id && ['queued', 'preparing_data', 'running'].includes(run.status); attempt++) {
      await delay(500); if (!current(captured)) return;
      run = await api.reportRun(run.id); if (!current(captured)) return;
    }
    await refreshCatalog(); if (!current(captured)) return;
    if (captured.page === 'reports') {
      await navigate(reportHref(run.workflow_id || captured.projectId, 'production', run.id));
    } else if (run.session_id) {
      await navigate(`#/claw?session=${encodeURIComponent(run.session_id)}`);
    } else if (['blocked_data', 'blocked_approval', 'delivery_incomplete', 'failed', 'cancelled', 'skipped_overlap', 'needs_attention'].includes(run.status)) {
      feedback({ error: `报告未进入执行：${run.failure_code || run.status}。`, success: '' });
    } else feedback({ error: '', success: '报告请求已受理，数据与实际执行状态仍需核对。' });
  }
  return {
    matches: data => ACTIONS.some(key => key in data),
    async handle(data) {
      if (!ACTIONS.some(key => key in data)) return false;
      await perform(async (captured, workflowId) => {
        if ('runReportWorkflow' in data || 'runHistoricalReportWorkflow' in data) return submit(data, captured);
        if ('prepareWeeklyProduction' in data) {
          const next = await api.prepareWeeklyProduction(data.prepareWeeklyProduction);
          if (current(captured) && detail()?.id === workflowId && next?.id === workflowId) {
            setDetail(next); feedback({ error: '', success: '已准备新的生产版本；验收通过前不能启用日程。' });
          }
        } else if ('publishWeeklyProduction' in data) {
          const version = Number(data.publishWeeklyProduction);
          if (workflowId !== 'huaan-etf-weekly' || !Number.isInteger(version) || version < 1) throw new Error('生产版本无效。');
          const next = await api.publishReportWorkflowVersion(workflowId, version);
          if (current(captured) && detail()?.id === workflowId && next?.id === workflowId) {
            setDetail(next); feedback({ error: '', success: '生产合同已发布；首次手动定稿通过后才能启用日程。' });
          }
        } else if ('probeReportProvider' in data) {
          const result = await api.probeReportProvider(data.probeReportProvider, globalThis.crypto.randomUUID());
          if (await refresh(captured, workflowId)) feedback({ error: '', success: result.ready ? '数据插件探测通过。' : `数据插件探测未通过：${result.code || '状态未知'}。` });
        } else if ('cancelReportRun' in data) {
          const result = await api.cancelReportRun(data.cancelReportRun);
          if (await refresh(captured, workflowId)) feedback({ error: '', success: result.status === 'cancelled' && result.monitoring_disposition !== 'ended_by_user' ? '运行记录已取消；实际执行及清理状态请查看原始证据。' : '取消结果尚未确认，请核对原运行状态。' });
        } else if ('retryReportRun' in data) {
          const run = await api.retryReportRun(data.retryReportRun);
          if (await refresh(captured, workflowId)) feedback({ error: '', success: run.id === data.retryReportRun ? '已核对原运行记录，未创建新的执行。' : `已创建重试记录 ${run.id}；实际受理状态另行确认。` });
        }
      });
      return true;
    },
    async saveSchedule(workflowId, body) {
      await perform(async (captured, originalId) => {
        if (originalId !== workflowId) throw new Error('报告项目已变化，请重新打开后操作。');
        await api.saveReportSchedule(workflowId, body);
        if (await refresh(captured, workflowId)) feedback({ error: '', success: body.enabled ? '报告日程已启用。' : '报告日程已保存但未启用。' });
      });
    },
  };
}
