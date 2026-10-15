export function canUploadToSession(detail, sourceScope = ['datahub', 'web', 'uploads']) {
  if (detail?.execution_restricted) return false;
  const scope = detail?.execution_context
    ? detail.execution_context.definition_snapshot?.research_task?.approved_data_sources
    : detail?.source_scope ?? sourceScope;
  return Array.isArray(scope) && scope.includes('uploads');
}

// All file-picker, paste and drop paths share the same UI guard. Host validation
// remains authoritative; late results are attached only to their original draft.
export function createUploadHandler({ state, ensureSession, upload, accept, notify, logger = () => {} }) {
  let pending = false;
  return async files => {
    if (!files.length || pending || state.busy || state.loading) return;
    if (!canUploadToSession(state.detail, state.sourceScope)) {
      logger('upload_scope_rejected'); notify('当前会话未批准上传资料，请使用已批准的数据范围。'); return;
    }
    const originId = state.detail?.id;
    pending = true;
    try {
      if (!await ensureSession()) return;
      const id = state.detail?.id;
      if (!id || (originId && originId !== id) || !canUploadToSession(state.detail, state.sourceScope)) return;
      const result = await upload(id, files);
      if (Array.isArray(result?.items)) { accept(id, result.items); logger('upload_draft_attached'); }
    } catch {
      logger('upload_failed'); notify('上传失败，请检查文件及当前会话后重试。');
    } finally { pending = false; }
  };
}
