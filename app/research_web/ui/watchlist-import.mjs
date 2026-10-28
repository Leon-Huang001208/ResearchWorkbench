import { createAPI, safeLog } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';

const LIMIT = 1024 * 1024;
const owner = () => String(globalThis.__RWB_USER_ID__ || 'single-user');
const fresh = () => ({ target: '', filename: '', sourceFile: null, file: null, selections: {}, skips: [], preview: null, dirty: true, busy: false, error: '', receipt: null, key: null, revision: 0 });
let draftOwner; let draft;
function accountDraft() {
  if (draftOwner !== owner()) { draftOwner = owner(); draft = fresh(); }
  return draft;
}
const messages = {
  watchlist_import_formula_rejected: '文件包含公式型字段。请去掉字段开头的 =、+、-、@，改为普通文本后重新选择文件。',
  watchlist_import_file_limit: '文件为空或超过 1 MiB，请选择较小的非空 CSV 文件。',
  watchlist_import_csv_invalid: 'CSV 编码或引号格式无效。请保存为 UTF-8，检查引号后重新选择文件。',
  watchlist_import_encoding_invalid: '文件传输编码无效，请重新选择文件并预览。',
  watchlist_import_file_hash_mismatch: '文件字节校验不一致，请重新选择原文件。',
  watchlist_import_header_invalid: '表头必须依次为 asset,asset_type,name，不能重复或增加列。',
  watchlist_import_columns_invalid: '每行必须恰好三列；含逗号的字段请使用双引号包裹。',
  watchlist_import_row_limit: '数据超过 1000 行，请拆分文件后重新选择。',
  watchlist_import_field_invalid: '字段不能超过 120 个字符，也不能含换行或控制字符。请修正后重新选择。',
  watchlist_import_empty: 'CSV 没有数据行，请加入股票记录后重新选择。',
  watchlist_import_selection_invalid: '行选择与真实候选不一致，请重新预览并逐行选择或跳过。',
  watchlist_import_preview_mismatch: '预览版本不一致，请重新冻结后确认。',
  watchlist_import_not_found: '当前账户找不到该列表或预览，请刷新列表后重新预览。',
  watchlist_import_unresolved: '仍有待处理行，请选择规范实体或明确跳过，再重新冻结。',
  watchlist_import_storage_invalid: '导入记录暂不可读取，请联系管理员核对服务；原自选保持。',
  watchlist_import_preview_corrupt: '预览内容校验失败，请重新冻结，不会使用已变化的预览。',
  watchlist_import_idempotency_conflict: '本次确认凭据已对应其他预览，请重新冻结后确认。',
  watchlist_import_target_changed: '自选列表已变化。保留了文件与选择，请重新冻结预览。',
  watchlist_import_catalog_changed: '本地目录已变化、过期或不可用。请核对目录后重新预览；导入不会自动取数。',
  watchlist_import_catalog_unauthorized: '当前账户没有可用目录授权。文件与选择已保留。',
  watchlist_import_preview_expired: '预览已过期或已被新选择替代，请重新冻结。',
  watchlist_import_preview_limit: '活动预览已达上限，请稍后重试。',
  watchlist_import_storage_limit: '导入记录空间已达上限，未修改自选列表。',
  watchlist_import_persist_failed: '保存失败，自选未追加。文件与预览已保留，可用同一确认键重试。',
};
const reason = row => ({ ready: '身份已核验', ambiguous: '多个同码或同名实体，需选择', needs_selection: '需明确选择规范实体', unsupported_identity_catalog: '该类型尚无规范目录', catalog_unavailable: '本地目录不可用', unresolved: '目录未找到', target_integrity_conflict: '旧列表身份冲突', skipped: '显式跳过' })[row.status] || '状态待核对';
const action = row => ({ add: '追加', skip_existing: '跳过：已在列表', skip_file_duplicate: '跳过：文件内重复', skip_explicit: '跳过：本人指定', blocked: '待处理' })[row.proposed_action] || '决定待核对';

export async function encodeWatchlistFile(file) {
  if (!file || file.size > LIMIT || file.size === 0) throw new Error('请选择非空 CSV 文件，最多 1 MiB。');
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (!bytes.length || bytes.length > LIMIT) throw new Error('CSV 文件超过 1 MiB。');
  const hash = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192) binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  return { file_base64: globalThis.btoa(binary), file_sha256: [...hash].map(b => b.toString(16).padStart(2, '0')).join('') };
}

export function createWatchlistImportController({ api, onChange = () => {}, onCommitted = () => {}, state = fresh(), account = owner, makeKey = () => globalThis.crypto.randomUUID() } = {}) {
  const scope = account();
  const notify = () => { if (scope === account()) onChange(state); };
  const current = revision => scope === account() && revision === state.revision;
  function invalidate() { state.revision++; state.dirty = true; state.key = null; state.receipt = null; state.error = ''; }
  function target(id) { if (state.busy) return; if (id !== state.target) { invalidate(); state.target = id; notify(); } }
  async function file(input) {
    if (state.busy) return;
    invalidate(); state.filename = input?.name || ''; state.sourceFile = input || null; state.file = null; state.preview = null; state.selections = {}; state.skips = []; state.busy = true;
    const revision = state.revision; notify();
    try { const encoded = await encodeWatchlistFile(input); if (current(revision)) state.file = encoded; }
    catch (error) { if (current(revision)) state.error = '无法读取所选文件，请重新选择非空、最多 1 MiB 的 CSV 文件。'; safeLog('watchlist_import_file_rejected', { status: 'invalid' }); }
    finally { if (current(revision)) { state.busy = false; notify(); } }
  }
  function choose(number, asset) { if (state.busy) return; invalidate(); state.selections[String(number)] = asset; notify(); }
  function skip(number, yes) { if (state.busy) return; invalidate(); state.skips = state.skips.filter(n => n !== number); if (yes) state.skips.push(number); notify(); }
  async function preview() {
    if (state.busy || !state.file || !state.target || scope !== account()) return;
    state.busy = true; state.error = ''; const revision = state.revision; notify();
    try {
      const result = await api.previewWatchlistImport(state.target, { schema_version: 1, ...state.file, selections: Object.fromEntries(Object.entries(state.selections).filter(([, asset]) => asset)), skipped_rows: [...state.skips] });
      if (!current(revision)) return;
      if (!result?.import_id || !result.preview_digest || !Array.isArray(result.rows)) throw new Error('导入预览响应不完整，请重新预览。');
      state.preview = result; state.dirty = false; state.key = makeKey(); state.receipt = null;
    } catch (error) { if (current(revision)) { state.dirty = true; state.error = messages[error.code] || (error.status === 403 ? '当前账户无权限，文件已保留。' : '暂时无法取得导入预览，文件与选择已保留。请核对服务后重试。'); } safeLog('watchlist_import_preview_failed', { status: error.code || 'request_failed' }); }
    finally { if (current(revision)) { state.busy = false; notify(); } }
  }
  async function confirm() {
    if (state.busy || state.dirty || !state.preview?.can_confirm || state.receipt || scope !== account()) return;
    const revision = state.revision, frozen = state.preview; state.busy = true; state.error = ''; notify();
    try {
      const receipt = await api.confirmWatchlistImport(state.target, frozen.import_id, { schema_version: 1, preview_digest: frozen.preview_digest, confirmed: true }, state.key);
      if (!current(revision)) return;
      state.receipt = receipt; onCommitted(receipt);
    } catch (error) {
      if (current(revision)) { state.error = messages[error.code] || (error.status === 403 ? '当前账户无权限，文件已保留。' : '确认结果尚未核实。文件已保留，请用原确认重试核对；不会自动追加。'); if (error.status === 409 || error.status === 403) state.dirty = true; }
      safeLog('watchlist_import_confirm_failed', { status: error.code || 'request_failed' });
    } finally { if (current(revision)) { state.busy = false; notify(); } }
  }
  return { state, target, file, choose, skip, preview, confirm };
}

export function renderWatchlistImportResults(state) {
  const p = state.preview;
  return `${state.error ? `<p class="notice warning" role="alert">${e(state.error)}</p>` : ''}${state.receipt ? `<p class="notice" role="status">${state.receipt.status === 'no_changes' ? '没有新增项' : `已追加 ${e(state.receipt.added_count)} 项`}，跳过 ${e(state.receipt.skipped_count)} 行。原自选已保留。</p>` : ''}${p ? `<p class="muted small" role="status">${state.dirty ? '选择已变化或预览已失效，请重新冻结。' : '已冻结预览；确认前会再次核对目录及原列表。'} 有效至 ${e(new Date(p.expires_at * 1000).toLocaleString())}。</p>${p.catalog_status !== 'ready' ? `<p class="notice warning">本地目录不可用（${e(p.catalog_status === 'stale' ? '缓存已过期' : '本地缓存缺失、损坏或当前无授权')}）；不能确认，导入不会自动刷新目录。</p>` : ''}<div class="asset-table-wrap" tabindex="0" aria-label="完整导入预览"><table class="asset-table"><thead><tr><th>数据行 / 文件行</th><th>原始代码 / 类型 / 名称</th><th>状态与决定</th><th>规范实体选择</th><th>显式跳过</th></tr></thead><tbody>${p.rows.map(row => `<tr><td>${e(row.row_number)} / ${e(row.line_number)}</td><td>${e(row.input.asset)}<br>${e(row.input.asset_type)}<br>${e(row.input.name)}</td><td>${e(reason(row))}<br>${e(action(row))}</td><td>${row.candidates.length ? `<select data-wi-choice="${e(row.row_number)}" aria-label="第${e(row.row_number)}行规范实体" ${state.busy ? 'disabled' : ''}><option value="">请选择</option>${row.candidates.map(c => `<option value="${e(c.asset)}" ${state.selections[String(row.row_number)] === c.asset || !Object.hasOwn(state.selections, String(row.row_number)) && row.selected === c.asset ? 'selected' : ''}>${e(c.asset)} · ${e(c.name)}</option>`).join('')}</select>${row.candidates_truncated ? `<small>共 ${e(row.candidate_count)} 个候选，仅展示前50个；可更正CSV为规范代码或跳过。</small>` : ''}` : '无可用规范候选'}</td><td><label><input type="checkbox" data-wi-skip="${e(row.row_number)}" ${state.skips.includes(row.row_number) ? 'checked' : ''} ${state.busy ? 'disabled' : ''}>跳过此行</label></td></tr>`).join('')}</tbody></table></div>` : '<p class="muted small">选择文件后预览全部行，处理歧义或明确跳过，再确认追加。</p>'}`;
}

// The existing asset renderer imports this element; no app.mjs entrypoint growth.
if (globalThis.customElements && globalThis.HTMLElement && !globalThis.customElements.get('rwb-watchlist-import')) {
  globalThis.customElements.define('rwb-watchlist-import', class extends HTMLElement {
    connectedCallback() {
      try {
        const lists = JSON.parse(this.getAttribute('data-lists') || '[]');
        const state = accountDraft();
        if (!lists.some(list => list.id === state.target)) { state.target = lists[0]?.id || ''; state.preview = null; state.dirty = true; state.key = null; }
        const previousFileInput = this.querySelector('[data-wi-file]');
        this.innerHTML = `<section class="watchlist-import"><h3>导入股票 CSV</h3><p class="muted small">仅本地已获准的沪深北股票目录；UTF-8 / BOM，最多1 MiB、1000行。固定表头：asset,asset_type,name。ETF、基金、指数、行业、主题逐行标为待支持。</p><label>目标自选<select data-wi-target>${lists.map(list => `<option value="${e(list.id)}">${e(list.name)}</option>`).join('')}</select></label><label>CSV 文件<input type="file" data-wi-file accept=".csv,text/csv"></label><p data-wi-filename class="muted small"></p>${!lists.length ? '<p class="notice warning">请先在上方创建自选列表。</p>' : ''}<div data-wi-results></div><div class="button-row"><button type="button" class="button small" data-wi-preview>冻结预览</button><button type="button" class="button small" data-wi-confirm>确认追加</button></div><p data-wi-loading role="status" aria-live="polite"></p></section>`;
        if (previousFileInput) this.querySelector('[data-wi-file]').replaceWith(previousFileInput);
        const draw = () => {
          if (!this.isConnected) return;
          const active = this.ownerDocument.activeElement;
          const focus = active?.hasAttribute?.('data-wi-choice') ? ['data-wi-choice', active.getAttribute('data-wi-choice')] : active?.hasAttribute?.('data-wi-skip') ? ['data-wi-skip', active.getAttribute('data-wi-skip')] : null;
          this.querySelector('[data-wi-results]').innerHTML = renderWatchlistImportResults(state);
          this.querySelector('[data-wi-target]').value = state.target;
          this.querySelector('[data-wi-target]').disabled = state.busy || !lists.length;
          const fileInput = this.querySelector('[data-wi-file]');
          fileInput.disabled = state.busy;
          if (state.sourceFile && fileInput.files?.[0] !== state.sourceFile) {
            try { const transfer = new DataTransfer(); transfer.items.add(state.sourceFile); fileInput.files = transfer.files; }
            catch { safeLog('watchlist_import_file_control_restore_failed', { status: 'unavailable' }); }
          }
          this.querySelector('[data-wi-filename]').textContent = state.filename ? `当前文件：${state.filename} · 文件与选择仅在当前页面账户内保留` : '尚未选择文件';
          this.querySelector('[data-wi-preview]').disabled = state.busy || !state.file || !state.target;
          this.querySelector('[data-wi-preview]').textContent = state.preview ? '重新冻结预览' : '冻结预览';
          this.querySelector('[data-wi-confirm]').disabled = state.busy || state.dirty || !state.preview?.can_confirm || Boolean(state.receipt);
          this.querySelector('[data-wi-loading]').textContent = state.busy ? '正在处理导入，请稍候…' : '';
          if (focus) this.querySelector(`[${focus[0]}="${focus[1]}"]`)?.focus({ preventScroll: true });
        };
        this.controller = createWatchlistImportController({ api: createAPI(), state, onChange: draw, onCommitted: receipt => this.ownerDocument.dispatchEvent(new CustomEvent('rwb-watchlist-import-committed', { detail: { receipt, account: owner() } })) });
        this.onChange = event => { const target = event.target; if (target.matches('[data-wi-file]')) void this.controller.file(target.files?.[0]); else if (target.matches('[data-wi-target]')) this.controller.target(target.value); else if (target.matches('[data-wi-choice]')) this.controller.choose(Number(target.dataset.wiChoice), target.value); else if (target.matches('[data-wi-skip]')) this.controller.skip(Number(target.dataset.wiSkip), target.checked); };
        this.onClick = event => { if (event.target.matches('[data-wi-preview]')) void this.controller.preview(); if (event.target.matches('[data-wi-confirm]')) void this.controller.confirm(); };
        this.addEventListener('change', this.onChange); this.addEventListener('click', this.onClick); draw();
      } catch (error) { this.textContent = '导入组件暂不可用，请刷新重试。'; safeLog('watchlist_import_mount_failed', { status: 'error' }); }
    }
    disconnectedCallback() { this.removeEventListener('change', this.onChange); this.removeEventListener('click', this.onClick); }
  });
}
