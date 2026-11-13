import { safeLog } from './core.mjs';

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
      target.textContent = 'AI 问答页面暂不可用，请检查安装后刷新。';
    }).finally(() => {
      if (element === target) pending = null;
    });
  }
  return { update };
}
