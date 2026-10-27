import { escapeHTML as e } from './markdown.mjs';

// Form controls are projected from the authenticated Host catalog. Neither form
// values nor this projection provide source, ownership or quality authority.
export function packScope(row, values = {}, locked = false) {
  if (!row?.pack_id) return '';
  const methods = values.research_scope?.methods || {};
  return `<section class="pack-scope" aria-label="组合包研究参数"><h3>研究范围与方法参数</h3><p class="notice warning">截止时点须明确填写时区，且换算为北京时间后与研究截止日相同。不会自动补午夜或日终。仅使用本人已取得资料；浏览、预览均不查询供应商或启动模型。</p><label>明确截止时点（含时区）<input id="scenario-cutoff_at" data-scenario-field="cutoff_at" type="text" placeholder="YYYY-MM-DDTHH:mm:ss+08:00" value="${e(values.research_scope?.cutoff_at || '')}" ${locked ? 'disabled' : ''}></label>${(row.ui_methods || []).map(method => `<fieldset><legend>${e(method.label)} · v${e(method.version || '未提供')}</legend><p>必要资料：${e((method.required_kinds || []).join('、'))}</p>${method.source_requirements?.length ? '<p class="notice warning">风险类别完整覆盖必须由来源核验，不能手填通过；当前缺口仍可能阻断此方法。</p>' : ''}${method.fields.map(field => renderField(method.id, field, methods[method.id]?.[field.name], locked)).join('')}${!method.fields.length ? '<p>此方法无需额外研究参数。</p>' : ''}</fieldset>`).join('')}<p class="small muted">${e(row.ui_limits || '')}</p></section>`;
}

function renderField(method, field, value, locked) {
  const key = `method:${method}:${field.name}`;
  const attribute = `id="scenario-${e(method)}-${e(field.name)}" data-scenario-field="${e(key)}" ${locked ? 'disabled' : ''}`;
  if (field.type === 'securities') {
    const securities = Array.isArray(value) && value.length ? value : [{}];
    return `<fieldset class="pack-universe"><legend>${e(field.label)}（显式证券身份，不从名称推断）</legend>${securities.map((security, index) => `<div class="pack-security">${[['security_id','证券代码'],['market','市场'],['asset_class','资产类别'],['currency','币种']].map(([part,label]) => `<label>${label}${part === 'asset_class' ? `<select id="scenario-${e(method)}-${e(field.name)}-${index}-${part}" data-scenario-field="${e(key)}:${index}:${part}" ${locked ? 'disabled' : ''}><option value="">请选择</option>${['equity','index','fund'].map(x=>`<option value="${x}" ${security[part]===x?'selected':''}>${e(x)}</option>`).join('')}</select>` : `<input id="scenario-${e(method)}-${e(field.name)}-${index}-${part}" data-scenario-field="${e(key)}:${index}:${part}" value="${e(security[part] || '')}" maxlength="100" ${locked ? 'disabled' : ''}>`}</label>`).join('')}</div>`).join('')}<button type="button" class="button small" data-scenario-action="add-security" data-pack-method="${e(method)}" data-pack-field="${e(field.name)}" ${locked || securities.length >= 100 ? 'disabled' : ''}>添加证券范围</button><p>空行不发送；请明确填写代码、市场、类别、币种。只声明研究范围，不提供持仓事实。</p></fieldset>`;
  }
  if (field.type === 'adjustment') return `<label>${e(field.label)}<select ${attribute}><option value="">请选择</option>${['none','forward','backward'].map(x=>`<option value="${x}" ${value===x?'selected':''}>${({none:'不复权',forward:'前复权',backward:'后复权'})[x]}</option>`).join('')}</select></label>`;
  return `<label>${e(field.label)}<input ${attribute} type="${field.type === 'integer' || field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'}" ${field.type === 'integer' ? 'step="1"' : field.type === 'number' ? 'step="any"' : ''} ${field.min !== undefined ? `min="${e(field.min)}"` : ''} ${field.max !== undefined ? `max="${e(field.max)}"` : ''} maxlength="4096" value="${e(Array.isArray(value) ? value.join(',') : value ?? '')}" ${field.type === 'instant' ? 'placeholder="YYYY-MM-DDTHH:mm:ss+08:00"' : ''}></label>`;
}

const gapLabels = {cutoff_timezone_required:'截止时点缺少有效时区',source_observed_after_cutoff:'材料取得时点晚于截止',required_kind_missing:'缺少必要资料类型',source_coverage_unverified:'来源完整覆盖尚未核验',dataset_mapping_unsupported:'此来源或资料类型尚无受审映射',material_schema_unsupported:'原件格式尚无受审映射',source_rows_truncated:'来源行被截断',price_unit_or_adjustment_unverified:'价格单位或复权口径未核验',source_observation_instant_unknown:'来源取得时点未知'};
export function packQualification(context, stale = false) {
  const q = context?.pack_qualification;
  if (!q) return stale ? '<p role="status" class="notice warning">参数或材料已变化，资格预览失效；请重新预览。输入已保留。</p>' : '';
  const pick = (item, keys) => Object.fromEntries(keys.filter(key=>item?.[key] !== undefined).map(key=>[key,item[key]]));
  const provenance = {
    references:(context.references || []).map(item=>pick(item,['source_session_id','reference','sha256','manifest_sha256','provider','capability','as_of','retrieved_at','published_at','date_gaps'])),
    transformations:(q.transformations || []).map(item=>pick(item,['mapping','dataset_id','source_sha256','manifest_sha256','unit_mapping','security_mapping','publication_time','historical_pit'])),
    capabilities:(context.scenario?.capabilities || []).map(item=>pick(item,['id','version','sha256','execution_status'])),
    input_sha256:q.input_sha256,closure_sha256:q.closure_sha256,
  };
  return `<section class="pack-qualification" aria-label="Host 只读资格预览"><h3>Host 只读资格预览 · ${e(q.status)}</h3><p>可执行方法：${e(q.executable_methods?.join('、') || '无')}。${q.status === 'blocked' || !q.executable_methods?.length ? '当前不能准备可发送草稿。' : '仅具备部分计算输入，准备及发送仍将由 Host 重新核验。'}</p><p>计算准入、完整文件保存、研究质量分别验收。partial／blocked 不代表报告通过；事件收益、基金穿透、财报监控保持原门。</p><ul>${(q.missing || []).map(gap=>`<li>${e(gapLabels[gap.code] || gap.code)}${gap.kind || gap.component || gap.id ? ` · ${e(gap.kind || gap.component || gap.id)}` : ''}<code>${e(gap.code)}</code></li>`).join('')}</ul><details><summary>逐来源范围、时点、hash 与方法版本</summary><pre>${e(JSON.stringify(provenance,null,2))}</pre></details></section>`;
}

export function packInputEdit(inputs, row, name, value) {
  if (!row?.pack_id) return false;
  if (name === 'cutoff_at') { inputs.research_scope = {...inputs.research_scope,cutoff_at:value}; return true; }
  const [prefix, methodID, fieldName, index, part] = name.split(':');
  if (prefix !== 'method') return false;
  const method = row.ui_methods?.find(item=>item.id === methodID);
  const field = method?.fields.find(item=>item.name === fieldName);
  if (!field) return false;
  const scope = inputs.research_scope ||= {methods:{}};
  const methods = scope.methods ||= {};
  const parameters = methods[methodID] ||= {};
  if (field.type === 'securities') {
    if (!/^\d{1,2}$/.test(index || '') || !['security_id','market','asset_class','currency'].includes(part)) return false;
    const rows = parameters[fieldName] ||= [];
    rows[Number(index)] = {...rows[Number(index)],[part]:value};
  } else if (value === '') delete parameters[fieldName];
  else parameters[fieldName] = field.type === 'integer' || field.type === 'number' ? Number(value) : field.type === 'periods' ? value.split(/[,，\s]+/).filter(Boolean) : value;
  return true;
}

export function packCapabilityGuide(item, busy = false) {
  if (!/^research-pack-(position-risk|expectation-gap|short-sentiment|research-prep|event-review|global-opinion|valuation-check|ownership-structure|earnings-preview)$/.test(item?.id || '')) return '';
  return `<section class="pack-capability-guide" aria-label="组合包配置与结果合同"><h3>组合包方法与输入</h3><p>当前 Skill v${e(item.version || '未发布')}。打开配置后从当前账号 Host 目录读取方法版本、必要资料、类型化参数、限额与示例；选择不会创建会话或调用模型。</p><p>输出为受控 full-result.json、receipt.json 与 manifest.json。预览最多128行；全量条数、遗漏数与 hash 以真实回执为准。完整文件保存、真实计算和研究质量 passed／incomplete／invalid 分开核验。</p><p>来源映射目前仅有 BaoStock 不复权日线子集；其他原件格式、覆盖、披露时点缺失会保留 partial／blocked。用户声明资料不升格为核验来源。复制、编辑、检查与发布继续使用本页原有流程。</p><button type="button" class="button" data-pack-configure="${e(item.id.slice('research-'.length))}" ${busy ? 'disabled' : ''}>配置此组合包并查看方法</button></section>`;
}

export function packResults(detail) {
  const pack = detail?.research_pack;
  if (!pack) return '';
  const files = detail.files || [];
  return `<section class="pack-results" aria-label="组合包计算与文件回执"><h3>组合包计算与文件回执</h3><p>来源资格：${e(pack.qualification_status)} · 研究质量：${e(detail.research_quality?.status || '尚未验收')} · 会话：${e(detail.status || 'unknown')}</p>${pack.executions.length ? pack.executions.map(execution=>`<article><p>文件保存：${e(({saved:'Host 已重新核验完整文件',invalid:'产物完整性失效',unavailable:'执行绑定不可核验',unknown:'执行结果未知，不自动重试',cancelled:'已取消'})[execution.state] || '未知')} · 计算：${e(execution.computation_status || '未核验')}</p>${execution.state === 'saved' ? `<p>部分计算与文件保存不表示正式研究通过。128仅为行预览上限，全量计数和遗漏见回执。</p><details><summary>全量计数与缺口</summary><pre>${e(JSON.stringify({counts:execution.counts,row_delivery:execution.row_delivery,missing:execution.missing},null,2))}</pre></details><ul>${(execution.files || []).map(file=>{
    const match=files.filter(registered=>registered.id===file.id && registered.url===file.url);
    const safe=match.length===1 && /^\/api\/research\/sessions\/[^/]+\/files\/[a-f0-9]{24}\/download$/.test(file.url || '');
    return safe ? `<li><a href="${e(file.url)}" download>${e(file.name)}</a> · ${e(file.bytes)} B<code>${e(file.sha256)}</code></li>` : '<li>文件引用不可核验；请刷新原会话。</li>';
  }).join('')}</ul>` : ''}</article>`).join('') : '<p>尚无受控计算回执。准备草稿尚未执行模型或计算。</p>'}<div class="button-row"><button class="button small" type="button" data-context-tab="files">查看原会话文件</button><button class="button small" type="button" data-context-tab="report">质量回看</button><a class="button small" href="#/assets?view=dossiers">到资产档案关联此会话（先预览）</a></div><p class="small">归档来源会话 ID：<code>${e(detail.id || "")}</code>。在原档案选择“关联已有研究成果”，预览后确认；保留原质量状态。</p></section>`;
}
