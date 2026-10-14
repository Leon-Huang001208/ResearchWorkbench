import { createEmbedReceiver } from './embed-bridge.mjs';
import { renderEmbedDashboard } from './embed-dashboard.mjs';
const slug = document.body.dataset.framework;
const root = document.getElementById('core-root');
if (window.parent === window) {
  root.textContent = '请从 Research Workbench 框架页面打开。';
  window.location.replace(`${window.location.origin}/#/frameworks/${slug}`);
} else {
  window.addEventListener('message', createEmbedReceiver({
    origin: window.location.origin, parentWindow: window.parent, slug,
    render: data => { root.innerHTML = renderEmbedDashboard(data); },
    applyTheme: theme => { document.documentElement.dataset.theme = theme; document.documentElement.style.colorScheme = theme; },
    acknowledge: message => window.parent.postMessage(message, window.location.origin),
    onError: error => { root.textContent = '框架快照无法显示，请返回主页面刷新。'; console.error('framework_embed_render_failed', error.name); },
  }));
  window.parent.postMessage({ channel: 'rwb-framework-v1', type: 'ready', slug }, window.location.origin);
}
