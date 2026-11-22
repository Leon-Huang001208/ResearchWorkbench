import { escapeHTML as e } from './markdown.mjs';

const value = record => record?.payload || record || {};
const title = record => record.label || value(record).title || value(record).label || value(record).spec?.title || '未命名资料';
const option = (record, field = 'id') => `<option value="${e(record[field])}">${e(title(record))}</option>`;
const select = (name, label, rows, { required = false, blank = '不关联' } = {}) => `<label>${label}<select name="${name}" ${required ? 'required' : ''}><option value="">${e(blank)}</option>${rows.map(row => option(row)).join('')}</select></label>`;
const sourceOptions = (state, kind) => (state.sourceChoices || []).flatMap(source => source.kind === kind ? [option({ ...source, choice: `${source.session_id}/${source.dataset_id}`, label: source.title }, 'choice')] : []).join('');
const bundles = state => (state.bundles || []).filter(record => value(record).price_role !== 'proxy');

export function inputControls(state) {
  const choices = state.choices || {};
  const basic = `<details><summary>登记已有行情与日历</summary>
    <form data-event-import><label>指数日线<select name="choice" required><option value="">选择已有指数资料</option>${sourceOptions(state, 'prices')}</select></label><button class="button secondary" ${state.busy ? 'disabled' : ''}>核验并登记日线</button></form>
    <form data-event-calendar>${select('bundle_id', '研究指数资料', bundles(state), { required: true, blank: '选择已登记日线' })}<label>交易日历<select name="calendar_choice" required><option value="">选择已有交易日历</option>${sourceOptions(state, 'calendar')}</select></label>${select('freeze_id', '已确认节假日定义', state.freezes || [])}<button class="button secondary" ${state.busy ? 'disabled' : ''}>关联日历</button></form>
    <p>日线、日历和交易代理分别核验。观测日期或标准交易时段假设不提供历史可得性证明。</p></details>`;
  const native = `<details><summary>登记原生证据与交易代理</summary><form data-event-native><label>已取得的原生资料<select name="native_choice" required><option value="">选择具有原生合同的资料</option>${sourceOptions(state, 'native')}</select></label><label>研究指数<select name="index_id">${(state.indices || []).map(index => option({ id: index.id, label: index.name || index.id })).join('')}</select></label>${select('proxy_ref', '关联交易代理', choices.proxies || [])}<button class="button secondary" ${state.busy ? 'disabled' : ''}>核验原生资料</button></form><p>仅接受本账号已有DataHub原件引用；来源、单位、实际交易状态和历史时点由服务核验。</p></details>`;
  const links = `<details><summary>组合研究输入</summary><form data-event-links>${select('bundle_id', '指数日线', bundles(state), { required: true, blank: '选择指数资料' })}${select('index_calendar_ref', '指数日历', choices.calendars || [])}${select('proxy_ref', '交易代理事实', choices.proxies || [])}${select('proxy_prices_ref', '代理日线', (choices.prices || []).filter(row => row.price_role === 'proxy'))}${select('proxy_calendar_ref', '代理交易日历', choices.calendars || [])}${select('factor_inputs_ref', '六维输入', choices.inputs || [])}<button class="button secondary" ${state.busy ? 'disabled' : ''}>保存新输入版本</button></form></details>`;
  return basic + native + links;
}

export function validationControls(state) {
  const selected = state.studySelection || [];
  return `<details><summary>封存与独立验证</summary><p>先固定窗口、方向和完整试验家族。打开测试集后，修改规则不能重复使用同一区间作为未见数据。</p>
    <form data-event-seal><fieldset><legend>本次一起封存的研究</legend>${(state.data?.items || []).map(record => `<label><input type="checkbox" name="study_id" value="${e(record.id)}" ${selected.includes(record.id) ? 'checked' : ''}>${e(title(record))}</label>`).join('')}</fieldset><button class="button secondary" ${state.busy ? 'disabled' : ''}>封存所选研究</button></form>
    <form data-event-evaluate>${select('batch_id', '已封存家族', state.validationBatches || [], { required: true, blank: '选择已封存批次' })}<label><input type="checkbox" name="acknowledge" required>确认本次打开测试集，接受样本不足或验证失败的结果</label><button class="button" ${state.busy ? 'disabled' : ''}>执行独立验证</button></form></details>`;
}

export function scoreControls(state) {
  const choices = state.choices || {};
  const roles = { base_score: '六维基础评分', event_overlay: '重大事件修正', calendar_overlay: '日历效应修正' };
  const indices = { SSE: '上证综指', CSI300: '沪深300', CHINEXT: '创业板指', SP500: '标普500', NASDAQ: '纳斯达克综合', DJI: '道琼斯工业平均', HSI: '恒生指数', HSCEI: '恒生国企指数', HSTECH: '恒生科技指数' };
  const validated = (choices.validations || []).filter(row => row.status === 'VALIDATED' && Object.hasOwn(roles, row.role)).map(row => ({ ...row, label: `${roles[row.role]} · ${(state.indices || []).find(index => index.id === row.index_id)?.name || indices[row.index_id] || row.index_id || '指数待核实'} · 版本${row.revision || '待核实'} · ${String(row.id).slice(0, 8)}` }));
  const bases = validated.filter(row => row.role === 'base_score'), overlays = validated.filter(row => ['event_overlay', 'calendar_overlay'].includes(row.role));
  return `<form data-event-score>${select('inputs_id', '六维研究输入', choices.inputs || [], { required: true, blank: '选择六维资料' })}${select('validation_id', '基础评分验证', bases)}${!bases.length ? '<p class="muted">尚无通过验证的基础评分证书。</p>' : ''}<fieldset><legend>事件／日历修正验证</legend>${overlays.map(row => `<label><input type="checkbox" name="overlay_id" value="${e(row.id)}">${e(row.label)}</label>`).join('')}${!overlays.length ? '<p class="muted">尚无通过验证的事件／日历修正证书。</p>' : ''}</fieldset><button class="button" ${state.busy ? 'disabled' : ''}>计算研究分</button></form><p>未通过验证的研究及拒绝原因请到<a href="#/simulation/events">事件与日历研究</a>查看。列表筛选仅帮助选择，当前时点、冻结版本和来源资格仍由服务端重新核验。</p><p>采用所选输入最新一期的实际时点；缺一维、缺少有效验证或因子不在当期窗口时，不生成正式总分。历史研究分不代表生产评分。</p>`;
}

export function collectionControls(state) {
  const sources = state.sources || [];
  const selected = sources.find(source => source.id === state.scheduleSource) || sources[0];
  const settings = state.scheduleDrafts?.[selected?.id] || selected?.schedule?.payload || {};
  const interval = settings.interval_hours || (['gdelt', 'ucdp'].includes(selected?.id) ? 1 : 24);
  return `<details><summary>公开来源与采集计划</summary><form data-event-source><label>来源<select name="source">${sources.map(source => option({ id: source.id, label: source.label || source.name || source.id })).join('')}</select></label><label>历史年份（可选）<input name="year" type="number" min="1990" max="2200"></label><button class="button secondary" ${state.busy ? 'disabled' : ''}>手动更新／分批回填</button></form>
    <ul>${sources.map(source => `<li>${e(source.label || source.name || source.id)} · ${source.requires_credentials || source.requires_token ? '凭据未配置，当前不可调用' : source.enabled ? '计划已启用' : '计划未启用'}${source.coverage_end ? ` · 覆盖至${e(source.coverage_end)}` : ''}</li>`).join('')}</ul>
    <form data-event-schedule><label>来源<select name="source">${sources.map(source => `<option value="${e(source.id)}" ${source.id === selected?.id ? 'selected' : ''}>${e(source.label || source.name || source.id)}</option>`).join('')}</select></label><label>间隔小时<input type="number" name="interval_hours" min="1" max="720" value="${e(interval)}" required></label><label><input type="checkbox" name="enabled" ${settings.enabled ? 'checked' : ''}>启用所选来源采集</label><button class="button secondary" ${state.busy ? 'disabled' : ''}>保存计划</button></form><p>默认关闭；保存不会启动模型。宿主禁用调度或来源未配置时会明确拒绝。采集失败／未知暂停并保留原任务。</p></details>`;
}

export function manualEventControls(state) {
  return `<details><summary>人工录入事件候选</summary><p>人工候选保留录入时间，出处与历史可得性另行核验；录入或确认不等于预测因子准入。</p><form data-event-create>
    <label>事件名称<input name="title" maxlength="300" required></label>
    <label>类别<select name="category"><option value="macro">宏观</option><option value="policy">政策</option><option value="geopolitics">地缘冲突</option><option value="war">战争</option><option value="sports">赛事</option><option value="unexpected">突发事件</option><option value="calendar">节假日</option><option value="other">其他</option></select></label>
    <label>开始日期<input name="occurrence_start" type="date" min="1990-01-01" required></label><label>结束日期（未知可留空）<input name="occurrence_end" type="date" min="1990-01-01"></label>
    <label>事件状态<select name="lifecycle"><option value="announced">已公布日程</option><option value="occurred">已发生</option><option value="ongoing">持续中</option><option value="scenario">风险情景</option></select></label>
    <fieldset><legend>相关市场</legend><label><input type="checkbox" name="market" value="CN">A股</label><label><input type="checkbox" name="market" value="US">美股</label><label><input type="checkbox" name="market" value="HK">港股</label></fieldset>
    <label>说明与公开出处<textarea name="description" maxlength="10000" rows="3"></textarea></label><button class="button secondary" ${state.busy ? 'disabled' : ''}>保存待审候选</button></form></details>`;
}

const eventCategories = { macro: '宏观', policy: '政策', geopolitics: '地缘冲突', war: '战争', sports: '赛事', disaster: '灾害', unexpected: '突发事件', calendar: '日历效应', other: '其他' };
const eventLifecycles = { announced: '已公布日程', occurred: '已发生', ongoing: '持续中', postponed: '已延期', cancelled: '已取消', scenario: '风险情景' };
const eventPrecisions = { month: '月份', day: '日期', minute: '含时区的时刻', interval: '日期区间', unknown: '时间精度待核实' };
const eventOptions = (choices, selected) => Object.entries(choices).map(([id, label]) => `<option value="${e(id)}" ${id === selected ? 'selected' : ''}>${e(label)}</option>`).join('');
const eventDates = (event, prefix = '') => `<label>开始时间<input name="${prefix}occurrence_start" maxlength="40" value="${e(event.occurrence_start || '')}" required></label><label>结束时间（未知可留空）<input name="${prefix}occurrence_end" maxlength="40" value="${e(event.occurrence_end || '')}"></label>`;

export function eventMergeControls(state) {
  const selected = (state.data?.items || []).filter(record => state.selected?.includes(record.id));
  return `<details><summary>合并所选事件（${selected.length}项）</summary><p>选择2至30项当前事件，将保留父事件与合并理由；新事件重新进入待确认状态。</p><ul>${selected.map(record => `<li>${e(title(record))} · 版本${e(record.revision)}</li>`).join('')}</ul><form data-event-merge><label>合并后的名称<input name="title" maxlength="300" required></label><label>合并理由<textarea name="reason" maxlength="2000" required></textarea></label><button class="button secondary" ${state.busy || selected.length < 2 || selected.length > 30 ? 'disabled' : ''}>合并当前所选版本</button></form></details>`;
}

export function eventDetailControls(record, state, historical = false) {
  const event = value(record), identifier = e(record.id), revision = e(record.revision);
  const heading = `<p>${historical ? '历史只读版本' : '当前读取版本'} ${revision} · ${e(event.occurrence_start || '时间待核实')}${event.occurrence_end ? ` 至 ${e(event.occurrence_end)}` : ''} · ${e(eventCategories[event.category] || event.category || '类别待核实')} · ${e(eventLifecycles[event.lifecycle] || event.lifecycle || '状态待核实')}</p><p>时间精度：${e(eventPrecisions[event.date_precision] || '待核实')} · 相关市场：${e((event.markets || []).map(id => ({ CN: 'A股', US: '美股', HK: '港股' })[id] || id).join('、') || '待核实')} · 人工处理：${e(({ candidate: '待确认', confirmed: '已确认', rejected: '已拒绝' })[event.admission] || '待确认')}</p><p>${e(event.description || '暂无说明')}</p><p class="muted">首次取得：${e(event.first_observed || '待核实')}；公告／首次公开：${e(event.source_published_at || '未知')}。人工处理不授予历史时点或评分资格。</p><button class="text-button" data-event-versions="${identifier}">查看版本历史</button><button class="text-button" data-event-latest="${identifier}">${historical ? '读取当前版本' : '重新读取当前版本'}</button>`;
  if (historical || event.superseded_by) return `${heading}${event.superseded_by ? '<p>此事件已由合并或拆分替代，保留历史记录。</p>' : ''}`;
  return `${heading}<details><summary>修订事件事实或日程</summary><p>保存基于版本${revision}；并发变更会拒绝提交，需重新读取并核对。修订后重新待确认，不补造历史可得性。</p><form data-event-revise data-event-id="${identifier}" data-event-revision="${revision}" data-draft-key="${identifier}:${revision}">
    <label>事件名称<input name="title" maxlength="300" value="${e(event.title || '')}" required></label><label>类别<select name="category">${eventOptions(eventCategories, event.category)}</select></label><label>时间精度<select name="date_precision">${eventOptions(eventPrecisions, event.date_precision || 'day')}</select></label>${eventDates(event)}<p>日期填YYYY-MM-DD；月份填YYYY-MM；时刻必须带时区，例如2026-11-04T09:00:00+08:00。</p><label>事件状态<select name="lifecycle">${eventOptions(eventLifecycles, event.lifecycle || 'occurred')}</select></label><fieldset><legend>相关市场</legend>${Object.entries({ CN: 'A股', US: '美股', HK: '港股' }).map(([id, label]) => `<label><input type="checkbox" name="market" value="${id}" ${(event.markets || []).includes(id) ? 'checked' : ''}>${label}</label>`).join('')}</fieldset><label>说明<textarea name="description" maxlength="10000" rows="3">${e(event.description || '')}</textarea></label><label>修订理由<textarea name="reason" maxlength="2000" required></textarea></label><button class="button secondary" ${state.busy ? 'disabled' : ''}>保存新待审版本</button></form></details>
    <details><summary>拆分为两个事件候选</summary><p>两个子事件沿用本版本的类别、市场、状态、时间精度和说明；分别核对名称与时间。父事件保留并标记被替代，子事件重新待确认。</p><form data-event-split data-event-id="${identifier}" data-event-revision="${revision}" data-draft-key="${identifier}:${revision}">${[0, 1].map(index => `<fieldset><legend>子事件${index + 1}</legend><label>名称<input name="child_${index}_title" maxlength="300" value="${e(event.title || '')}" required></label>${eventDates(event, `child_${index}_`)}</fieldset>`).join('')}<label>拆分理由<textarea name="reason" maxlength="2000" required></textarea></label><button class="button secondary" ${state.busy ? 'disabled' : ''}>拆分当前版本</button></form></details>`;
}
