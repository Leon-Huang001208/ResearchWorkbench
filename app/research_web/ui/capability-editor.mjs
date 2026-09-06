import { escapeHTML as e } from './markdown.mjs';

const array = (value) => Array.isArray(value) ? value : [];
const text = (value) => typeof value === 'string' ? value : '';
const lines = (value) => text(value).split('\n').map(line => line.trim()).filter(Boolean);
const jsonCopy = (value) => structuredClone(value);
const field = (name, label, value = '', type = 'text', required = false) => `<label for="cap-${e(name)}">${e(label)}<input id="cap-${e(name)}" name="${e(name)}" type="${type}" value="${e(value)}" ${required ? 'required' : ''}></label>`;
const textarea = (name, label, value = '', required = false) => `<label for="cap-${e(name)}">${e(label)}<textarea id="cap-${e(name)}" name="${e(name)}" rows="4" ${required ? 'required' : ''}>${e(value)}</textarea></label>`;
const stepTypes = ['取数', '刷新底稿', '检索', '分析', '段落', '图表', '表格', '文件组装', '交付检查'];
let stepClientSequence = 0;
const nextStepKey = () => `step-${Date.now().toString(36)}-${(++stepClientSequence).toString(36)}`;

export function ensureStepKeys(steps, makeKey = nextStepKey) {
  return array(steps).map(step => ({ ...step, client_key: text(step.client_key) || makeKey() }));
}

export function newWorkflowStep() {
  return { client_key: nextStepKey(), type: '分析', title: '', instruction: '', skill_id: null, tools: [] };
}

export function editableDraft(draft = {}) {
  const steps = array(draft.steps).map(({ client_key: _clientKey, ...step }) => jsonCopy(step));
  return { kind: draft.kind || 'skill', metadata: jsonCopy(draft.metadata || {}), instructions: text(draft.instructions), files: array(draft.files).map(file => ({ path: file.path, ...(typeof file.content === 'string' ? { content: file.content } : { base64: file.base64 }) })), steps, reviewed_scripts: [...array(draft.reviewed_scripts)] };
}

export function newDraft(kind = 'skill') {
  return { kind, metadata: { name: '', slug: '', description: '', category: '', inputs: [{ name: 'question', label: '研究问题', type: 'text', required: true }], scenarios: [], default_formats: ['md'], required_tools: [], dependencies: [] }, instructions: '', files: [], steps: kind === 'workflow' ? [newWorkflowStep()] : [], reviewed_scripts: [] };
}

export function moveStep(steps, index, direction) {
  const result = jsonCopy(steps); const target = index + direction;
  if (!Number.isInteger(index) || ![-1, 1].includes(direction) || index < 0 || target < 0 || index >= result.length || target >= result.length) return result;
  [result[index], result[target]] = [result[target], result[index]]; return result;
}

export function readEditor(values, previous) {
  const get = name => String(values.get(name) || '');
  const inputs = array(previous.metadata?.inputs).map((_input, index) => ({ name: get(`input-${index}-name`), label: get(`input-${index}-label`), type: get(`input-${index}-type`), required: values.has(`input-${index}-required`) }));
  const files = array(previous.files).map((file, index) => ({ ...file, path: get(`file-${index}-path`), ...(typeof file.content === 'string' ? { content: get(`file-${index}-content`), sha256: get(`file-${index}-content`) === file.content ? file.sha256 : undefined } : {}) }));
  const scriptsChanged = files.some((file, index) => file.path !== previous.files[index].path || file.content !== previous.files[index].content);
  return { kind: previous.kind, metadata: { name: get('name'), slug: get('slug'), description: get('description'), category: get('category'), inputs, scenarios: lines(get('scenarios')), default_formats: values.getAll('default_formats').map(String), required_tools: values.getAll('required_tools').map(String), dependencies: lines(get('dependencies')) }, instructions: get('instructions'), files,
    steps: ensureStepKeys(previous.steps).map((step, index) => ({ client_key: step.client_key, type: get(`step-${index}-type`) || step.type || '分析', title: get(`step-${index}-title`), instruction: get(`step-${index}-instruction`), skill_id: get(`step-${index}-skill`) || null, tools: values.getAll(`step-${index}-tools`).map(String) })),
    reviewed_scripts: scriptsChanged ? [] : [...array(previous.reviewed_scripts)] };
}

function toolChecks(tools, selected, name) {
  // Keep unknown imported requirements visible and removable, never silently drop them.
  const all = [...tools, ...array(selected).filter(id => !tools.some(tool => tool.id === id)).map(id => ({ id, name: `${id}（目录未声明）` }))];
  return all.map(tool => `<label class="check-label"><input type="checkbox" name="${e(name)}" value="${e(tool.id)}" ${array(selected).includes(tool.id) ? 'checked' : ''}>${e(tool.name)}</label>`).join('');
}

export function renderCapabilityEditor({ draft, id = '', items = [], tools = [], busy = false } = {}) {
  if (!draft) return '';
  const meta = draft.metadata || {};
  const steps = draft.kind === 'workflow' ? ensureStepKeys(draft.steps) : [];
  if (draft.kind === 'workflow') draft.steps = steps;
  const inputRows = array(meta.inputs).map((input, index) => `<div class="editor-row"><div class="form-grid">${field(`input-${index}-name`, '输入技术名称', input.name, 'text', true)}${field(`input-${index}-label`, '中文标签', input.label, 'text', true)}<label>类型<select id="cap-input-${index}-type" name="input-${index}-type">${['text', 'file', 'date', 'number'].map(type => `<option ${input.type === type ? 'selected' : ''}>${type}</option>`).join('')}</select></label><label class="check-label"><input id="cap-input-${index}-required" type="checkbox" name="input-${index}-required" ${input.required ? 'checked' : ''}>必填</label></div><button type="button" class="text-button" data-input-remove="${index}">移除此输入</button></div>`).join('');
  const stepRows = steps.map((step, index) => {
    const key = e(step.client_key);
    return `<div class="editor-row workflow-step-row" data-step-key="${key}"><div class="step-row-heading"><h3>步骤 ${index + 1}</h3><span class="mono small">${key}</span></div><div class="form-grid"><label for="cap-step-${key}-type">步骤类型<select id="cap-step-${key}-type" name="step-${index}-type">${stepTypes.map(type => `<option value="${type}" ${step.type === type ? 'selected' : ''}>${type}</option>`).join('')}</select></label><label for="cap-step-${key}-title">步骤名称<input id="cap-step-${key}-title" name="step-${index}-title" value="${e(step.title)}" required></label></div><label for="cap-step-${key}-instruction">步骤要求<textarea id="cap-step-${key}-instruction" name="step-${index}-instruction" rows="4" required>${e(step.instruction)}</textarea></label><label for="cap-step-${key}-skill">关联已启用 Skill<select id="cap-step-${key}-skill" name="step-${index}-skill"><option value="">不关联</option>${items.filter(item => item.kind === 'skill' && (item.enabled || item.id === step.skill_id)).map(item => `<option value="${e(item.id)}" ${item.id === step.skill_id ? 'selected' : ''}>${e(item.name)} · v${e(item.version)}${!item.enabled ? '（已停用）' : ''}</option>`).join('')}${step.skill_id && !items.some(item => item.id === step.skill_id) ? `<option value="${e(step.skill_id)}" selected>${e(step.skill_id)}（目录缺失，需处理）</option>` : ''}</select></label><div class="format-options">${toolChecks(tools, step.tools, `step-${index}-tools`)}</div><div class="button-row"><button type="button" class="button small" data-step-move="${index}" data-step-key="${key}" data-direction="-1" ${index === 0 ? 'disabled' : ''}>上移</button><button type="button" class="button small" data-step-move="${index}" data-step-key="${key}" data-direction="1" ${index === steps.length - 1 ? 'disabled' : ''}>下移</button><button type="button" class="text-button" data-step-remove="${index}" data-step-key="${key}">移除步骤</button></div></div>`;
  }).join('');
  const workflowEditor = draft.kind === 'workflow' ? `<section class="step-editor" aria-label="结构化 Workflow 步骤"><div class="section-heading"><div><h3>结构化步骤</h3><p class="muted small">步骤顺序是模板，不代表执行证据。每行使用稳定的编辑键，移动后输入焦点不会串行。</p></div><button type="button" class="button small" data-step-add>添加步骤</button></div>${stepRows}<p class="sr-only" aria-live="polite" id="workflow-step-announcer">当前 ${steps.length} 个步骤</p></section>` : '';
  const fileRows = array(draft.files).map((file, index) => `<div class="editor-row">${field(`file-${index}-path`, '包内相对路径', file.path, 'text', true)}${typeof file.content === 'string' ? textarea(`file-${index}-content`, '文件内容', file.content) : '<p class="muted">二进制资源；不渲染、不执行。需要替换请重新导入候选包。</p>'}${/^scripts\/.*\.py$/.test(file.path || '') ? `<p class="small">脚本 SHA256：${e(file.sha256 || '点击审查后计算当前内容')}</p><button type="button" class="button small" data-review-script="${index}">${file.sha256 && array(draft.reviewed_scripts).includes(file.sha256) ? '已确认审查此脚本' : '我已阅读，确认审查此脚本'}</button>` : ''}<button type="button" class="text-button" data-package-file-remove="${index}">移除此文件</button></div>`).join('');
  return `<section class="capability-editor" aria-label="能力草稿编辑器"><div class="section-heading"><h2>${id ? '编辑' : '新建'} ${draft.kind === 'workflow' ? 'Workflow' : 'Skill'} 草稿</h2><button type="button" class="button" data-cap-cancel-edit ${busy ? 'disabled' : ''}>返回详情</button></div><p class="notice warning">保存完整候选，不改变当前启用版本。导入问题需你明确修正；保存不等于发布，静态检查不执行包。</p><form id="cap-editor-form"><fieldset ${busy ? 'disabled' : ''}><div class="form-grid">${field('name', '中文名称', meta.name, 'text', true)}${field('slug', '技术名称 slug（须与 SKILL.md name 一致）', meta.slug, 'text', true)}${field('category', '分类', meta.category, 'text', true)}</div>${textarea('description', '中文简介', meta.description, true)}${textarea('scenarios', '适用场景（每行一项）', array(meta.scenarios).join('\n'), true)}<section><div class="section-heading"><h3>输入与文件要求</h3><button type="button" class="button small" data-input-add>添加输入</button></div>${inputRows}</section><h3>默认输出（发送时显式格式优先）</h3><div class="format-options">${['md', 'html', 'docx', 'xlsx', 'png'].map(format => `<label class="check-label"><input id="cap-default-${format}" type="checkbox" name="default_formats" value="${format}" ${array(meta.default_formats).includes(format) ? 'checked' : ''}>${format.toUpperCase()}</label>`).join('')}</div><h3>所需工具（不改变原生审批）</h3><div class="format-options">${toolChecks(tools, meta.required_tools, 'required_tools')}</div>${textarea('dependencies', '依赖（每行一项，不自动安装）', array(meta.dependencies).join('\n'))}${workflowEditor}${textarea('instructions', draft.kind === 'workflow' ? '补充指令（Workflow 可空，服务端按步骤编译）' : '完整 SKILL.md（含 YAML name / description）', draft.instructions, draft.kind !== 'workflow')}<section><div class="section-heading"><h3>候选文件（审查后保留原字节）</h3><button type="button" class="button small" data-package-file-add>添加文本文件</button></div>${fileRows}</section><button type="submit" class="button primary">${busy ? '保存中…' : '保存草稿'}</button></fieldset></form></section>`;
}

export function renderCreationForm(kind = 'skill', goal = '', busy = false) {
  return `<section class="capability-editor"><h2>对话创建 ${kind === 'workflow' ? 'Workflow' : 'Skill'}</h2><p class="muted">先创建专用会话并放入未发送的制作草稿。你确认发送后才开始调用模型，产物还须导入、检查和发布。</p><form id="cap-creation-form">${textarea('goal', '描述目标、输入和希望的交付', goal, true)}<div class="button-row"><button type="submit" class="button primary" ${busy ? 'disabled' : ''}>创建会话并准备草稿</button><button type="button" class="button" data-cap-cancel-edit ${busy ? 'disabled' : ''}>取消</button></div></form></section>`;
}

export function renderCopyForm(item, values = {}, busy = false) {
  return `<section class="capability-editor"><h2>复制 ${e(item?.name)}</h2><p class="muted">原包与内置版本保持不变；脚本在副本发布前需重新审查。</p><form id="cap-copy-form">${field('copy-name', '副本中文名称', values.name, 'text', true)}${field('copy-slug', '副本技术名称 slug', values.slug, 'text', true)}<div class="button-row"><button type="submit" class="button primary" ${busy ? 'disabled' : ''}>创建副本草稿</button><button type="button" class="button" data-cap-cancel-edit ${busy ? 'disabled' : ''}>取消</button></div></form></section>`;
}
