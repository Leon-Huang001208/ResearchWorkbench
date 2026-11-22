import { isRunning, safeLog } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';

export function createQAMount({ document, load = () => import('./qa-dist/qa.js'), logger = safeLog }) {
  let element;
  let mounted;
  let pending;
  let latest;
  let stylesheet;
  function attachCSS() {
    if (stylesheet) return stylesheet;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = new URL('./qa-dist/qa.css', import.meta.url).href;
    stylesheet = new Promise((resolve, reject) => {
      link.onload = resolve;
      link.onerror = () => {
        stylesheet = null;
        link.remove();
        reject(new Error('qa_stylesheet_unavailable'));
      };
    });
    document.head.append(link);
    return stylesheet;
  }
  function update(placeholder, props) {
    if (!placeholder) {
      mounted?.dispose();
      element = mounted = pending = latest = null;
      return;
    }
    latest = props;
    if (element && element !== placeholder) placeholder.replaceWith(element);
    else element = placeholder;
    if (mounted) { mounted.render(latest); return; }
    if (pending) return;
    const target = element;
    pending = Promise.all([load(), attachCSS()]).then(([module]) => {
      if (element !== target) return;
      mounted = module.mountQA(target);
      mounted.render(latest);
    }).catch(() => {
      if (element !== target) return;
      logger('qa_frontend_load_failed');
      target.textContent = 'FinGPT页面暂不可用，请检查安装后刷新。';
    }).finally(() => {
      if (element === target) pending = null;
    });
  }
  return { update };
}

const emptyEvents = [];

export function renderQAPage({ state, contextExpanded, composer, renderResearchAttention }) {
  const detail = state.detail;
  const unavailable = state.route.sessionId && !detail && !state.loading;
  const toolbar = detail
    ? `<header class="session-toolbar"><button class="button small context-toggle" data-toggle-context aria-expanded="${contextExpanded}">活动与文件</button></header>${renderResearchAttention(detail)}`
    : '';
  return `<div data-qa-app role="region" aria-label="问答工作区"></div>${unavailable ? '<button class="button" data-reload-session>重新读取</button>' : ''}${toolbar}<div class="composer-dock">${composer()}</div>`;
}

export function paintQAPage({ root, mount, state, catalog, controller, document, render, loadCatalog }) {
  const placeholder = root.querySelector('[data-qa-app]');
  mount.update(placeholder, placeholder ? {
    sessionId: state.route.sessionId,
    events: state.detail?.qa_events || emptyEvents,
    mode: state.researchMode,
    model: state.detail?.model || catalog.runtime?.model || '',
    status: state.detail?.status || '',
    disabled: state.busy || state.stopping || state.loading || Boolean(state.detail?.scenario_context || state.detail?.execution_restricted || isRunning(state.detail?.status) || state.detail?.can_recheck_stop),
    loading: state.loading,
    streamError: state.streamError,
    onMode: mode => controller.setResearchMode(mode),
    onSuggest: question => {
      if (state.draft.trim()) {
        state.error = '输入区已有草稿，请先发送或清除。';
        render();
        return;
      }
      controller.setDraft(question);
      render();
      document.getElementById('prompt')?.focus();
    },
    onStop: async () => {
      await controller.cancel();
      await loadCatalog(['sessions']);
    },
  } : null);
}

export function renderQAHistory(route, sessions, historyFilter, enabled, renderHistory) {
  const mode = route.historyMode;
  const view = route.historyView || 'active';
  const modeLabel = mode === 'claw' ? 'Claw' : mode === 'fingpt' ? enabled ? 'FinGPT与专业协作' : 'FinGPT' : '';
  const modeQuery = mode ? `mode=${mode}` : '';
  const activeHref = `#/history${modeQuery ? `?${modeQuery}` : ''}`;
  const deletedHref = `#/history?${modeQuery ? `${modeQuery}&` : ''}view=deleted`;
  return `<header class="page-header"><div><div class="eyebrow">YOUR RESEARCH</div><h1>${modeLabel ? `${modeLabel} 研究历史` : '研究历史'}</h1><p class="muted">${view === 'deleted' ? '删除的会话保留 30 天，可恢复或立即永久删除。' : modeLabel ? `所有 ${modeLabel} 会话，随时回来继续。` : enabled ? '所有 FinGPT、专业协作与 Claw 会话。' : '所有 FinGPT 与 Claw 会话，随时回来继续。'}</p></div><button class="button" data-refresh>刷新</button></header><nav class="history-tabs" aria-label="研究历史视图"><a href="${activeHref}" class="${view === 'active' ? 'active' : ''}" ${view === 'active' ? 'aria-current="page"' : ''}>研究</a><a href="${deletedHref}" class="${view === 'deleted' ? 'active' : ''}" ${view === 'deleted' ? 'aria-current="page"' : ''}>已删除</a></nav><label class="search-box"><span aria-hidden="true">⌕</span><input id="history-search" type="search" placeholder="搜索会话标题…" value="${e(historyFilter)}" aria-label="搜索${modeLabel ? ` ${modeLabel}` : ''}研究历史"></label><div id="history-results">${renderHistory(sessions, historyFilter, mode, view)}</div>`;
}

export function qaSendBlockReason({ dossierDraftOpening, state, catalog }) {
  if (dossierDraftOpening) return '正在准备档案研究草稿，请等待冻结上下文就绪后发送。';
  if (state.detail?.execution_restricted) return '此历史会话执行受限；保留可读记录，请新建研究。';
  if (state.busy || state.stopping || state.loading || (state.route.sessionId && !state.detail)) return '操作尚未结束；草稿已保留，未发送。';
  if (state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || state.detail.can_recheck_stop || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status))) return '上一任务与交付尚未确认结束；草稿已保留，未发送。';
  if (catalog.pending.has('runtime') || catalog.runtime?.connected !== true || catalog.runtime.credential_configured === false) return '运行时未就绪，请检查连接与授权；草稿已保留。';
  return '';
}

export function qaRetryBlockReason({ dossierDraftOpening, state, catalog }) {
  const blocked = qaSendBlockReason({ dossierDraftOpening, state, catalog });
  if (blocked) return blocked;
  if (state.draft.trim() || state.attachments.length || state.tabbitTabs.length || state.skillId || state.capability || state.toolIds.length || state.methodIds.length || state.expectedFormats !== null) return '输入区已有未发送的草稿或选择；请先发送或清除后再重试历史问题，当前输入已保留。';
  return '';
}
