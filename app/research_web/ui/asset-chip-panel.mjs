import { escapeHTML as e } from './markdown.mjs';
import { CHIP_AGES, normalizeChipSettings } from './asset-chips.mjs';

const fmt = (v, n = 2) => typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString('zh-CN', { minimumFractionDigits: n, maximumFractionDigits: n }) : '—';
const pct = v => typeof v === 'number' && Number.isFinite(v) ? `${fmt(v * 100)}%` : '—';
const range = v => Array.isArray(v) ? `${fmt(v[0])}–${fmt(v[1])}` : '—';
const button = (action, text, active = false) => `<button type="button" class="chip-tab" data-asset-chart-action="${action}" aria-pressed="${active}">${text}</button>`;
const row = (label, value, title = '') => `<div class="chip-stat-row"><span${title ? ` title="${e(title)}"` : ''}>${e(label)}</span><strong>${e(value)}</strong></div>`;
const costRow = (label, values, concentration) => `<div class="chip-stat-row chip-cost-row"><span>${e(label)}</span><strong>${e(range(values))}<small title="集中度：(上界−下界)/(上界＋下界)" aria-label="集中度 ${e(pct(concentration))}">${e(pct(concentration))}</small></strong></div>`;
export const chipReason = reason => ({
  chip_history_short: '需至少5条有效日线。', chip_input_invalid: '逐日换手率、日期或价格输入未完整核验。',
  chip_vwap_unverified: '三角分布所需的同复权均价未取得；可在设置中显式选择平均分布。',
  chip_inputs_not_loaded: '尚未取得逐日换手率输入，行情快照仍可查看。',
  chip_settings_invalid: '设置无效，请恢复默认设置。',
})[reason] || '筹码估算输入尚未完整取得。';

export function chipStatistics(chip, tab = 'statistics') {
  if (chip.status !== 'ready') return `<p class="asset-chip-empty">${e(chipReason(chip.reason))}</p><button type="button" class="kline-btn" data-asset-chart-action="chip-load">加载筹码输入</button>`;
  if (tab === 'age') {
    const ages = (fractions, prefix) => `<div class="chip-age-composition" aria-label="${prefix}筹码构成">${CHIP_AGES.map((age, i) => `<span style="width:${Math.max(0, fractions?.[i] || 0) * 100}%;background:${age.color}" title="${age.name} ${pct(fractions?.[i])}"></span>`).join('')}</div>${CHIP_AGES.map((age, i) => `<div class="chip-age-row"><span><i style="background:${age.color}"></i>${age.name}占比</span><strong>${pct(fractions?.[i])}</strong></div>`).join('')}`;
    const definition = '按当前残存筹码概率加权的日线期数。不是已验证的 Wind 均龄公式；停牌缺失日期不补交易日。';
    return `<section class="chip-stat-group"><h4>全部筹码</h4>${row('筹码均龄（估算）', `${fmt(chip.meanAge)}期`, definition)}${ages(chip.ageFractions, '全部')}</section><section class="chip-stat-group"><h4>筹码峰区域</h4>${row('筹码峰龄（估算）', chip.peakMeanAge === null ? '—' : `${fmt(chip.peakMeanAge)}期`, definition)}${ages(chip.peakAgeFractions, '峰区')}</section>`;
  }
  return `<section class="chip-stat-group">${row('获利比率', pct(chip.profitFraction), '成本严格低于所选收盘价；平价筹码另计。')}${row('平均成本', fmt(chip.averageCost))}${costRow('90%成本', chip.cost90, chip.concentration90)}${costRow('70%成本', chip.cost70, chip.concentration70)}${chip.atCostFraction > 1e-9 ? row('平价筹码', pct(chip.atCostFraction)) : ''}</section><section class="chip-stat-group">${row('筹码峰', fmt(chip.peak))}${row('峰区均价', fmt(chip.peakAverageCost))}${row('上界', fmt(chip.peakUpper))}${row('下界', fmt(chip.peakLower))}${row('峰区成本权重占比', pct(chip.peakCapitalFraction), '峰区的一阶成本矩／全部平均成本；不是持股数量占比。')}</section>`;
}

export function chipSettingsForm(options) {
  const s = normalizeChipSettings(options);
  const number = (key, label, min, max, step = 1) => `<label class="chip-setting-row"><span>${label}</span><input type="number" name="${key}" value="${s[key]}" min="${min}" max="${max}" step="${step}" required></label>`;
  return `<form data-asset-chip-settings-form><h3 id="asset-chip-settings-title">筹码分布设置</h3><fieldset><legend>分布算法</legend><label><input type="radio" name="algorithm" value="triangle"${s.algorithm === 'triangle' ? ' checked' : ''}>三角形分布</label><label><input type="radio" name="algorithm" value="uniform"${s.algorithm === 'uniform' ? ' checked' : ''}>平均分布</label></fieldset>${number('decay', '历史衰减换手系数', 0, 10, .01)}${number('peakUpperPct', '峰上界高于峰值（%）', 0, 100, .01)}${number('peakLowerPct', '峰下界低于峰值（%）', 0, 100, .01)}<label class="chip-setting-check"><input type="checkbox" name="showPeak"${s.showPeak ? ' checked' : ''}>显示筹码峰区域</label><fieldset><legend>筹码龄定义与显示 · 按已取得日线期数</legend>${number('ageLong', '长线：此前的筹码', 1, 10000)}${number('ageMiddle', '中线起点', 1, 10000)}${number('ageShort', '短线起点／超短上界', 1, 10000)}<div class="chip-setting-ages">${CHIP_AGES.map(age => `<label><input type="checkbox" name="age-${age.id}"${s.visibleAges.includes(age.id) ? ' checked' : ''}><i style="background:${age.color}"></i>${age.name}</label>`).join('')}</div><small>超短 &lt;${s.ageShort}；短线 ${s.ageShort}–${s.ageMiddle - 1}；中线 ${s.ageMiddle}–${s.ageLong - 1}；长线 ≥${s.ageLong}。</small></fieldset><label class="chip-setting-check"><input type="checkbox" name="overlayEnabled"${s.overlayEnabled ? ' checked' : ''}>叠加历史筹码</label>${number('overlayDays', '叠加所选日期之前的日线期数', 1, 10000)}<p class="chip-settings-explanation">三角分布以单位已核验的同复权日均价为峰；换手率按百分数输入，超过100%的有效置换按100%处理。结果为 RWB 自有估算。</p><p class="chip-settings-error" data-chip-settings-error role="alert" hidden></p><footer><button type="button" data-asset-chart-action="chip-settings-default">恢复默认</button><button type="button" data-asset-chart-action="chip-settings-cancel">取消</button><button type="submit">确认</button></footer></form>`;
}

export function chipPanel(chip, settings, tab = 'statistics') {
  return `<aside class="asset-chip-panel"><div class="asset-chip-heading">普通筹码 <small title="逐日换手衰减与同复权价格估算，非实际持仓">估算</small></div><div class="asset-chip-chart" data-asset-chip-chart role="img" aria-label="同版本日线与逐日换手率估算筹码分布"></div><div class="chip-window-label" data-asset-chip-window>${chip.startDate ? e(`${chip.startDate}–${chip.endDate}`) : '尚未取得完整输入'}</div><div class="chip-tabs" data-asset-chip-tabs>${button('chip-tab-statistics', '筹码统计', tab === 'statistics')}${button('chip-tab-age', '筹码龄分析', tab === 'age')}<button type="button" class="chip-tab" data-asset-chart-action="chip-settings-open">设置</button></div><div class="asset-chip-stats" data-asset-chip-stats>${chipStatistics(chip, tab)}</div><p class="asset-chip-note">首条已取得日线至所选日的估算；不代表实际持仓。</p><dialog class="asset-chip-settings" aria-labelledby="asset-chip-settings-title" data-asset-chip-settings>${chipSettingsForm(settings)}</dialog></aside>`;
}

export function chipPeakLines(chip, palette, labels = 'price') {
  if (chip?.status !== 'ready' || !chip.settings.showPeak) return { silent: true, symbol: 'none', data: [] };
  const values = [['上界', chip.peakUpper], ['筹码峰', chip.peak], ['下界', chip.peakLower]];
  return { silent: true, symbol: 'none', precision: 4, animation: false,
    lineStyle: { color: '#c99a4a', width: 1, type: 'dashed' },
    label: { show: true, color: palette.text, fontSize: 12, position: labels === 'price' ? 'end' : 'insideEndTop', formatter: p => labels === 'price' ? fmt(p.value) : p.name },
    data: values.map(([name, yAxis]) => ({ name, yAxis, label: { show: name === '筹码峰' } })) };
}

export function chipChartOption(chip, domain, echarts, palette, tab = 'statistics', overlay = null) {
  const selected = chip.settings?.visibleAges || [];
  const active = tab === 'age' ? CHIP_AGES.map((a, i) => ({ ...a, i })).filter(a => selected.includes(a.id)) : [{ id: 'all', name: '全部筹码', i: null }];
  const series = active.map((age, layer) => ({
    name: age.name, type: 'custom', animation: false,
    data: chip.points.map(p => {
      const start = tab === 'age' ? active.slice(0, layer).reduce((s, a) => s + p.massByAge[a.i] * 100, 0) : 0;
      const mass = tab === 'age' ? p.massByAge[age.i] * 100 : p.concentration_pct;
      return [start, start + mass, p.price];
    }),
    renderItem: (params, api) => {
      const price = api.value(2), start = api.coord([api.value(0), price]), end = api.coord([api.value(1), price]);
      const height = Math.max(.5, Math.abs(api.size([0, chip.bucketWidth * .98])[1]));
      const rect = { x: start[0], y: start[1] - height / 2, width: Math.max(0, end[0] - start[0]), height };
      const shape = echarts?.graphic?.clipRectByRect ? echarts.graphic.clipRectByRect(rect, params.coordSys) : rect;
      return shape ? { type: 'rect', shape, style: api.style({ fill: tab === 'age' ? age.color : price < chip.referenceClose ? '#ff4d4f' : price > chip.referenceClose ? '#00c896' : palette.muted }) } : null;
    },
    ...(layer === 0 ? { markLine: chipPeakLines(chip, palette, 'name') } : {}),
  }));
  if (overlay?.status === 'ready') series.push({ name: `历史 ${overlay.endDate}`, type: 'line', showSymbol: false, clip: true, lineStyle: { color: palette.muted, width: 1, type: 'dashed', opacity: .7 }, data: overlay.points.map(p => [p.concentration_pct, p.price]) });
  const visible = chip.points.filter(p => p.price >= domain[0] && p.price <= domain[1]);
  const maxima = visible.map(p => tab === 'age' ? active.reduce((s, a) => s + p.massByAge[a.i] * 100, 0) : p.concentration_pct);
  if (overlay?.status === 'ready') maxima.push(...overlay.points.filter(p => p.price >= domain[0] && p.price <= domain[1]).map(p => p.concentration_pct));
  const empty = chip.status !== 'ready' ? '筹码输入未就绪' : tab === 'age' && !active.length ? '未选择筹码分层' : '';
  return { backgroundColor: 'transparent', animation: false,
    tooltip: { trigger: 'item', backgroundColor: palette.surface, borderColor: palette.grid, textStyle: { color: palette.text, fontSize: 11 }, formatter: p => p.seriesType === 'custom' ? `${e(p.seriesName)} · 估算<br>价格 ${fmt(p.data[2])}<br>占比 ${fmt(p.data[1] - p.data[0])}%` : e(p.seriesName) },
    grid: { left: 0, right: 2, top: 0, bottom: 0, containLabel: false },
    xAxis: { type: 'value', min: 0, max: Math.max(.001, ...maxima) * 1.06, axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
    yAxis: { type: 'value', min: domain[0], max: domain[1], axisLabel: { show: false }, axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false } },
    graphic: empty ? [{ type: 'text', left: 'center', top: 'middle', style: { text: empty, fill: palette.muted, font: '11px sans-serif', textAlign: 'center' } }] : [], series,
  };
}
