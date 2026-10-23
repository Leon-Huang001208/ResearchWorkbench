import { escapeHTML as e } from './markdown.mjs';

const HUAAN = 'huaan-etf-weekly';
const rows = (value) => Array.isArray(value) ? value : [];
const runSource = (run) => {
  const recorded = run?.weekly_data_source;
  const frozen = run?.weekly_production?.data_source;
  if (recorded && frozen && recorded !== frozen) return null;
  const source = recorded || frozen;
  return ['wind_excel', 'wind_client_api'].includes(source) ? source : null;
};
const sourceLabel = (source) => source === 'wind_excel' ? 'Wind Excel'
  : source === 'wind_client_api' ? 'Wind Client API' : '来源未记录';
const STATUS_LABEL = { blocked_dependency: 'Wind 数据依赖未就绪', unverified: '尚未核验',
  passed: '已通过', incomplete: '未通过', complete: '已生成', finalized: '已定稿',
  blocked: '未定稿', pending: '待检查', not_run: '未执行' };

// Presentation only: the gateway independently enforces the account boundary.
export function canUseReportWorkflows(userId, account) {
  return !userId || (account?.role === 'admin' && account?.primary === true);
}

export function weeklyScheduleDefaults(detail) {
  return detail?.id === HUAAN
    ? { kind: 'weekly', enabled: false, timezone: 'Asia/Shanghai', weekday: 4, hour: 15, minute: 30 }
    : { kind: 'manual', enabled: false, timezone: 'Asia/Shanghai' };
}

export function weeklyManualRunAccepted(detail) {
  if (detail?.id === HUAAN && detail?.weekly_production?.data_source === 'wind_excel') return false;
  const upgraded = detail?.id === HUAAN && detail?.weekly_production?.enabled === true;
  return rows(detail?.runs).some(run => run.trigger === 'manual'
    && run.status === 'completed' && run.delivery_status === 'complete'
    && (!upgraded || (run.version === detail.current_version
      && run.quality_status === 'passed' && run.finalization_status === 'finalized')));
}

export function renderWeeklyProductionStatus(detail) {
  if (detail?.id !== HUAAN) return '';
  const policy = detail.weekly_production || {};
  const currentSource = policy.data_source || 'wind_client_api';
  const matchesCurrent = (run) => policy.enabled === true && Number.isInteger(detail.current_version)
    && run.version === detail.current_version && runSource(run) === currentSource;
  const runs = [...rows(detail.runs)];
  if (policy.latest && !runs.some(run => run === policy.latest
    || (run.id && run.id === policy.latest.id))) runs.push(policy.latest);
  const latest = runs.find(matchesCurrent) || {};
  const gaps = rows(latest.missing);
  const checks = [
    ['数据就绪', latest.weekly_data_assessment?.status || latest.data_status || policy.provider?.status || '尚未核验'],
    ['内容质量', latest.quality_status || '尚未核验'],
    ['文件交付', latest.delivery_status || '尚未生成'],
    ['正式定稿', latest.finalization_status || '未定稿'],
  ];
  const prepare = !policy.enabled || policy.data_source !== 'wind_excel'
    ? `<button class="button small" type="button" data-prepare-weekly-production="${HUAAN}">准备自动生产版本</button>` : '';
  const publish = Number.isInteger(policy.prepared_version)
    ? `<button class="button small" type="button" data-publish-weekly-production="${e(policy.prepared_version)}">发布生产合同 v${e(policy.prepared_version)}</button>` : '';
  const runHistory = runs.length ? `<details class="report-weekly-run-history"><summary>查看运行版本、来源与历史验收</summary><ul>${runs.map(run => `<li><strong>${matchesCurrent(run) ? '当前版本运行' : '历史运行（不计当前验收）'} · ${Number.isInteger(run.version) ? `v${e(run.version)}` : '版本未记录'} · ${e(sourceLabel(runSource(run)))}</strong><p>${e(run.id || '运行标识未记录')} · 内容质量：${e(STATUS_LABEL[run.quality_status] || run.quality_status || '尚未核验')} · 正式定稿：${e(STATUS_LABEL[run.finalization_status] || run.finalization_status || '未定稿')}</p>${run.session_id ? `<a class="text-button" href="#/claw?session=${e(run.session_id)}">查看该次 Claw 活动与工具事件</a>` : ''}</li>`).join('')}</ul><p class="muted small">历史文件仍可在下方运行与交付中查看。</p></details>` : '';
  return `<section class="report-weekly-production" aria-label="周报自动生产">
    <h2>华安 ETF 周报自动生产</h2>
    <p>当前来源：${policy.data_source === 'wind_excel' ? 'Wind Excel（原始导出与工作表取数）' : 'Wind Client API'}；依赖就绪不代表数据已核验。</p>
    <p>${policy.data_source === 'wind_excel' ? 'Excel 模式目前仅支持手动生产；市场截止为周五 15:30，实际采集完成后冻结并记录时间。' : '每周五 15:30（北京时间）开始生产；通过数据、内容与文件检查后自动定稿。'}</p>
    ${policy.data_source === 'wind_excel' ? '<p class="notice warning">取数只在既有 Excel 实例中新建任务专用临时工作簿。Excel 模式仍须本期有效的 EDB 和经济日历原生导出；暂不支持启用定时，自动刷新及无人值守取数尚未验证。</p>' : ''}
    <p class="muted small">行情最多落后各自市场一个已结束交易日，正文标明实际日期；新闻材料不足时明确说明。</p>
    <p>当前生产验收：${Number.isInteger(detail.current_version) ? `v${e(detail.current_version)}` : '版本未发布'} · ${e(sourceLabel(currentSource))}</p>
    ${latest.version ? `<p>当前验收运行：${e(latest.id || '运行标识未记录')} · v${e(latest.version)} · ${e(sourceLabel(runSource(latest)))}</p>` : '<p>当前版本及来源尚无运行验收。</p>'}
    <dl class="report-workflow-overview" data-weekly-current-acceptance>${checks.map(([label, value]) => `<div><dt>${e(label)}</dt><dd data-weekly-state="${e(value)}">${e(STATUS_LABEL[value] || value)}</dd></div>`).join('')}</dl>
    ${latest.weekly_cutoff ? `<p>本期截止：${e(latest.weekly_cutoff)}</p>` : ''}
    ${latest.weekly_data_assessment?.frozen_at ? `<p>实际采集开始：${e(latest.weekly_data_assessment.acquisition_started_at || '')}；实际冻结：${e(latest.weekly_data_assessment.frozen_at)}</p>` : ''}
    ${gaps.length ? `<ul class="notice warning">${gaps.map(gap => `<li>${e(String(gap))}</li>`).join('')}</ul>` : ''}
    ${runHistory}
    ${!policy.enabled ? '<p class="notice warning">当前版本尚未启用新的生产合同；历史交付不代表已通过自动定稿检查。</p>' : ''}
    ${prepare}${publish}
  </section>`;
}
