// Finite control vocabulary: every operation delegates to the upstream audited admin handler.
export function assertPublicConfiguration(value, depth=0) {
  if(depth>32)throw new Error('source_config_depth_invalid');
  if(value && typeof value==='object') {
    for(const [key,item] of Object.entries(value)) {
      const folded=key.toLowerCase().replace(/[_-]/g,'');
      if(['key','xkey','auth'].includes(folded)||['password','secret','token','apikey','authorization','cookie','accesskey','subscriptionkey'].some(word=>folded.includes(word)))throw new Error('source_credentials_require_private_store');
      assertPublicConfiguration(item,depth+1);
    }
  } else if(typeof value==='string' && /^https?:\/\//i.test(value)) {
    const url=new URL(value);
    if(url.username||url.password||[...url.searchParams.keys()].some(key=>/^key$|^auth$|token|secret|password|api.?key|access.?key/i.test(key)))throw new Error('source_credentials_require_private_store');
  }
}
export function assertFreePreview(input) {
  if (!['rss', 'web_list', 'json_list'].includes(input?.kind) || !input.config || typeof input.config !== 'object') throw new Error('paid_preview_forbidden');
  const target = input.kind === 'rss' ? input.config.feedUrl : input.config.url;
  const url = new URL(target);
  const host = url.hostname.toLowerCase().replace(/\.$/, '');
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || host === 'r.jina.ai' || host.endsWith('.jina.ai') || host === 'aihot.news' || host.endsWith('.aihot.news')) throw new Error('preview_destination_forbidden');
  return input;
}
export function controlRoute(action, input = {}) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('invalid_control_input');
  if(['source.create','source.update','source.preview'].includes(action))assertPublicConfiguration(action==='source.update'?input.patch?.config:input.config);
  const id = () => {
    if (typeof input.id !== 'string' || !/^[A-Za-z0-9_-]{1,120}$/.test(input.id)) throw new Error('invalid_id');
    return encodeURIComponent(input.id);
  };
  const query = () => new URLSearchParams(typeof input.query === 'object' && input.query !== null ? input.query : {}).toString();
  switch (action) {
    case 'source.list': return { method: 'GET', url: '/api/admin/sources?' + query() };
    case 'source.detail': return { method: 'GET', url: `/api/admin/sources/${id()}` };
    case 'source.preview': return { method: 'POST', url: '/api/admin/sources/preview', payload: assertFreePreview(input) };
    case 'source.create': return { method: 'POST', url: '/api/admin/sources', payload: input };
    case 'source.update': { const { id: _id, ...payload } = input; return { method: 'PATCH', url: `/api/admin/sources/${id()}`, payload }; }
    case 'content.list': return { method: 'GET', url: '/api/admin/content?' + query() };
    case 'content.detail': return { method: 'GET', url: `/api/admin/content/${id()}` };
    case 'content.visibility':
    case 'content.override': { const { id: _id, ...payload } = input; return { method: 'POST', url: `/api/admin/content/${id()}/${action.split('.')[1]}`, payload }; }
    case 'receipt.release': {
      if (!Number.isSafeInteger(input.id) || input.id < 1 || typeof input.billed !== 'boolean' || typeof input.note !== 'string' || !input.note.trim()) throw new Error('receipt_reconciliation_required');
      return {method:'POST',url:`/api/admin/receipts/${input.id}/release`,payload:{billed:input.billed,note:input.note}};
    }
    case 'processing.requeue': {
      if (!(input.group===null || typeof input.group==='string') || typeof input.reason!=='string' || !input.reason.trim()) throw new Error('recovery_reason_required');
      return {method:'POST',url:'/api/admin/processing/requeue',payload:input};
    }
    case 'budget.update': { const {service,...payload}=input; if(typeof service!=='string'||!/^[a-z0-9_-]{1,60}$/.test(service))throw new Error('invalid_service'); return {method:'PUT',url:'/api/admin/budgets/'+encodeURIComponent(service),payload}; }
    case 'model.update': { const {capability,...payload}=input;if(typeof capability!=='string'||!/^[A-Za-z0-9_-]{1,60}$/.test(capability))throw new Error('invalid_capability');return {method:'POST',url:'/api/admin/models/'+encodeURIComponent(capability),payload}; }
    case 'settings.contact-qr': return {method:'POST',url:'/api/admin/settings/contact-qr',payload:input};
    case 'runs': return { method: 'GET', url: '/api/admin/runs' };
    case 'settings': return { method: 'GET', url: '/api/admin/settings' };
    case 'models': return { method: 'GET', url: '/api/admin/models' };
    case 'audit': return { method: 'GET', url: '/api/admin/audit?' + query() };
    default: throw new Error('control_action_not_allowed');
  }
}
