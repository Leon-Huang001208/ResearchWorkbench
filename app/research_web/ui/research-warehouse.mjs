import { escapeHTML as e } from './markdown.mjs';

export async function verifyWarehouseReads(api, parameters, {signal, pause = () => new Promise(resolve=>setTimeout(resolve,500))} = {}) {
  const asset = parameters.asset.toUpperCase();
  const start = new Date(parameters.start_date), end = new Date(parameters.end_date);
  if (!/^[0-9]{6}\.(SH|SZ)$/.test(asset) || !['akshare','baostock'].includes(parameters.source)
      || !Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())
      || start.toISOString().slice(0,10) !== parameters.start_date || end.toISOString().slice(0,10) !== parameters.end_date
      || end<start || end-start>13*86400000) throw Error('请选择沪深证券、免费来源和最多14天的完整日期区间。');
  const body = {asset,asset_type:'stock',source:parameters.source,sections:['history'],
    start_date:parameters.start_date,end_date:parameters.end_date,frequency:'daily',adjustment:'none'};
  async function read() {
    if (signal?.aborted) throw new DOMException('验证已停止等待','AbortError');
    let observation = await api.createAssetObservation(body,`warehouse-${crypto.randomUUID()}`,{signal});
    for (let count=0;observation.blocks?.history?.status === 'loading' && count<60;count++) {
      await pause();
      if (signal?.aborted) throw new DOMException('验证已停止等待','AbortError');
      observation = await api.assetObservation(observation.id,{signal});
    }
    const block = observation.blocks?.history;
    if (block?.status !== 'complete' || !block.dataset?.dataset_id || !(block.dataset.row_count>0))
      throw Error(`行情验证未完成：${block?.failure_code || block?.status || 'unknown'}；未自动重发。`);
    return api.datasetManifest(observation.session_id,block.dataset.dataset_id);
  }
  const first = await read();
  if (!first.provider_metadata?.warehouse_persisted && !first.provider_metadata?.warehouse_hit)
    throw Error('来源数据已取得，但没有持久化到研究仓；未执行第二次取数。');
  const second = await read();
  if (second.provider_metadata?.warehouse_hit !== true || second.row_count !== first.row_count)
    throw Error('第二次没有得到相同覆盖的数据库命中，不能标记验证成功。');
  return {source:second.provider || second.source,rows:second.row_count,
    initialCache:first.provider_metadata?.warehouse_hit === true,
    snapshot:second.provider_metadata.warehouse_snapshot_sha256};
}

export function warehousePanelHTML(status = {}, {busy = false, error = '', validation = null} = {}) {
  const configuration = status.configuration || {};
  const input = (name, label, fallback = '', type = 'text') => `<label><span>${label}</span><input name="${name}" type="${type}" value="${e(configuration[name] ?? fallback)}" required ${busy ? 'disabled' : ''}></label>`;
  const validationHTML = `${status.enabled ? `<form data-warehouse-validate class="automation-form-grid"><h3>有界免费验证</h3><p class="muted small">仅沪深股票原始日线，最多14天。建立两份验证输入，不调用模型；第二次必须命中研究仓。未证明的源、覆盖或版本不会记为成功。</p><label><span>证券代码</span><input name="asset" value="000001.SZ" required></label><label><span>免费来源</span><select name="source"><option value="akshare">AKShare（新浪 / 东方财富）</option><option value="baostock">BaoStock</option></select></label><label><span>开始日期</span><input name="start_date" type="date" value="2025-01-02" required></label><label><span>结束日期</span><input name="end_date" type="date" value="2025-01-03" required></label><button type="submit" class="button" ${busy ? 'disabled' : ''}>验证取数与数据库命中</button></form>` : ''}${validation ? `<p role="status" class="notice success">${e(validation.source)} · ${e(validation.rows)} 行 · 第二次数据库命中；首次${validation.initialCache ? '读取已有仓库数据，未验证当前上游' : '从实际来源取得'}。<br>冻结摘要 <code>${e(validation.snapshot)}</code></p>` : ''}`;
  return `<section class="settings-card" aria-label="研究数据仓库"><div class="section-heading"><div><span class="eyebrow">RESEARCH WAREHOUSE</span><h2>研究数据仓库</h2></div><span class="badge ${status.enabled ? 'live' : ''}">${status.enabled ? '已启用' : status.configured ? '已保存，未启用' : '未配置'}</span></div><p>按覆盖查询已存数据，再补内部缺口与最新范围。原件、修订和冻结版本分别保留，未证明的历史时点不会用今日下载代替。</p><p class="muted small">当前为个人仓。共享仓尚未接入；正式数据库与外盘迁移需另行确认。保存不会连接；初始化只允许独立的 rwb_market_* 数据库，现有 5432 端口受保护。</p>${error ? `<p role="alert" class="notice warning">${e(error)}</p>` : ''}<form data-warehouse-profile class="automation-form-grid">${input('host','数据库主机','127.0.0.1')}${input('port','端口',55432,'number')}${input('database','专用数据库名','rwb_market_research')}${input('username','数据库用户名','research')}<label><span>TLS</span><select name="sslmode" ${busy ? 'disabled' : ''}>${[['verify-full','校验证书与主机名'],['require','本机 TLS'],['disable','仅本机连接']].map(([value,label])=>`<option value="${value}" ${configuration.sslmode === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label><label><span>密码（仅存凭据后端）</span><input name="password" type="password" autocomplete="new-password" placeholder="${status.password_configured ? '已保存，留空保留' : '本机受信任 socket 可留空'}" ${busy ? 'disabled' : ''}></label><div class="button-row"><button type="submit" class="button" ${busy ? 'disabled' : ''}>保存配置，保持停用</button><button type="button" class="button" data-warehouse-action="refresh" ${busy ? 'disabled' : ''}>刷新状态</button></div></form>${status.configured ? `<form data-warehouse-initialize><p>初始化会在已存在的专用数据库中创建研究仓表，不创建数据库或服务，不迁移现有数据。</p><label><span>输入专用数据库名确认初始化</span><input name="database_confirmation" required autocomplete="off" placeholder="${e(configuration.database || '')}" ${busy ? 'disabled' : ''}></label><div class="button-row"><button type="submit" class="button primary" ${busy ? 'disabled' : ''}>初始化并启用研究仓</button><button type="button" class="button" data-warehouse-action="disable" ${busy || !status.enabled ? 'disabled' : ''}>停用后续入库</button></div></form>` : ''}<p class="muted small">${status.calendar_ready ? '交易日历已取得；历史时点仍按存档可得时间检查。' : '交易日历尚未取得；启用后仅按实际请求获取有界公开日历。'} 查询、数据覆盖与正式回测就绪分别验收。</p>${validationHTML}</section>`;
}

export function createWarehousePanel({api, logger = () => {}}) {
  const element = document.createElement('div');
  let status = {}, busy = false, error = '', disposed = false, validation = null;
  const lifetime = new AbortController();
  const render = () => { if (!disposed) element.innerHTML = warehousePanelHTML(status,{busy,error,validation}); };
  async function run(operation) {
    if (busy || disposed) return;
    busy = true; error = ''; render();
    try { const result = await operation(); if (!disposed) status = result; }
    catch (failure) { if (!disposed && failure.name !== 'AbortError') { error = failure.message || '研究仓操作失败'; logger('research_warehouse_ui_failed'); } }
    finally { busy = false; render(); }
  }
  element.addEventListener('submit', event => {
    if (!(event.target instanceof HTMLFormElement)) return;
    event.preventDefault();
    const values = new FormData(event.target);
    if (event.target.matches('[data-warehouse-validate]')) {
      const parameters = Object.fromEntries(['asset','source','start_date','end_date'].map(name=>[name,String(values.get(name) || '').trim()]));
      void run(async()=>{validation=await verifyWarehouseReads(api,parameters,{signal:lifetime.signal});return api.warehouseStatus({signal:lifetime.signal});});
    } else if (event.target.matches('[data-warehouse-profile]')) {
      validation = null;
      const configuration = Object.fromEntries(['host','database','username','sslmode'].map(name=>[name,String(values.get(name) || '').trim()]));
      configuration.port = Number(values.get('port'));
      const password = String(values.get('password') || '');
      if (password) configuration.password = password;
      const secretInput = event.target.elements.namedItem('password');
      if (secretInput) secretInput.value = '';
      void run(()=>api.warehouseControl({operation:'save',configuration},{signal:lifetime.signal}));
    } else if (event.target.matches('[data-warehouse-initialize]')) {
      void run(()=>api.warehouseControl({operation:'initialize',profile_id:status.profile_id,database_confirmation:String(values.get('database_confirmation') || '')},{signal:lifetime.signal}));
    }
  });
  element.addEventListener('click', event => {
    const action = event.target.closest('[data-warehouse-action]')?.dataset.warehouseAction;
    if (action === 'refresh') void run(()=>api.warehouseStatus({signal:lifetime.signal}));
    if (action === 'disable') void run(()=>api.warehouseControl({operation:'disable',profile_id:status.profile_id},{signal:lifetime.signal}));
  });
  render();
  void run(()=>api.warehouseStatus({signal:lifetime.signal}));
  return {element,dispose(){disposed=true;lifetime.abort();element.remove();}};
}
