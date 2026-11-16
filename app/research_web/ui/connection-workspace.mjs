import { safeLog } from './core.mjs';

export function forgetConfigurationSecrets(value) {
  if (!value || typeof value !== 'object') return;
  for (const key of Object.keys(value)) {
    if (['password', 'token', 'api_key', 'cj_key'].includes(key)) delete value[key];
    else forgetConfigurationSecrets(value[key]);
  }
}

export function applyConnectionWorkspaceFilters(workbench) {
  if (!workbench) return;
  try {
    const query = String(workbench.querySelector('[data-connection-search]')?.value || '').trim().toLocaleLowerCase();
    const status = workbench.querySelector('[data-connection-status]')?.value || 'all';
    const group = workbench.dataset.activeGroup || 'professional';
    let visible = 0;
    workbench.querySelectorAll('[data-connection-card]').forEach((card) => {
      const matchesGroup = query ? true : card.dataset.connectionGroupName === group;
      const matchesStatus = status === 'all' || card.dataset.connectionStatusName === status;
      const matchesQuery = !query || String(card.dataset.connectionSearchText || '').includes(query);
      card.hidden = !(matchesGroup && matchesStatus && matchesQuery);
      if (!card.hidden) visible += 1;
    });
    const count = workbench.querySelector('[data-connection-result-count]');
    if (count) count.textContent = String(visible);
    const emptyState = workbench.querySelector('[data-connection-empty]');
    if (emptyState) emptyState.hidden = visible > 0;
    const searchScope = workbench.querySelector('[data-connection-search-scope]');
    if (searchScope) searchScope.hidden = !query;
    const grid = workbench.querySelector('#connection-source-grid');
    if (grid) grid.setAttribute('aria-labelledby', `connection-group-${group}`);
  } catch (error) {
    safeLog('connection_workspace_filter_failed', { status: error?.name || 'unknown' });
  }
}
