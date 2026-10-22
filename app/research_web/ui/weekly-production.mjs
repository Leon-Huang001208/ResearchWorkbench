import { escapeHTML as e } from './markdown.mjs';

const HUAAN = 'huaan-etf-weekly';
const rows = (value) => Array.isArray(value) ? value : [];

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
  const upgraded = detail?.id === HUAAN && detail?.weekly_production?.enabled === true;
  return rows(detail?.runs).some(run => run.trigger === 'manual'
    && run.status === 'completed' && run.delivery_status === 'complete'
    && (!upgraded || (run.version === detail.current_version
      && run.quality_status === 'passed' && run.finalization_status === 'finalized')));
}

export function renderWeeklyProductionStatus(detail) {
  if (detail?.id !== HUAAN) return '';
  const policy = detail.weekly_production || {};
  const latest = policy.latest || rows(detail.runs)[0] || {};
  const gaps = rows(latest.missing);
  const checks = [
    ['数据就绪', latest.data_status || policy.provider?.status || '尚未核验'],
    ['内容质量', latest.quality_status || '尚未核验'],
    ['文件交付', latest.delivery_status || '尚未生成'],
    ['正式定稿', latest.finalization_status || '未定稿'],
  ];
  const prepare = !policy.enabled
    ? `<button class="button small" type="button" data-prepare-weekly-production="${HUAAN}">准备自动生产版本</button>` : '';
  const publish = Number.isInteger(policy.prepared_version)
    ? `<button class="button small" type="button" data-publish-weekly-production="${e(policy.prepared_version)}">发布生产合同 v${e(policy.prepared_version)}</button>` : '';
  return `<section class="report-weekly-production" aria-label="周报自动生产">
    <h2>华安 ETF 周报自动生产</h2>
    <p>每周五 15:30（北京时间）开始生产；通过数据、内容与文件检查后自动定稿。</p>
    <p class="muted small">行情最多落后各自市场一个已结束交易日，正文标明实际日期；新闻材料不足时明确说明。</p>
    <dl class="report-workflow-overview">${checks.map(([label, value]) => `<div><dt>${e(label)}</dt><dd>${e(value)}</dd></div>`).join('')}</dl>
    ${latest.cutoff ? `<p>本期截止：${e(latest.cutoff)}</p>` : ''}
    ${gaps.length ? `<ul class="notice warning">${gaps.map(gap => `<li>${e(String(gap))}</li>`).join('')}</ul>` : ''}
    ${!policy.enabled ? '<p class="notice warning">当前版本尚未启用新的生产合同；历史交付不代表已通过自动定稿检查。</p>' : ''}
    ${prepare}${publish}
  </section>`;
}
