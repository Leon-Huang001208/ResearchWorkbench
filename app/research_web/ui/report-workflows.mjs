import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const STATUS = {
  draft: '草稿', needs_attention: '需要补充', enabled: '已启用', disabled: '已停用',
};
const RUN_STATUS = {
  queued: '排队中', preparing_data: '刷新底稿', blocked_data: '数据阻塞',
  blocked_approval: '等待审批', running: 'Claw 执行中', validating: '校验交付',
  completed: '已完成', delivery_incomplete: '交付不完整', failed: '失败',
  cancelled: '已取消', skipped_overlap: '重叠跳过',
};
const roleName = (role) => ({ template: '模板', workbook: 'Excel 底稿', asset: '素材', mapping: '映射', validation: '校验', workflow: '流程' })[role] || role || '资源';
const providerName = (provider) => ({ wind_excel: 'Wind Excel', ifind_excel: '同花顺 iFinD Excel' })[provider] || provider || '未知 Provider';
const currentManifest = (detail) => list(detail?.versions).find(item => item.current)?.manifest || list(detail?.versions).at(-1)?.manifest || detail?.draft || {};
const canRun = (item) => item?.status === 'enabled' && Number.isInteger(item?.current_version);
const artifactLink = (file) => String(file?.url || '').startsWith('/api/research/')
  ? `<a class="text-button" href="${e(file.url)}">${e(file.name || file.format || '产物')}</a>`
  : `<span>${e(file?.name || file?.format || '产物')}</span>`;

const renderRunEvidence = (item) => {
  const agents = list(item.subagents);
  const artifacts = list(item.artifacts);
  const missing = list(item.missing);
  const sessionLink = item.session_id
    ? `<a class="text-button" href="#/claw?session=${e(item.session_id)}">查看 Claw 活动与工具事件</a>`
    : '<span class="muted">尚未创建 Claw 会话</span>';
  return `<details class="report-run-evidence"><summary>查看运行证据</summary><dl><dt>Excel 刷新</dt><dd>刷新清单 ${list(item.refresh_manifests).length}</dd><dt>共享快照</dt><dd>${item.dataset_snapshot_sha256 ? `<code>${e(String(item.dataset_snapshot_sha256).slice(0, 16))}…</code>` : '尚未生成'}</dd><dt>子 Agent</dt><dd>${agents.length ? agents.map(agent => `${e(agent.name || agent.id)} · ${e(agent.status || 'unknown')}`).join('<br>') : '无真实证据'}</dd><dt>产物</dt><dd>${artifacts.length ? artifacts.map(artifactLink).join(' · ') : '尚无本次产物'}</dd><dt>缺失</dt><dd>${missing.length ? missing.map(value => e(value)).join('<br>') : '无已记录缺失项'}</dd></dl>${sessionLink}</details>`;
};

export function renderReportWorkflowShelf(items = [], { busy = false, compact = false } = {}) {
  const workflows = list(items);
  const cards = workflows.map((item) => {
    const runnable = canRun(item);
    const latest = item.latest_run;
    const latestLabel = latest && typeof latest === 'object'
      ? RUN_STATUS[latest?.status] || latest?.status || '已记录'
      : latest ? '已记录' : '尚未运行';
    return `<article class="report-workflow-library-card ${runnable ? '' : 'unavailable'}"><header><span class="report-workflow-icon">${icon('layers')}</span><div><span class="eyebrow">REPORT WORKFLOW</span><h3>${e(item.name)}</h3></div><span class="badge ${runnable ? 'live' : 'danger'}">${e(STATUS[item.status] || item.status)}</span></header><p>${e(item.description || '该报告的模板、Excel 底稿、步骤和交付格式随版本锁定。')}</p><dl><div><dt>版本</dt><dd>${item.current_version ? `v${e(item.current_version)}` : '未发布'}</dd></div><div><dt>交付</dt><dd>${list(item.delivery_formats).map(value => String(value).toUpperCase()).join(' / ') || '未声明'}</dd></div><div><dt>数据插件</dt><dd>${list(item.providers).join('、') || '无 Excel Provider'}</dd></div><div><dt>最近运行</dt><dd>${e(latestLabel)}</dd></div></dl><div class="button-row"><button type="button" class="button small" data-report-workflow-detail="${e(item.id)}">查看模板与底稿</button><button type="button" class="button small primary" data-run-report-workflow="${e(item.id)}" ${busy || !runnable ? 'disabled' : ''}>交给 Claw 执行</button></div>${!runnable ? `<p class="small muted" role="status">${item.status === 'needs_attention' ? '模板或配置尚不完整，只能查看，不能运行。' : 'Workflow 尚未发布或已停用。'}</p>` : ''}</article>`;
  }).join('');
  return `<section class="report-workflow-library ${compact ? 'compact' : ''}" aria-label="报告 Workflow"><div class="section-heading"><div><span class="eyebrow">CLAW REPORT WORKFLOWS</span><h2>报告 Workflow</h2></div><a href="#/skills?kind=workflow" class="text-button">管理 Workflow</a></div><p class="muted small">每篇报告锁定自己的 Word/PPT 模板与 Excel 底稿；运行会创建独立 Claw 会话。</p>${cards ? `<div class="report-workflow-library-grid">${cards}</div>` : '<p class="notice warning" role="status">尚未导入任何真实报告 Workflow。通用研究模板不能替代报告项目。</p>'}</section>`;
}

export function renderReportWorkflowDetail(detail, { busy = false } = {}) {
  if (!detail) return '';
  const manifest = currentManifest(detail);
  const resources = list(manifest.resources);
  const policies = list(manifest.workbook_policies);
  const excluded = new Set(list(manifest.excluded_workbooks));
  const blocks = list(manifest.blocks);
  const providers = list(detail.providers_status).filter(item => list(manifest.providers).some(required => required.provider === item.id));
  const runs = list(detail.runs);
  const runnable = canRun(detail);
  const resourceRows = resources.map(item => {
    const inactive = excluded.has(item.path);
    return `<li class="${inactive ? 'resource-excluded' : ''}"><span>${e(roleName(item.role))}</span><strong>${e(item.path)}</strong><small>${inactive ? '保留但不运行' : `${e(Math.ceil((item.size || 0) / 1024))} KB`}</small></li>`;
  }).join('');
  const providerRows = providers.map(item => `<li><div><strong>${e(providerName(item.id))}</strong><small>${item.integration_state === 'ready' ? '依赖已就绪' : '依赖不可用'} · ${e(item.health || 'untested')}</small></div><button class="button small" type="button" data-probe-report-provider="${e(item.id)}" ${busy || item.integration_state !== 'ready' ? 'disabled' : ''}>检测 ${e(providerName(item.id))}</button></li>`).join('');
  const runRows = runs.slice(0, 12).map(item => {
    const active = ['queued', 'preparing_data', 'blocked_approval', 'running', 'validating'].includes(item.status);
    const retryable = ['blocked_data', 'delivery_incomplete', 'failed', 'cancelled'].includes(item.status);
    return `<li class="report-run-row"><div><strong>${e(item.id)}</strong><small>v${e(item.version)} · ${e(item.trigger)} · ${e(RUN_STATUS[item.status] || item.status)}</small></div><span class="badge ${item.status === 'completed' ? 'live' : active ? '' : 'danger'}">${e(item.delivery_status || 'pending')}</span>${active ? `<button class="button small" data-cancel-report-run="${e(item.id)}">取消运行</button>` : ''}${retryable ? `<button class="button small" data-retry-report-run="${e(item.id)}">失败重试</button>` : ''}${renderRunEvidence(item)}</li>`;
  }).join('');
  const manualPassed = runs.some(item => item.trigger === 'manual' && item.status === 'completed' && item.delivery_status === 'complete');
  const schedule = detail.schedule || { kind: 'manual', enabled: false, timezone: 'Asia/Shanghai' };
  const scheduleForm = `<form class="report-schedule-form" data-report-schedule-form="${e(detail.id)}"><label>方式<select name="kind"><option value="manual" ${schedule.kind === 'manual' ? 'selected' : ''}>仅手动</option><option value="once" ${schedule.kind === 'once' ? 'selected' : ''}>一次性</option><option value="weekly" ${schedule.kind === 'weekly' ? 'selected' : ''}>每周</option></select></label><label>一次执行时间<input type="datetime-local" name="once_at" value="${e(schedule.once_at || '')}"></label><label>星期<select name="weekday">${['周一','周二','周三','周四','周五','周六','周日'].map((label, index) => `<option value="${index}" ${Number(schedule.weekday) === index ? 'selected' : ''}>${label}</option>`).join('')}</select></label><div class="schedule-time"><label>小时<input type="number" name="hour" min="0" max="23" value="${e(schedule.hour ?? 9)}"></label><label>分钟<input type="number" name="minute" min="0" max="59" value="${e(schedule.minute ?? 0)}"></label></div><label class="check"><input type="checkbox" name="enabled" ${schedule.enabled ? 'checked' : ''} ${manualPassed ? '' : 'disabled'}>启用自动运行</label><button class="button small" type="submit" ${busy ? 'disabled' : ''}>保存日程</button></form>`;
  return `<section class="report-workflow-page" aria-label="报告 Workflow 详情"><header class="page-header"><div><span class="eyebrow">REPORT WORKFLOW · ${e(detail.id)}</span><h1>${e(detail.name)}</h1><p class="muted">模板、Excel 底稿、组装区块、版本、运行和日程属于同一个不可变 Workflow 版本。</p></div><div class="button-row"><button class="button" data-close-report-workflow>返回目录</button><button class="button primary" data-run-report-workflow="${e(detail.id)}" ${busy || !runnable ? 'disabled' : ''}>交给 Claw 执行</button></div></header><div class="report-workflow-overview"><article><span>状态</span><strong>${e(STATUS[detail.status] || detail.status)}</strong></article><article><span>当前版本</span><strong>${detail.current_version ? `v${e(detail.current_version)}` : '未发布'}</strong></article><article><span>交付格式</span><strong>${list(detail.delivery_formats).map(value => String(value).toUpperCase()).join(' / ') || '未声明'}</strong></article><article><span>真实运行</span><strong>${runs.length}</strong></article></div><div class="report-workflow-detail-grid"><section><h2>模板与底稿</h2>${resourceRows ? `<ul class="resource-list">${resourceRows}</ul>` : '<p class="notice warning">当前版本没有资源清单。</p>'}</section><section><h2>数据与插件要求</h2>${providerRows ? `<ul class="provider-list">${providerRows}</ul>` : '<p class="muted small">该报告不需要 Excel Provider。</p>'}${policies.length ? `<ul class="resource-list">${policies.map(item => `<li><strong>${e(item.workbook)}</strong><span>${list(item.providers).map(provider => e(provider.provider)).join(' + ') || '无需插件'}</span></li>`).join('')}</ul>` : ''}</section><section><h2>报告结构</h2>${blocks.length ? `<ol class="report-block-list">${blocks.map(item => `<li><span>${e(item.kind)}</span><strong>${e(item.title)}</strong><small>${item.required ? '必需' : '可选'}</small></li>`).join('')}</ol>` : '<p class="notice warning">尚未解析出可组装的报告区块。</p>'}</section><section><h2>运行与交付</h2>${runRows ? `<ul class="provider-list report-run-list">${runRows}</ul>` : '<p class="muted small">尚无真实运行。旧历史产物不会计入本次交付。</p>'}</section><section><h2>一次 / 每周日程</h2><p>${schedule.enabled ? `${e(schedule.kind)} · ${e(schedule.timezone)}` : '未启用；仅手动运行'}</p>${scheduleForm}<p class="muted small">${manualPassed ? '已通过手动完整运行，可配置项目日程。' : '手动完整运行通过后才能启用日程。'}</p></section><section><h2>不可变版本</h2>${list(detail.versions).map(item => `<p class="version-row"><strong>v${e(item.version)}</strong><span>${item.current ? '当前' : ''}${item.published ? ' · 已发布' : ' · 未发布'}</span></p>`).join('') || '<p class="muted small">尚无版本。</p>'}</section><section><h2>历史产物</h2>${list(detail.historical_artifacts).slice(0, 12).map(item => `<p class="artifact-row"><strong>${e(item.name || item.path)}</strong><span>${e(Math.ceil((item.size || 0) / 1024))} KB · 只读历史</span></p>`).join('') || '<p class="muted small">尚无历史产物索引。</p>'}</section></div>${!runnable ? '<p class="notice warning" role="status">该 Workflow 当前不能运行。请先补齐配置并发布版本。</p>' : ''}</section>`;
}
