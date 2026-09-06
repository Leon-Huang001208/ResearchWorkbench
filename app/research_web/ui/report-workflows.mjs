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
const currentManifest = (detail) => list(detail?.versions).find(item => item.current)?.manifest || list(detail?.versions).at(-1)?.manifest || detail?.draft || {};
const canRun = (item) => item?.status === 'enabled' && Number.isInteger(item?.current_version);

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
  const blocks = list(manifest.blocks);
  const runnable = canRun(detail);
  return `<section class="report-workflow-page" aria-label="报告 Workflow 详情"><header class="page-header"><div><span class="eyebrow">REPORT WORKFLOW · ${e(detail.id)}</span><h1>${e(detail.name)}</h1><p class="muted">模板、Excel 底稿、组装区块、版本、日程和历史产物都属于这一个 Workflow。</p></div><div class="button-row"><button class="button" data-close-report-workflow>返回目录</button><button class="button primary" data-run-report-workflow="${e(detail.id)}" ${busy || !runnable ? 'disabled' : ''}>交给 Claw 执行</button></div></header><div class="report-workflow-overview"><article><span>状态</span><strong>${e(STATUS[detail.status] || detail.status)}</strong></article><article><span>当前版本</span><strong>${detail.current_version ? `v${e(detail.current_version)}` : '未发布'}</strong></article><article><span>交付格式</span><strong>${list(detail.delivery_formats).map(value => String(value).toUpperCase()).join(' / ') || '未声明'}</strong></article><article><span>历史产物</span><strong>${list(detail.historical_artifacts).length}</strong></article></div><div class="report-workflow-detail-grid"><section><h2>模板与底稿</h2>${resources.length ? `<ul class="resource-list">${resources.map(item => `<li><span>${e(roleName(item.role))}</span><strong>${e(item.path)}</strong><small>${e(Math.ceil((item.size || 0) / 1024))} KB</small></li>`).join('')}</ul>` : '<p class="notice warning">当前版本没有资源清单。</p>'}</section><section><h2>Excel 刷新</h2>${policies.length ? `<ul class="resource-list">${policies.map(item => `<li><strong>${e(item.workbook)}</strong><span>${list(item.providers).map(provider => e(provider.provider)).join(' + ') || '无需插件'}</span></li>`).join('')}</ul>` : '<p class="muted small">该报告未声明需要刷新的 Excel 底稿。</p>'}</section><section><h2>报告结构</h2>${blocks.length ? `<ol class="report-block-list">${blocks.map(item => `<li><span>${e(item.kind)}</span><strong>${e(item.title)}</strong><small>${item.required ? '必需' : '可选'}</small></li>`).join('')}</ol>` : '<p class="notice warning">尚未解析出可组装的报告区块。</p>'}</section><section><h2>日程</h2><p>${detail.schedule?.enabled ? `${e(detail.schedule.kind)} · ${e(detail.schedule.timezone)}` : '未启用；仅手动运行'}</p><p class="muted small">日程到期创建独立 Claw 会话，不依赖浏览器页面保持打开。</p></section><section><h2>不可变版本</h2>${list(detail.versions).map(item => `<p class="version-row"><strong>v${e(item.version)}</strong><span>${item.current ? '当前' : ''}${item.published ? ' · 已发布' : ' · 未发布'}</span></p>`).join('') || '<p class="muted small">尚无版本。</p>'}</section><section><h2>历史产物</h2>${list(detail.historical_artifacts).slice(0, 12).map(item => `<p class="artifact-row"><strong>${e(item.name || item.path)}</strong><span>${e(Math.ceil((item.size || 0) / 1024))} KB</span></p>`).join('') || '<p class="muted small">尚无历史产物索引。</p>'}</section></div>${!runnable ? '<p class="notice warning" role="status">该 Workflow 当前不能运行。请先补齐配置并发布版本。</p>' : ''}</section>`;
}
