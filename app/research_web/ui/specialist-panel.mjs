import { escapeHTML as e } from './markdown.mjs';

const fields = {
  max_tokens: ['Token 保守准入额度', 1, 2000000],
  max_calls: ['模型调用上限', 1, 48],
  max_concurrency: ['并发节点上限', 1, 2],
  timeout_seconds: ['自动执行秒数', 1, 1800],
  max_revisions: ['计划修订上限', 0, 2],
};

export function defaultSpecialistBudget() {
  return { confirmed: false, max_tokens: 200000, max_calls: 12, max_concurrency: 2, timeout_seconds: 1800, max_revisions: 2 };
}

export function specialistBudgetError(value) {
  if (!value || value.confirmed !== true) return '请先核对并确认本次协作研究预算。';
  for (const [key, [label, min, max]] of Object.entries(fields)) {
    if (!Number.isSafeInteger(value[key]) || value[key] < min || value[key] > max) return `${label}须为 ${min} 至 ${max} 的整数。`;
  }
  return '';
}

export function renderSpecialistBudget(value = defaultSpecialistBudget(), disabled = false) {
  const budget = { ...defaultSpecialistBudget(), ...value };
  return `<fieldset class="specialist-budget"${disabled ? ' disabled' : ''}><legend>专业协作研究预算</legend><p class="small muted">行业与量化并行，独立审查；最多自动执行30分钟、修订两轮。Token预算是保守准入额度，实际用量按原生回执；不是人民币费用上限。离线样本首次请求已需预留至少48,613单位，真实提示词和历史可能更大。请先核对当前模型费用，再明确确认。</p><div class="button-row">${Object.entries(fields).map(([key, [label, min, max]]) => `<label>${e(label)}<input type="number" inputmode="numeric" min="${min}" max="${max}" step="1" data-specialist-budget="${key}" value="${e(budget[key])}"></label>`).join('')}</div><label><input type="checkbox" data-specialist-budget="confirmed"${budget.confirmed === true ? ' checked' : ''}>我已核对模型费用，并确认本次预算；费用上限尚未确认时不启动。</label></fieldset>`;
}

export function handleSpecialistBudgetChange(target, controller) {
  const key = target?.dataset?.specialistBudget;
  if (key !== 'confirmed' && !Object.hasOwn(fields, key || '')) return false;
  controller.setSpecialistBudget({ ...controller.state.specialistBudget, [key]: key === 'confirmed' ? target.checked : Number(target.value), ...(key === 'confirmed' ? {} : { confirmed: false }) });
  return true;
}

const statuses = {
  pending: '等待依赖', running: '执行中', accepted: '已受理，待核对结果', prepared: '已准备',
  awaiting_plan: '等待已校验计划', reserved: '已预留，待核对受理', ready_for_validation: '节点齐备，等待质量验收',
  needs_attention: '需要处理', unknown: '结果未知', cancel_requested: '取消待确认', cancelling: '取消待确认', cancel_pending: '取消待确认',
  cancelled: '已取消本次运行', completed: '节点已完成', succeeded: '节点已完成', failed: '失败',
  incomplete: '研究未完成', timed_out: '已超时', invalidated: '成果已失效', stale: '成果已失效',
};
const rows = value => Array.isArray(value) ? value : value && typeof value === 'object' ? Object.entries(value).map(([id, item]) => ({ id, ...item })) : [];
const stateText = value => statuses[value] || value || '未知';
const textRows = values => Array.isArray(values) ? values.map(item => e(item)).join('、') : '';

export function specialistCanResume(task) {
  const live = new Set(['reserved', 'accepted', 'unknown', 'cancel_requested']);
  if (rows(task?.attempts).some(attempt => live.has(attempt.status)) || rows(task?.model_requests).some(request => request.usage == null)) return false;
  if (typeof task?.can_resume === 'boolean') return task.can_resume;
  return ['needs_attention', 'cancelled', 'timed_out', 'failed', 'incomplete'].includes(task?.status);
}

function usageSummary(task) {
  if (task.model_requests && typeof task.model_requests === 'object') {
    const requests = rows(task.model_requests);
    const known = requests.filter(request => Number.isSafeInteger(request.usage?.input_tokens) && Number.isSafeInteger(request.usage?.output_tokens));
    const total = known.reduce((sum, request) => sum + request.usage.input_tokens + request.usage.output_tokens, 0);
    const unknown = requests.length - known.length;
    return `已记录调用：${requests.length} · ${unknown || !requests.length ? '用量未知' : `已记录 Token：${total}`}${unknown && known.length ? `（已记录 ${total}，另有 ${unknown} 项未知）` : ''} · 金额未知`;
  }
  const count = task.usage?.total_tokens ?? task.usage?.tokens;
  return `${Number.isSafeInteger(count) && count >= 0 ? `已记录 Token：${count}` : '用量未知'} · 金额未知`;
}

function deadlineText(value) {
  if (typeof value !== 'number') return value || '未知';
  const date = new Date(value * 1000);
  return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false }) : '未知';
}

export function renderSpecialistPanel(detail, busy = false) {
  const task = detail?.specialist;
  if (!task || typeof task !== 'object') return '';
  const attempts = rows(task.attempts);
  const plan = task.active_plan || {};
  const version = plan.version ?? task.revision ?? '未知';
  const nodes = rows(plan.nodes || task.nodes).map(node => {
    const attempt = attempts.filter(row => row.node_id === node.id && row.plan_version === version && !row.invalidated).at(-1);
    return { ...node, status: attempt?.status || node.status || 'pending' };
  });
  const history = rows(task.plan_history).filter(entry => entry.version > 0);
  const historyHTML = history.length ? `<details><summary>历史计划（${history.length}）</summary><ul>${history.map(entry => `<li>v${e(entry.version)}：${rows(entry.nodes).map(node => e(`${node.id} · ${node.role}`)).join('、')}</li>`).join('')}</ul></details>` : '';
  return `<section class="notice specialist-panel" aria-label="专业 Agent 协作状态"><h3>专业协作研究 · 计划 v${e(version)}</h3><p role="status">${e(stateText(task.status))} · ${e(usageSummary(task))}</p><p class="small muted">运行 ${e(task.id || '未知')} · 截止 ${e(deadlineText(task.deadline))}。节点成果与可读草稿不代表正式定稿；取消回执不等于已经停止。</p>${nodes.length ? `<ul>${nodes.map(node => `<li><strong>${e(node.id || node.name || '未知节点')}</strong> · ${e(node.role || node.agent_id || '')} · ${e(stateText(node.status))}</li>`).join('')}</ul>` : '<p class="muted">尚无已校验计划节点。</p>'}${historyHTML}${attempts.length ? `<details><summary>执行尝试与部分成果（${attempts.length}）</summary>${attempts.map(attempt => { const output = attempt.output || attempt.result || {}; return `<article><strong>${e(attempt.node_id || attempt.id || '未知尝试')}</strong> · ${e(attempt.invalidated ? '成果已失效' : stateText(attempt.status))} · 计划 v${e(attempt.plan_version ?? '未知')}${output.conclusion ? `<p>${e(output.conclusion)}</p>` : ''}${output.limitations?.length ? `<p>限制：${textRows(output.limitations)}</p>` : ''}${output.artifact_ids?.length ? `<p>产物引用：${textRows(output.artifact_ids)}</p>` : ''}</article>`; }).join('')}</details>` : ''}<div class="button-row"><button type="button" class="button small" data-specialist-refresh${busy ? ' disabled' : ''}>核对状态</button>${specialistCanResume(task) ? `<button type="button" class="button small" data-specialist-resume${busy ? ' disabled' : ''}>确认后续跑</button>` : ''}</div><p class="small muted">续跑创建关联的新尝试；已受理或接受状态未知的请求不会自动重发。</p></section>`;
}
