import { safeLog } from './core.mjs';
import { editableDraft, newDraft } from './capability-editor.mjs';

// Catalog mutations are explicit user actions. This controller never calls models or tools.
export function createCapabilityController({ api, onChange = () => {}, onCatalogChange = async () => {}, logger = safeLog } = {}) {
  const state = { kind: 'skill', source: 'all', category: '', query: '', detail: null, tool: null, versions: [], versionDetail: null, editor: null, editorId: '', form: '', goal: '', copy: {}, busy: false, error: '', success: '' };
  let generation = 0;
  const emit = () => onChange(state);
  async function run(operation) {
    if (state.busy) return null;
    state.busy = true; state.error = ''; state.success = ''; emit();
    try { return await operation(); }
    catch (error) { logger('capability_operation_failed'); state.error = `${error.code ? `[${error.code}] ` : ''}${error.message || '能力操作失败，请重试。'}`; return null; }
    finally { state.busy = false; emit(); }
  }
  function adopt(detail) {
    if (!detail?.id || !detail.draft) throw new Error('能力响应不含完整草稿，请刷新后重试。');
    state.detail = detail; state.kind = detail.kind; state.tool = null; state.versions = []; state.versionDetail = null; state.form = ''; state.editor = null; state.editorId = '';
  }
  return {
    state, run,
    open: (id) => run(async () => { const ticket = ++generation; const detail = await api.capability(id); if (ticket === generation) adopt(detail); return detail; }),
    close: () => { generation++; state.detail = null; state.tool = null; state.versions = []; state.versionDetail = null; state.form = ''; state.editor = null; state.error = ''; emit(); },
    edit: () => { if (state.detail?.builtin) return; state.editor = structuredClone(state.detail?.draft || newDraft(state.kind)); state.editorId = state.detail?.id || ''; state.form = 'editor'; emit(); },
    create: (form) => { state.detail = null; state.tool = null; state.editorId = ''; state.editor = form === 'manual' ? newDraft(state.kind) : null; state.form = form === 'manual' ? 'editor' : 'conversation'; state.error = ''; state.success = ''; emit(); },
    save: () => run(async () => {
      if (!state.editor) throw new Error('没有可保存的草稿');
      const payload = editableDraft(state.editor);
      const result = state.editorId ? await api.saveCapability(state.editorId, payload) : await api.createCapability(payload);
      adopt(result); state.success = '草稿已保存；未发布，当前启用版本不变。'; await onCatalogChange(); return result;
    }),
    copy: () => run(async () => {
      if (!state.detail?.id) throw new Error('请先打开能力详情');
      const result = await api.capabilityAction(state.detail.id, 'copy', state.copy);
      adopt(result); state.success = '已创建副本草稿，脚本需要重新审查。'; await onCatalogChange(); return result;
    }),
    import: (file) => run(async () => {
      if (!file || (file.name !== 'SKILL.md' && !/\.zip$/i.test(file.name))) throw new Error('请选择精确命名的 SKILL.md 或 ZIP 包。');
      const result = await api.importCapability(file); adopt(result);
      state.success = result.checks?.valid ? '候选包已导入，静态检查通过；仍需显式发布。' : '候选包已保留，检查未通过；请阅读问题并编辑，尚未发布。';
      await onCatalogChange(); return result;
    }),
    fromArtifact: (sessionId, fileId) => run(async () => {
      const result = await api.capabilityFromArtifact(sessionId, fileId); adopt(result); state.success = '实际产物已导入为待审查草稿，尚未发布。'; await onCatalogChange(); return result;
    }),
    action: (action, version) => run(async () => {
      const id = state.detail?.id;
      if (!id) throw new Error('请先打开能力详情');
      const result = await api.capabilityAction(id, action, action === 'rollback' ? { version } : {});
      if (action === 'check') { state.detail.checks = result; state.success = result.valid ? '静态检查通过；尚未发布。' : '检查未通过，问题和草稿已保留。'; }
      else { adopt(result); state.success = ({ publish: '新版本已发布并启用。', disable: '能力已停用。', enable: '当前版本已启用。', rollback: '已明确切回所选历史版本；旧版本未改写。' })[action] || ''; }
      await onCatalogChange(); return result;
    }),
    versions: () => run(async () => { const result = await api.capabilityVersions(state.detail.id); state.versions = result.items || []; return result; }),
    version: (version) => run(async () => { const result = await api.capabilityVersion(state.detail.id, version); state.versionDetail = result; return result; }),
  };
}
