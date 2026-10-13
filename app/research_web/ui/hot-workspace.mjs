import { renderIntelligenceNavigation } from './intel.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { renderHotReaderFeed, renderHotReaderRank } from './hot-reader.mjs';

const score = (value) => typeof value === 'number' && Number.isFinite(value) ? String(value) : '—';
const names = { disabled: '尚未配置', stopped: '已停止', initialized: '运行中' };
export function hotURL(value) { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''; } catch { return ''; } }
export function hotTime(value, timezone = 'Asia/Shanghai') { if (!value) return '未知'; try { return new Intl.DateTimeFormat('zh-CN', { timeZone: timezone, dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)); } catch { return '未知'; } }
function metrics(judgment) { return `<dl class="hot-metrics">${[['相关性','relevance'],['研究重要性','importance'],['传播热度','heat'],['信息增量','informationIncrement']].map(([label,key]) => `<div><dt>${label}</dt><dd>${e(score(judgment?.[key]))}</dd></div>`).join('')}</dl>`; }
function reports(detail, timezone, selected = [], selectable = true) { return (detail?.reports || []).map(report => {
  const url = hotURL(report.url);
  return `<article class="hot-report"><h3>${url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(report.title)}</a>` : e(report.title)}</h3><p>${e(report.excerpt || '来源未提供摘要。')}</p><p class="muted small">${report.excerptIsPartial ? '显示部分摘要 · ' : ''}发布 ${e(hotTime(report.publishedAt, timezone))} · 取得 ${e(hotTime(report.acquiredAt, timezone))}</p><details><summary>版本与证据</summary><p class="small">材料 ${e(report.materialId)} · 版本 ${e(report.revision)} · ${e(report.state)}</p><code>${e(report.contentHash)}</code><p>${e((report.sources || []).map(source => source.operator).join('、'))}</p></details>${selectable ? `<label class="small"><input type="checkbox" name="materialIds" data-hot-material value="${e(report.materialId)}" ${selected.includes(report.materialId) ? 'checked' : ''} form="hot-correction"> 选择此材料用于拆分或重新归属</label>` : ''}</article>`;
}).join(''); }
function correction(detail, channels, disabled) {
  return `<details class="hot-correction"><summary>人工纠错</summary><form id="hot-correction" data-hot-form="correction" data-hot-form-key="correction:${e(detail.canonicalId)}:${e(detail.revision)}"><label>操作<select name="type"><option value="title">修改标题</option><option value="channels">修改频道</option><option value="merge">合并到已有事件</option><option value="split">拆出所选材料</option><option value="reassign">将所选材料重新归属</option></select></label><label>标题（修改或拆分时使用）<input name="title" maxlength="500" value="${e(detail.title)}"></label><label>目标事件 ID（合并／重新归属）<input name="target" placeholder="目标事件 UUID"></label><label>目标当前版本<input name="targetExpected" type="number" min="1"></label><label>频道（修改频道时使用）<select name="channelIds" multiple>${channels.map(channel => `<option value="${e(channel.channel_id)}" ${detail.manual?.channels?.includes(channel.channel_id) ? 'selected' : ''}>${e(channel.config.name)}</option>`).join('')}</select></label><label>修正理由<textarea name="reason" required maxlength="2000" rows="2"></textarea></label><p class="small muted">所选事件版本 ${e(detail.revision)}；拆分／重新归属请先选择材料，至少保留一份原材料。</p><button class="button primary" ${disabled}>保存修正</button></form></details>`;
}
export function renderHotBrief(brief) {
  if (!brief?.payload) return '';
  const p = brief.payload, timezone = p.timezone || 'Asia/Shanghai';
  const url = `/api/research/hot/briefs/${encodeURIComponent(brief.briefId)}/markdown?version=${brief.version}`;
  return `<aside class="hot-detail"><header><h2>冻结简报 · 版本 ${e(brief.version)}</h2><button class="button" data-hot-action="close-brief">关闭简报</button></header><p>截止 ${e(hotTime(p.cutoff, timezone))} · ${e(timezone)}</p><p>频道 ${e(p.channel.channel_id)} · 配置版本 ${e(p.channel.version)}</p><p>选材发布时间：${p.window.from ? e(hotTime(p.window.from, timezone)) : '未指定'} — ${p.window.to ? e(hotTime(p.window.to, timezone)) : '未指定'}</p><a class="button" href="${e(url)}" download>下载此版本 Markdown</a><a class="button" href="${e(url.replace('/markdown?', '/docx?'))}" download>下载此版本 DOCX</a><details><summary>内容校验与覆盖限制</summary><code>${e(brief.contentHash)}</code><ul>${p.limitations.map(value => `<li>${e(value)}</li>`).join('')}</ul></details>${p.events.map(event => `<article class="hot-card"><h3>事件摘要（归组结果）</h3><p>${e(event.title)}</p><p class="small">事件 ${e(event.canonicalId)} · 版本 ${e(event.revision)} · 发生 ${e(hotTime(event.occurredAt, timezone))} · 生效 ${e(hotTime(event.effectiveAt, timezone))}</p>${event.judgments.map(basis => `<section><h4>${e(({human:'人工判断',model:'模型推断',rule:'规则判断'})[basis.authority] || '判断')}</h4>${metrics(basis.judgment)}<p>${e(basis.judgment.reason)}</p><p class="small">原事件/频道版本 ${e(basis.event_revision)} / ${e(basis.channel_version)} · 应用版本 ${e(basis.applied_event_revision)} / ${e(basis.applied_channel_version)} · ${basis.inherited ? '继承判断' : '当前版本判断'}</p><ul>${(basis.ruleEvidence?.details?.coverage || []).map(source => `<li>${e(source.operator)} · ${source.enabled ? '启用' : '暂停'} · ${e(source.snapshot?.coverage || '无覆盖记录')} · ${e(source.snapshot?.parsedCount ?? '未知')} 条</li>`).join('')}</ul></section>`).join('')}<h4>来源摘录（发布者陈述）</h4>${reports(event, timezone, [], false)}</article>`).join('')}</aside>`;
}
export function renderHotResults(rows, loading = false, hasMore = false, disabled = '') {
  const states = {prepared:'交接已准备',session_creating:'会话准备中',session_ready:'会话已准备',snapshot_ready:'资料已冻结',execution_starting:'正在提交',execution_outcome_unknown:'提交结果未知',running:'运行中',completed:'运行完成',failed:'运行失败',abandoned:'已终止',unavailable:'运行状态暂不可核验'};
  const deliveries = {completed:'报告已生成并校验',available:'已有报告文件',not_generated:'尚未生成报告',unavailable:'报告暂不可读取'};
  return `<div class="hot-source-grid">${rows.map(row => {
    const sid = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(row.sessionId || '') ? row.sessionId : '';
    const mode = row.targetMode === 'claw' ? 'claw' : 'fingpt';
    return `<article class="hot-card"><h2>${e(row.title)}</h2><p><strong>${e(states[row.runState] || '状态未知')}</strong> · ${e(deliveries[row.deliveryState] || '交付状态未知')}</p>${row.runState === 'failed' && row.artifacts?.length ? '<p class="notice">运行失败不会删除已经生成的报告；请结合来源与覆盖限制阅读。</p>' : ''}${!row.stateVerified ? '<p class="muted small">Hot状态暂不可核验，保留本会话已保存的报告。</p>' : ''}${row.errorCode ? `<p>${e(/budget/.test(row.errorCode) ? '达到模型预算上限，后续请求已停止。' : '执行未完整结束，请查看研究会话。')}</p>` : ''}<p class="small muted">运行 ${e(row.runId)} · 更新 ${e(hotTime(typeof row.updatedAt === 'number' ? row.updatedAt * 1000 : row.updatedAt))}</p>${(row.artifacts || []).map(file => {
      const expected = `/api/research/sessions/${sid}/files/${file.id}/download`;
      const safe = sid && /^[a-f0-9]{24}$/.test(file.id || '') && file.url === expected;
      return `<p>${safe ? `<a class="button" href="${e(expected)}" download>下载 ${e(file.name)}</a>` : e(file.name)} <span class="small muted">${file.changed ? '文件已变化，旧校验不再适用' : file.verified ? '本次交付已校验' : '附加文件'}</span></p>`;
    }).join('')}${row.artifacts?.some(file=>file.verified&&file.format==='md')&&/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(row.runId)?`<a class="button" href="/api/research/hot/research/runs/${e(row.runId)}/docx" download>下载 Word 报告</a>`:''}${sid ? `<a class="button" href="#/${mode}?session=${e(sid)}">查看研究会话</a>` : ''}<button class="button" data-hot-action="refresh-run" data-run="${e(row.runId)}" ${disabled}>核对运行状态</button><details><summary>冻结证据与文件校验</summary><code>${e(row.manifestHash)}</code>${(row.artifacts || []).map(file => `<p>${e(file.name)} · ${e(file.sha256)}</p>`).join('')}</details></article>`;
  }).join('') || (loading ? '<p>研究与报告读取中…</p>' : '<p>暂无已保存的Hot研究。冻结简报后可继续研究。</p>')}</div>${hasMore ? `<button class="button" data-hot-action="more-research" ${loading ? 'disabled' : ''}>下一页研究</button>` : ''}`;
}
export function renderHotWorkspace(state, { settings = false } = {}) {
  const disabled = state.busy || state.pending ? 'disabled' : '', timezone = state.config?.timezone || 'Asia/Shanghai';
  const status = names[state.status?.state] || '暂时不可用';
  const top = `<div class="hot-status"><span>${e(state.view === 'research' ? '已保存研究与报告' : status)}</span><span class="muted">显示时区：${e(timezone)}</span>${state.status?.model === 'blocked_model' ? '<span class="muted">模型未就绪，保留待处理资料</span>' : ''}<button class="button" type="button" data-hot-action="refresh" ${state.loading ? 'disabled' : ''}>刷新读取</button></div>`;
  const notice = `${state.error ? `<div class="notice error" role="alert">${e(state.error)}</div>` : ''}${state.message ? `<div class="notice" role="status">${e(state.message)}</div>` : ''}${state.pending ? `<div class="notice" role="status"><strong>操作结果尚不确定</strong><p>请求 ${e(state.pending.body.requestId)} 已保留。重试使用完全相同参数。</p><button class="button" data-hot-action="retry" ${state.busy ? 'disabled' : ''}>核对并重试原请求</button></div>` : ''}`;
  if (settings) return `<div data-hot-workspace>${top}${notice}<form data-hot-form="configuration" data-hot-form-key="configuration"><label>Hot 非秘密配置<textarea name="configuration" rows="20" spellcheck="false" aria-label="Hot 非秘密配置">${e(JSON.stringify(state.config || {}, null, 2))}</textarea></label><p class="muted small">仅保存配置，运行参数在重启后生效。密码由系统凭据库管理，不填入此处。</p><button class="button primary" ${disabled}>保存配置</button></form><div class="hot-lifecycle">${['start','stop','restart'].map((action,index) => `<button class="button" data-hot-action="${action}" ${disabled}>${['启动','停止','重启'][index]}</button>`).join('')}<a href="#/intel/hot">查看事件</a></div><p class="muted small">首次依赖和数据库准备仍通过 rwb hot setup 完成；不会由页面刷新自动安装。</p></div>`;
  const header = `<header class="page-header"><div><p class="eyebrow">RESEARCH INTELLIGENCE</p><h1>研究情报</h1><p class="muted">本地热点与事件 · 共享事实与原文，按研究方向判断重要性。</p></div><a class="button" href="#/settings/hot">运行配置</a></header>${renderIntelligenceNavigation('hot')}`;
  const tabs = `<nav class="hot-tabs" aria-label="热点视图">${[['events','事件'],['sources','来源覆盖'],['channels','频道配置'],['briefs','简报'],['research','研究与报告']].map(([view,label]) => `<a href="#/intel/hot?view=${view}" ${state.view === view ? 'aria-current="page" class="active"' : ''}>${label}</a>`).join('')}</nav>`;
  let body = '';
  if (state.view === 'research') body = renderHotResults(state.researchRows || [], state.loading, state.researchHasMore, state.loading ? 'disabled' : disabled);
  else if (state.view === 'sources') body = `<div class="hot-source-grid">${state.sources.map(source => `<article class="hot-card"><h2>${e(source.operator)}</h2><p>${source.enabled ? '采集中' : '已暂停'} · ${e(source.latest_snapshot?.coverage === 'latest_snapshot' ? '最新快照' : source.latest_snapshot?.coverage || '尚无取得记录')}</p><dl><dt>最近成功</dt><dd>${e(hotTime(source.last_success_at, timezone))}</dd><dt>待解析条目</dt><dd>${e(source.pending_items)}</dd><dt>已知缺口／错误</dt><dd>${e(source.last_error_code || source.latest_snapshot?.gap?.code || '未记录；不等于完整覆盖')}</dd></dl><p class="small muted">覆盖发布区间 ${e(hotTime(source.latest_snapshot?.oldestPublishedAt, timezone))} — ${e(hotTime(source.latest_snapshot?.newestPublishedAt, timezone))}</p><button class="button" data-hot-action="source-toggle" data-source="${e(source.id)}" ${disabled}>${source.enabled ? '暂停' : '恢复'}此来源</button></article>`).join('') || '<p class="muted">暂无来源状态。</p>'}</div>`;
  else if (state.view === 'briefs') body = `<div class="hot-source-grid">${state.briefs.map(brief => `<article class="hot-card"><h2>${e(brief.channelId)} · 简报版本 ${e(brief.version)}</h2><p>选材截止 ${e(hotTime(brief.cutoff, timezone))}</p><button class="button" data-hot-action="open-brief" data-brief="${e(brief.briefId)}" data-version="${e(brief.version)}">查看冻结简报</button></article>`).join('') || (state.loading ? '<p>简报读取中…</p>' : '<p>暂无已保存简报。打开事件详情可显式生成。</p>')}</div>${state.briefHasMore ? '<button class="button" data-hot-action="more-briefs">下一页简报</button>' : ''}`;
  else if (state.view === 'channels') body = `<div class="hot-source-grid">${state.channels.map(channel => `<article class="hot-card"><h2>${e(channel.config.name)}</h2><p>版本 ${e(channel.version)} · ${e(channel.channel_id)}</p><p>${e(channel.config.topics.join('、'))}</p><button class="button" data-hot-action="edit-channel" data-channel="${e(channel.channel_id)}" ${disabled}>编辑频道</button></article>`).join('')}</div><form data-hot-form="channel" data-hot-form-key="channel:${e(state.editChannel)}:${e(state.editVersion)}"><h2>${state.editChannel ? '修改频道' : '新增频道'}</h2><label>频道 ID<input name="channelId" required pattern="[a-z][a-z0-9_-]{0,47}" value="${e(state.editChannel || '')}" ${state.editChannel ? 'readonly' : ''}></label><label>版本化配置<textarea name="config" rows="12" spellcheck="false">${e(JSON.stringify(state.channelDraft || { name:'新频道', topics:[], sourceIds:[], importanceRules:[], rules:[] }, null, 2))}</textarea></label><p class="small muted">名称、主题、来源和规则权重通过配置保存，来源须已登记。</p><button class="button primary" ${disabled}>保存频道</button><button type="button" class="button" data-hot-action="new-channel" ${disabled}>新建另一频道</button></form>`;
  else {
    const filters = state.filters;
    const form = `<form class="hot-filters" data-hot-form="filters" data-hot-form-key="filters"><label>频道<select name="channelId"><option value="">全部事件</option>${state.channels.map(channel => `<option value="${e(channel.channel_id)}" ${filters.channelId === channel.channel_id ? 'selected' : ''}>${e(channel.config.name)}</option>`).join('')}</select></label><label>排序<select name="sort">${[['recent','最近更新'],['importance','研究重要性'],['heat','传播热度'],['increment','信息增量'],['relevance','相关性']].map(([value,label]) => `<option value="${value}" ${filters.sort === value ? 'selected' : ''}>${label}</option>`).join('')}</select></label>${[['q','关键词'],['topic','主题'],['institution','机构'],['asset','资产']].map(([key,label]) => `<label>${label}<input name="${key}" maxlength="200" value="${e(filters[key] || '')}"></label>`).join('')}<label>发布时间起点（含时区）<input name="from" placeholder="2026-10-08T00:00:00+08:00" value="${e(filters.from || '')}"></label><label>终点（含时区）<input name="to" placeholder="可留空" value="${e(filters.to || '')}"></label><button class="button primary" ${state.loading ? 'disabled' : ''}>筛选</button></form>`;
    const cards = renderHotReaderFeed(state.events,timezone,{loading:state.loading,blocked:state.status?.model==='blocked_model',sort:filters.sort});
    const readerDisabled=state.loading||state.busy||state.pending?'disabled':'';
    const readerControls=`<div class="hot-reader-toolbar"><nav class="hot-reader-modes" aria-label="事件阅读顺序">${[['recent','全部事件'],['importance','频道重点'],['heat','传播热点']].map(([sort,label])=>`<button type="button" data-hot-action="feed-sort" data-sort="${sort}" aria-pressed="${filters.sort===sort}" ${readerDisabled||(!filters.channelId&&sort!=='recent'?'disabled title="先选择研究频道"':'')}>${label}</button>`).join('')}</nav><nav class="hot-reader-channels" aria-label="研究频道">${[{channel_id:'',config:{name:'全部频道'}},...state.channels].map(channel=>`<button type="button" data-hot-action="feed-channel" data-channel="${e(channel.channel_id)}" aria-pressed="${filters.channelId===channel.channel_id}" ${readerDisabled}>${e(channel.config.name)}</button>`).join('')}</nav></div>`;
    const detail = state.detail ? `<aside class="hot-detail"><header><h2>${e(state.detail.title)}</h2><button class="button" data-hot-action="close-detail">关闭详情</button></header><p class="small muted">观察截止 ${e(hotTime(state.detail.cutoff, timezone))} · 事件版本 ${e(state.detail.revision)}</p>${state.detail.requestedId !== state.detail.canonicalId ? '<p class="notice">旧事件 ID 已解析为合并后的当前事件。</p>' : ''}<p>发生时间 ${e(hotTime(state.detail.occurredAt, timezone))} · 生效时间 ${e(hotTime(state.detail.effectiveAt, timezone))}</p>${state.detail.judgments.map(j => `<section><h3>${e(state.channels.find(c => c.channel_id === j.channelId)?.config.name || j.channelId)}</h3>${metrics(j.judgment)}<p>${e(j.judgment.reason)}</p>${j.inherited ? '<p class="small muted">继承既有人工判断，保留原始版本。</p>' : ''}<details><summary>判断依据与限制</summary><ul>${j.judgment.limitations.map(value => `<li>${e(value)}</li>`).join('')}</ul></details></section>`).join('')}<h3>来源报道</h3>${reports(state.detail, timezone, state.selectedMaterialIds)}${state.detail.reportOffset + state.detail.reports.length < state.detail.materialCount ? '<button class="button" data-hot-action="more-reports">下一页材料</button>' : ''}<h3>历史进展</h3><ol>${state.detail.history.map(item => `<li>版本 ${e(item.revision)} · ${e(hotTime(item.created_at, timezone))} · ${e(item.title)}</li>`).join('')}</ol>${state.detail.links.map(link => `<p><button class="button" data-hot-action="detail" data-event="${e(link.id)}">${e(({direct_followup:'直接前序',related:'相关事件',pending_review:'待复核关系'})[link.relation] || link.relation)}</button></p>`).join('')}<form data-hot-form="brief" data-hot-form-key="brief:${e(state.detail.canonicalId)}:${e(state.detail.revision)}"><label>简报频道<select name="channelId" required>${state.channels.map(c => `<option value="${e(c.channel_id)}" ${c.channel_id === state.filters.channelId ? 'selected' : ''}>${e(c.config.name)}</option>`).join('')}</select></label><p class="small muted">冻结此事件在详情截止时点的全部材料和频道判断，不调用模型。</p><button class="button primary" ${disabled}>生成此事件简报</button></form>${correction(state.detail, state.channels, disabled)}</aside>` : '';
    body = `${readerControls}${renderHotReaderRank(state.events,{loading:state.loading})}<details class="hot-reader-filter-panel"><summary>搜索、机构、资产与时间筛选</summary>${form}</details><p class="small muted">筛选为原文与事件的文字匹配；未知发布时间不进入日期窗口。截止 ${e(hotTime(state.cutoff, timezone))}。</p><div class="hot-layout"><div>${cards}${state.hasMore ? '<button class="button" data-hot-action="more">下一页事件</button>' : ''}</div>${detail}</div>`;
  }
  return `<section class="hot-reader" data-hot-workspace aria-busy="${state.loading ? 'true' : 'false'}">${header}${top}${notice}${tabs}${body}${renderHotBrief(state.brief)}</section>`;
}

export function createHotController({ api, onChange = () => {}, isActive = () => true, uuid = () => crypto.randomUUID() }) {
  const state = { view:'events', status:null, config:null, channels:[], sources:[], events:[], detail:null, filters:{sort:'recent'}, cutoff:'', offset:0, hasMore:false, loading:false, busy:false, error:'', message:'', pending:null, editChannel:'', editVersion:0, channelDraft:null, selectedMaterialIds:[], selectionKey:'', briefs:[], brief:null, briefCutoff:'', briefOffset:0, briefHasMore:false, researchRows:[], researchOffset:0, researchHasMore:false };
  let generation = 0, detailGeneration = 0, briefGeneration = 0, lastRoute = {page:'workbench',section:'hot'};
  const current = (ticket) => ticket === generation && isActive();
  async function loadEvents(ticket, append = false) {
    const data = await api.hotEvents({ ...state.filters, cutoff: append ? state.cutoff : undefined, offset: append ? state.offset + 20 : 0, limit:20 });
    if (!current(ticket)) return;
    state.events = append ? [...state.events, ...data.items] : data.items; state.cutoff = data.cutoff; state.offset = data.offset; state.hasMore = data.hasMore;
  }
  async function reloadEvents(filters) {
    const ticket=++generation;detailGeneration++;
    state.filters=filters;state.events=[];state.cutoff='';state.offset=0;state.hasMore=false;
    state.detail=null;state.loading=true;state.error='';onChange();
    safeLog('hot_reader_filter_requested');
    try {await loadEvents(ticket);}
    catch(error) {safeLog('hot_reader_filter_failed');if(current(ticket))state.error=error.message||'事件读取失败。';}
    finally {if(current(ticket)){state.loading=false;onChange();}}
  }
  async function loadBriefs(ticket, append = false) {
    const data = await api.hotBriefs({limit:20,offset:append ? state.briefOffset + 20 : 0,cutoff:append ? state.briefCutoff : undefined});
    if (!current(ticket)) return;
    state.briefs = append ? [...state.briefs,...data.items] : data.items;
    state.briefCutoff = data.cutoff; state.briefOffset = data.offset; state.briefHasMore = data.hasMore;
  }
  async function openBrief(id, version, ticket = generation) {
    const selection = ++briefGeneration, data = await api.hotBrief(id,{version});
    if (current(ticket) && selection === briefGeneration) {state.brief = data;onChange();}
  }
  async function activate(route) {
    lastRoute = route; detailGeneration++; briefGeneration++; state.brief = null; const ticket = ++generation; state.view = route.page === 'settings' ? 'configuration' : route.hotView || 'events'; state.loading = true; state.error = ''; state.detail = null; onChange();
    try {
      if (state.view === 'research') { const data=await api.hotResearchResults({limit:10,offset:0}); if(current(ticket)){state.researchRows=data.items;state.researchOffset=0;state.researchHasMore=data.hasMore;} return; }
      const [status, configuration] = await Promise.all([api.hotStatus(), api.hotConfiguration()]);
      if (!current(ticket)) return;
      state.status = status; state.config = configuration.config;
      if (state.view !== 'configuration' && status.state === 'initialized') {
        const channels = await api.hotChannels(); if (!current(ticket)) return; state.channels = channels.items;
        if (state.view === 'briefs') { await loadBriefs(ticket); }
        else if (state.view === 'sources') { const sources = await api.hotSources(); if (current(ticket)) state.sources = sources.items; }
        else if (state.view === 'events') { await loadEvents(ticket); if (route.hotEventId) await selectDetail(route.hotEventId, ticket); }
      } else { state.channels = []; state.sources = []; state.events = []; state.briefs = []; state.cutoff = ''; state.hasMore = false; }
    } catch (error) { safeLog('hot_read_failed'); if (current(ticket)) state.error = error.message || '热点读取失败。'; }
    finally { if (current(ticket)) { state.loading = false; onChange(); } }
  }
  async function selectDetail(id, ticket = generation, offset = 0, cutoff = state.cutoff) {
    const detailTicket = ++detailGeneration;
    const data = await api.hotEvent(id, { cutoff:cutoff || undefined, reportOffset:offset, reportLimit:20 });
    if (current(ticket) && detailTicket === detailGeneration) { const key=data.canonicalId+':'+data.revision; if(state.selectionKey!==key){state.selectedMaterialIds=[];state.selectionKey=key;} state.detail = data; onChange(); }
  }
  async function sendPending() {
    if (!state.pending || state.busy) return;
    state.busy = true; state.error = ''; onChange();
    const pending = state.pending, ticket = generation, previewTicket = briefGeneration;
    try {
      const result = await api[pending.method](pending.body);
      if (result.state === 'outcome_unknown' || result.requestId !== pending.body.requestId) { state.message = '服务未能确认此次修改，原请求已保留。'; return; }
      state.pending = null; state.message = pending.method === 'hotBriefCreate' ? '简报已保存，网页与下载使用同一冻结版本。' : '修改已保存，请刷新读取最新版本。'; if(current(ticket)) state.detail = null;
      if (pending.method === 'hotBriefCreate' && current(ticket) && previewTicket === briefGeneration) { try { await openBrief(result.briefId,result.version,ticket); } catch {safeLog('hot_brief_read_failed');state.error = '简报已保存，详情暂不可用；可从简报列表重读。';} }
    } catch (error) {
      safeLog('hot_mutation_failed');
      state.error = error.message || '修改结果未知。';
      if (/(?:conflict|invalid|required|denied|limit)$/.test(error.code || '') || ['hot_event_unknown','hot_channel_unknown','hot_channel_source_unknown','hot_service_stopped'].includes(error.code)) state.pending = null;
    } finally { state.busy = false; if (isActive()) onChange(); }
  }
  async function submit(form) {
    const values = new FormData(form), kind = form.dataset.hotForm;
    if (kind === 'filters') { const filters=Object.fromEntries(['channelId','sort','q','topic','institution','asset','from','to'].map(key=>[key,String(values.get(key)||'').trim()]));if(!filters.channelId)filters.sort='recent';return await reloadEvents(filters); }
    if (state.pending || state.busy) return;
    try {
      if (kind === 'configuration') { state.busy = true; onChange(); await api.hotConfigure(JSON.parse(String(values.get('configuration')))); state.message = '配置已保存，重启后生效。'; state.busy = false; onChange(); return; }
      let method, body;
      if (kind === 'brief' && state.detail) { method = 'hotBriefCreate'; body = {briefId:uuid(),expectedVersion:0,eventIds:[state.detail.canonicalId],channelId:String(values.get('channelId')),cutoff:state.detail.cutoff,timezone:state.config?.timezone || 'Asia/Shanghai',...(state.filters.from ? {from:state.filters.from} : {}),...(state.filters.to ? {to:state.filters.to} : {}),requestId:uuid()}; }
      else if (kind === 'channel') { const channelId = String(values.get('channelId')); method = 'hotChannelConfigure'; body = { channelId, expectedVersion:state.editChannel === channelId ? state.editVersion : 0, config:JSON.parse(String(values.get('config'))), requestId:uuid() }; }
      else if (kind === 'correction' && state.detail) {
        const type = String(values.get('type')), change = { type, id:state.detail.canonicalId, expected:state.detail.revision };
        if (['title','split'].includes(type)) change.title = String(values.get('title'));
        if (['merge','reassign'].includes(type)) { change.target = String(values.get('target')).trim(); change.targetExpected = Number(values.get('targetExpected')); }
        if (['split','reassign'].includes(type)) change.materialIds = [...state.selectedMaterialIds];
        if (type === 'channels') change.channelIds = values.getAll('channelIds').map(String);
        method = 'hotCorrect'; body = { change, reason:String(values.get('reason')), requestId:uuid() };
      } else return;
      state.pending = {method,body}; await sendPending();
    } catch { safeLog('hot_input_rejected'); state.busy = false; state.error = '输入格式错误，请核对 JSON 和必要字段。'; if (isActive()) onChange(); }
  }
  async function action(button) {
    const action = button.dataset.hotAction;
    try {
      if (action === 'refresh-run') {
        if(state.busy||state.pending||state.loading)return;
        const ticket=generation;state.busy=true;let refreshed=false;onChange();
        try{const result=await api.hotResearchRefresh(button.dataset.run);refreshed=true;if(current(ticket))state.message=result.state==='outcome_unknown'||result.observation==='unknown'?'核对结果仍未知，未重新启动研究。':'运行状态已核对；未启动新研究。';}
        catch(error){safeLog('hot_result_refresh_failed');if(current(ticket))state.error=error.message||'运行核对失败。';}
        finally{state.busy=false;if(isActive())onChange();}
        if(refreshed&&current(ticket))await activate(lastRoute);return;
      }
      if (action === 'more-research') {
        if(state.loading||!state.researchHasMore)return;
        const ticket=generation;state.loading=true;onChange();
        try{const data=await api.hotResearchResults({limit:10,offset:state.researchOffset+10});if(current(ticket)){state.researchRows.push(...data.items);state.researchOffset=data.offset;state.researchHasMore=data.hasMore;}}
        catch(error){safeLog('hot_result_page_failed');if(current(ticket))state.error=error.message||'研究分页读取失败。';}
        finally{if(current(ticket)){state.loading=false;onChange();}}return;
      }
      if (action === 'refresh') return await activate(lastRoute);
      if (action === 'feed-channel' || action === 'feed-sort') {
        if(state.loading||state.busy||state.pending)return;
        let filters;
        if(action==='feed-channel') {
          const channel=button.dataset.channel;
          if(channel!==''&&!state.channels.some(item=>item.channel_id===channel))throw Error('请选择有效的研究频道。');
          filters={...state.filters,channelId:channel,sort:channel?state.filters.sort:'recent'};
        } else {
          const sort=button.dataset.sort;
          if(!['recent','importance','heat'].includes(sort)||!state.filters.channelId&&sort!=='recent')throw Error('请选择研究频道及有效的排序。');
          filters={...state.filters,sort};
        }
        return await reloadEvents(filters);
      }
      if (action === 'retry') return await sendPending();
      if (action === 'open-brief') return await openBrief(button.dataset.brief,Number(button.dataset.version));
      if (action === 'close-brief') {briefGeneration++;state.brief=null;onChange();return;}
      if (action === 'more-briefs') {if(state.loading)return;const ticket=generation;state.loading=true;onChange();try{await loadBriefs(ticket,true);}finally{if(current(ticket)){state.loading=false;onChange();}}return;}
      if (action === 'detail') {if(state.loading)return;return await selectDetail(button.dataset.event);}
      if (action === 'close-detail') { detailGeneration++; state.detail = null; onChange(); return; }
      if (action === 'more-reports' && state.detail) return await selectDetail(state.detail.requestedId, generation, state.detail.reportOffset + state.detail.reports.length,state.detail.cutoff);
      if (action === 'more') { if(state.loading||!state.hasMore)return; const ticket=generation; state.loading = true; onChange(); try { await loadEvents(ticket,true); } catch(error) {safeLog('hot_reader_page_failed');if(current(ticket))state.error=error.message||'事件分页读取失败。';} finally { if(current(ticket)){state.loading = false; onChange();} } return; }
      if (action === 'edit-channel') { const channel = state.channels.find(c => c.channel_id === button.dataset.channel); state.editChannel = channel.channel_id; state.editVersion = channel.version; state.channelDraft = channel.config; onChange(); return; }
      if (action === 'new-channel') { state.editChannel = ''; state.editVersion = 0; state.channelDraft = null; onChange(); return; }
      if (state.pending || state.busy) return;
      if (action === 'source-toggle') { const source = state.sources.find(s => s.id === button.dataset.source); state.pending = {method:'hotSourceConfigure',body:{sourceId:source.id,expectedRevision:source.config_revision,enabled:!source.enabled,requestId:uuid()}}; return await sendPending(); }
      if (['start','stop','restart'].includes(action)) { state.busy = true; onChange(); try { await api.hotLifecycle(action); state.message = '运行操作已返回，请刷新核对当前状态。'; } finally { state.busy = false; onChange(); } }
    } catch (error) { state.error = error.message || '操作失败，请刷新核对。'; if (isActive()) onChange(); }
  }
  return {state,activate,deactivate(){generation++;detailGeneration++;briefGeneration++;},submit,action,selectMaterial(id,selected){if(!state.detail?.reports.some(report=>report.materialId===id))return;state.selectedMaterialIds=selected?[...new Set([...state.selectedMaterialIds,id])]:state.selectedMaterialIds.filter(value=>value!==id);onChange();}};
}
