import { escapeHTML as e } from './markdown.mjs';

const idPattern = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i;
export function renderHotPreparation(brief, disabled = '') {
  const materials = [...new Map((brief?.payload?.events || []).flatMap(event => event.reports || []).map(item => [item.materialId, item])).values()];
  if (!materials.length) return '';
  return `<form data-hot-form="research-prepare" data-hot-form-key="research-prepare:${e(brief.briefId)}:${e(brief.version)}"><h3>继续研究</h3><p class="small muted">从此冻结版本选择 1–20 份材料。准备会话不会提交研究问题。</p>${materials.map(item => `<label><input type="checkbox" name="materialIds" value="${e(item.materialId)}">${e(item.title)} · 版本 ${e(item.revision)}</label>`).join('')}<label>研究模式<select name="targetMode"><option value="fingpt">FinGPT</option><option value="claw">Claw</option></select></label><button class="button primary" ${disabled}>冻结所选资料并准备研究</button></form>`;
}
export function renderHotExecution(runId, disabled = '') {
  if (!idPattern.test(runId || '')) return '';
  return `<form data-hot-form="research-execute" data-hot-run="${e(runId)}" data-hot-form-key="research-execute:${e(runId)}"><h3>提交研究问题</h3><label>研究问题<textarea name="question" required maxlength="6000" rows="3"></textarea></label><p class="small muted">提交后沿现有研究流程执行，可能消耗已批准的模型额度；不会提高预算。报告先保存在站内。</p><button class="button primary" ${disabled}>开始研究（使用现有额度）</button></form>`;
}
export function hotResearchSubmission(kind, values, state, form, uuid) {
  if (kind === 'research-prepare') {
    const brief = state.brief;
    const allowed = new Set((brief?.payload?.events || []).flatMap(event => event.reports || []).map(item => item.materialId));
    const materialIds = values.getAll('materialIds').map(String), targetMode = String(values.get('targetMode'));
    if (!brief || !idPattern.test(brief.briefId) || !Number.isInteger(brief.version) || !materialIds.length || materialIds.length > 20 || new Set(materialIds).size !== materialIds.length || materialIds.some(id => !idPattern.test(id) || !allowed.has(id)) || !['fingpt','claw'].includes(targetMode)) throw Error('请选择当前冻结简报中的 1–20 份材料及研究模式。');
    return {method:'hotResearchPrepare',body:{runId:uuid(),briefId:brief.briefId,version:brief.version,materialIds,targetMode,requestId:uuid()}};
  }
  const runId = form.dataset.hotRun, question = String(values.get('question') || '').trim();
  const ready = state.researchDraft?.runId === runId ? state.researchDraft.state === 'snapshot_ready' : state.researchRows.some(row => row.runId === runId && row.stateVerified && row.runState === 'snapshot_ready');
  if (!idPattern.test(runId || '') || !ready || !question || question.length > 6000) throw Error('请先准备并核验资料，再填写研究问题。');
  return {method:'hotResearchExecute',body:{runId,question,formats:['md']}};
}
