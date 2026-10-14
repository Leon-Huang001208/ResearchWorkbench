export const isNativeFramework = slug => slug === 'gold' || slug === 'dollar';
export function adaptFrameworkSnapshot(data) {
  const { framework, snapshot } = data || {};
  if (!isNativeFramework(framework?.slug) || typeof snapshot?.revision !== 'string' || !/^[a-f0-9]{64}$/.test(snapshot.revision) || !snapshot.research_state) throw new Error('框架快照合同不完整');
  // Presentation only: retain native scores, nulls, evidence and revision verbatim.
  return structuredClone({ framework, snapshot });
}
export function createEmbedBridge({ origin, logger = () => {} }) {
  let binding = null;
  let theme = 'light';
  return {
    bind(frame, data, token) {
      const payload = adaptFrameworkSnapshot(data);
      binding = { frame, payload, token, acknowledged: false };
      return binding;
    },
    clear() { binding = null; },
    setTheme(next) {
      if (!['light', 'dark'].includes(next)) return false;
      theme = next;
      if (binding && origin) binding.frame.contentWindow.postMessage({ channel: 'rwb-framework-v1', type: 'theme', slug: binding.payload.framework.slug, revision: binding.payload.snapshot.revision, token: binding.token, theme }, origin);
      return true;
    },
    ready(slug, revision) { return Boolean(binding?.acknowledged && binding.payload.framework.slug === slug && binding.payload.snapshot.revision === revision); },
    receive(event) {
      const b = binding; const m = event.data;
      if (!origin || !b || event.origin !== origin || event.source !== b.frame.contentWindow || m?.channel !== 'rwb-framework-v1' || m.slug !== b.payload.framework.slug) return false;
      if (m.type === 'ready') {
        b.frame.contentWindow.postMessage({ channel: m.channel, type: 'snapshot', slug: m.slug, revision: b.payload.snapshot.revision, token: b.token, payload: b.payload, theme }, origin);
        return false;
      }
      if (m.type !== 'ack' || m.revision !== b.payload.snapshot.revision || m.token !== b.token) return false;
      b.acknowledged = true; logger('framework_embed_ack', { slug: m.slug }); return true;
    },
  };
}
export function createFrameworkLoadGuard() {
  let sequence = 0;
  return { begin: () => ++sequence, current: token => token === sequence, invalidate: () => ++sequence };
}

export function createEmbedReceiver({ origin, parentWindow, slug, render, applyTheme, acknowledge, onError = () => {} }) {
  let displayed = null;
  return event => {
    const m = event.data;
    if (!origin || event.origin !== origin || event.source !== parentWindow || m?.channel !== 'rwb-framework-v1' || m.slug !== slug || typeof m.token !== 'string' || !m.token) return false;
    if (m.type === 'theme') {
      if (!displayed || displayed.revision !== m.revision || displayed.token !== m.token || !['light', 'dark'].includes(m.theme)) return false;
      applyTheme(m.theme); return true;
    }
    if (m.type !== 'snapshot' || m.revision !== m.payload?.snapshot?.revision || m.payload?.framework?.slug !== slug || !['light', 'dark'].includes(m.theme)) return false;
    try {
      const data = adaptFrameworkSnapshot(m.payload);
      render(data);
      applyTheme(m.theme);
      displayed = { revision: m.revision, token: m.token };
      acknowledge({ channel: m.channel, type: 'ack', slug, revision: m.revision, token: m.token });
      return true;
    } catch (error) { displayed = null; onError(error); return false; }
  };
}
