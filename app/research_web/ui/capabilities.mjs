import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { empty } from './views.mjs';
import { renderDataCatalog } from './data-catalog.mjs';

export const capabilityStatus = (status) => ({ draft: '草稿', invalid: '检查未通过', blocked_dependencies: '依赖不足', enabled: '已启用', disabled: '已停用' })[status] || '未知状态';
const statusBadge = (item) => `<span class="badge ${['invalid', 'blocked_dependencies'].includes(item.status) ? 'danger' : item.enabled ? 'live' : ''}">${e(capabilityStatus(item.status))}${item.version ? ` · v${e(item.version)}` : ''}</span>`;
const list = (values) => (Array.isArray(values) ? values : []);
const line = (values, fallback = '无') => e(list(values).join('、') || fallback);
const button = (label, attribute, disabled = false, variant = '') => `<button type="button" class="button small ${variant}" ${attribute}${disabled ? ' disabled' : ''}>${e(label)}</button>`;
const reportConfig = (item) => item?.metadata?.report_workflow || item?.report_workflow || null;
const reportRunStatus = (status) => ({ queued: '排队中', preparing_data: '准备资料', blocked_data: '数据阻塞', blocked_approval: '等待审批', running: 'Claw 执行中', validating: '校验交付', completed: '已完成', delivery_incomplete: '交付不完整', failed: '失败', cancelled: '已取消', skipped_overlap: '重叠跳过' })[status] || status || '未知';
const resourceLabel = (resource) => ({ template: '模板', workbook: '底稿', asset: '品牌素材', mapping: '映射', validation: '校验规则' })[resource?.kind] || resource?.kind || '资源';

export function filterCapabilities(items = [], { kind = 'skill', source = 'all', category = '', query = '' } = {}) {
  const q = String(query).trim().toLocaleLowerCase();
  return list(items).filter(item => item.kind === kind && (source === 'all' || (source === 'builtin' ? item.builtin : !item.builtin)) && (!category || item.category === category) && (!q || `${item.name} ${item.description} ${item.category} ${item.id}`.toLocaleLowerCase().includes(q)));
}

function capabilityTabs(kind) {
  return `<div class="capability-tabs" role="tablist" aria-label="能力类型">${[['skill', 'Skill'], ['tool', 'Tool'], ['workflow', 'Workflow'], ['data', '数据']].map(([value, label]) => `<button type="button" role="tab" aria-selected="${kind === value}" class="button ${kind === value ? 'primary' : ''}" data-cap-kind="${value}">${label}</button>`).join('')}</div>`;
}

function capabilityCard(item, isTool, kind, busy) {
  const report = reportConfig(item);
  return `<article class="skill-card ${report ? 'report-workflow-card' : ''}"><div class="card-top"><span class="skill-icon">${icon(isTool ? 'grid' : kind === 'workflow' ? 'layers' : ({ 'document-reading': 'document', 'company-research': 'company', 'industry-research': 'industry', 'fund-evaluation': 'chart' })[item.id] || 'document')}</span><h2>${e(item.name)}</h2>${report ? '<span class="badge">报告 Workflow</span>' : ''}</div><p class="card-description">${e(item.description || '待补充简介')}</p>${report ? `<div class="report-workflow-card-meta"><span>资源 ${list(report.resources).length} 项</span><span>锁定 v${e(report.package_version || item.version || '—')}</span><span>${e(report.schedule?.enabled ? report.schedule.label || '日程已启用' : '手动运行')}</span></div>` : ''}<div class="card-bottom"><span>${isTool ? item.selectable ? '可选研究工具' : 'Agent 内部控制' : `${e(item.category)} · ${item.builtin ? '内置' : '我的'}${item.has_draft ? ' · 有未发布草稿' : ''}`}</span><span class="card-formats">${!isTool ? line(item.metadata?.default_formats, '无需文件') : ''}</span></div>${!isTool ? `<details class="card-requirements"><summary>输入要求与场景</summary><p class="small">场景：${line(item.metadata?.scenarios, '待补充')}</p><p class="small">输入：${e(list(item.metadata?.inputs).map(input => `${input.label}（${input.type}${input.required ? ' · 必填' : ' · 可选'}）`).join('、') || '待补充')}</p><p class="small">输出：${line(item.metadata?.default_formats, '无需文件')}</p></details>` : ''}<div class="card-state">${isTool ? '<span class="badge">只读 Tool</span>' : statusBadge(item)}<div class="button-row">${button('查看详情', `${isTool ? 'data-tool-detail' : 'data-skill-detail'}="${e(item.id)}"`, busy)}${isTool ? item.selectable ? button('放入草稿', `data-use-tool="${e(item.id)}"`, busy) : '' : button('放入草稿', `data-use-skill="${e(item.id)}"`, busy || !item.enabled)}</div></div></article>`;
}

export function renderCapabilityCatalog({ items = [], tools = [], dataCatalog = {}, dataView = 'capabilities', dataMarket = '', dataStatus = '', dataAuth = '', probe = null, kind = 'skill', source = 'all', category = '', query = '', busy = false, loading = false, error = '' } = {}) {
  if (kind === 'data') return `<header class="page-header capability-heading"><div><h1>能力中心</h1><p class="muted">统一查看数据能力、候选来源与真实接入状态。</p></div>${button('刷新目录', 'data-cap-refresh', busy)}</header>${capabilityTabs(kind)}${renderDataCatalog({ catalog: dataCatalog, view: dataView, query, category, market: dataMarket, status: dataStatus, auth: dataAuth, busy, loading, error, probe })}`;
  const isTool = kind === 'tool';
  const categories = [...new Set(items.filter(item => item.kind === kind).map(item => item.category).filter(Boolean))];
  const results = isTool ? tools.filter(tool => `${tool.name} ${tool.description} ${tool.id}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) : filterCapabilities(items, { kind, source, category, query });
  const actions = isTool ? '' : `<div class="button-row capability-create-actions">${button('对话创建', 'data-cap-create="conversation"', busy, 'primary')}${button('手动新建', 'data-cap-create="manual"', busy)}${button('导入 SKILL.md / ZIP', 'data-cap-import', busy)}<input id="cap-import-file" type="file" accept=".md,.zip" hidden></div>`;
  const intro = kind === 'workflow' ? '<p class="capability-intro"><strong>Workflow 分两类：</strong>普通研究步骤模板，以及持有 Word/PPT 模板、Excel 底稿和交付约束的报告 Workflow。执行统一交给 Claw。</p>' : '';
  return `<header class="page-header capability-heading"><div><h1>能力中心</h1><p class="muted">Skill、Workflow、真实工具与数据目录。选择只准备草稿；由你确认开始。</p></div><div class="catalog-actions">${actions}${button('刷新目录', 'data-cap-refresh', busy)}</div></header>${capabilityTabs(kind)}${intro}<div class="capability-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索能力名称和简介" value="${e(query)}" placeholder="搜索名称、简介或技术 ID"></label>${!isTool ? `<label>来源<select id="cap-source" data-cap-source>${[['all', '全部'], ['builtin', '内置'], ['mine', '我的']].map(([value, label]) => `<option value="${value}" ${source === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label>分类<select id="cap-category" data-cap-category><option value="">全部分类</option>${categories.map(value => `<option value="${e(value)}" ${category === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label>` : ''}</div>${isTool ? '<p class="notice warning">只读目录声明，不代表实例在线、凭据齐备或已获审批。工具选择不改变任何原生权限。</p>' : ''}${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}${loading ? '<p role="status">正在读取能力目录…</p>' : ''}${results.length ? `<div class="skills-grid capability-grid">${results.map(item => capabilityCard(item, isTool, kind, busy)).join('')}</div>` : empty('没有匹配的能力', '调整搜索、来源或分类；目录不会补充演示内容。')}`;
}

export function renderChecks(checks) {
  if (!checks) return '<p class="muted small">尚无检查结果。保存后执行检查。</p>';
  return `<section class="cap-checks" aria-label="导入与发布检查"><h3>${checks.valid ? '静态检查通过' : '检查未通过'} · ${e(capabilityStatus(checks.status))}</h3><p class="muted small">检查不执行代码，不证明脚本或资料绝对安全。脚本需逐项人工审查，不会自动安装依赖。</p>${list(checks.issues).map(issue => `<p class="notice error" role="alert"><strong>${e(issue.code)}</strong> ${e(issue.message)}${issue.path ? ` · ${e(issue.path)}` : ''}</p>`).join('')}${list(checks.bindings).length ? `<p class="small">关联版本：${checks.bindings.map(binding => `${e(binding.id)} v${e(binding.version)} (${e(binding.native_name)})`).join('；')}</p>` : ''}</section>`;
}

export function renderWorkflowPlan(capability) {
  if (capability?.kind !== 'workflow') return '';
  return `<section class="workflow-plan" aria-label="Workflow 预设步骤"><h3>Workflow 预设步骤 · v${e(capability.version || '草稿')}</h3><p class="muted small">以下是步骤模板，不代表已经执行。真实活动与文件另行显示，不自动勾选完成。</p>${list(capability.steps).length ? `<ol>${capability.steps.map(step => `<li><span class="step-type">${e(step.type || '步骤')}</span><strong>${e(step.title)}</strong><p>${e(step.instruction)}</p>${step.skill_id ? `<small>关联 Skill：${e(step.skill_id)}</small>` : ''}${list(step.tools).length ? `<small>工具意图：${line(step.tools)}</small>` : ''}</li>`).join('')}</ol>` : '<p class="small muted">尚未载入此版本的步骤；不能根据当前目录推断历史执行。</p>'}</section>`;
}

export function renderReportWorkflowDetail(item) {
  const report = reportConfig(item);
  if (!report) return '';
  const resources = list(report.resources); const providers = list(report.providers); const runs = list(report.runs); const artifacts = list(report.artifacts);
  return `<section class="report-workflow-detail" aria-label="报告 Workflow 管理"><header><div><span class="eyebrow">报告 Workflow</span><h3>模板、底稿与运行约束</h3></div><span class="badge">包版本 v${e(report.package_version || item.version || '—')}</span></header><p class="muted small">报告专属文件属于此 Workflow 版本；Claw 运行时复制母版并锁定版本，不在这里直接执行。</p><div class="report-workflow-grid"><article><h4>模板与底稿</h4>${resources.length ? `<ul class="resource-list">${resources.map(resource => `<li><span>${e(resourceLabel(resource))}</span><strong>${e(resource.name || resource.path)}</strong><code>${e(resource.path)}</code></li>`).join('')}</ul>` : '<p class="muted small">该版本尚未载入资源清单。</p>'}</article><article><h4>数据与插件要求</h4>${providers.length ? `<ul>${providers.map(provider => `<li><strong>${e(provider.name || provider.id)}</strong> · ${provider.required === false ? '可选' : '必需'} · ${e(provider.status || '未检测')}</li>`).join('')}</ul>` : '<p class="muted small">未声明 Excel Provider；不能推断可刷新。</p>'}</article><article><h4>版本</h4><p>当前报告包 <strong>v${e(report.package_version || item.version || '—')}</strong></p><p class="muted small">发布与回滚沿用能力版本管理；活动运行保持启动时锁定版本。</p></article><article><h4>一次 / 每周日程</h4><p>${e(report.schedule?.enabled ? report.schedule.label || report.schedule.kind : '未启用')}</p><p class="muted small">日程仅创建独立 Claw 会话；不会在页面打开时运行。</p></article><article><h4>历史运行</h4>${runs.length ? `<ul>${runs.slice(0, 4).map(run => `<li><code>${e(run.id)}</code><span>${e(reportRunStatus(run.status))} · ${e(run.status || 'unknown')}</span></li>`).join('')}</ul>` : '<p class="muted small">尚未载入运行记录。</p>'}</article><article><h4>产物</h4>${artifacts.length ? `<ul>${artifacts.slice(0, 5).map(file => `<li><strong>${e(file.name)}</strong><span>${e(String(file.format || '').toUpperCase())}</span></li>`).join('')}</ul>` : '<p class="muted small">尚未载入实际产物。</p>'}<p class="small">交付：${e(report.delivery?.status || '未知')}</p></article></div><section class="report-workflow-steps"><h4>结构化步骤</h4>${renderWorkflowPlan(item)}</section></section>`;
}

function renderPackageFiles(files) {
  return list(files).map(file => `<details class="package-file"><summary>${e(file.path)} · ${e(file.size ?? '大小未知')} B</summary><p class="small mono">SHA256：${e(file.sha256 || '保存后计算')}</p>${typeof file.content === 'string' ? `<pre>${e(file.content)}</pre>` : '<p class="muted small">二进制资源；通过版本导出下载，不在页面执行或直接渲染。</p>'}</details>`).join('');
}

export function exportURL(id, version) {
  return /^[a-z0-9-]{1,100}$/.test(id) && Number.isInteger(version) && version > 0 ? `/api/research/capabilities/${id}/versions/${version}/export` : null;
}

export function renderCapabilityDetail(item, { busy = false, versions = [], versionDetail = null, running = false } = {}) {
  if (!item) return '';
  const metadata = item.metadata || {}; const draft = item.draft || {}; const locked = busy;
  return `<section class="capability-detail" aria-label="能力详情"><div class="section-heading"><div><span class="eyebrow">${item.builtin ? '内置 · 仅可复制修改' : '我的能力'}</span><h2>${e(item.name)}</h2>${statusBadge(item)}</div>${button('关闭详情', 'data-cap-close', busy)}</div><p>${e(item.description)}</p><dl class="runtime-details"><div><dt>技术 ID / 原生名称</dt><dd class="mono">${e(item.id)} / ${e(item.native_name || '尚未发布')}</dd></div><div><dt>分类 / 来源</dt><dd>${e(item.category)} / ${e(item.source || '未知')}</dd></div><div><dt>适用场景</dt><dd>${line(metadata.scenarios)}</dd></div><div><dt>默认输出（显式格式优先）</dt><dd>${line(metadata.default_formats, '无需文件')}</dd></div><div><dt>所需工具（不授予权限）</dt><dd>${line(metadata.required_tools)}</dd></div><div><dt>依赖（不自动安装）</dt><dd>${line(metadata.dependencies)}</dd></div></dl><h3>输入与文件要求</h3><ul>${list(metadata.inputs).map(input => `<li>${e(input.label)} · ${e(input.name)} · ${e(input.type)} · ${input.required ? '必填' : '可选'}</li>`).join('')}</ul><div class="button-row">${button('放入研究草稿', `data-use-skill="${e(item.id)}"`, busy || !item.enabled)}${button('复制为我的能力', 'data-cap-copy', busy)}${!item.builtin ? button('编辑草稿', 'data-cap-edit', busy) : ''}${item.version ? button(item.enabled ? '停用' : '启用', `data-cap-action="${item.enabled ? 'disable' : 'enable'}"`, locked, item.enabled ? 'danger-outline' : '') : ''}${!item.builtin ? button('检查草稿', 'data-cap-action="check"', busy) + button('发布新版本', 'data-cap-action="publish"', locked || !item.checks?.valid, 'primary') : ''}${button('查看版本', 'data-cap-versions', busy)}</div>${running ? '<p class="notice warning">会话列表显示有活动回合，可能尚未刷新；可保存草稿，发布等操作由后端确认全局活动状态。</p>' : ''}${renderChecks(item.checks)}${renderReportWorkflowDetail(item) || renderWorkflowPlan(item)}<details class="package-source"><summary>当前候选指令与文件${item.has_draft ? '（未发布）' : ''}</summary><pre>${e(draft.instructions || 'Workflow 将由服务端编译为原生步骤模板。')}</pre>${renderPackageFiles(draft.files)}</details>${versions.length ? `<section class="cap-versions"><h3>不可变版本</h3>${versions.map(version => `<div class="version-row"><span>v${e(version.version)}${version.current ? ' · 当前' : ''}</span>${button('查看内容', `data-cap-version="${e(version.version)}"`, busy)}${exportURL(item.id, version.version) ? `<a class="button small" download href="${exportURL(item.id, version.version)}">导出 v${e(version.version)} ZIP</a>` : ''}${!version.current ? button('回滚到此版本', `data-cap-rollback="${e(version.version)}"`, locked) : ''}</div>`).join('')}</section>` : ''}${versionDetail ? `<section class="version-detail"><h3>只读版本 v${e(versionDetail.version)}</h3><pre>${e(JSON.stringify(versionDetail.metadata, null, 2))}</pre><pre>${e(versionDetail.instructions || '')}</pre>${renderWorkflowPlan({ ...versionDetail, kind: item.kind })}${renderPackageFiles(versionDetail.files)}</section>` : ''}</section>`;
}

export function renderToolDetail(tool) {
  if (!tool) return '';
  return `<section class="capability-detail" aria-label="只读工具详情"><div class="section-heading"><h2>${e(tool.name)}</h2>${button('关闭详情', 'data-cap-close')}</div><p>${e(tool.description)}</p><p>技术 ID：<code>${e(tool.id)}</code> · 只读目录，未执行</p><p>来源：${e(tool.source || '未提供')} ${e(tool.source_commit || '')}</p><p>审批：${e(tool.approval)}</p><ul>${list(tool.conditions).map(item => `<li>${e(item)}</li>`).join('')}</ul><details><summary>参数 schema 与资料来源</summary><pre>${e(JSON.stringify(tool.parameters, null, 2))}</pre><pre>${e(JSON.stringify(tool.data_sources || {}, null, 2))}</pre></details>${tool.selectable ? button('放入研究草稿（仍需原生审批）', `data-use-tool="${e(tool.id)}"`) : '<p class="muted">Agent 内部控制工具，不可单独选择。</p>'}</section>`;
}

export function creationArtifacts(detail) {
  if (detail?.purpose !== 'capability_creation') return [];
  return list(detail.files).filter(file => file.kind === 'outputs' && (file.name === 'SKILL.md' || /\.zip$/i.test(file.name || '')));
}

export function renderCreationArtifacts(detail, busy = false) {
  if (detail?.purpose !== 'capability_creation') return '';
  const files = creationArtifacts(detail);
  return `<section class="creation-artifacts"><h3>能力创建会话 · ${e(detail.creation_kind || 'Skill')}</h3><p class="small muted">候选文件不会自动发布。先在普通对话中明确发送制作请求，完成后选择实际产物导入审查。</p>${files.length ? files.map(file => button(`审查 ${file.name}`, `data-cap-artifact="${e(file.id)}"`, busy)).join('') : '<p class="muted small">尚无实际 SKILL.md / ZIP 候选产物。</p>'}</section>`;
}
