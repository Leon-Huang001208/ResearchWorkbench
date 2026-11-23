// Each RWB entry completes native OIDC before displaying any cached workspace.
// Only native authentication state is removed; preferences and documents remain.
const keys = ['weknora_user', 'weknora_tenant', 'weknora_token', 'weknora_refresh_token',
  'weknora_knowledge_bases', 'weknora_current_kb', 'weknora_selected_tenant_id',
  'weknora_selected_tenant_name', 'weknora_memberships', 'weknora_lite_mode'];
try {
  for (const key of keys) localStorage.removeItem(key);
  location.replace('/api/v1/auth/oidc/start');
} catch {
  document.querySelector('[role="status"]').textContent = '浏览器未允许工作台存储，请允许后重新打开 FinGPT。';
}
