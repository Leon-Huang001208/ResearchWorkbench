(function () {
  const state = {};
  let activeOptionsSnapshotId = null;

  function isFiniteNumber(v) { return typeof v === 'number' && Number.isFinite(v); }
  function chgClass(v) { return !isFiniteNumber(v) ? 'neutral' : v >= 0 ? 'up' : 'down'; }
  function chgTxt(v) { return !isFiniteNumber(v) ? '—' : (v >= 0 ? '+' : '') + v.toFixed(2) + '%'; }
  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
  function importantTag(item) { return item.important ? '<span class="breaking-tag">要闻</span>' : ''; }

  async function loadAll() {
    const [market, news, timeline, framework, logic, reports, signal, topics, calendar, goldHistory, marketChart, assetPerformance, supplyDemand, goldhubCharts, fedCycle, macroRelations, optionsQuant, quantStrategy, strategyDecision, backtest] = await Promise.all([
      fetch('data/market.json').then(r => r.json()),
      fetch('data/news.json').then(r => r.json()),
      fetch('data/timeline.json').then(r => r.json()),
      fetch('data/framework.json').then(r => r.json()),
      fetch('data/logic.json').then(r => r.json()),
      fetch('data/reports.json').then(r => r.json()),
      fetch('data/signal.json').then(r => r.json()),
      fetch('data/topics.json').then(r => r.json()),
      fetch('data/calendar.json').then(r => r.json()),
      fetch('data/gold-history.json').then(r => r.json()),
      fetch('data/market-chart.json').then(r => r.json()),
      fetch('data/asset-performance.json').then(r => r.json()),
      fetch('data/supply-demand.json').then(r => r.json()),
      fetch('data/goldhub-charts.json').then(r => r.json()),
      fetch('data/fed-cycle.json').then(r => r.json()),
      fetch('data/macro-relations.json').then(r => r.json()),
      fetch('data/options-quant.json').then(r => r.json()),
      fetch('data/quant-strategy.json').then(r => r.json()),
      fetch('data/strategy-decision.json').then(r => r.json()),
      fetch('data/backtest.json').then(r => r.json()),
    ]);
    Object.assign(state, { market, news, timeline, framework, logic, reports, signal, topics, calendar, goldHistory, marketChart, assetPerformance, supplyDemand, goldhubCharts, fedCycle, macroRelations, optionsQuant, quantStrategy, strategyDecision, backtest });
  }

  function formatOptionsNumber(value, digits = 2) {
    if (!isFiniteNumber(value)) return '—';
    return `${value > 0 ? '+' : ''}${value.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
  }

  function compactOptionsNumber(value) {
    if (!isFiniteNumber(value)) return '—';
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}m`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}k`;
    return String(value);
  }

  function renderOptionsStrikeChart(snapshot) {
    const rows = [...snapshot.strikes].sort((a, b) => a.strike - b.strike || a.type.localeCompare(b.type));
    const width = 1440;
    const height = 210;
    const margin = { top: 24, right: 28, bottom: 44, left: 64 };
    const baseline = 110;
    const plotWidth = width - margin.left - margin.right;
    const maxOi = Math.max(...rows.map(row => row.openInterest), 1);
    const slot = plotWidth / rows.length;
    const barWidth = Math.min(44, Math.max(18, slot * .42));
    const yScale = value => value / maxOi * 68;
    const toneColor = row => row.bias === 'bull' ? 'var(--up)' : row.bias === 'bear' ? 'var(--down)' : 'var(--gold)';
    return `<svg class="options-strike-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(snapshot.label)}关键行权价持仓变化">
      <line class="options-strike-zero" x1="${margin.left}" x2="${width - margin.right}" y1="${baseline}" y2="${baseline}"></line>
      <text class="options-svg-caption" x="${margin.left}" y="15">未平仓量 OI（张）</text>
      <text class="options-svg-caption" x="${width - margin.right}" y="15" text-anchor="end">红：偏多　绿：偏空　金：待确认</text>
      ${rows.map((row, index) => {
        const x = margin.left + slot * index + slot / 2;
        const barHeight = yScale(row.openInterest);
        const y = baseline - barHeight;
        const valueY = y - 5;
        return `<g class="options-strike-mark" tabindex="0" role="button" aria-label="${esc(`${row.strike} ${row.type}，OI ${row.openInterest}张，${row.signal}`)}">
          <rect x="${x - barWidth / 2}" y="${y}" width="${barWidth}" height="${Math.max(2, barHeight)}" rx="3" fill="${toneColor(row)}"></rect>
          <text class="options-strike-value" x="${x}" y="${valueY}" text-anchor="middle">${compactOptionsNumber(row.openInterest)}</text>
          <text class="options-strike-label" x="${x}" y="${height - 30}" text-anchor="middle">${row.strike}</text>
          <text class="options-strike-type ${row.type.toLowerCase()}" x="${x}" y="${height - 13}" text-anchor="middle">${row.type}</text>
          <title>${esc(`${row.signal}｜IV ${formatOptionsNumber(row.iv)}%｜Delta ${formatOptionsNumber(row.delta, 3)}｜${row.note}`)}</title>
        </g>`;
      }).join('')}
    </svg>`;
  }

  function renderOptionsQuant() {
    const data = state.optionsQuant;
    const root = document.getElementById('optionsMonitor');
    if (!root || !data?.snapshots?.length) return;
    const snapshot = data.snapshots.find(item => item.id === activeOptionsSnapshotId) || data.snapshots[0];
    activeOptionsSnapshotId = snapshot.id;
    const weightedScore = Math.round(snapshot.metrics.reduce((total, metric) => {
      const weight = data.methodology.weights.find(item => item.key === metric.key)?.weight || 0;
      return total + metric.score * weight / 100;
    }, 0));
    const scorePosition = Math.max(0, Math.min(100, (weightedScore + 100) / 2));
    const scoreClass = weightedScore >= data.methodology.bullishThreshold ? 'bull' : weightedScore <= data.methodology.bearishThreshold ? 'bear' : 'neutral';
    const stateLabel = snapshot.dataState === 'delayed-live' ? '延迟实时链' : '最后有效快照';
    const status = document.getElementById('optionsStatus');
    if (status) status.innerHTML = `<span class="options-status-dot"></span><span>${esc(data.statusLabel)}</span><strong>${esc(snapshot.updatedAt)}</strong>`;

    root.innerHTML = `
      <div class="options-snapshot-bar" aria-label="选择监控快照">
        <div class="options-snapshot-copy">
          <span>${esc(data.market)}</span>
          <strong>${esc(snapshot.expiry)}</strong>
        </div>
        <div class="options-snapshot-switch">
          ${data.snapshots.map(item => `<button class="${item.id === snapshot.id ? 'active' : ''}" data-options-snapshot="${esc(item.id)}" aria-pressed="${item.id === snapshot.id}">${esc(item.label)}</button>`).join('')}
        </div>
      </div>

      <section class="options-hero card">
        <div class="options-score-block">
          <div class="options-score-kicker"><span>${esc(stateLabel)}</span><span>置信度 ${snapshot.composite.confidence}%</span></div>
          <div class="options-score-line">
            <strong class="${scoreClass}">${weightedScore > 0 ? '+' : ''}${weightedScore}</strong>
            <div><span>黄金期权复合信号</span><h2>${esc(snapshot.composite.signal)}</h2></div>
          </div>
          <div class="options-score-track" aria-label="复合信号从负100到正100，当前${weightedScore}">
            <span class="options-score-zone bear"></span><span class="options-score-zone neutral"></span><span class="options-score-zone bull"></span>
            <i style="left:${scorePosition}%"></i>
          </div>
          <div class="options-score-scale"><span>-100 偏空</span><span>0</span><span>+100 偏多</span></div>
        </div>
        <div class="options-hero-reading">
          <span class="options-action ${scoreClass}">${esc(snapshot.composite.action)}</span>
          <p>${esc(snapshot.composite.summary)}</p>
          <dl>
            <div><dt>标的</dt><dd>${esc(snapshot.underlying)}${snapshot.underlyingPrice ? ` · ${snapshot.underlyingPrice.toLocaleString('zh-CN')}` : ''}</dd></div>
            <div><dt>正式更新</dt><dd>${esc(data.confirmedCadence)}</dd></div>
            <div><dt>盘中预览</dt><dd>${esc(data.provisionalCadence)}</dd></div>
          </dl>
        </div>
      </section>

      <section class="options-level-grid" aria-label="关键行权价区域">
        ${snapshot.levels.map(level => `<article class="options-level-card ${esc(level.tone)}">
          <span>${esc(level.label)}</span><strong>${esc(level.value)}</strong><p>${esc(level.note)}</p>
        </article>`).join('')}
      </section>

      <section class="options-metric-grid" aria-label="期权五维信号">
        ${snapshot.metrics.map(metric => `<article class="card options-metric-card ${esc(metric.tone)}">
          <div class="options-metric-top"><span>${esc(metric.eyebrow)}</span><b>${formatOptionsNumber(metric.score, 0)}</b></div>
          <h3>${esc(metric.label)}</h3>
          <strong>${esc(metric.value)}</strong>
          <small>${esc(metric.unit)}</small>
          <div class="options-metric-verdict"><i></i>${esc(metric.judgment)}</div>
          <p>${esc(metric.detail)}</p>
        </article>`).join('')}
      </section>

      <section class="card options-strike-card">
        <div class="options-card-head">
          <div><span class="options-section-index">01</span><div><p class="card-label">关键行权价压力图</p><h3>筹码往哪里移动，压力与防守就在哪里形成</h3></div></div>
          <span>${esc(snapshot.tradeDate)} · ${esc(snapshot.expiry)}</span>
        </div>
        <div class="options-strike-chart">${renderOptionsStrikeChart(snapshot)}</div>
      </section>

      <section class="card options-table-card">
        <div class="options-card-head">
          <div><span class="options-section-index">02</span><div><p class="card-label">行权价诊断</p><h3>OI、成交、IV、Delta 与盘口</h3></div></div>
          <span>Cboe 延迟期权链</span>
        </div>
        <div class="options-table-scroll">
          <table class="options-data-table">
            <thead><tr><th>期权</th><th>行权价</th><th>OI</th><th>成交</th><th>买价</th><th>卖价</th><th>IV</th><th>相对IV</th><th>Delta</th><th>关键识别</th><th>研判</th></tr></thead>
            <tbody>${snapshot.strikes.map(row => `<tr>
              <td><span class="options-type ${row.type.toLowerCase()}">${esc(row.type)}</span></td>
              <td><strong>${row.strike.toLocaleString('zh-CN')}</strong></td>
              <td class="mono">${row.openInterest.toLocaleString('zh-CN')}</td>
              <td class="mono">${row.volume.toLocaleString('zh-CN')}</td>
              <td class="mono">${row.bid.toFixed(2)}</td>
              <td class="mono">${row.ask.toFixed(2)}</td>
              <td class="mono">${row.iv.toFixed(2)}%</td>
              <td class="mono">${formatOptionsNumber(row.relativeIv)}pp</td>
              <td class="mono">${formatOptionsNumber(row.delta, 3)}</td>
              <td><span class="options-bias ${esc(row.bias)}">${esc(row.signal)}</span></td>
              <td>${esc(row.note)}</td>
            </tr>`).join('')}</tbody>
          </table>
        </div>
      </section>

      <section class="options-method-grid">
        <div class="card options-rules-card">
          <div class="options-card-head">
            <div><span class="options-section-index">03</span><div><p class="card-label">指标阅读顺序</p><h3>从筹码位置到尾部定价</h3></div></div>
          </div>
          <div class="options-rule-grid">
            ${data.readingGuide.map(item => `<div class="options-rule"><span>${esc(item.key)}</span><b>${esc(item.title)}</b><p>${esc(item.detail)}</p></div>`).join('')}
          </div>
        </div>
        <aside class="card options-method-card">
          <span class="options-section-index">04</span>
          <p class="card-label">复合评分方法</p>
          <h3>方向与热度分开判断</h3>
          <div class="options-weight-list">${data.methodology.weights.map(item => `<div><span>${esc(item.label)}</span><strong>${item.weight}%</strong></div>`).join('')}</div>
          <p>${esc(data.methodology.note)}</p>
          <div class="options-thresholds"><span>≥ +${data.methodology.bullishThreshold}　偏多</span><span>≤ ${data.methodology.bearishThreshold}　偏空</span></div>
        </aside>
      </section>

      <section class="card options-source-card">
        <div class="options-source-intro"><div><p class="card-label">数据来源与更新边界</p><h3>每天 14:30 读取最新 GLD 期权链</h3></div><p>北京时间更新；OI 使用最近美股交易日确认值。失联时保留最后有效快照。</p></div>
        <div class="options-source-list">${data.sources.map(source => source.url
          ? `<a href="${esc(source.url)}" target="_blank" rel="noopener"><strong>${esc(source.name)}</strong><span>${esc(source.detail)}</span><i class="ti ti-external-link"></i></a>`
          : `<div><strong>${esc(source.name)}</strong><span>${esc(source.detail)}</span><i class="ti ti-file-description"></i></div>`).join('')}</div>
      </section>`;

    root.querySelectorAll('[data-options-snapshot]').forEach(button => {
      button.addEventListener('click', () => {
        activeOptionsSnapshotId = button.dataset.optionsSnapshot;
        renderOptionsQuant();
      });
    });
  }

  function renderStrategyDecision() {
    const root = document.getElementById('strategyDecision');
    const data = state.strategyDecision;
    if (!root) return;
    if (!data) { root.innerHTML = ''; return; }
    const tone = data.strength >= 1 ? 'bull' : data.strength <= -1 ? 'bear' : 'neutral';
    const dots = Array.from({ length: 11 }, (_, index) => {
      const value = index - 5;
      const cls = value <= -1 ? 'bear' : value >= 1 ? 'bull' : 'neutral';
      return `<i class="strategy-dot ${cls} ${value === data.strength ? 'active' : ''}">${value > 0 ? `+${value}` : value}</i>`;
    }).join('');
    const positionCards = Object.values(data.positions).map(item => `
      <article class="strategy-position-card">
        <span>${esc(item.label)}</span>
        <strong>${item.value}%</strong>
        <small>${esc(item.note)}</small>
      </article>`).join('');
    const factorTags = list => list.map(item =>
      `<span class="${item.contribution >= 0 ? 'bull' : 'bear'}">${esc(item.name)} ${item.contribution > 0 ? '+' : ''}${Number(item.contribution).toFixed(3)}</span>`).join('');
    root.innerHTML = `
      <section class="card strategy-decision">
        <div class="strategy-decision-head">
          <div>
            <p class="card-label">今日加减仓决策</p>
            <h2>14:50 强度分 · 收盘前下单</h2>
          </div>
          <div class="strategy-decision-stamp">模型读数 ${esc(data.modelUpdatedAt)}<br>决策生成 ${esc(data.updatedAt)}</div>
        </div>
        <div class="strategy-decision-body">
          <div class="strategy-strength">
            <b class="${tone}">${data.strength > 0 ? '+' : ''}${data.strength}</b>
            <span>${esc(data.action)} · ${esc(data.level)}档</span>
            <small>${data.changePp === 0 ? '今天保持现有仓位' : `${data.changePp > 0 ? '计划加仓' : '计划减仓'} ${Math.abs(data.changePp)} 个百分点`}</small>
          </div>
          <div class="strategy-scale">
            <div class="strategy-dots">${dots}</div>
            <div class="strategy-scale-labels"><span>-5 满档减仓</span><span>0 不动</span><span>+5 满档加仓</span></div>
          </div>
        </div>
        <div class="strategy-positions">${positionCards}</div>
        <div class="strategy-reason">
          <p>${esc(data.summary)}</p>
          <p class="strategy-factors"><span class="strategy-factor-label">主要支撑</span>${factorTags(data.supporting)}</p>
          <p class="strategy-factors"><span class="strategy-factor-label">主要拖累</span>${factorTags(data.dragging)}</p>
          <p class="strategy-regime">机制：${esc(data.regime.label)} · 52周相关系数 ${data.regime.correlation}</p>
        </div>
        <p class="source-note">${esc(data.scale.rule)}。${esc(data.note)}</p>
      </section>`;
  }

  function backtestCurve(chart) {
    const width = 1180;
    const height = 330;
    const margin = { top: 18, right: 92, bottom: 30, left: 76 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const length = chart.dates.length;
    const stride = Math.max(1, Math.ceil(length / 700));
    const picked = [];
    for (let index = 0; index < length; index += stride) picked.push(index);
    if (picked.at(-1) !== length - 1) picked.push(length - 1);
    const lines = [
      { key: 'benchmark', label: '买入持有', cls: 'benchmark' },
      { key: 'strategy', label: '规则A · 分批加减仓', cls: 'strategy' },
      { key: 'target', label: '规则C · 目标仓位型', cls: 'target' },
      { key: 'overlay', label: '规则B · 满仓打底', cls: 'overlay' },
    ];
    const all = lines.flatMap(line => chart[line.key]);
    const max = Math.max(...all);
    const min = Math.min(...all);
    const top = Math.ceil(max / 50000) * 50000;
    const bottom = Math.floor(min / 50000) * 50000;
    const x = index => margin.left + (plotWidth * index) / (length - 1);
    const y = value => margin.top + plotHeight - ((value - bottom) / (top - bottom)) * plotHeight;
    const grid = Array.from({ length: 6 }, (_, step) => {
      const value = bottom + ((top - bottom) * step) / 5;
      return `<line class="bt-grid" x1="${margin.left}" x2="${width - margin.right}" y1="${y(value).toFixed(1)}" y2="${y(value).toFixed(1)}"></line>
        <text class="bt-axis" x="${margin.left - 10}" y="${(y(value) + 3).toFixed(1)}" text-anchor="end">${(value / 10000).toFixed(0)}万</text>`;
    }).join('');
    const yearTicks = [];
    chart.dates.forEach((date, index) => {
      if (!date.endsWith('-01-01')) return;
      if (yearTicks.length && index - yearTicks.at(-1).index < 12) return;
      yearTicks.push({ index, date });
    });
    const yearGrid = yearTicks.map(tick =>
      `<line class="bt-grid bt-grid-year" x1="${x(tick.index).toFixed(1)}" x2="${x(tick.index).toFixed(1)}" y1="${margin.top}" y2="${margin.top + plotHeight}"></line>
       <text class="bt-axis" x="${x(tick.index).toFixed(1)}" y="${height - 10}" text-anchor="middle">${tick.date.slice(0, 4)}</text>`).join('');
    const paths = lines.map(line => {
      const points = picked.map(index => `${x(index).toFixed(1)},${y(chart[line.key][index]).toFixed(1)}`).join(' ');
      return `<polyline class="bt-line ${line.cls}" points="${points}"></polyline>`;
    }).join('');
    const legend = lines.map((line, index) => {
      const value = chart[line.key].at(-1);
      return `<g transform="translate(${width - margin.right + 12}, ${margin.top + 16 + index * 34})">
        <line class="bt-line ${line.cls}" x1="0" x2="22" y1="0" y2="0"></line>
        <text class="bt-legend-label" x="0" y="12">${esc(line.label)}</text>
        <text class="bt-legend-value" x="0" y="25">${(value / 10000).toFixed(2)}万</text>
      </g>`;
    }).join('');
    return `<svg class="bt-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="策略与买入持有净值对比">
      ${grid}${yearGrid}${paths}
      <line class="bt-axis-line" x1="${margin.left}" x2="${width - margin.right}" y1="${margin.top + plotHeight}" y2="${margin.top + plotHeight}"></line>
      ${legend}
    </svg>`;
  }

  function renderStrategyBacktest() {
    const root = document.getElementById('strategyBacktest');
    const data = state.backtest;
    if (!root) return;
    if (!data) { root.innerHTML = ''; return; }
    const order = ['target', 'strategy', 'overlay', 'benchmark'];
    const rows = order.map(key => {
      const item = data.metrics[key];
      return `<tr class="${key === 'strategy' ? 'bt-row-highlight' : ''}">
        <td>${esc(item.label || key)}</td>
        <td class="mono">${(item.finalValue / 10000).toFixed(2)}万</td>
        <td class="mono ${item.totalReturn >= 0 ? 'bull' : 'bear'}">${item.totalReturn >= 0 ? '+' : ''}${item.totalReturn}%</td>
        <td class="mono">${item.annualised}%</td>
        <td class="mono">${item.maxDrawdown}%</td>
        <td class="mono">${item.volatility}%</td>
        <td class="mono">${item.sharpe}</td>
        <td class="mono">${item.winMonths}%</td>
        <td class="mono">${item.averagePosition}%</td>
        <td class="mono">${item.trades}</td>
      </tr>`;
    }).join('');
    const monthly = data.monthly.slice(-24).map(row => `<tr>
      <td class="mono">${esc(row.month)}</td>
      <td class="mono ${row.strategy >= 0 ? 'bull' : 'bear'}">${row.strategy >= 0 ? '+' : ''}${row.strategy}%</td>
      <td class="mono ${row.target >= 0 ? 'bull' : 'bear'}">${row.target >= 0 ? '+' : ''}${row.target}%</td>
      <td class="mono ${row.benchmark >= 0 ? 'bull' : 'bear'}">${row.benchmark >= 0 ? '+' : ''}${row.benchmark}%</td>
      <td class="mono">${row.diff >= 0 ? '+' : ''}${row.diff}%</td>
    </tr>`).join('');
    const comparison = data.metrics.comparison;
    const conclusion = comparison.excessReturn < 0
      ? `在 ${data.meta.start} 至 ${data.meta.end} 的样本里，规则A 的总收益比满仓买入持有低 ${Math.abs(comparison.excessReturn).toLocaleString('zh-CN')} 元（${Math.abs(comparison.monthWinRateDiff)} 个百分点的月度胜率差），但最大回撤改善 ${comparison.drawdownImprovement} 个百分点、年化波动低 ${(data.metrics.benchmark.volatility - data.metrics.strategy.volatility).toFixed(2)} 个百分点。`
      : `在 ${data.meta.start} 至 ${data.meta.end} 的样本里，规则A 跑赢满仓买入持有 ${comparison.excessReturn.toLocaleString('zh-CN')} 元。`;
    root.innerHTML = `
      <section class="card strategy-backtest">
        <div class="strategy-decision-head">
          <div>
            <p class="card-label">策略回测</p>
            <h2>10 万本金 · ${esc(data.meta.start)} → ${esc(data.meta.end)}</h2>
          </div>
          <div class="strategy-decision-stamp">${esc(data.meta.fundLabel)}<br>更新 ${esc(data.updatedAt)}</div>
        </div>
        <div class="bt-chart-wrap">${backtestCurve(data.series)}</div>
        <div class="table-wrap bt-table-wrap">
          <table class="bt-table">
            <thead><tr>
              <th>规则</th><th>期末资产</th><th>总收益</th><th>年化</th><th>最大回撤</th><th>年化波动</th><th>夏普</th><th>月度胜率</th><th>平均仓位</th><th>交易次数</th>
            </tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <p class="bt-conclusion">${conclusion}</p>
        <details class="bt-monthly">
          <summary>近 24 个月逐月对比</summary>
          <div class="table-wrap">
            <table class="bt-table">
              <thead><tr><th>月份</th><th>规则A</th><th>规则C</th><th>买入持有</th><th>规则A − 买入持有</th></tr></thead>
              <tbody>${monthly}</tbody>
            </table>
          </div>
        </details>
        <p class="source-note">
          口径：${esc(data.meta.decisionTime)}；${esc(data.meta.rule)}。<br>
          成本：${esc(data.meta.fees)}。<br>
          严谨性：${esc(data.meta.lags)}；${esc(data.meta.proxies)}。<br>
          标的：${esc(data.meta.fundNote)}。历史回测不代表未来表现。
        </p>
      </section>`;
  }

  function renderQuantStrategy() {
    const data = state.quantStrategy;
    const root = document.getElementById('quantStrategy');
    if (!root || !data?.factors?.length) return;
    const actionClass = data.action === '加仓' ? 'bull' : data.action === '止盈' ? 'bear' : 'neutral';
    const scorePosition = Math.max(0, Math.min(100, (data.score + 1) * 50));
    const maxContribution = Math.max(...data.factors.filter(item => !item.monitorOnly).map(item => Math.abs(item.contribution)), .01);
    const dimensionLabel = Object.fromEntries(data.dimensions.map(item => [item.key, item.label]));
    const factorRows = data.factors.map(item => `<tr>
      <td><span class="quant-dimension-tag">${esc(dimensionLabel[item.dimension])}</span></td>
      <td><strong>${esc(item.name)}</strong>${item.proxy ? '<small>公开代理</small>' : item.monitorOnly ? '<small>仅监控</small>' : ''}</td>
      <td class="mono">${esc(item.value)}</td>
      <td class="mono ${item.tone}">${item.monitorOnly ? '—' : formatOptionsNumber(item.score)}</td>
      <td class="mono ${item.contribution > 0 ? 'bull' : item.contribution < 0 ? 'bear' : 'neutral'}">${item.monitorOnly ? '—' : formatOptionsNumber(item.contribution, 3)}</td>
      <td>${esc(item.note)}</td>
      <td><span class="quant-date">${esc(item.date)}</span><a href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.source)}<i class="ti ti-external-link"></i></a></td>
    </tr>`).join('');

    root.innerHTML = `
      <section class="card quant-hero">
        <div class="quant-hero-score">
          <div class="quant-eyebrow"><span>当日模型读数</span><strong>${esc(data.updatedAt)}</strong></div>
          <div class="quant-score-line"><b class="${actionClass}">${data.score > 0 ? '+' : ''}${data.score.toFixed(2)}</b><div><span>${esc(data.modelView)}</span><h2>${esc(data.action)}</h2></div></div>
          <div class="quant-score-track" aria-label="模型分数${data.score.toFixed(2)}"><span></span><span></span><span></span><i style="left:${scorePosition}%"></i></div>
          <div class="quant-score-scale"><span>≤ -0.30 止盈</span><span>中性区</span><span>≥ +0.30 加仓</span></div>
        </div>
        <div class="quant-decision ${actionClass}">
          <span>15:00 前场外基金操作</span>
          <strong>${esc(data.action)}</strong>
          <p>${esc(data.summary)}</p>
          <dl><div><dt>判断时点</dt><dd>${esc(data.decisionTime)}</dd></div><div><dt>研判周期</dt><dd>${esc(data.horizon)}</dd></div><div><dt>机制状态</dt><dd>${esc(data.regime.label)}</dd></div></dl>
        </div>
      </section>

      <section class="quant-dimension-grid" aria-label="四维模型读数">
        ${data.dimensions.map(item => `<article class="card quant-dimension-card ${esc(item.tone)}">
          <div><span>${esc(item.label)}</span><em>${item.weight}%</em></div>
          <strong>${formatOptionsNumber(item.score)}</strong>
          <p>综合贡献 ${formatOptionsNumber(item.contribution, 3)}</p>
          <small>${esc(item.driver)}</small>
        </article>`).join('')}
      </section>

      <section class="quant-analysis-grid">
        <article class="card quant-contribution-card">
          <div class="options-card-head"><div><span class="options-section-index">01</span><div><p class="card-label">因子贡献图</p><h3>今天的分数由什么推高、由什么拖累</h3></div></div><span>贡献至综合分</span></div>
          <div class="quant-contribution-chart">
            ${data.factors.filter(item => !item.monitorOnly).map(item => {
              const width = Math.max(1, Math.abs(item.contribution) / maxContribution * 48);
              return `<div class="quant-contribution-row" title="${esc(`${item.name}：${formatOptionsNumber(item.contribution, 3)}`)}"><span>${esc(item.short)}</span><div class="quant-contribution-axis"><i class="${item.contribution >= 0 ? 'positive' : 'negative'}" style="width:${width}%;${item.contribution >= 0 ? 'left:50%' : `right:50%`}"></i></div><b class="${item.contribution > 0 ? 'bull' : item.contribution < 0 ? 'bear' : 'neutral'}">${formatOptionsNumber(item.contribution, 3)}</b></div>`;
            }).join('')}
          </div>
        </article>
        <aside class="card quant-regime-card">
          <div class="options-card-head"><div><span class="options-section-index">02</span><div><p class="card-label">机制切换层</p><h3>${esc(data.regime.label)}</h3></div></div></div>
          <div class="quant-regime-reading"><span>52周相关系数</span><strong>${formatOptionsNumber(data.regime.correlation)}</strong></div>
          <div class="quant-regime-scale"><span>利率主导</span><i style="left:${Math.max(0, Math.min(100, (data.regime.correlation + .6) / .9 * 100))}%"></i><span>利率脱敏</span></div>
          <p>${esc(data.regime.rule)}</p>
          <div class="quant-regime-note">当前若处于利率脱敏，基本面内部将下调实际利率与美元权重，上调央行购金权重。</div>
        </aside>
      </section>

      <section class="card quant-factor-card">
        <div class="options-card-head"><div><span class="options-section-index">03</span><div><p class="card-label">完整因子体系与当前读数</p><h3>13个计分因子 + 1个风险监控项</h3></div></div><span>红色支撑 · 绿色拖累</span></div>
        <div class="quant-table-scroll"><table class="quant-factor-table"><thead><tr><th>维度</th><th>因子</th><th>当前读数</th><th>标准分</th><th>综合贡献</th><th>当前解释</th><th>日期 / 来源</th></tr></thead><tbody>${factorRows}</tbody></table></div>
      </section>

      <section class="quant-method-grid">
        <article class="card quant-method-card">
          <div><span class="options-section-index">04</span><p class="card-label">模型计算链</p></div>
          <div class="quant-method-steps">${data.methodology.steps.map((step, index) => `<span><b>${String(index + 1).padStart(2, '0')}</b>${esc(step)}</span>`).join('')}</div>
          <p>${esc(data.methodology.note)}</p>
        </article>
        <aside class="card quant-source-card">
          <span class="options-section-index">05</span><p class="card-label">可钻取数据来源</p>
          <div>${data.sources.map(source => `<a href="${esc(source.url)}" target="_blank" rel="noopener"><strong>${esc(source.name)}</strong><span>${esc(source.detail)}</span><i class="ti ti-external-link"></i></a>`).join('')}</div>
        </aside>
      </section>

      <p class="quant-disclaimer">模型用于统一当日决策纪律，不构成个性化投资建议；场外基金按14:30读数执行时，仍需结合自身仓位、申购截止时间和风险承受能力。</p>`;
  }

  function bindOptionsTabs() {
    document.querySelectorAll('[data-options-panel]').forEach(button => {
      button.addEventListener('click', () => {
        const panel = button.dataset.optionsPanel;
        document.querySelectorAll('[data-options-panel]').forEach(item => {
          const active = item === button;
          item.classList.toggle('active', active);
          item.setAttribute('aria-selected', String(active));
        });
        document.querySelectorAll('[data-options-content]').forEach(item => item.classList.toggle('active', item.dataset.optionsContent === panel));
      });
    });
  }

  function renderAllocation() {
    const labels = ['沪深300', '创业板50', '恒生指数', '纳斯达克100', '日经225', '德国DAX', '国债', '黄金AU9999', 'NYMEX原油'];
    const matrix = [
      [1, .82, .67, .16, .34, .22, -.22, .01, .14],
      [.82, 1, .48, .14, .23, .16, -.12, .01, .12],
      [.67, .48, 1, .17, .44, .33, -.22, -.02, .12],
      [.16, .14, .17, 1, .18, .49, -.03, .01, .18],
      [.34, .23, .44, .18, 1, .37, -.07, -.04, .11],
      [.22, .16, .33, .49, .37, 1, -.08, .05, .13],
      [-.22, -.12, -.22, -.03, -.07, -.08, 1, .14, -.08],
      [.01, .01, -.02, .01, -.04, .05, .14, 1, -.01],
      [.14, .12, .12, .18, .11, .13, -.08, -.01, 1],
    ];
    const matrixRoot = document.getElementById('allocationCorrelationMatrix');
    matrixRoot.innerHTML = `<div class="allocation-matrix-wrap"><table class="allocation-matrix"><thead><tr><th></th>${labels.map(label => `<th class="${label.includes('黄金') ? 'gold' : ''}">${esc(label)}</th>`).join('')}</tr></thead><tbody>${matrix.map((row, rowIndex) => `<tr><th class="${labels[rowIndex].includes('黄金') ? 'gold' : ''}">${esc(labels[rowIndex])}</th>${row.map((value, columnIndex) => {
      const alpha = value === 1 ? .58 : Math.min(.48, .08 + Math.abs(value) * .48);
      const color = value >= 0 ? `rgba(194, 81, 65, ${alpha})` : `rgba(75, 115, 164, ${alpha})`;
      return `<td style="background:${color}" title="${esc(`${labels[rowIndex]} × ${labels[columnIndex]}`)}">${value.toFixed(2)}</td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div>`;

    const diversificationRoot = document.getElementById('allocationDiversificationChart');
    const dWidth = 700;
    const dHeight = 390;
    const dMargin = { top: 24, right: 24, bottom: 54, left: 58 };
    const dPlotW = dWidth - dMargin.left - dMargin.right;
    const dPlotH = dHeight - dMargin.top - dMargin.bottom;
    const correlations = [
      { name: '相关性 0.6', color: '#9b7730', values: [10, 9.15, 8.65, 8.35, 8.15, 8.05, 8.0, 7.95, 7.95, 7.9, 7.9, 7.9, 7.85, 7.85, 7.85, 7.85, 7.85] },
      { name: '相关性 0.4', color: '#b36a49', values: [10, 8.75, 8.0, 7.55, 7.25, 7.05, 6.9, 6.82, 6.75, 6.7, 6.65, 6.62, 6.6, 6.58, 6.55, 6.52, 6.5] },
      { name: '相关性 0.2', color: '#8c826d', values: [10, 8.2, 7.05, 6.25, 5.7, 5.35, 5.25, 5.05, 4.9, 4.82, 4.75, 4.68, 4.65, 4.58, 4.55, 4.5] },
      { name: '相关性 0', color: '#c99e1d', values: [10, 7.55, 5.7, 4.25, 3.55, 3.0, 2.72, 2.5, 2.25, 2.12, 2.05] },
      { name: '相关性 -0.2', color: '#7895aa', values: [10, 7.1, 5.15, 3.55, 2.0, 1.5] },
      { name: '相关性 -0.4', color: '#6c8e45', values: [10, 6.2, 2.8, 1.2] },
    ];
    const dx = index => dMargin.left + index / 16 * dPlotW;
    const dy = value => dMargin.top + (12 - value) / 12 * dPlotH;
    diversificationRoot.innerHTML = `<svg class="allocation-svg" viewBox="0 0 ${dWidth} ${dHeight}" role="img" aria-label="组合波动率与资产数量及相关性关系">
      ${[0, 2, 4, 6, 8, 10, 12].map(value => `<line class="allocation-grid" x1="${dMargin.left}" x2="${dWidth - dMargin.right}" y1="${dy(value)}" y2="${dy(value)}"></line><text class="allocation-axis" x="${dMargin.left - 10}" y="${dy(value) + 4}" text-anchor="end">${value}%</text>`).join('')}
      ${Array.from({ length: 17 }, (_, index) => `<text class="allocation-axis" x="${dx(index)}" y="${dHeight - 27}" text-anchor="middle">${index + 1}</text>`).join('')}
      ${correlations.map(item => `<polyline class="allocation-line" stroke="${item.color}" points="${item.values.map((value, index) => `${dx(index)},${dy(value)}`).join(' ')}"></polyline>`).join('')}
      <text class="allocation-axis-title" x="${dMargin.left}" y="15">组合波动率</text>
      <text class="allocation-axis-title" x="${dWidth - dMargin.right}" y="${dHeight - 8}" text-anchor="end">资产数量</text>
    </svg><div class="allocation-legend">${correlations.map(item => `<span><i style="background:${item.color}"></i>${item.name}</span>`).join('')}</div>`;

    const frontierRoot = document.getElementById('allocationFrontierChart');
    const fWidth = 700;
    const fHeight = 390;
    const fMargin = { top: 28, right: 24, bottom: 52, left: 58 };
    const fPlotW = fWidth - fMargin.left - fMargin.right;
    const fPlotH = fHeight - fMargin.top - fMargin.bottom;
    const fx = value => fMargin.left + (value - 4) / 10 * fPlotW;
    const fy = value => fMargin.top + (8.5 - value) / 4.5 * fPlotH;
    const withoutGold = [[5,4.7],[5.5,4.9],[6,5.1],[6.5,5.3],[7,5.5],[7.5,5.65],[8.1,5.82],[8.6,6],[9.1,6.18],[9.6,6.3],[10.1,6.5],[10.6,6.65],[11.1,6.8],[11.6,6.92],[12.1,7.1],[12.6,7.2],[13.1,7.35]];
    const withGold = withoutGold.map(([volatility, returns], index) => [volatility, Number((returns + .3 + index * .04).toFixed(2))]);
    frontierRoot.innerHTML = `<svg class="allocation-svg" viewBox="0 0 ${fWidth} ${fHeight}" role="img" aria-label="加入黄金前后的组合有效前沿">
      <defs><marker id="allocationArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 Z" fill="currentColor"></path></marker></defs>
      ${[4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5].map(value => `<line class="allocation-grid" x1="${fMargin.left}" x2="${fWidth - fMargin.right}" y1="${fy(value)}" y2="${fy(value)}"></line><text class="allocation-axis" x="${fMargin.left - 10}" y="${fy(value) + 4}" text-anchor="end">${value.toFixed(1)}%</text>`).join('')}
      ${[4, 6, 8, 10, 12, 14].map(value => `<text class="allocation-axis" x="${fx(value)}" y="${fHeight - 25}" text-anchor="middle">${value}%</text>`).join('')}
      ${withoutGold.map(([volatility, returns]) => `<circle class="frontier-dot without" cx="${fx(volatility)}" cy="${fy(returns)}" r="6"></circle>`).join('')}
      ${withGold.map(([volatility, returns]) => `<circle class="frontier-dot with" cx="${fx(volatility)}" cy="${fy(returns)}" r="6"></circle>`).join('')}
      <path class="frontier-arrow" d="M${fx(10.7)},${fy(6.68)} L${fx(10.7)},${fy(7.36)}" marker-end="url(#allocationArrow)"></path>
      <path class="frontier-arrow" d="M${fx(10.7)},${fy(6.68)} L${fx(10.05)},${fy(6.68)}" marker-end="url(#allocationArrow)"></path>
      <text class="allocation-axis-title" x="${fMargin.left}" y="16">年化收益率</text>
      <text class="allocation-axis-title" x="${fWidth - fMargin.right}" y="${fHeight - 7}" text-anchor="end">年化波动率</text>
      <text class="frontier-note" x="${fx(8.9)}" y="${fy(7.5)}">同等波动率，提高收益</text>
      <text class="frontier-note" x="${fx(8.3)}" y="${fy(6.45)}">同等收益，降低波动</text>
    </svg><div class="allocation-legend"><span><i class="frontier-without"></i>不含黄金</span><span><i class="frontier-with"></i>加入黄金</span></div>`;

    const fixedReturnRoot = document.getElementById('allocationFixedIncomeReturn');
    const rWidth = 700;
    const rHeight = 390;
    const rMargin = { top: 28, right: 22, bottom: 48, left: 56 };
    const rPlotW = rWidth - rMargin.left - rMargin.right;
    const rPlotH = rHeight - rMargin.top - rMargin.bottom;
    const years = Array.from({ length: 11 }, (_, index) => 2016 + index);
    const fixedSeries = [
      { name: '15%黄金 + 85%债', color: '#a88331', data: [1,1.02,1.05,1.13,1.22,1.23,1.29,1.35,1.42,1.53,1.65] },
      { name: '10%黄金 + 90%债', color: '#b86d48', data: [1,1.015,1.045,1.12,1.20,1.20,1.26,1.32,1.39,1.48,1.56] },
      { name: '5%黄金 + 95%债', color: '#8b816d', data: [1,1.01,1.04,1.11,1.18,1.18,1.23,1.29,1.35,1.42,1.48] },
      { name: '中债1—5年国开行债券指数', color: '#c79c1d', data: [1,1.01,1.045,1.115,1.18,1.16,1.22,1.27,1.32,1.36,1.40] },
    ];
    const rx = index => rMargin.left + index / (years.length - 1) * rPlotW;
    const ry = value => rMargin.top + (1.9 - value) / 1.0 * rPlotH;
    fixedReturnRoot.innerHTML = `<svg class="allocation-svg" viewBox="0 0 ${rWidth} ${rHeight}" role="img" aria-label="不同比例黄金与债券组合累计净值">
      ${[.9, 1.1, 1.3, 1.5, 1.7, 1.9].map(value => `<line class="allocation-grid" x1="${rMargin.left}" x2="${rWidth - rMargin.right}" y1="${ry(value)}" y2="${ry(value)}"></line><text class="allocation-axis" x="${rMargin.left - 9}" y="${ry(value) + 4}" text-anchor="end">${value.toFixed(1)}</text>`).join('')}
      ${years.map((year, index) => `<text class="allocation-axis" x="${rx(index)}" y="${rHeight - 20}" text-anchor="middle">${year}</text>`).join('')}
      ${fixedSeries.map(series => `<polyline class="allocation-line" stroke="${series.color}" points="${series.data.map((value, index) => `${rx(index)},${ry(value)}`).join(' ')}"></polyline>`).join('')}
    </svg><div class="allocation-legend">${fixedSeries.map(series => `<span><i style="background:${series.color}"></i>${series.name}</span>`).join('')}</div>`;

    const riskRoot = document.getElementById('allocationFixedIncomeRisk');
    const allocationColumns = ['100%', '50%', '30%', '20%', '15%', '10%', '5%', '3%', '2%', '1%', '0%'];
    const riskRows = [
      ['黄金比例', ...allocationColumns],
      ['债券比例', '0%', '50%', '70%', '80%', '85%', '90%', '95%', '97%', '98%', '99%', '100%'],
      ['年化收益率', '14.21%', '8.98%', '6.79%', '5.67%', '5.11%', '4.55%', '3.98%', '3.76%', '3.64%', '3.53%', '3.42%'],
      ['年化波动率', '14.75%', '7.42%', '4.52%', '3.09%', '2.40%', '1.74%', '1.18%', '1.02%', '0.96%', '0.92%', '0.91%'],
      ['夏普比率', '0.96', '1.21', '1.50', '1.84', '2.13', '2.62', '3.38', '3.70', '3.80', '3.82', '3.75'],
      ['最大回撤', '-25.61%', '-13.04%', '-7.75%', '-5.05%', '-3.69%', '-3.01%', '-2.67%', '-2.53%', '-2.51%', '-2.58%', '-2.66%'],
    ];
    riskRoot.innerHTML = `<div class="allocation-risk-wrap"><table class="allocation-risk-table"><tbody>${riskRows.map((row, rowIndex) => `<tr>${row.map((value, columnIndex) => {
      const highlighted = (rowIndex === 0 && [5,6,7].includes(columnIndex))
        || (rowIndex === 2 && [5,6,7].includes(columnIndex))
        || (rowIndex === 4 && [9,10].includes(columnIndex))
        || (rowIndex === 5 && [8,9,10].includes(columnIndex));
      return `<${columnIndex === 0 ? 'th' : 'td'} class="${highlighted ? 'highlight' : ''}">${esc(value)}</${columnIndex === 0 ? 'th' : 'td'}>`;
    }).join('')}</tr>`).join('')}</tbody></table></div>`;

    const retailRoot = document.getElementById('allocationRetailTable');
    const institutionRoot = document.getElementById('allocationInstitutionTable');
    const investorSource = document.getElementById('allocationInvestorSource');
    const au9999 = state.market?.spot?.find(item => item.name === '上海金 AU9999');
    const auPrice = Number(au9999?.price) || 0;
    const goldEtf = state.market?.funds?.domestic?.find(item => item.code === '518880');
    const goldStockEtf = state.market?.funds?.domesticGoldStock?.find(item => item.code === '159321');
    const money = value => value ? `¥${Math.round(value).toLocaleString('zh-CN')}` : '—';
    const textCell = value => esc(String(value)).replaceAll('\n', '<br>');
    const investorTable = (headers, rows, className) => `<div class="allocation-table-scroll"><table class="${className}"><thead><tr>${headers.map(header => `<th>${textCell(header)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map((value, index) => `<${index === 0 ? 'th' : 'td'}>${textCell(value)}</${index === 0 ? 'th' : 'td'}>`).join('')}</tr>`).join('')}</tbody></table></div>`;

    const retailHeaders = ['投资渠道', '投资方式', '交易成本', '持有成本', '投资风险', '特点', '投资起点'];
    const retailRows = [
      ['场内券商', '黄金ETF\n（518880）', '买卖佣金同股票\n免印花税', '约0.6%/年', '无杠杆\n跟踪AU9999', '证券账户；T+0交易\n部分会员可换实物', `1手约${money(Number(goldEtf?.price) * 100)}\n对应约1克`],
      ['基金直销\n银行/三方', '黄金ETF联接\nA类：000216\nC类：000217\nI类：022653', '申购费：A类为0\n赎回费：A类持有超7日为0', 'A类约0.6%/年\nC类约0.95%/年', '无杠杆\n跟踪AU9999', '基金账户\n部分平台可换实物', '10元起'],
      ['场内券商', '黄金股ETF\n（159321）', '买卖佣金同股票\n免印花税', '约0.6%/年', '无杠杆\n跟踪黄金股', '证券账户\n黄金股高弹性', `1手约${money(Number(goldStockEtf?.price) * 100)}`],
      ['银行', '黄金积存金', '买入卖出合计\n约0.3%—1%/次', '无', '无杠杆\n跟踪AU9999', '银行账户\n可兑换实物', `1克起\n约${money(auPrice)}`],
      ['银行、金店', '投资金条', '买入溢价2%—3%\n回购折价1%—2%', '实物存储成本', '无杠杆\n跟踪AU9999', '银行实物交割', `5克起\n约${money(auPrice * 5)}`],
      ['金店', '金饰品', '买入溢价20%—30%\n回购折价3%—5%', '实物存储成本', '无杠杆\n跟踪AU9999', '金店实物交割', `5克起\n金价约${money(auPrice * 5)}+工费`],
    ];
    const institutionHeaders = ['品种', '黄金ETF\n（518880）', '黄金ETF联接\nA：000216\nC：000217\nI：022653', '黄金现货\n实盘交易', '黄金现货\n延期交易', '黄金期货\n交易', '银行、公司、金店', '积存金'];
    const institutionRows = [
      ['交易场所', '上海证券交易所', '银行、券商、互联网平台等\n基金代销渠道', '上海黄金交易所', '上海黄金交易所', '上海期货交易所', '银行、黄金公司、金店', '银行'],
      ['交易门槛', '低，最低交易单位为1手', '低，10元可以参与', `高，最低投资10g\n约${money(auPrice * 10)}`, '高，保证金交易\n最低保证金约3万元', '高，保证金交易\n最低保证金近2.1万元', '较高', `1克黄金价格\n约${money(auPrice)}`],
      ['交易成本', '低，佣金约0.03%—0.08%\n持有成本约0.6%/年', '低，申购费\nA类0.15%—0.6%\n持有成本0.6%—0.95%/年', '较低，佣金单边约0.08%', '较低，佣金单边约0.13%\n延期补偿费按合约市值计', '低，期货经纪公司\n收取约40元/手', '很高，双边价差约3%—5%', '交易一次价差约0.5%'],
      ['交易方向', '可多做，证券账户可融券做空', '仅能单向做多', '仅能单向做多', '多空双向', '多空双向', '仅能单向做多', '仅能单向做多'],
      ['流动性', '好', '好', '一般', '好', '好', '差', '好'],
      ['实金关系', '有100%实物黄金支持', '间接投资国内黄金ETF', '实金', '保证金交易\n实金交割较低', '保证金交易\n实金交割较低', '实金', '有实物黄金支持'],
      ['金价拟合度', '紧密跟随国内黄金现货', '紧密跟随国内黄金现货', '国内现货黄金价格', '国内现货黄金价格', '国内现货黄金价格', '买卖成本影响收益', '国内现货黄金价格'],
      ['优势', '交易便捷，投资门槛低\n跟踪误差小', '交易便捷，投资门槛低\n跟踪误差小', '交易价格直接为\n黄金现货价格', '保证金操作\n收益和杠杆放大', '保证金操作\n收益和杠杆放大', '直接获得黄金实物', '交易便捷，门槛低\n跟踪误差小'],
      ['劣势', '有持有成本', '有一定持有成本', '高门槛，需在金交所开户\n交易界面不友好', '风险过高，机构为主\n个人投资者受限', '风险过高，机构为主\n个人投资者受限', '交易成本高\n变现有损失', '交易成本高\n个人资金为主'],
    ];
    if (retailRoot) retailRoot.innerHTML = investorTable(retailHeaders, retailRows, 'allocation-investor-table allocation-retail-table');
    if (institutionRoot) institutionRoot.innerHTML = investorTable(institutionHeaders, institutionRows, 'allocation-investor-table allocation-institution-table');
    if (investorSource) investorSource.textContent = `克数起点按上海金 AU9999 ${auPrice ? `¥${auPrice.toLocaleString('zh-CN', { maximumFractionDigits: 2 })}/克` : '最新行情'} 换算；行情时间：${state.market?.updatedAt || '—'}。费率与规则以交易所、基金合同及机构页面为准。`;

    const pricingRoot = document.getElementById('allocationPricingSystem');
    if (pricingRoot) pricingRoot.innerHTML = `<svg class="allocation-pricing-svg" viewBox="0 0 940 590" role="img" aria-label="人民币计价黄金定价体系，需求方与供给方在上海黄金交易所汇聚">
      <defs><marker id="pricingArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path fill="var(--gold)" d="M0 0L10 5L0 10Z"></path></marker></defs>
      <rect class="pricing-band pricing-band-demand" x="8" y="16" width="924" height="190" rx="6"></rect>
      <text class="pricing-band-label" x="904" y="45" text-anchor="end">主要买入方（需求方）</text>
      <rect class="pricing-node" x="52" y="62" width="130" height="50" rx="8"></rect><text class="pricing-text" x="117" y="93" text-anchor="middle">个人</text>
      <rect class="pricing-node" x="238" y="62" width="150" height="50" rx="8"></rect><text class="pricing-text" x="313" y="93" text-anchor="middle">银行理财</text>
      <rect class="pricing-node" x="405" y="62" width="130" height="50" rx="8"></rect><text class="pricing-text" x="470" y="93" text-anchor="middle">资管FOF</text>
      <rect class="pricing-node" x="630" y="62" width="130" height="50" rx="8"></rect><text class="pricing-text" x="695" y="93" text-anchor="middle">个人</text>
      <rect class="pricing-node" x="50" y="142" width="265" height="48" rx="8"></rect><text class="pricing-text" x="182" y="164" text-anchor="middle">商业银行</text><text class="pricing-subtext" x="182" y="181" text-anchor="middle">自营做市、积存金、金条</text>
      <rect class="pricing-node" x="330" y="142" width="280" height="48" rx="8"></rect><text class="pricing-text" x="470" y="164" text-anchor="middle">黄金ETF及联接基金</text><text class="pricing-subtext" x="470" y="181" text-anchor="middle">场内基金和场外基金</text>
      <rect class="pricing-node" x="695" y="142" width="88" height="48" rx="8"></rect><text class="pricing-text" x="739" y="171" text-anchor="middle">金店</text>
      <rect class="pricing-node pricing-node-emphasis" x="815" y="132" width="104" height="68" rx="8"></rect><text class="pricing-text" x="867" y="158" text-anchor="middle">保险</text><text class="pricing-subtext" x="867" y="176" text-anchor="middle">黄金账户</text><text class="pricing-subtext" x="867" y="191" text-anchor="middle">配置需求</text>
      <path class="pricing-connector" d="M117 112V142M313 112V126H470V142M470 112V142M695 112V126H470V142M182 190V230H470M739 190V230H470M867 200V230H470"></path>
      <path class="pricing-arrow" d="M470 190V260"></path>
      <rect class="pricing-exchange" x="326" y="260" width="288" height="70" rx="10"></rect><text class="pricing-exchange-text" x="470" y="302" text-anchor="middle">上海黄金交易所</text>
      <rect class="pricing-band pricing-band-supply" x="8" y="380" width="924" height="190" rx="6"></rect>
      <text class="pricing-band-label" x="904" y="409" text-anchor="end">主要卖出方（供给方）</text>
      <rect class="pricing-node" x="212" y="468" width="176" height="52" rx="8"></rect><text class="pricing-text" x="300" y="500" text-anchor="middle">金矿生产商</text>
      <rect class="pricing-node" x="522" y="462" width="222" height="64" rx="8"></rect><text class="pricing-text" x="633" y="489" text-anchor="middle">商业银行</text><text class="pricing-subtext" x="633" y="508" text-anchor="middle">自营做市、进口</text>
      <path class="pricing-connector" d="M300 468V426H470M633 462V426H470"></path>
      <path class="pricing-arrow" d="M470 426V330"></path>
      <g class="pricing-flow-dots" aria-hidden="true">
        <circle class="pricing-flow-dot" r="3.5"><animateMotion dur="3s" repeatCount="indefinite" path="M182 190V230H470V260"></animateMotion><animate attributeName="opacity" values="0;.95;.95;0" dur="3s" repeatCount="indefinite"></animate></circle>
        <circle class="pricing-flow-dot" r="3.5"><animateMotion dur="3s" begin="-1.5s" repeatCount="indefinite" path="M867 200V230H470V260"></animateMotion><animate attributeName="opacity" values="0;.95;.95;0" dur="3s" begin="-1.5s" repeatCount="indefinite"></animate></circle>
        <circle class="pricing-flow-dot" r="3.5"><animateMotion dur="3s" repeatCount="indefinite" path="M300 468V426H470V330"></animateMotion><animate attributeName="opacity" values="0;.95;.95;0" dur="3s" repeatCount="indefinite"></animate></circle>
        <circle class="pricing-flow-dot" r="3.5"><animateMotion dur="3s" begin="-1.5s" repeatCount="indefinite" path="M633 462V426H470V330"></animateMotion><animate attributeName="opacity" values="0;.95;.95;0" dur="3s" begin="-1.5s" repeatCount="indefinite"></animate></circle>
      </g>
    </svg>`;
  }

  function renderTicker() {
    const m = state.market;
    const parts = [
      ['伦敦金现', m.spot[0]],
      ['COMEX期货', m.futures[0]],
      ['上海金AU9999', m.spot[1]],
    ].map(([label, d]) => `${label} ${d.unit === '¥/g' ? '¥' : '$'}${d.price.toLocaleString()} <span class="${chgClass(d.chg)}">${chgTxt(d.chg)}</span>`);
    const vol = [
      ['GVZ', m.volatility[0]],
      ['沪金AU波动率', m.volatility[2]],
    ].map(([label, d]) => `${label} ${d.value} <span class="${chgClass(d.chg)}">${chgTxt(d.chg)}</span>`);
    const rsi = getGoldRsi();
    const rsiItem = `黄金RSI14 ${Number.isFinite(rsi.value) ? rsi.value.toFixed(1) : '—'} <span class="rsi-${rsi.tone}">${esc(rsi.state)}</span>`;
    document.getElementById('ticker').innerHTML = parts.join(' &nbsp;&nbsp; ') + ' &nbsp;|&nbsp; ' + vol.join(' &nbsp;&nbsp; ') + ' &nbsp;&nbsp; ' + rsiItem;
  }

  function calculateRsi(rows, period = 14, livePrice) {
    const validRows = (rows || []).filter(row => Number.isFinite(Number(row.close)));
    if (validRows.length <= period) return null;
    const closes = validRows.map(row => Number(row.close));
    const updatedDate = String(state.market?.updatedAt || '').slice(0, 10);
    const lastDate = String(validRows[validRows.length - 1]?.date || '');
    if (Number.isFinite(livePrice)) {
      if (updatedDate && lastDate === updatedDate) closes[closes.length - 1] = livePrice;
      else closes.push(livePrice);
    }
    let gain = 0;
    let loss = 0;
    for (let index = 1; index <= period; index += 1) {
      const delta = closes[index] - closes[index - 1];
      gain += Math.max(delta, 0);
      loss += Math.max(-delta, 0);
    }
    let averageGain = gain / period;
    let averageLoss = loss / period;
    for (let index = period + 1; index < closes.length; index += 1) {
      const delta = closes[index] - closes[index - 1];
      averageGain = (averageGain * (period - 1) + Math.max(delta, 0)) / period;
      averageLoss = (averageLoss * (period - 1) + Math.max(-delta, 0)) / period;
    }
    if (averageLoss === 0) return 100;
    return 100 - (100 / (1 + averageGain / averageLoss));
  }

  function getGoldRsi() {
    const livePrice = state.market?.spot?.find(item => item.name === '伦敦金现 XAU/USD')?.price;
    const value = calculateRsi(state.marketChart?.rows, 14, livePrice);
    if (!Number.isFinite(value)) return { value: null, state: '等待数据', tone: 'neutral' };
    if (value >= 70) return { value, state: '超买', tone: 'overbought' };
    if (value <= 30) return { value, state: '超卖', tone: 'oversold' };
    return { value, state: '中性区间', tone: 'neutral' };
  }

  function metricCard(label, value, chg) {
    const cls = chg === undefined ? '' : chgClass(chg);
    return `<div class="metric-card"><p class="metric-label">${label}</p><p class="metric-value ${cls}">${value}</p></div>`;
  }

  function renderOverview() {
    const m = state.market;

    const londonSpot = m.spot.find(d => d.name === '伦敦金现 XAU/USD');
    const shanghaiSpot = m.spot.find(d => d.name === '上海金 AU9999');
    const comexFutures = m.futures.find(d => d.name === 'COMEX黄金主力');
    const shfeFutures = m.futures.find(d => d.name.startsWith('上期所沪金主力'));
    const sgeDeferred = m.futures.find(d => d.name === '上金所Au(T+D)');
    const goldVolatility = m.volatility.find(d => d.name.startsWith('GVZ'));
    const shfeVolatility = m.volatility.find(d => d.name.startsWith('沪金AU期货'));
    const globalLargestEtf = m.funds.international.find(f => f.code === 'GLD');
    const asiaLargestEtf = m.funds.domestic.find(f => f.code === '518880');
    document.getElementById('overviewMarket').innerHTML = [
      heatTile('伦敦金现', '$' + londonSpot.price.toLocaleString(), londonSpot.chg),
      heatTile('纽约金(COMEX)', '$' + comexFutures.price.toLocaleString(), comexFutures.chg),
      heatTile('上海金AU9999', '¥' + shanghaiSpot.price.toLocaleString(), shanghaiSpot.chg),
      heatTile('沪金AU2612', '¥' + shfeFutures.price.toLocaleString(), shfeFutures.chg),
      heatTile(sgeDeferred.name, '¥' + sgeDeferred.price.toLocaleString(), sgeDeferred.chg),
      heatTile('GVZ黄金波动率', goldVolatility.value, goldVolatility.chg),
      heatTile('沪金波动率', shfeVolatility.value, shfeVolatility.chg),
      heatTile('SPDR GLD', '$' + globalLargestEtf.price, globalLargestEtf.chg),
      heatTile(asiaLargestEtf.name, '¥' + asiaLargestEtf.price, asiaLargestEtf.chg),
    ].join('');
    document.getElementById('overviewMarketUpdated').textContent = `实时 · ${m.updatedAt}`;

    const macro = m.macro;
    const silverSpot = m.spot.find(d => d.name.includes('白银'));
    const goldSilverRatio = (m.spot[0].price / silverSpot.price).toFixed(1);
    const goldRsi = getGoldRsi();
    const goldRsiValue = Number.isFinite(goldRsi.value)
      ? `${goldRsi.value.toFixed(1)} · ${goldRsi.state}`
      : '—';
    document.getElementById('overviewKeyData').innerHTML = [
      heatTile('美元指数 DXY', macro.dxy.value, macro.dxy.chg),
      heatTile('5Y美债收益率', macro.yields.y5.value + '%', macro.yields.y5.chg),
      heatTile('10Y美债收益率', macro.yields.y10.value + '%', macro.yields.y10.chg),
      heatTile('10Y实际利率(TIPS)', macro.yields.y10Real.value + '%', macro.yields.y10Real.chg),
      heatTile('30Y美债收益率', macro.yields.y30.value + '%', macro.yields.y30.chg),
      heatTileNeutral(`美国CPI${macro.inflation.cpi.basis}(${macro.inflation.cpi.period})`, macro.inflation.cpi.value + '%'),
      heatTileNeutral(`美国PCE${macro.inflation.pce.basis}(${macro.inflation.pce.period})`, macro.inflation.pce.value + '%'),
      heatTileNeutral('央行购金(' + macro.cbPurchase.month.period + ')', macro.cbPurchase.month.value + macro.cbPurchase.month.unit),
      heatTileNeutral('央行购金(' + macro.cbPurchase.ytd.period + ')', macro.cbPurchase.ytd.value + macro.cbPurchase.ytd.unit),
      heatTileFlow('北美ETF净流入(周)', '+' + macro.etf.northAmerica.value + macro.etf.northAmerica.unit, macro.etf.northAmerica.value),
      heatTileFlow('欧洲ETF净流入(周)', '+' + macro.etf.europe.value + macro.etf.europe.unit, macro.etf.europe.value),
      heatTileFlow('亚洲ETF净流入(周)', '+' + macro.etf.asia.value + macro.etf.asia.unit, macro.etf.asia.value),
      heatTile('全球ETF总持仓', macro.etf.totalHoldings.value.toLocaleString() + macro.etf.totalHoldings.unit, macro.etf.totalHoldings.chg),
      heatTileNeutral('金银比', goldSilverRatio),
      heatTileNeutral('黄金 RSI(14日)', goldRsiValue),
    ].join('');

    const s = state.signal;
    document.getElementById('overviewGauge').innerHTML = gaugeSvg(s.score, 10, 150, 86) +
      `<p class="gauge-value">${Number(s.score).toFixed(1)}<small>/10</small></p>
       <p class="gauge-level signal-action-${signalActionClass(s.action)}">${esc(s.action)}</p>
       <p class="overview-signal-time">判断更新 ${esc(s.updatedAt)}</p>`;

    document.getElementById('overviewNewsList').innerHTML = state.news.items.filter(n => n.important).slice(0, 8).map(n =>
      `<div class="list-row"><a class="title n-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a><span class="time">${esc(n.time)}</span></div>`
    ).join('');

    document.getElementById('overviewTopicsList').innerHTML = state.topics.items.map((t, i) =>
      `<div class="list-row topic-clickable" data-topic="${i}"><div class="t-head"><span class="t-title">${esc(t.title)}</span><span class="t-date">${esc(t.date)}</span></div><p class="t-summary">${esc(t.summary)}</p></div>`
    ).join('');
    document.querySelectorAll('#overviewTopicsList .topic-clickable').forEach(el => {
      el.addEventListener('click', () => openTopic(Number(el.dataset.topic)));
    });

    renderGoldTimelineChart();
  }

  function gaugeSvg(score, max = 10, w = 120, h = 70) {
    const frac = Math.max(0, Math.min(max, score)) / max;
    const angle = Math.PI * (1 - frac);
    const cx = w / 2, cy = h - 5, r = w / 2 - 10;
    const nx = cx + r * 0.55 * Math.cos(angle);
    const ny = cy - r * 0.55 * Math.sin(angle);
    const point = value => {
      const tickAngle = Math.PI * (1 - value / max);
      return [cx + r * Math.cos(tickAngle), cy - r * Math.sin(tickAngle)];
    };
    const arc = (start, end) => {
      const [sx, sy] = point(start);
      const [ex, ey] = point(end);
      return `M${sx},${sy} A${r},${r} 0 0,1 ${ex},${ey}`;
    };
    return `<svg class="overview-signal-gauge" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-label="黄金信号分 ${score} 分">
      <path d="${arc(0, max)}" fill="none" stroke="var(--border-strong)" stroke-width="10"/>
      <path d="${arc(0, 4)}" fill="none" class="signal-arc cool" stroke-width="10"/>
      <path d="${arc(4, 6)}" fill="none" class="signal-arc warm" stroke-width="10"/>
      <path d="${arc(6, 10)}" fill="none" class="signal-arc hot" stroke-width="10"/>
      <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="var(--gold-bright)" stroke-width="2"/>
      <circle cx="${cx}" cy="${cy}" r="4" fill="var(--gold-bright)"/>
    </svg>`;
  }

  function signalActionClass(action) {
    return action === '加仓' ? 'add' : action === '止盈' ? 'trim' : 'hold';
  }

  function signalActionForScore(score) {
    if (score >= 6) return '加仓';
    if (score <= 4) return '止盈';
    return '保持不变';
  }

  function signalPolar(score, radius, cx = 450, cy = 328) {
    const angle = Math.PI * (1 - score / 10);
    return {
      x: cx + radius * Math.cos(angle),
      y: cy - radius * Math.sin(angle),
    };
  }

  function signalArcPath(start, end, radius = 242) {
    const first = signalPolar(start, radius);
    const last = signalPolar(end, radius);
    return `M${first.x.toFixed(2)},${first.y.toFixed(2)} A${radius},${radius} 0 0,1 ${last.x.toFixed(2)},${last.y.toFixed(2)}`;
  }

  function renderSignalGaugeMachine(signal) {
    const score = Math.max(0, Math.min(10, Number(signal.score) || 0));
    const needle = signalPolar(score, 166);
    const ticks = Array.from({ length: 11 }, (_, value) => {
      const outer = signalPolar(value, 232);
      const inner = signalPolar(value, value % 5 === 0 ? 207 : 216);
      const label = signalPolar(value, 187);
      return `<line x1="${outer.x}" y1="${outer.y}" x2="${inner.x}" y2="${inner.y}" class="signal-dial-tick ${value % 5 === 0 ? 'major' : ''}"></line>
        <text x="${label.x}" y="${label.y + 5}" text-anchor="middle" class="signal-dial-number">${value}</text>`;
    }).join('');
    return `<div class="signal-machine signal-machine-gauge">
      <div class="signal-gauge-shell">
        <svg class="signal-gauge-svg" viewBox="0 0 900 380" role="img" aria-label="0到10分指针评分仪表，当前${score.toFixed(1)}分">
          <path d="${signalArcPath(0, 10, 254)}" class="signal-dial-rim outer"></path>
          <path d="${signalArcPath(0, 10, 242)}" class="signal-dial-base"></path>
          <path d="${signalArcPath(0, 4)}" class="signal-dial-zone cool"></path>
          <path d="${signalArcPath(4, 6)}" class="signal-dial-zone warm"></path>
          <path d="${signalArcPath(6, 10)}" class="signal-dial-zone hot"></path>
          ${ticks}
          <line x1="450" y1="328" x2="${needle.x}" y2="${needle.y}" class="signal-dial-needle"></line>
          <circle cx="450" cy="328" r="19" class="signal-dial-hub outer"></circle>
          <circle cx="450" cy="328" r="8" class="signal-dial-hub inner"></circle>
        </svg>
        <div class="signal-gauge-readouts">
          <div class="signal-score-window"><strong>${score.toFixed(1)}</strong><span>分</span></div>
          <div class="signal-action-window signal-action-${signalActionClass(signal.action)}">${esc(signal.action)}</div>
        </div>
      </div>
    </div>`;
  }

  function renderSignalFlipMachine(signal) {
    const score = Math.max(0, Math.min(10, Number(signal.score) || 0)).toFixed(1);
    const characters = score.split('');
    return `<div class="signal-machine signal-machine-flip">
      <div class="signal-flip-main">
        <span class="signal-flip-label">当前评分</span>
        <div class="signal-flip-digits" aria-label="当前评分 ${score} 分">${characters.map(character =>
          character === '.' ? '<span class="signal-flip-decimal">.</span>' : `<span class="signal-flip-digit">${character}<i></i></span>`
        ).join('')}</div>
        <span class="signal-flip-unit">分</span>
        <div class="signal-flip-action signal-action-${signalActionClass(signal.action)}">${esc(signal.action)}</div>
      </div>
      <div class="signal-temp-rail" aria-label="0到10分信号水温">
        <div class="signal-temp-track">${Array.from({ length: 11 }, (_, value) => `<i class="${value <= 4 ? 'cool' : value <= 5 ? 'warm' : 'hot'}"></i>`).join('')}</div>
        <div class="signal-temp-pointer" style="left:${Number(score) * 10}%"></div>
        <div class="signal-temp-labels">${Array.from({ length: 11 }, (_, value) => `<span>${value}</span>`).join('')}</div>
      </div>
    </div>`;
  }

  function renderSignal() {
    const root = document.getElementById('signalDashboard');
    const signal = state.signal;
    if (!root || !signal?.factors?.length) return;
    signal.action = signal.action || signalActionForScore(Number(signal.score));
    const categoryCounts = signal.factors.reduce((counts, item) => {
      counts[item.category] = (counts[item.category] || 0) + 1;
      return counts;
    }, {});
    const seenCategories = new Set();
    const rows = signal.factors.map(item => {
      const categoryCell = seenCategories.has(item.category) ? '' : `<td class="signal-category" rowspan="${categoryCounts[item.category]}">${esc(item.category)}</td>`;
      seenCategories.add(item.category);
      return `<tr>
        ${categoryCell}
        <td class="signal-indicator">${esc(item.indicator)}</td>
        <td class="signal-judgement">${esc(item.judgement)} <a href="${esc(item.source.url)}" target="_blank" rel="noopener" title="${esc(item.source.label)}"><i class="ti ti-external-link"></i></a></td>
        <td class="signal-impact"><span class="signal-impact-badge ${item.impact === '利好' ? 'positive' : item.impact === '利空' ? 'negative' : 'neutral'}">${esc(item.impact)}</span></td>
      </tr>`;
    }).join('');
    root.innerHTML = `<div class="signal-dashboard-head">
      <div>
        <p class="view-title">黄金信号评分机</p>
        <p>10项指标等权判断 · 0—10分水温</p>
      </div>
      <div class="signal-machine-switch" role="group" aria-label="选择评分机外观">
        <button type="button" data-signal-machine="gauge" title="指针仪表" aria-label="切换到指针仪表">
          <svg viewBox="0 0 28 22" aria-hidden="true"><path d="M3 18a11 11 0 0 1 22 0"></path><line x1="14" y1="17" x2="20" y2="9"></line><circle cx="14" cy="17" r="1.5"></circle></svg>
        </button>
        <button type="button" data-signal-machine="flip" title="机械翻牌机" aria-label="切换到机械翻牌机">
          <svg viewBox="0 0 28 22" aria-hidden="true"><rect x="2" y="3" width="11" height="16" rx="2"></rect><rect x="15" y="3" width="11" height="16" rx="2"></rect><line x1="2" y1="11" x2="13" y2="11"></line><line x1="15" y1="11" x2="26" y2="11"></line></svg>
        </button>
      </div>
    </div>
    <div class="signal-machine-stage" data-machine-stage>
      <div data-machine-view="gauge">${renderSignalGaugeMachine(signal)}</div>
      <div data-machine-view="flip">${renderSignalFlipMachine(signal)}</div>
      <div class="signal-machine-rule"><span>0—4</span> 止盈 <b>·</b> <span>5</span> 保持不变 <b>·</b> <span>6—10</span> 加仓</div>
      <div class="signal-update-stamp"><i class="ti ti-clock"></i>判断更新时间：${esc(signal.updatedAt)}</div>
    </div>
    <div class="signal-table-card">
      <div class="signal-table-heading">
        <div><strong>当前情形判断</strong><span>点击每行来源图标可查看原始公开资料</span></div>
        <span class="signal-score-method">利好 1分 · 中性 0.5分 · 利空 0分</span>
      </div>
      <div class="signal-table-wrap"><table class="signal-table">
        <thead><tr><th>大类</th><th>指标</th><th>当前的情形判断</th><th>对金价影响</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <p class="signal-method-note">${esc(signal.method)}</p>
    </div>`;

    const key = 'goldar-signal-machine';
    let selected = localStorage.getItem(key) || 'gauge';
    if (!['gauge', 'flip'].includes(selected)) selected = 'gauge';
    const selectMachine = mode => {
      root.querySelectorAll('[data-signal-machine]').forEach(button => {
        const active = button.dataset.signalMachine === mode;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', String(active));
      });
      root.querySelectorAll('[data-machine-view]').forEach(view => {
        view.hidden = view.dataset.machineView !== mode;
      });
      localStorage.setItem(key, mode);
    };
    root.querySelectorAll('[data-signal-machine]').forEach(button => {
      button.addEventListener('click', () => selectMachine(button.dataset.signalMachine));
    });
    selectMachine(selected);
  }

  function renderGoldTimelineChart() {
    const config = state.timeline.goldCurve;
    if (!config || !state.goldHistory?.points?.length) return;
    const currentSpot = state.market.spot.find(item => item.name === '伦敦金现 XAU/USD')?.price;
    const hasDailyHistory = state.goldHistory.dailyPoints?.length > 1000;
    const sourcePoints = hasDailyHistory ? state.goldHistory.dailyPoints : state.goldHistory.points;
    const points = sourcePoints.map(point => ({
      date: point.date,
      price: Number(point.close ?? point.price),
      time: new Date(`${point.date}${hasDailyHistory ? '' : '-01'}T00:00:00Z`).getTime(),
    }));
    if (!hasDailyHistory && Number.isFinite(currentSpot)) {
      const currentDate = new Date().toISOString().slice(0, 7);
      if (points[points.length - 1].date === currentDate) points[points.length - 1].price = currentSpot;
      else points.push({ date: currentDate, price: currentSpot, time: new Date(`${currentDate}-01T00:00:00Z`).getTime() });
    }

    const width = 1040;
    const height = 824;
    const margin = { top: 8, right: 24, bottom: 134, left: 54 };
    const historyStartX = margin.left;
    const historyEndX = 190;
    const marketStartX = 220;
    const marketEndX = width - margin.right;
    const innerWidth = marketEndX - marketStartX;
    const innerHeight = height - margin.top - margin.bottom;
    const minTime = points[0].time;
    const maxTime = points[points.length - 1].time;
    const maxPrice = Math.ceil(Math.max(...points.map(point => point.price)) / 1000) * 1000;
    const xByTime = time => marketStartX + ((time - minTime) / (maxTime - minTime)) * innerWidth;
    const yByPrice = price => margin.top + innerHeight - (price / maxPrice) * innerHeight;

    const linePath = points.map((point, index) =>
      `${index ? 'L' : 'M'}${xByTime(point.time).toFixed(1)},${yByPrice(point.price).toFixed(1)}`
    ).join(' ');
    const areaPath = `${linePath} L${marketEndX},${margin.top + innerHeight} L${marketStartX},${margin.top + innerHeight} Z`;
    const yTicks = Array.from({ length: 6 }, (_, index) => Math.round(maxPrice / 5 * index));
    const tickYears = [1971, 1980, 1990, 1999, 2011, 2018, 2026];

    const grids = yTicks.map(value => {
      const py = yByPrice(value);
      return `<line x1="${historyStartX}" y1="${py}" x2="${marketEndX}" y2="${py}" class="curve-grid-line"/>
        <text x="${historyStartX - 8}" y="${py + 4}" text-anchor="end" class="curve-axis-label">$${value.toLocaleString()}</text>`;
    }).join('');
    const xAxisLabelY = margin.top + innerHeight + 24;
    const xLabels = tickYears.map(year => {
      const time = new Date(`${year}-01-01T00:00:00Z`).getTime();
      const px = xByTime(time);
      return `<text x="${px}" y="${xAxisLabelY}" text-anchor="middle" class="curve-axis-label">${year}</text>`;
    }).join('');

    function eventTime(label) {
      if (label.startsWith('公元前')) return null;
      const year = Number(label.match(/\d{4}/)?.[0]);
      if (!year) return null;
      const month = Number(label.match(/年(\d{1,2})月/)?.[1] || 1);
      return new Date(`${year}-${String(month).padStart(2, '0')}-01T00:00:00Z`).getTime();
    }
    function nearestPoint(time) {
      let low = 0;
      let high = points.length - 1;
      while (low < high) {
        const middle = Math.floor((low + high) / 2);
        if (points[middle].time < time) low = middle + 1;
        else high = middle;
      }
      if (low === 0) return points[0];
      const before = points[low - 1];
      const after = points[low];
      return !after || time - before.time <= after.time - time ? before : after;
    }

    const ancientEvents = state.timeline.events.filter(event => {
      const time = eventTime(event.year);
      return time === null || time < minTime;
    });
    const modernEvents = state.timeline.events.filter(event => {
      const time = eventTime(event.year);
      return time !== null && time >= minTime;
    });
    const historyAxisY = margin.top + innerHeight;
    const ancientMarks = ancientEvents.map((event, index) => {
      const px = historyStartX + (index / Math.max(1, ancientEvents.length - 1)) * (historyEndX - historyStartX);
      return { event, x: px, y: historyAxisY, premarket: true };
    });
    const modernMarks = modernEvents.map(event => {
      const time = eventTime(event.year);
      const point = nearestPoint(time);
      return { event, x: xByTime(time), y: yByPrice(point.price), premarket: false };
    });
    const eventMarks = [...ancientMarks, ...modernMarks];
    const labelWidth = 24;
    const labelStartY = margin.top;
    const labelLeft = margin.left + labelWidth / 2;
    const labelRight = marketEndX - labelWidth / 2;
    const eventLayouts = eventMarks.map((mark, index) => {
      const labelX = labelLeft + (index / Math.max(1, eventMarks.length - 1)) * (labelRight - labelLeft);
      const textLength = Array.from(`${mark.event.year}·${mark.event.type}${mark.event.text}`).length;
      const labelTime = minTime + Math.max(0, Math.min(1, (labelX - marketStartX) / innerWidth)) * (maxTime - minTime);
      const curveYAtLabel = labelX < marketStartX ? historyAxisY : yByPrice(nearestPoint(labelTime).price);
      const availableHeight = Math.max(88, Math.min(mark.y, curveYAtLabel) - labelStartY - 12);
      const charsPerColumn = Math.max(12, Math.floor((availableHeight - 12) / 6.5));
      const columns = Math.max(1, Math.ceil(textLength / charsPerColumn));
      const eventLabelWidth = Math.max(labelWidth, columns * 7.6 + 8);
      const labelHeight = Math.min(availableHeight, Math.ceil(textLength / columns) * 6.5 + 12);
      const labelBottom = labelStartY + labelHeight;
      return { mark, index, labelX, labelBottom, labelHeight, eventLabelWidth };
    });
    const eventConnectors = eventLayouts.map(layout =>
      `<path class="event-annotation-line" data-event-id="${layout.index}" data-label-x="${layout.labelX}" data-mark-x="${layout.mark.x}" data-mark-y="${layout.mark.y}" d="M${layout.labelX},${layout.labelBottom} L${layout.mark.x},${layout.mark.y}"></path>`
    ).join('');
    const eventAnnotations = eventLayouts.map(layout => {
      const { mark, index, labelX, labelBottom, labelHeight, eventLabelWidth } = layout;
      const labelY = labelStartY;
      const aria = `${mark.event.year}，${mark.event.type}，${mark.event.text}`;
      return `<g class="event-annotation${mark.premarket ? ' premarket' : ''}" data-event-id="${index}" tabindex="0" role="button" aria-label="${esc(aria)}">
        <foreignObject x="${labelX - eventLabelWidth / 2}" y="${labelY}" width="${eventLabelWidth}" height="${labelHeight}">
          <div xmlns="http://www.w3.org/1999/xhtml" class="event-annotation-vertical"><strong>${esc(mark.event.year)} · ${esc(mark.event.type)}</strong><span>${esc(mark.event.text)}</span></div>
        </foreignObject>
      </g>`;
    }).join('');
    const eventMarkers = eventMarks.map((mark, index) =>
      `<circle class="curve-history-event${mark.premarket ? ' premarket' : ''}" data-event-id="${index}" cx="${mark.x}" cy="${mark.y}" r="3.2"></circle>`
    ).join('');

    const latest = points[points.length - 1];
    const peak = points.reduce((highest, point) => point.price > highest.price ? point : highest, points[0]);
    const cycleStart = nearestPoint(new Date('1971-08-01T00:00:00Z').getTime());
    const currentDisplayPrice = Number.isFinite(currentSpot) ? currentSpot : latest.price;
    const cumulative = (currentDisplayPrice / cycleStart.price - 1) * 100;
    const drawdown = (currentDisplayPrice / peak.price - 1) * 100;
    const cycleBrackets = config.cycles.map(cycle => {
      const start = xByTime(new Date(`${cycle.start}-01T00:00:00Z`).getTime());
      const cycleEndTime = cycle.end === 'latest' ? maxTime : new Date(`${cycle.end}-01T00:00:00Z`).getTime();
      const end = Math.min(marketEndX, xByTime(cycleEndTime));
      const y = historyAxisY + 100;
      return `<g class="cycle-period-bracket ${esc(cycle.tone)}">
        <path d="M${start},${y - 5} V${y} H${end} V${y - 5}"></path>
        <text x="${(start + end) / 2}" y="${y + 11}" text-anchor="middle">${esc(cycle.label)}</text>
        <title>${esc(cycle.phase)}</title>
      </g>`;
    }).join('');
    const phaseBrackets = (config.phases || []).map(phase => {
      const start = xByTime(new Date(`${phase.start}-01T00:00:00Z`).getTime());
      const phaseEndTime = phase.end === 'latest' ? maxTime : new Date(`${phase.end}-01T00:00:00Z`).getTime();
      const end = Math.min(marketEndX, xByTime(phaseEndTime));
      const y = historyAxisY + 47 + (phase.row || 0) * 22;
      const isNarrow = end - start < 72;
      const textX = isNarrow ? Math.min(marketEndX, end + 2) : (start + end) / 2;
      const anchor = isNarrow ? 'end' : 'middle';
      return `<g class="cycle-phase-bracket ${esc(phase.tone)}">
        <path d="M${start},${y - 5} V${y} H${end} V${y - 5}"></path>
        <text x="${textX}" y="${y + 11}" text-anchor="${anchor}">${esc(phase.label)}</text>
      </g>`;
    }).join('');
    const milestones = (config.milestones || []).map(item => {
      const x = xByTime(new Date(`${item.date}-01T00:00:00Z`).getTime());
      const y = yByPrice(item.price);
      const tx = x + (item.dx || 0);
      const ty = y + (item.dy || -12);
      return `<g class="price-milestone">
        <line x1="${x}" y1="${y}" x2="${tx}" y2="${ty + 3}"></line>
        <circle cx="${x}" cy="${y}" r="3.2"></circle>
        <text x="${tx}" y="${ty}" text-anchor="${esc(item.anchor || 'middle')}">
          <tspan x="${tx}">${esc(item.label)}</tspan>
          <tspan class="milestone-price" x="${tx}" dy="9">$${Number(item.price).toLocaleString()}</tspan>
        </text>
      </g>`;
    }).join('');
    const latestMilestone = `<g class="price-milestone current">
      <circle cx="${marketEndX}" cy="${yByPrice(latest.price)}" r="3.5"></circle>
      <text x="${marketEndX - 5}" y="${yByPrice(latest.price) - 18}" text-anchor="end">
        <tspan x="${marketEndX - 5}">${esc(latest.date.replaceAll('-', '/'))} 收盘</tspan>
        <tspan class="milestone-price" x="${marketEndX - 5}" dy="9">$${Math.round(latest.price).toLocaleString()}</tspan>
      </text>
    </g>`;

    document.getElementById('overviewTimeline').innerHTML = `
      <div class="curve-summary">
        <div><span>1971脱钩至今</span><strong class="${cumulative >= 0 ? 'up' : 'down'}">${cumulative >= 0 ? '+' : ''}${cumulative.toFixed(0)}%</strong></div>
        <div><span>当前伦敦金</span><strong>$${currentDisplayPrice.toLocaleString()}</strong></div>
        <div><span>距日线高点</span><strong class="${drawdown >= 0 ? 'up' : 'down'}">${drawdown.toFixed(1)}%</strong></div>
      </div>
      <p class="cycle-current-note"><strong>当前周期判断：</strong>仍处第三轮黄金大周期。2026年高位回撤已确认，但是否进入长期下行后半段尚不明确，需继续观察实际利率、美元、ETF资金与央行购金。</p>
      <div class="curve-scroll">
        <svg class="gold-curve-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(config.title)}">
          ${grids}
          ${xLabels}
          <line x1="${historyStartX}" y1="${historyAxisY}" x2="${historyEndX}" y2="${historyAxisY}" class="history-compressed-line"></line>
          <text x="${historyStartX}" y="${xAxisLabelY}" text-anchor="start" class="curve-axis-label">公元前6世纪</text>
          <text x="${historyEndX}" y="${xAxisLabelY}" text-anchor="end" class="curve-axis-label">1968</text>
          <path d="M197,${historyAxisY - 5} l6,10 l6,-10" class="history-axis-break"></path>
          <path d="${areaPath}" class="curve-area"></path>
          ${eventConnectors}
          <path d="${linePath}" class="curve-line"></path>
          ${milestones}
          ${latestMilestone}
          ${eventMarkers}
          ${eventAnnotations}
          ${phaseBrackets}
          ${cycleBrackets}
          <g class="curve-price-inspector" aria-hidden="true">
            <line class="curve-price-crosshair" y1="${margin.top}" y2="${historyAxisY}"></line>
            <circle class="curve-price-dot" r="4"></circle>
          </g>
          <path class="curve-hit-line" d="${linePath}" tabindex="0" role="button" aria-label="查看伦敦金历史日收盘价"></path>
        </svg>
      </div>
      <div class="curve-price-tooltip" role="status" aria-live="polite"></div>
      <p class="curve-note">${esc(config.note)} 关键点位为历史首次突破的盘中价；牛熊括线按阶段高低点划分，2026年回撤尚未确认转熊。数据来源：${esc(state.goldHistory.source)}。</p>`;

    const timelineRoot = document.getElementById('overviewTimeline');
    timelineRoot.querySelectorAll('.event-annotation').forEach(annotation => {
      const foreignObject = annotation.querySelector('foreignObject');
      const content = foreignObject.firstElementChild;
      const contentParts = [...content.children];
      const objectHeight = Number(foreignObject.getAttribute('height'));
      const objectRect = foreignObject.getBoundingClientRect();
      const contentRect = content.getBoundingClientRect();
      const scaleY = objectRect.height / objectHeight;
      const contentBottom = Math.max(...contentParts.map(part => part.getBoundingClientRect().bottom));
      let fittedHeight = Math.ceil((contentBottom - contentRect.top + 4) / scaleY);
      foreignObject.setAttribute('height', fittedHeight);
      while ((content.scrollWidth > content.clientWidth + 2 || content.scrollHeight > content.clientHeight + 2) && fittedHeight < objectHeight) {
        fittedHeight += 3;
        foreignObject.setAttribute('height', fittedHeight);
      }
      const connector = timelineRoot.querySelector(`.event-annotation-line[data-event-id="${annotation.dataset.eventId}"]`);
      connector.setAttribute('d', `M${connector.dataset.labelX},${labelStartY + fittedHeight} L${connector.dataset.markX},${connector.dataset.markY}`);
    });
    const annotations = timelineRoot.querySelectorAll('.event-annotation');
    let lockedEventId = null;
    const emphasizeEvent = eventId => {
      timelineRoot.querySelectorAll('[data-event-id].is-active').forEach(element => element.classList.remove('is-active'));
      if (eventId === null) return;
      timelineRoot.querySelectorAll(`[data-event-id="${eventId}"]`).forEach(element => element.classList.add('is-active'));
    };
    const toggleEvent = eventId => {
      lockedEventId = lockedEventId === eventId ? null : eventId;
      emphasizeEvent(lockedEventId);
    };
    annotations.forEach(annotation => {
      const eventId = annotation.dataset.eventId;
      annotation.addEventListener('mouseenter', () => emphasizeEvent(eventId));
      annotation.addEventListener('mouseleave', () => emphasizeEvent(lockedEventId));
      annotation.addEventListener('focus', () => emphasizeEvent(eventId));
      annotation.addEventListener('blur', () => emphasizeEvent(lockedEventId));
      annotation.addEventListener('click', event => {
        event.stopPropagation();
        toggleEvent(eventId);
      });
      annotation.addEventListener('keydown', event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        toggleEvent(eventId);
      });
    });
    const svg = timelineRoot.querySelector('.gold-curve-svg');
    const hitLine = timelineRoot.querySelector('.curve-hit-line');
    const priceInspector = timelineRoot.querySelector('.curve-price-inspector');
    const priceCrosshair = timelineRoot.querySelector('.curve-price-crosshair');
    const priceDot = timelineRoot.querySelector('.curve-price-dot');
    const priceTooltip = timelineRoot.querySelector('.curve-price-tooltip');
    let priceLocked = false;
    const svgCoordinates = event => {
      const point = svg.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      return point.matrixTransform(svg.getScreenCTM().inverse());
    };
    const inspectedPoint = event => {
      const position = svgCoordinates(event);
      const x = Math.max(marketStartX, Math.min(marketEndX, position.x));
      const time = minTime + ((x - marketStartX) / innerWidth) * (maxTime - minTime);
      return nearestPoint(time);
    };
    const showPricePoint = point => {
      const x = xByTime(point.time);
      const y = yByPrice(point.price);
      priceCrosshair.setAttribute('x1', x);
      priceCrosshair.setAttribute('x2', x);
      priceDot.setAttribute('cx', x);
      priceDot.setAttribute('cy', y);
      priceInspector.classList.add('visible');
      const date = new Intl.DateTimeFormat('zh-CN', {
        timeZone: 'UTC', year: 'numeric', month: 'long', day: 'numeric',
      }).format(new Date(point.time));
      priceTooltip.innerHTML = `<span class="curve-price-date">${esc(date)}</span>
        <strong>$${point.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong>
        <span>伦敦金（LBMA PM）· 当日收盘价 · 美元/盎司</span>`;
      priceTooltip.classList.add('visible');
      const rootRect = timelineRoot.getBoundingClientRect();
      const screenPoint = svg.createSVGPoint();
      screenPoint.x = x;
      screenPoint.y = y;
      const screen = screenPoint.matrixTransform(svg.getScreenCTM());
      const preferredLeft = screen.x - rootRect.left + 12;
      const preferredTop = screen.y - rootRect.top - priceTooltip.offsetHeight - 10;
      priceTooltip.style.left = `${Math.max(8, Math.min(rootRect.width - priceTooltip.offsetWidth - 8, preferredLeft))}px`;
      priceTooltip.style.top = `${Math.max(8, preferredTop)}px`;
    };
    const hidePricePoint = () => {
      priceInspector.classList.remove('visible');
      priceTooltip.classList.remove('visible');
    };
    hitLine.addEventListener('pointermove', event => {
      if (!priceLocked) showPricePoint(inspectedPoint(event));
    });
    hitLine.addEventListener('pointerleave', () => {
      if (!priceLocked) hidePricePoint();
    });
    hitLine.addEventListener('click', event => {
      event.stopPropagation();
      lockedEventId = null;
      emphasizeEvent(null);
      priceLocked = true;
      showPricePoint(inspectedPoint(event));
    });
    svg.addEventListener('click', event => {
      lockedEventId = null;
      emphasizeEvent(null);
      if (event.target !== hitLine) {
        priceLocked = false;
        hidePricePoint();
      }
    });
  }

  function renderCalendar() {
    const now = Date.now();
    const format = value => new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
    }).format(new Date(value)).replace('/', '-');
    const sorted = [...state.calendar.events].sort((a, b) => new Date(a.releaseAt) - new Date(b.releaseAt));
    const upcoming = sorted.filter(event => new Date(event.releaseAt).getTime() >= now).slice(0, 12);
    const visible = upcoming.length >= 12
      ? upcoming
      : [...sorted.filter(event => new Date(event.releaseAt).getTime() < now).slice(-(12 - upcoming.length)), ...upcoming];
    document.getElementById('overviewCalendar').innerHTML = visible.map(event => {
      const start = new Date(event.releaseAt).getTime();
      const end = event.windowEnd ? new Date(event.windowEnd).getTime() : start;
      const due = now >= start;
      const time = event.timePrecision === 'window'
        ? `${format(event.releaseAt).slice(0, 5)}—${format(event.windowEnd).slice(0, 5)} 发布窗口`
        : format(event.releaseAt);
      const status = event.result
        ? `实际 ${event.result.actual} · ${event.result.surprise}`
        : due ? (now <= end ? '发布窗口中' : '已到公布时间') : '待公布';
      return `<div class="calendar-item">
        <p class="c-time">${esc(time)}</p>
        <p class="c-name" title="${esc(event.name)}">${esc(event.name)}</p>
        <p class="c-meta">${esc(event.period)} · ${esc(event.source)} · <span class="calendar-status ${due || event.result ? 'due' : ''}">${esc(status)}</span></p>
      </div>`;
    }).join('');
  }

  let calendarMonth = new Date();
  calendarMonth.setDate(1);

  function renderMonthCalendar() {
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const today = new Date();
    const dayEvents = new Map();
    const dateKey = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const timeFormat = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', hour12: false });
    state.calendar.events.forEach(event => {
      const date = new Date(event.releaseAt);
      const key = dateKey(date);
      if (!dayEvents.has(key)) dayEvents.set(key, []);
      dayEvents.get(key).push({ ...event, time: timeFormat.format(date) });
    });

    document.getElementById('goldCalendarMonth').textContent = `${year} 年 ${month + 1} 月`;
    const firstDay = new Date(year, month, 1);
    const gridStart = new Date(year, month, 1 - firstDay.getDay());
    const resultClass = event => event.result?.surprise === '高于预期'
      ? 'above'
      : event.result?.surprise === '低于预期' ? 'below' : event.result?.surprise === '符合预期' ? 'inline' : 'unknown';
    const eventMarkup = event => {
      const title = `${event.name} · ${event.period} · ${event.time}${event.result ? ` · 实际 ${event.result.actual} / 预期 ${event.result.forecast} / 前值 ${event.result.previous} · ${event.result.surprise}` : ''}`;
      if (!event.result) {
        return `<article class="month-event ${event.type === 'central-bank-gold' ? 'central-bank' : 'macro'}" title="${esc(title)}">
          <p class="month-event-title"><time>${esc(event.time)}</time>${esc(event.name)}</p>
        </article>`;
      }
      return `<article class="month-event macro has-result ${resultClass(event)}" title="${esc(title)}">
        <p class="month-event-title"><time>${esc(event.time)}</time>${esc(event.name)}</p>
        <div class="month-event-values">
          <span>实 <b>${esc(event.result.actual)}</b></span>
          <span>预 ${esc(event.result.forecast)}</span>
          <span>前 ${esc(event.result.previous)}</span>
        </div>
        <p class="month-event-surprise">${esc(event.result.surprise)}</p>
      </article>`;
    };
    const publishedCount = state.calendar.events.filter(event => event.result && new Date(event.releaseAt).getFullYear() === year).length;
    document.getElementById('goldCalendarStats').textContent = `${year} 年已公布 ${publishedCount} 项`;
    const cells = [];
    for (let index = 0; index < 42; index += 1) {
      const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
      const key = dateKey(date);
      const events = dayEvents.get(key) || [];
      const currentMonth = date.getMonth() === month;
      const isToday = key === dateKey(today);
      cells.push(`<div class="month-day ${currentMonth ? '' : 'outside-month'} ${isToday ? 'today' : ''}">
        <span class="month-day-number">${date.getDate()}</span>
        <div class="month-day-events">${events.map(eventMarkup).join('')}</div>
      </div>`);
    }
    document.getElementById('goldMonthCalendar').innerHTML = `
      <div class="month-weekdays">${['日', '一', '二', '三', '四', '五', '六'].map(day => `<span>${day}</span>`).join('')}</div>
      <div class="month-days">${cells.join('')}</div>`;
    document.getElementById('goldCalendarPrev').onclick = () => { calendarMonth = new Date(year, month - 1, 1); renderMonthCalendar(); };
    document.getElementById('goldCalendarNext').onclick = () => { calendarMonth = new Date(year, month + 1, 1); renderMonthCalendar(); };
    document.getElementById('goldCalendarToday').onclick = () => { calendarMonth = new Date(); calendarMonth.setDate(1); renderMonthCalendar(); };
  }

  function table(headers, rows) {
    return `<table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
  }

  function tileTone(chg) {
    const a = Math.abs(chg);
    const tier = a < 0.5 ? 1 : a < 1.5 ? 2 : 3;
    return (chg >= 0 ? 'tile-up-' : 'tile-down-') + tier;
  }

  function heatTile(name, valueStr, chg, url) {
    const tag = url ? 'a' : 'div';
    const attrs = url ? ` href="${esc(url)}" target="_blank" rel="noopener" aria-label="查看${esc(name)}详细行情"` : '';
    return `<${tag} class="heat-tile ${tileTone(chg)}"${attrs}><p class="t-name">${esc(name)}${url ? '<i class="ti ti-external-link"></i>' : ''}</p><p class="t-val">${valueStr}<span class="t-chg">${chgTxt(chg)}</span></p></${tag}>`;
  }

  function heatTileFlow(name, valueStr, sign) {
    const tone = sign >= 0 ? 'tile-up-2' : 'tile-down-2';
    return `<div class="heat-tile ${tone}"><p class="t-name">${esc(name)}</p><p class="t-val">${valueStr}</p></div>`;
  }

  function heatTileNeutral(name, valueStr, url) {
    const tag = url ? 'a' : 'div';
    const attrs = url ? ` href="${esc(url)}" target="_blank" rel="noopener" aria-label="查看${esc(name)}详情"` : '';
    return `<${tag} class="heat-tile tile-neutral"${attrs}><p class="t-name">${esc(name)}${url ? '<i class="ti ti-external-link"></i>' : ''}</p><p class="t-val">${valueStr}</p></${tag}>`;
  }

  function heatGroup(title, tag, items, tileFn) {
    const avg = items.reduce((s, i) => s + i.chg, 0) / items.length;
    return `<div class="heat-group">
      <div class="heat-group-head"><span class="name">${esc(title)}</span><span class="tag">${esc(tag)}</span><span class="avg ${chgClass(avg)}">${chgTxt(avg)}</span></div>
      <div class="heat-grid">${items.map(tileFn).join('')}</div>
    </div>`;
  }

  function formatSpot(d) {
    if (d.unit === '$/oz') return '$' + d.price.toLocaleString();
    if (d.unit === '¥/g') return '¥' + d.price.toLocaleString();
    return d.price.toLocaleString() + ' ' + d.unit;
  }

  function marketDetailUrl(kind, item) {
    const name = item.name || '';
    if (kind === 'domesticStock') {
      const exchange = /^(6|9)/.test(item.code) ? 'sh' : 'sz';
      return `https://quote.eastmoney.com/${exchange}${item.code}.html`;
    }
    if (kind === 'domesticFund') return `https://fund.eastmoney.com/${item.code}.html`;
    if (kind === 'international') return `https://finance.yahoo.com/quote/${encodeURIComponent(item.code)}/`;
    if (kind === 'coin') return 'http://www.chngc.net/';
    if (kind === 'retail') return 'https://gold.cngold.org/price/';
    if (kind === 'sge') return 'https://www.sge.com.cn/sjzx/mrhqsj';
    if (kind === 'paperGold') return 'https://quote.cngold.org/gjs/';
    if (kind === 'volatility') {
      if (name.startsWith('GVZ')) return 'https://finance.yahoo.com/quote/%5EGVZ/';
      if (name.startsWith('VIX')) return 'https://finance.yahoo.com/quote/%5EVIX/';
      if (name.includes('美元指数')) return 'https://www.tradingview.com/symbols/TVC-DXY/';
      if (name.includes('沪金')) return 'https://www.tradingview.com/symbols/SHFE-AU1!/';
      return 'https://www.tradingview.com/symbols/OANDA-XAUUSD/';
    }
    if (kind === 'future') {
      if (name.includes('COMEX黄金')) return 'https://www.tradingview.com/symbols/COMEX-GC1!/';
      if (name.includes('沪金')) return 'https://www.tradingview.com/symbols/SHFE-AU1!/';
      if (name.includes('东京')) return 'https://www.tradingview.com/symbols/TOCOM-GOLD1!/';
      if (name.includes('Au(T+D)')) return 'https://www.sge.com.cn/sjzx/mrhqsj';
      if (name.includes('MCX')) return 'https://www.tradingview.com/symbols/MCX-GOLD1!/';
      return 'https://www.tradingview.com/symbols/COMEX-MGC1!/';
    }
    if (kind === 'spot') {
      if (name.includes('XAU/USD')) return 'https://www.tradingview.com/symbols/OANDA-XAUUSD/';
      if (name.includes('AU9999')) return 'https://www.sge.com.cn/sjzx/mrhqsj';
      if (name.includes('白银')) return 'https://www.tradingview.com/symbols/OANDA-XAGUSD/';
      if (name.includes('铂金')) return 'https://www.tradingview.com/symbols/OANDA-XPTUSD/';
      if (name.includes('钯金')) return 'https://www.tradingview.com/symbols/OANDA-XPDUSD/';
      if (name.includes('香港')) return 'https://www.cgse.com.hk/';
      if (name.includes('台湾')) return 'https://www.tpex.org.tw/';
      return 'https://www.tradingview.com/markets/futures/quotes-metals/';
    }
    return '';
  }

  let marketChartDays = 252;

  function renderMarketChart() {
    const root = document.getElementById('marketChart');
    if (!root || !state.marketChart?.rows?.length) return;
    const rows = state.marketChart.rows.map(row => ({ ...row }));
    const latest = rows[rows.length - 1];
    const livePrice = state.market.spot.find(item => item.name.startsWith('伦敦金现'))?.price;
    const liveGvz = state.market.volatility.find(item => item.name.startsWith('GVZ'))?.value;
    if (Number.isFinite(livePrice)) {
      latest.close = livePrice;
      latest.high = Math.max(latest.high, livePrice);
      latest.low = Math.min(latest.low, livePrice);
    }
    if (Number.isFinite(liveGvz)) latest.gvz = liveGvz;

    const count = marketChartDays === 'all' ? rows.length : Math.min(rows.length, marketChartDays);
    const visible = rows.slice(-count);
    const width = 1100;
    const height = 400;
    const left = 58;
    const right = 86;
    const plotWidth = width - left - right;
    const priceTop = 28;
    const priceBottom = 350;
    const priceValues = visible.flatMap(row => [row.low, row.high]).filter(Number.isFinite);
    const priceMinRaw = Math.min(...priceValues);
    const priceMaxRaw = Math.max(...priceValues);
    const pricePad = Math.max(5, (priceMaxRaw - priceMinRaw) * 0.07);
    const priceMin = priceMinRaw - pricePad;
    const priceMax = priceMaxRaw + pricePad;
    const gvzValues = visible.map(row => row.gvz).filter(Number.isFinite);
    const gvzMinRaw = Math.min(...gvzValues);
    const gvzMaxRaw = Math.max(...gvzValues);
    const gvzPad = Math.max(1, (gvzMaxRaw - gvzMinRaw) * 0.12);
    const gvzMin = gvzMinRaw - gvzPad;
    const gvzMax = gvzMaxRaw + gvzPad;
    const volumeMax = Math.max(...visible.map(row => row.volume || 0), 1);
    const step = plotWidth / visible.length;
    const candleWidth = Math.max(0.8, Math.min(9, step * 0.64));
    const x = index => left + (index + 0.5) * step;
    const yPrice = value => priceBottom - ((value - priceMin) / (priceMax - priceMin)) * (priceBottom - priceTop);
    const yGvz = value => priceBottom - ((value - gvzMin) / (gvzMax - gvzMin)) * (priceBottom - priceTop);
    const yVolume = value => priceBottom - (value / volumeMax) * (priceBottom - priceTop);
    const priceTicks = Array.from({ length: 5 }, (_, index) => priceMin + ((priceMax - priceMin) * index) / 4);
    const grid = priceTicks.map(value => `<g>
      <line class="mvc-grid" x1="${left}" x2="${width - right}" y1="${yPrice(value)}" y2="${yPrice(value)}"></line>
      <text class="mvc-axis" x="${left - 9}" y="${yPrice(value) + 4}" text-anchor="end">$${Math.round(value).toLocaleString()}</text>
    </g>`).join('');
    const candles = visible.map((row, index) => {
      const rising = row.close >= row.open;
      const tone = rising ? 'up' : 'down';
      const bodyTop = yPrice(Math.max(row.open, row.close));
      const bodyBottom = yPrice(Math.min(row.open, row.close));
      return `<g class="mvc-candle ${tone}">
        <line x1="${x(index)}" x2="${x(index)}" y1="${yPrice(row.high)}" y2="${yPrice(row.low)}"></line>
        <rect x="${x(index) - candleWidth / 2}" y="${bodyTop}" width="${candleWidth}" height="${Math.max(1.2, bodyBottom - bodyTop)}"></rect>
      </g>`;
    }).join('');
    const volumes = visible.map((row, index) => `<rect class="mvc-volume ${row.close >= row.open ? 'up' : 'down'}"
      x="${x(index) - candleWidth / 2}" y="${yVolume(row.volume || 0)}" width="${candleWidth}" height="${priceBottom - yVolume(row.volume || 0)}"></rect>`).join('');
    const gvzPath = visible.map((row, index) => Number.isFinite(row.gvz) ? `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yGvz(row.gvz).toFixed(2)}` : '').join(' ');
    const labelIndexes = Array.from(new Set(Array.from({ length: 6 }, (_, index) => Math.round(index * (visible.length - 1) / 5))));
    const dateFormat = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short' });
    const dateLabels = labelIndexes.map(index => `<text class="mvc-axis" x="${x(index)}" y="378" text-anchor="middle">${esc(dateFormat.format(new Date(`${visible[index].date}T00:00:00Z`)))}</text>`).join('');
    const lastIndex = visible.length - 1;
    const last = visible[lastIndex];
    const change = last.open ? ((last.close / last.open) - 1) * 100 : 0;
    const formatVolume = value => value >= 1000000 ? `${(value / 1000000).toFixed(2)}M` : value >= 1000 ? `${(value / 1000).toFixed(1)}K` : value.toLocaleString();

    root.innerHTML = `<div class="market-chart-canvas">
      <svg class="market-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="伦敦金XAU/USD价格、COMEX量能代理与GVZ走势图">
        ${grid}
        ${volumes}
        ${candles}
        <path class="mvc-gvz-line" d="${gvzPath}"></path>
        ${dateLabels}
        <text class="mvc-panel-label" x="${left}" y="${priceTop - 9}">价格 · 伦敦金 XAU/USD</text>
        <text class="mvc-volume-axis-title" x="${width - right + 7}" y="${priceTop - 9}">COMEX量能</text>
        <text class="mvc-volume-axis" x="${width - right + 7}" y="${priceTop + 4}">${formatVolume(volumeMax)}</text>
        <text class="mvc-volume-axis" x="${width - right + 7}" y="${(priceTop + priceBottom) / 2 + 4}">${formatVolume(volumeMax / 2)}</text>
        <text class="mvc-volume-axis" x="${width - right + 7}" y="${priceBottom + 4}">0</text>
        <text class="mvc-gvz-label" x="${width - right - 7}" y="${yGvz(last.gvz) + 4}" text-anchor="end">GVZ ${last.gvz.toFixed(2)}</text>
        <text class="mvc-price-label ${change >= 0 ? 'up' : 'down'}" x="${width - right - 7}" y="${yPrice(last.close) + 4}" text-anchor="end">$${last.close.toLocaleString()}</text>
        <g class="mvc-inspector">
          <line class="mvc-crosshair-x" x1="${left}" x2="${width - right}"></line>
          <line class="mvc-crosshair-y" y1="${priceTop}" y2="${priceBottom}"></line>
          <circle class="mvc-focus-dot" r="4"></circle>
        </g>
        <rect class="mvc-overlay" x="${left}" y="${priceTop}" width="${plotWidth}" height="${priceBottom - priceTop}"></rect>
      </svg>
      <div class="mvc-tooltip"></div>
    </div>`;

    const live = document.getElementById('marketChartLive');
    live.innerHTML = `<span>${esc(last.date)}</span>
      <span>开 <b>${last.open.toLocaleString()}</b></span>
      <span>高 <b>${last.high.toLocaleString()}</b></span>
      <span>低 <b>${last.low.toLocaleString()}</b></span>
      <span>收 <b class="${change >= 0 ? 'up' : 'down'}">${last.close.toLocaleString()}</b></span>
      <span>量 <b>${formatVolume(last.volume)}</b></span>
      <span>GVZ <b>${last.gvz.toFixed(2)}</b></span>
      <span class="mvc-live-dot">实时 ${esc(state.market.updatedAt)}</span>`;
    document.getElementById('marketChartNote').textContent = `${state.marketChart.note} 历史数据：${state.marketChart.sources.provider}；最新价格每15秒更新，历史日线每5分钟同步。滚轮缩放时间区间。`;

    document.querySelectorAll('#marketChartRanges button').forEach(button => {
      const days = button.dataset.days === 'all' ? 'all' : Number(button.dataset.days);
      button.classList.toggle('active', days === marketChartDays);
      if (button.dataset.bound) return;
      button.dataset.bound = '1';
      button.addEventListener('click', () => {
        marketChartDays = button.dataset.days === 'all' ? 'all' : Number(button.dataset.days);
        renderMarketChart();
      });
    });

    const canvas = root.querySelector('.market-chart-canvas');
    const svg = root.querySelector('.market-chart-svg');
    const inspector = root.querySelector('.mvc-inspector');
    const crossX = root.querySelector('.mvc-crosshair-x');
    const crossY = root.querySelector('.mvc-crosshair-y');
    const dot = root.querySelector('.mvc-focus-dot');
    const tooltip = root.querySelector('.mvc-tooltip');
    const inspect = event => {
      const rect = svg.getBoundingClientRect();
      const px = (event.clientX - rect.left) * width / rect.width;
      const index = Math.max(0, Math.min(lastIndex, Math.floor((px - left) / step)));
      const row = visible[index];
      const rowX = x(index);
      const rowY = yPrice(row.close);
      const rowChange = row.open ? ((row.close / row.open) - 1) * 100 : 0;
      crossX.setAttribute('y1', rowY);
      crossX.setAttribute('y2', rowY);
      crossY.setAttribute('x1', rowX);
      crossY.setAttribute('x2', rowX);
      dot.setAttribute('cx', rowX);
      dot.setAttribute('cy', rowY);
      inspector.classList.add('visible');
      tooltip.innerHTML = `<strong>${esc(row.date)} · $${row.close.toLocaleString()}</strong>
        <span>开 ${row.open.toLocaleString()}　高 ${row.high.toLocaleString()}　低 ${row.low.toLocaleString()}</span>
        <span class="${rowChange >= 0 ? 'up' : 'down'}">${rowChange >= 0 ? '+' : ''}${rowChange.toFixed(2)}%</span>
        <span>COMEX量能 ${formatVolume(row.volume)}　GVZ ${Number(row.gvz).toFixed(2)}</span>`;
      tooltip.classList.add('visible');
      const localX = event.clientX - canvas.getBoundingClientRect().left;
      const localY = event.clientY - canvas.getBoundingClientRect().top;
      tooltip.style.left = `${Math.max(8, Math.min(canvas.clientWidth - tooltip.offsetWidth - 8, localX + 14))}px`;
      tooltip.style.top = `${Math.max(8, localY - tooltip.offsetHeight - 12)}px`;
    };
    root.querySelector('.mvc-overlay').addEventListener('pointermove', inspect);
    root.querySelector('.mvc-overlay').addEventListener('pointerleave', () => {
      inspector.classList.remove('visible');
      tooltip.classList.remove('visible');
    });
    canvas.addEventListener('wheel', event => {
      event.preventDefault();
      const current = marketChartDays === 'all' ? rows.length : marketChartDays;
      const next = Math.round(current * (event.deltaY > 0 ? 1.18 : 0.84));
      marketChartDays = Math.max(22, Math.min(rows.length, next));
      if (marketChartDays >= rows.length - 5) marketChartDays = 'all';
      renderMarketChart();
    }, { passive: false });
  }

  function renderMarket() {
    const m = state.market;
    renderMarketChart();
    renderMarketPremium();
    renderAssetPerformance();
    renderTradingVolumes();
    document.getElementById('marketUpdated').textContent = `高频行情每15秒刷新 · 最新 ${m.updatedAt}`;
    const fundUnit = u => u === '¥/g' ? '¥' : u === 'GBp' ? '£' : u === '€' ? '€' : u === 'CHF' ? 'CHF ' : '$';
    const huaanFirst = (items, code) => items.slice().sort((a, b) => (a.code === code ? -1 : b.code === code ? 1 : 0));
    const groups = [
      heatGroup('黄金现货', '现货', m.spot, d => heatTile(d.name, formatSpot(d), d.chg, marketDetailUrl('spot', d))),
      heatGroup('黄金期货', '期货', m.futures, d => heatTile(d.name, d.price.toLocaleString(), d.chg, marketDetailUrl('future', d))),
      heatGroup('上海黄金交易所', 'SGE', m.sge, d => heatTile(d.name, d.price.toLocaleString() + ' ' + d.unit, d.chg, marketDetailUrl('sge', d))),
      heatGroup('纸黄金', '银行OTC', m.paperGold, d => heatTile(d.name, (d.name.includes('人民币') ? '¥' : '$') + d.price, d.chg, marketDetailUrl('paperGold', d))),
      heatGroup('波动率', '指数', m.volatility, d => heatTile(d.name, d.value, d.chg, marketDetailUrl('volatility', d))),
      heatGroup('黄金股 · 国内', 'A股', m.stocks.domestic, s => heatTile(s.name, '¥' + s.price, s.chg, marketDetailUrl('domesticStock', s))),
      heatGroup('黄金股 · 海外', '海外', m.stocks.international, s => heatTile(s.name, '$' + s.price, s.chg, marketDetailUrl('international', s))),
      heatGroup('黄金基金 · 国内', '场内ETF', huaanFirst(m.funds.domestic, '518880'), f => heatTile(f.name, '¥' + f.price, f.chg, marketDetailUrl('domesticFund', f))),
      heatGroup('黄金股基金 · 国内', '股票ETF', huaanFirst(m.funds.domesticGoldStock, '159321'), f => heatTile(f.name, '¥' + f.price, f.chg, marketDetailUrl('domesticFund', f))),
      heatGroup('黄金基金 · 海外', 'ETF/全球前十', m.funds.international, f => heatTile(f.name, fundUnit(f.unit) + f.price, f.chg, marketDetailUrl('international', f))),
    ];
    groups.push(`<div class="heat-group">
      <div class="heat-group-head"><span class="name">熊猫金币</span><span class="tag">纪念币</span></div>
      <div class="heat-grid">${m.coins.map(c => heatTileNeutral(c.name, c.price.toLocaleString() + ' ' + c.unit, marketDetailUrl('coin', c))).join('')}</div>
    </div>`);
    document.getElementById('marketHeat').innerHTML = groups.join('');

    document.getElementById('feedersNote').textContent = m.funds.feedersNote;
    renderFundFeeders();

    const statusCls = st => st === '超预期' ? 'bull' : st === '不及预期' ? 'bear' : 'neutral';
    document.getElementById('earningsTimeline').innerHTML = m.earnings.map(e => {
      const perf = e.revenue
        ? `营收 ${e.revenue}(<span class="${chgClass(e.revenueYoY)}">${chgTxt(e.revenueYoY)}</span>) · 净利 ${e.profit}(<span class="${chgClass(e.profitYoY)}">${chgTxt(e.profitYoY)}</span>)`
        : `预期营收 ${e.revenueExp || '-'} · 预期净利 ${e.profitExp || '-'}`;
      return `<div class="earn-row">
        <div class="list-row"><span class="title">${esc(e.date)} · ${esc(e.name)} (${esc(e.period)})</span><span class="badge ${statusCls(e.status)}">${esc(e.status)}</span></div>
        <p class="earn-perf">${perf}</p>
      </div>`;
    }).join('');

    renderRetail();
  }

  function retailTile(item) {
    const amt = (item.price * item.chg / 100).toFixed(1);
    const amtTxt = (item.chg >= 0 ? '+' : '') + amt;
    return `<a class="heat-tile ${tileTone(item.chg)}" href="${marketDetailUrl('retail', item)}" target="_blank" rel="noopener"><p class="t-name">${esc(item.name)}<i class="ti ti-external-link"></i></p><p class="t-val">${item.price} ${esc(item.unit)}<span class="t-chg">${chgTxt(item.chg)} / ${amtTxt}</span></p></a>`;
  }

  function renderRetail() {
    const r = state.market.retail;
    document.getElementById('retailNote').textContent = r.note;
    document.getElementById('retailBank').innerHTML = r.bank.map(retailTile).join('');
    document.getElementById('retailJewelry').innerHTML = r.jewelry.map(retailTile).join('');
  }

  const PERIOD_LABELS = { d1: '当日', w1: '近1周', m1: '近1月', m3: '近3月', m6: '近6月', ytd: '今年以来', y1: '近1年' };
  let feederSort = { key: null, dir: -1 };

  function feederSharePriority(fund) {
    if (/I(?:类)?$/.test(fund.name)) return 0;
    if (/C(?:类)?$/.test(fund.name)) return 1;
    if (/A(?:类)?$/.test(fund.name)) return 2;
    return 3;
  }

  function sortFundFeeders(a, b) {
    const scaleDifference = (Number(b.underlyingEtfScale) || -1) - (Number(a.underlyingEtfScale) || -1);
    if (scaleDifference) return scaleDifference;
    if (a.underlyingEtfCode && a.underlyingEtfCode === b.underlyingEtfCode) {
      const shareDifference = feederSharePriority(a) - feederSharePriority(b);
      if (shareDifference) return shareDifference;
    }
    if (feederSort.key) {
      const returnDifference = ((Number(b.returns[feederSort.key]) || 0) - (Number(a.returns[feederSort.key]) || 0)) * feederSort.dir;
      if (returnDifference) return returnDifference;
    }
    return a.name.localeCompare(b.name, 'zh-CN');
  }

  function renderFundFeeders() {
    const periodKeys = Object.keys(PERIOD_LABELS);
    const headHtml = ['名称', '代码', '类型', ...periodKeys.map(k => PERIOD_LABELS[k])].map((h, i) => {
      if (i < 3) return `<th>${h}</th>`;
      const key = periodKeys[i - 3];
      const active = feederSort.key === key ? (feederSort.dir === -1 ? ' ↓' : ' ↑') : '';
      return `<th class="sortable-th" data-key="${key}">${h}${active}</th>`;
    }).join('');
    const renderTable = items => {
      const sorted = items.slice().sort(sortFundFeeders);
      const rows = sorted.map(f => {
        const cells = periodKeys.map(k => `<td class="${chgClass(f.returns[k])}">${chgTxt(f.returns[k])}</td>`).join('');
        const url = marketDetailUrl('domesticFund', f);
        return `<tr><td><a class="fund-detail-link" href="${url}" target="_blank" rel="noopener">${esc(f.name)}<i class="ti ti-external-link"></i></a></td><td><a class="fund-detail-link" href="${url}" target="_blank" rel="noopener">${esc(f.code)}</a></td><td>${esc(f.category)}</td>${cells}</tr>`;
      }).join('');
      return `<table><thead><tr>${headHtml}</tr></thead><tbody>${rows}</tbody></table>`;
    };
    const funds = state.market.funds.feeders;
    document.getElementById('fundFeedersGold').innerHTML = renderTable(funds.filter(f => !f.category.includes('黄金股')));
    document.getElementById('fundFeedersStock').innerHTML = renderTable(funds.filter(f => f.category.includes('黄金股')));
    document.querySelectorAll('#fundFeedersGold .sortable-th, #fundFeedersStock .sortable-th').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.key;
        feederSort.dir = feederSort.key === key ? -feederSort.dir : -1;
        feederSort.key = key;
        renderFundFeeders();
      });
    });
  }

  function renderNews(filter) {
    const items = state.news.items.filter(n => !filter || filter === '全部' || n.cat === filter);
    document.getElementById('newsList').innerHTML = items.map(n => `
      <div class="news-item">
        <a class="n-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a>${importantTag(n)}
        <p class="n-summary">${esc(n.summary)}</p>
        <div class="n-meta">
          <span>${esc(n.time)}</span>
          <span>${esc(n.source)}</span>
          <span class="badge tag">${esc(n.cat)}</span>
        </div>
      </div>`
    ).join('');
  }

  const NEWS_CAT_ORDER = ['全部', '宏观', '央行', '地缘', '行业', '公司', '基金'];

  function renderNewsFilters() {
    const present = new Set(state.news.items.map(n => n.cat));
    const cats = NEWS_CAT_ORDER.filter(c => c === '全部' || present.has(c));
    document.getElementById('newsFilters').innerHTML = cats.map((c, i) =>
      `<button class="filter-chip ${i === 0 ? 'active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`
    ).join('');
    document.querySelectorAll('#newsFilters .filter-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#newsFilters .filter-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderNews(btn.dataset.cat);
      });
    });
    renderNews('全部');
  }

  function renderSignalTable(signals) {
    const cls = s => s === '看多' ? 'bull' : s === '看空' ? 'bear' : 'neutral';
    return table(['大类', '细分', '当前状态', '建议方向', '周期'], signals.map(s =>
      `<tr><td>${esc(s.category)}</td><td>${esc(s.sub)}</td><td>${esc(s.status)}</td><td><span class="badge ${cls(s.suggest)}">${esc(s.suggest)}</span></td><td>${esc(s.term)}</td></tr>`
    ).join(''));
  }

  let balancePeriod = 'quarter';

  function formatTonnes(value) {
    if (!Number.isFinite(value)) return '—';
    return `${value.toLocaleString('zh-CN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}t`;
  }

  function balanceYoy(value) {
    if (!Number.isFinite(value)) return '<span class="balance-yoy neutral">—</span>';
    const sign = value > 0 ? '+' : '';
    const cls = value > 0 ? 'increase' : value < 0 ? 'decrease' : 'neutral';
    return `<span class="balance-yoy ${cls}">${sign}${value}%</span>`;
  }

  function balanceBar(title, items) {
    const positiveTotal = items.reduce((sum, item) => sum + Math.max(0, item.value), 0);
    const segments = items.filter(item => item.value > 0).map((item, index) => {
      const share = item.value / positiveTotal * 100;
      return `<div class="balance-segment tone-${index % 5}" style="width:${share.toFixed(2)}%" title="${esc(item.name)} ${formatTonnes(item.value)}">
        ${share >= 13 ? `<span>${esc(item.name)}</span>` : ''}
      </div>`;
    }).join('');
    const legend = items.map((item, index) =>
      `<span><i class="balance-legend-swatch tone-${index % 5}"></i>${esc(item.name)} <b>${formatTonnes(item.value)}</b></span>`
    ).join('');
    return `<div class="balance-composition-row">
      <p>${esc(title)}</p>
      <div class="balance-bar">${segments}</div>
      <div class="balance-legend">${legend}</div>
    </div>`;
  }

  function renderSupplyDemand() {
    const data = state.supplyDemand;
    const period = data.periods[balancePeriod];
    const rows = period.rows;
    const totalSupply = rows.find(row => row.name === '总供给');
    const investment = rows.find(row => row.name === '投资需求');
    const centralBank = rows.find(row => row.name === '央行及其他机构');

    document.getElementById('balanceInsight').textContent = period.insight;
    document.getElementById('balanceMetrics').innerHTML = [
      ['总供给', totalSupply],
      ['投资需求', investment],
      ['央行购金', centralBank],
    ].map(([label, row]) => `<div>
      <span>${label}</span>
      <strong>${formatTonnes(row.current)}</strong>
      ${balanceYoy(row.yoy)}
    </div>`).join('');

    document.getElementById('balanceComposition').innerHTML =
      balanceBar('供给构成', period.composition.supply) +
      balanceBar('需求构成', period.composition.demand);

    let currentSection = '';
    const body = rows.map(row => {
      const sectionRow = row.section !== currentSection
        ? `<tr class="balance-section-row"><td colspan="5">${esc(row.section)}</td></tr>`
        : '';
      currentSection = row.section;
      const shareBase = row.section === '供给' ? totalSupply.current : rows.find(item => item.name === '总需求').current;
      const share = row.total ? '100.0%' : `${(row.current / shareBase * 100).toFixed(1)}%`;
      return `${sectionRow}<tr class="${row.total ? 'balance-total-row' : ''} ${row.sub ? 'balance-sub-row' : ''}">
        <td>${esc(row.name)}</td>
        <td>${formatTonnes(row.previous)}</td>
        <td>${formatTonnes(row.current)}</td>
        <td>${balanceYoy(row.yoy)}</td>
        <td>${share}</td>
      </tr>`;
    }).join('');
    document.getElementById('balanceTable').innerHTML = table(
      ['项目', period.comparisonLabel, period.label, '同比', '占总量'],
      body
    );
    document.getElementById('balanceSource').innerHTML =
      `${esc(period.asOf)} · 单位：${esc(data.unit)} · <a href="${esc(data.sourceUrl)}" target="_blank" rel="noopener">${esc(data.source)}</a> · OTC及其他为平衡项，近期数据可能修订`;

    document.querySelectorAll('#balancePeriods button').forEach(button => {
      button.classList.toggle('active', button.dataset.period === balancePeriod);
      button.onclick = () => {
        balancePeriod = button.dataset.period;
        renderSupplyDemand();
      };
    });

    const statusClass = status => status === '可直接获取' ? 'direct' : status === '代理指标' ? 'proxy' : 'partial';
    document.getElementById('supplyDemandAvailability').innerHTML = table(
      ['框架项目', '数据状态', '频率', '主要来源', '适合展示'],
      data.availability.map(item => `<tr>
        <td>${esc(item.factor)}</td>
        <td><span class="availability-status ${statusClass(item.status)}">${esc(item.status)}</span></td>
        <td>${esc(item.frequency)}</td>
        <td>${esc(item.source)}</td>
        <td>${esc(item.visual)}</td>
      </tr>`).join('')
    );
  }

  const GOLDHUB_SERIES_NAMES = {
    'Jewellery fabrication': '首饰加工',
    Technology: '科技用金',
    Investment: '投资需求',
    'Central banks': '央行购金',
    'Mine production': '矿山产量',
    'Recycled gold': '再生金',
    'Net producer hedging': '生产商净套保',
    'North America': '北美',
    Europe: '欧洲',
    Asia: '亚洲',
    Other: '其他',
    AISC: 'AISC',
    '全球合计': '全球合计',
    COMEX: 'COMEX',
    '净多仓': '净多仓',
  };
  const GOLDHUB_COLORS = ['#c9a227', '#8f6d31', '#dfc47c', '#6f5938', '#a9894d'];

  function goldhubName(name) {
    return GOLDHUB_SERIES_NAMES[name] || name;
  }

  function goldhubNumber(value) {
    if (!Number.isFinite(value)) return '—';
    return Math.abs(value) >= 1000
      ? value.toLocaleString('zh-CN', { maximumFractionDigits: 1 })
      : value.toLocaleString('zh-CN', { maximumFractionDigits: 2 });
  }

  function goldhubTicks(min, max, count = 5) {
    const span = max - min || 1;
    return Array.from({ length: count }, (_, index) => min + span * index / (count - 1));
  }

  function goldhubChartSvg(panel) {
    const width = 1000;
    const height = panel.chartHeight || 360;
    const showEveryCategory = panel.showEveryCategory === true
      || (panel.type === 'bar' && panel.categories.length <= 20);
    const rotateCategoryLabels = showEveryCategory && (
      panel.categories.length > 8 || panel.categories.some(category => String(category).length > 4)
    );
    const margin = { top: 18, right: 24, bottom: rotateCategoryLabels ? 72 : 48, left: 70 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const categories = panel.categories;
    const series = panel.series;
    const isStacked = panel.type === 'stacked';
    const allValues = series.flatMap(item => item.data).filter(Number.isFinite);
    let min = Math.min(0, ...allValues);
    let max = Math.max(0, ...allValues);

    if (isStacked) {
      min = 0;
      max = 0;
      categories.forEach((_, index) => {
        let positive = 0;
        let negative = 0;
        series.forEach(item => {
          const value = Number(item.data[index]) || 0;
          if (value >= 0) positive += value;
          else negative += value;
        });
        max = Math.max(max, positive);
        min = Math.min(min, negative);
      });
    }
    if (panel.type === 'line' && min >= 0) min = Math.max(0, min - (max - min || max) * 0.12);
    const pad = (max - min || Math.abs(max) || 1) * 0.08;
    max += pad;
    if (min < 0) min -= pad;

    const y = value => margin.top + (max - value) / (max - min || 1) * plotHeight;
    const xStep = plotWidth / Math.max(1, categories.length);
    const x = index => margin.left + xStep * (index + 0.5);
    const ticks = goldhubTicks(min, max);
    const grid = ticks.map(value => `
      <line class="goldhub-grid" x1="${margin.left}" y1="${y(value)}" x2="${width - margin.right}" y2="${y(value)}"></line>
      <text class="goldhub-axis-label" x="${margin.left - 9}" y="${y(value) + 3}" text-anchor="end">${goldhubNumber(value)}</text>
    `).join('');
    const labelEvery = showEveryCategory ? 1 : Math.max(1, Math.ceil(categories.length / 8));
    const labels = categories.map((category, index) => (
      index % labelEvery === 0 || index === categories.length - 1
        ? rotateCategoryLabels
          ? `<text class="goldhub-axis-label" x="${x(index)}" y="${height - 35}" text-anchor="end" transform="rotate(-28 ${x(index)} ${height - 35})">${esc(String(category).replace(/-01$/, ''))}</text>`
          : `<text class="goldhub-axis-label" x="${x(index)}" y="${height - 17}" text-anchor="middle">${esc(String(category).replace(/-01$/, ''))}</text>`
        : ''
    )).join('');

    let marks = '';
    if (panel.type === 'line') {
      marks = series.map((item, seriesIndex) => {
        const points = item.data.map((value, index) =>
          Number.isFinite(value) ? `${x(index).toFixed(1)},${y(value).toFixed(1)}` : ''
        ).filter(Boolean).join(' ');
        const dots = panel.showDots === false ? '' : item.data.map((value, index) => Number.isFinite(value)
          ? `<circle class="goldhub-dot goldhub-mark" tabindex="0" cx="${x(index)}" cy="${y(value)}" r="3.4" fill="${GOLDHUB_COLORS[seriesIndex % GOLDHUB_COLORS.length]}" data-tip="${esc(`${categories[index]}｜${goldhubName(item.name)}：${goldhubNumber(value)} ${panel.unit}`)}"></circle>`
          : '').join('');
        return `<polyline class="goldhub-line" points="${points}" stroke="${GOLDHUB_COLORS[seriesIndex % GOLDHUB_COLORS.length]}"></polyline>${dots}`;
      }).join('');
    } else if (isStacked) {
      const barWidth = Math.max(4, Math.min(46, xStep * 0.68));
      const positive = Array(categories.length).fill(0);
      const negative = Array(categories.length).fill(0);
      marks = series.map((item, seriesIndex) => item.data.map((value, index) => {
        if (!Number.isFinite(value)) return '';
        const start = value >= 0 ? positive[index] : negative[index];
        const end = start + value;
        if (value >= 0) positive[index] = end;
        else negative[index] = end;
        const top = Math.min(y(start), y(end));
        const barHeight = Math.max(1, Math.abs(y(start) - y(end)));
        return `<rect class="goldhub-mark" tabindex="0" x="${x(index) - barWidth / 2}" y="${top}" width="${barWidth}" height="${barHeight}" rx="1.5" fill="${GOLDHUB_COLORS[seriesIndex % GOLDHUB_COLORS.length]}" data-tip="${esc(`${categories[index]}｜${goldhubName(item.name)}：${goldhubNumber(value)} ${panel.unit}`)}"></rect>`;
      }).join('')).join('');
    } else if (panel.type === 'grouped') {
      const groupWidth = Math.max(8, Math.min(72, xStep * 0.78));
      const barWidth = Math.max(2, groupWidth / Math.max(1, series.length));
      marks = series.map((item, seriesIndex) => item.data.map((value, index) => {
        if (!Number.isFinite(value)) return '';
        const left = x(index) - groupWidth / 2 + seriesIndex * barWidth;
        const top = Math.min(y(0), y(value));
        const barHeight = Math.max(1, Math.abs(y(0) - y(value)));
        return `<rect class="goldhub-mark" tabindex="0" x="${left}" y="${top}" width="${Math.max(1, barWidth - 1)}" height="${barHeight}" rx="1" fill="${GOLDHUB_COLORS[seriesIndex % GOLDHUB_COLORS.length]}" data-tip="${esc(`${categories[index]}｜${goldhubName(item.name)}：${goldhubNumber(value)} ${panel.unit}`)}"></rect>`;
      }).join('')).join('');
    } else {
      const values = series[0].data;
      const barWidth = Math.max(5, Math.min(58, xStep * 0.62));
      marks = values.map((value, index) => {
        if (!Number.isFinite(value)) return '';
        const top = Math.min(y(0), y(value));
        const barHeight = Math.max(1, Math.abs(y(0) - y(value)));
        return `<rect class="goldhub-mark" tabindex="0" x="${x(index) - barWidth / 2}" y="${top}" width="${barWidth}" height="${barHeight}" rx="2" fill="${GOLDHUB_COLORS[0]}" data-tip="${esc(`${categories[index]}｜${goldhubName(series[0].name)}：${goldhubNumber(value)} ${panel.unit}`)}"></rect>`;
      }).join('');
    }

    return `<svg class="goldhub-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(panel.title)}">
      ${grid}
      <line class="goldhub-grid" x1="${margin.left}" y1="${y(0)}" x2="${width - margin.right}" y2="${y(0)}"></line>
      ${marks}
      ${labels}
      <text class="goldhub-axis-label" x="${margin.left}" y="11">${esc(panel.unit)}</text>
    </svg>`;
  }

  function bindGoldhubTooltips(stage) {
    const tooltip = stage.querySelector('.goldhub-chart-tooltip');
    const show = target => {
      tooltip.textContent = target.dataset.tip;
      tooltip.style.display = 'block';
      const stageRect = stage.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const left = Math.min(stage.clientWidth - 220, Math.max(8, targetRect.left - stageRect.left + targetRect.width / 2));
      const top = Math.max(8, targetRect.top - stageRect.top - 52);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    };
    stage.querySelectorAll('[data-tip]').forEach(mark => {
      mark.addEventListener('mouseenter', () => show(mark));
      mark.addEventListener('focus', () => show(mark));
      mark.addEventListener('click', () => show(mark));
      mark.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
      mark.addEventListener('blur', () => { tooltip.style.display = 'none'; });
    });
  }

  function renderMarketPremium() {
    const chart = state.goldhubCharts?.charts?.premium;
    const root = document.getElementById('marketPremium');
    if (!chart || !root) return;
    root.innerHTML = chart.panels.map(panel => `
      <section class="goldhub-panel">
        <div class="goldhub-chart-stage">
          ${goldhubChartSvg(panel)}
          <div class="goldhub-chart-tooltip" role="status"></div>
        </div>
        <div class="goldhub-legend">${panel.series.map((item, index) =>
          `<span><i style="background:${GOLDHUB_COLORS[index % GOLDHUB_COLORS.length]}"></i>${esc(goldhubName(item.name))}</span>`
        ).join('')}</div>
      </section>
    `).join('');
    document.getElementById('marketPremiumMeta').innerHTML =
      `<span>截至 ${esc(chart.asOf)}</span><span>${esc(chart.frequency)}</span><span>5日滚动平均</span>`;
    document.getElementById('marketPremiumSource').innerHTML =
      `数据来源：<a href="${esc(chart.sourceUrl)}" target="_blank" rel="noopener">世界黄金协会 Goldhub</a> · 单位：美元/盎司`;
    root.querySelectorAll('.goldhub-chart-stage').forEach(bindGoldhubTooltips);
  }

  function renderAssetPerformance() {
    const data = state.assetPerformance;
    const root = document.getElementById('assetPerformance');
    if (!data?.items?.length || !root) return;
    const items = data.items;
    const width = 640;
    const height = Math.max(430, 82 + items.length * 25);
    const margin = { top: 44, right: 42, bottom: 38, left: 126 };
    const plotWidth = width - margin.left - margin.right;
    const rowHeight = (height - margin.top - margin.bottom) / items.length;
    const available = items.filter(item => Number.isFinite(item.ytdReturn) && Number.isFinite(item.volatility));
    const returns = available.map(item => item.ytdReturn);
    const minReturn = Math.min(-10, Math.floor(Math.min(...returns) / 10) * 10);
    const maxReturn = Math.max(10, Math.ceil(Math.max(...returns) / 10) * 10);
    const maxVolatility = Math.max(30, Math.ceil(Math.max(...available.map(item => item.volatility)) / 10) * 10);
    const returnX = value => margin.left + (value - minReturn) / (maxReturn - minReturn) * plotWidth;
    const volatilityX = value => margin.left + value / maxVolatility * plotWidth;
    const zeroX = returnX(0);
    const returnTicks = goldhubTicks(minReturn, maxReturn, 6);
    const volatilityTicks = goldhubTicks(0, maxVolatility, 5);
    const linePoints = items.map((item, index) =>
      Number.isFinite(item.volatility) ? `${volatilityX(item.volatility)},${margin.top + rowHeight * (index + 0.5)}` : null
    ).filter(Boolean).join(' ');
    root.innerHTML = `<div class="asset-performance-stage">
      <svg class="asset-performance-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与大类资产年初至今收益率和近20日年化波动率">
        ${returnTicks.map(tick => {
          const x = returnX(tick);
          return `<line class="asset-grid" x1="${x}" y1="${margin.top}" x2="${x}" y2="${height - margin.bottom}"></line>
            <text class="asset-axis-label" x="${x}" y="${height - 12}" text-anchor="middle">${tick.toFixed(0)}%</text>`;
        }).join('')}
        ${volatilityTicks.map(tick =>
          `<text class="asset-vol-axis-label" x="${volatilityX(tick)}" y="17" text-anchor="middle">${tick.toFixed(0)}%</text>`
        ).join('')}
        <text class="asset-axis-title" x="${margin.left}" y="${height - 1}">年初至今收益率</text>
        <text class="asset-vol-axis-title" x="${margin.left}" y="32">近20日年化波动率</text>
        <line class="asset-zero-line" x1="${zeroX}" y1="${margin.top}" x2="${zeroX}" y2="${height - margin.bottom}"></line>
        ${items.map((item, index) => {
          const y = margin.top + rowHeight * index + rowHeight * 0.23;
          if (!Number.isFinite(item.ytdReturn)) {
            return `<text class="asset-name" x="${margin.left - 9}" y="${y + rowHeight * 0.43}" text-anchor="end">${esc(item.name)}</text>
              <text class="asset-unavailable" x="${margin.left + 5}" y="${y + rowHeight * 0.43}">暂无可比行情</text>`;
          }
          const end = returnX(item.ytdReturn);
          const x = Math.min(zeroX, end);
          const barWidth = Math.max(1.5, Math.abs(end - zeroX));
          return `<text class="asset-name ${item.group === '黄金' ? 'is-gold' : ''}" x="${margin.left - 9}" y="${y + rowHeight * 0.43}" text-anchor="end">${esc(item.name)}</text>
            <rect class="asset-return-bar ${item.ytdReturn < 0 ? 'negative' : ''} ${item.group === '黄金' ? 'is-gold' : ''}"
              x="${x}" y="${y}" width="${barWidth}" height="${rowHeight * 0.36}" rx="3"
              tabindex="0" data-tip="${esc(item.name)} · 年初至今 ${item.ytdReturn >= 0 ? '+' : ''}${item.ytdReturn.toFixed(2)}%"></rect>
            <text class="asset-return-value" x="${item.ytdReturn >= 0 ? end + 5 : end - 5}" y="${y + rowHeight * 0.42}"
              text-anchor="${item.ytdReturn >= 0 ? 'start' : 'end'}">${item.ytdReturn >= 0 ? '+' : ''}${item.ytdReturn.toFixed(1)}%</text>`;
        }).join('')}
        <polyline class="asset-vol-line" points="${linePoints}"></polyline>
        ${items.map((item, index) => {
          if (!Number.isFinite(item.volatility)) return '';
          const x = volatilityX(item.volatility);
          const y = margin.top + rowHeight * (index + 0.5);
          return `<circle class="asset-vol-dot" cx="${x}" cy="${y}" r="4.2" tabindex="0"
            data-tip="${esc(item.name)} · 近20日年化波动率 ${item.volatility.toFixed(2)}%"></circle>`;
        }).join('')}
      </svg>
      <div class="goldhub-chart-tooltip" role="status"></div>
    </div>
    <div class="asset-performance-legend"><span><i class="bar"></i>收益率</span><span><i class="line"></i>波动率</span></div>`;
    document.getElementById('assetPerformanceMeta').innerHTML =
      `<span>${esc(data.period)}</span><span>截至 ${esc(data.updatedAt.slice(0, 16))}</span>`;
    const sourceLinks = Array.isArray(data.sources) && data.sources.length
      ? data.sources.map(source => `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.name)}</a>`).join('、')
      : `<a href="${esc(data.sourceUrl)}" target="_blank" rel="noopener">${esc(data.source)}</a>`;
    document.getElementById('assetPerformanceSource').innerHTML =
      `数据来源：${sourceLinks} · 收益按各资产本币计价；带“代理”的资产使用可交易ETF或期货；波动率按日收益率年化`;
    bindGoldhubTooltips(root.querySelector('.asset-performance-stage'));
  }

  function renderTradingVolumes() {
    const chart = state.goldhubCharts?.charts?.tradingVolumes;
    const root = document.getElementById('marketTradingVolumes');
    if (!chart?.items?.length || !root) return;
    const items = chart.items.map(item => ({
      ...item,
      total: item.children?.length
        ? item.children.reduce((sum, child) => sum + child.value, 0)
        : item.value,
    }));
    const width = 640;
    const height = 430;
    const margin = { top: 28, right: 55, bottom: 42, left: 188 };
    const plotWidth = width - margin.left - margin.right;
    const rowHeight = (height - margin.top - margin.bottom) / items.length;
    const maxValue = Math.ceil(Math.max(...items.map(item => item.total)) / 100) * 100;
    const x = value => margin.left + value / maxValue * plotWidth;
    const ticks = goldhubTicks(0, maxValue, 5);
    const goldOrder = ['场外成交', '交易所成交', '黄金ETF'];
    const groupClass = group => ({ 债券: 'bond', 外汇: 'fx', 股票: 'stock' }[group] || 'other');
    root.innerHTML = `<div class="trading-volume-stage">
      <svg class="trading-volume-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与主要资产年平均日交易量">
        <defs>
          <pattern id="tradingHatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="8"></line>
          </pattern>
        </defs>
        ${ticks.map(tick => `<line class="trading-grid" x1="${x(tick)}" y1="${margin.top}" x2="${x(tick)}" y2="${height - margin.bottom}"></line>
          <text class="trading-axis-label" x="${x(tick)}" y="${height - 17}" text-anchor="middle">${tick}</text>`).join('')}
        <text class="trading-axis-title" x="${width - margin.right}" y="${height - 2}" text-anchor="end">${esc(chart.unit)}</text>
        ${items.map((item, index) => {
          const y = margin.top + rowHeight * index + rowHeight * 0.2;
          const barHeight = rowHeight * 0.34;
          const label = `<text class="trading-name ${item.name === '黄金' ? 'is-gold' : ''}" x="${margin.left - 9}" y="${y + barHeight * 0.72}" text-anchor="end">${esc(item.name)}</text>`;
          if (!item.children?.length) {
            return `${label}<rect class="trading-bar ${groupClass(item.group)}" x="${margin.left}" y="${y}" width="${x(item.total) - margin.left}" height="${barHeight}" rx="3"
              tabindex="0" data-tip="${esc(item.name)} · ${goldhubNumber(item.total)} ${esc(chart.unit)}"></rect>
              <text class="trading-value" x="${x(item.total) + 5}" y="${y + barHeight * 0.72}">${goldhubNumber(item.total)}</text>`;
          }
          let offset = margin.left;
          const children = item.children.slice().sort((a, b) => goldOrder.indexOf(a.name) - goldOrder.indexOf(b.name));
          const segments = children.map(child => {
            const segmentWidth = child.value / maxValue * plotWidth;
            const type = child.name === '交易所成交' ? 'exchange' : child.name === '黄金ETF' ? 'etf' : 'otc';
            const segment = `<rect class="trading-bar gold-${type}" x="${offset}" y="${y}" width="${segmentWidth}" height="${barHeight}"
              tabindex="0" data-tip="${esc(child.name)} · ${goldhubNumber(child.value)} ${esc(chart.unit)}"></rect>`;
            offset += segmentWidth;
            return segment;
          }).join('');
          return `${label}${segments}<text class="trading-value is-gold" x="${x(item.total) + 5}" y="${y + barHeight * 0.72}">${goldhubNumber(item.total)}</text>`;
        }).join('')}
      </svg>
      <div class="goldhub-chart-tooltip" role="status"></div>
    </div>
    <div class="trading-volume-legend">
      <span><i class="bond"></i>债券</span><span><i class="fx"></i>外汇</span><span><i class="stock"></i>股票</span>
      <span><i class="gold-otc"></i>黄金场外</span><span><i class="gold-exchange"></i>黄金交易所</span><span><i class="gold-etf"></i>黄金ETF</span>
    </div>`;
    document.getElementById('marketTradingMeta').innerHTML =
      `<span>截至 ${esc(chart.asOf)}</span><span>${esc(chart.frequency)}</span>`;
    document.getElementById('marketTradingSource').innerHTML =
      `数据来源：<a href="${esc(chart.sourceUrl)}" target="_blank" rel="noopener">世界黄金协会 Goldhub</a> · ${esc(chart.unit)}`;
    bindGoldhubTooltips(root.querySelector('.trading-volume-stage'));
  }

  let cbdUi = {
    page: 'snapshot',
    periodicity: 'QTD_FULL',
    chartType: 'tree_map',
    metric: 'gold_reserves_tns',
    period: null,
    startDate: null,
    endDate: null,
    selectedDates: [],
  };
  let cbdPayload = null;
  let cbdCacheMeta = null;

  const CBD_METRIC_NAMES = {
    gold_reserves: '黄金储备（百万美元）',
    gold_reserves_tns: '黄金储备（吨）',
    fx_reserves: '外汇储备（百万美元）',
    holdings_pct: '黄金占总储备（%）',
    total_reserves: '总储备（百万美元）',
  };
  const CBD_COUNTRY_NAMES = {
    'United States of America': '美国', Germany: '德国', Italy: '意大利', France: '法国',
    China: '中国', 'Russian Federation': '俄罗斯', India: '印度', Japan: '日本',
    Poland: '波兰', Turkey: '土耳其', Uzbekistan: '乌兹别克斯坦', Kazakhstan: '哈萨克斯坦',
    'United Kingdom': '英国', Thailand: '泰国', Singapore: '新加坡', Brazil: '巴西',
    Mexico: '墨西哥', Indonesia: '印度尼西亚', Ukraine: '乌克兰', Bulgaria: '保加利亚',
    'Czech Republic': '捷克', Switzerland: '瑞士', Netherlands: '荷兰', Australia: '澳大利亚',
  };

  function cbdCountryName(name) {
    return CBD_COUNTRY_NAMES[name] || name;
  }

  function cbdDateLabel(date, periodicity = cbdUi.periodicity) {
    const [year, month] = String(date).split('-');
    if (periodicity === 'LAST_YEAR_END') return `${year}年`;
    return `${year} Q${Math.ceil(Number(month) / 3)}`;
  }

  function cbdMetricOptions(options) {
    return (options.metrics || []).flat();
  }

  function updateCbdMeta() {
    if (!cbdCacheMeta?.fetchedAt) return;
    const updated = new Date(cbdCacheMeta.fetchedAt).toLocaleString('zh-CN', {
      hour12: false,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
    const status = cbdCacheMeta.status === 'stale'
      ? `接口暂不可用 · 显示上次成功更新 ${updated}`
      : `数据更新 ${updated}`;
    document.getElementById('goldhubChartMeta').innerHTML =
      `<span>${esc(status)}</span><span>月度与季度按协会计划更新</span><span>每日检查协会新版本</span>`;
  }

  function cbdTableHtml(tableData) {
    if (!tableData?.rows?.length) return '';
    const headers = (tableData.headers?.[0] || []).map(item => item.val);
    return `<div class="cbd-table-tools"><input id="cbdTableSearch" type="search" placeholder="搜索国家或地区"></div>
      <div class="table-wrap cbd-table-wrap"><table class="cbd-table"><thead><tr>${headers.map(header =>
        `<th>${esc(header.replace('Country', '国家').replace('Region', '地区').replace('Economic grouping', '收入组').replace('FX Reserves', '外汇储备').replace('Total Reserves', '总储备').replace('Gold Reserves Tonnes', '黄金储备/吨').replace('Gold Reserves Millions', '黄金储备/百万美元').replace('Holdings %', '黄金占比'))}</th>`
      ).join('')}</tr></thead><tbody>${tableData.rows.map(row =>
        `<tr data-search="${esc(row.map(cell => cell.val).join(' ').toLowerCase())}">${row.map((cell, index) => {
          const raw = cell.val;
          const numeric = Number(raw);
          const value = index === 0 ? cbdCountryName(raw) : Number.isFinite(numeric) ? goldhubNumber(numeric) : raw === 'AWAITED' ? '待更新' : raw;
          return `<td>${esc(String(value))}</td>`;
        }).join('')}</tr>`
      ).join('')}</tbody></table></div>`;
  }

  function cbdSnapshotHtml(data) {
    const p = cbdUi.periodicity;
    const dates = Object.keys(data.treeMap?.[p] || {}).sort().reverse();
    if (!dates.length) return '<p class="cbd-empty">暂无快照数据</p>';
    if (!dates.includes(cbdUi.period)) cbdUi.period = dates[0];
    const metric = cbdUi.metric;
    const metricName = CBD_METRIC_NAMES[metric] || metric;
    const tree = (data.treeMap[p][cbdUi.period]?.[metric]?.data || [])
      .filter(item => Number.isFinite(item.value) && item.value > 0)
      .sort((a, b) => b.value - a.value);
    const regions = new Map();
    tree.forEach(item => {
      const group = regions.get(item.parent) || [];
      group.push(item);
      regions.set(item.parent, group);
    });
    const regionEntries = [...regions.entries()].map(([name, items]) => ({
      name, items, total: items.reduce((sum, item) => sum + item.value, 0),
    })).sort((a, b) => b.total - a.total);
    const total = regionEntries.reduce((sum, region) => sum + region.total, 0);
    const treeHtml = regionEntries.map((region, regionIndex) => {
      const basis = Math.max(12, region.total / total * 100);
      return `<section class="cbd-region cbd-region-${regionIndex % 6}" style="flex:${basis} 1 ${basis}%">
        <strong>${esc(region.name)}</strong>
        <div>${region.items.slice(0, 14).map(item => {
          const share = item.value / region.total * 100;
          return `<button class="cbd-tree-item" style="flex:${Math.max(7, share)} 1 ${Math.max(7, share)}%" data-tip="${esc(`${cbdCountryName(item.name)}：${goldhubNumber(item.value)}`)}"><span>${esc(cbdCountryName(item.name))}</span><b>${goldhubNumber(item.value)}</b></button>`;
        }).join('')}</div>
      </section>`;
    }).join('');
    const changes = data.barChart?.[p]?.[cbdUi.period]?.[metric];
    const cats = changes?.categories || [];
    const negative = changes?.series?.data?.[0]?.data || [];
    const positive = changes?.series?.data?.[1]?.data || [];
    const maxChange = Math.max(1, ...negative.concat(positive).filter(Number.isFinite).map(Math.abs));
    const changeHtml = cats.map((name, index) => {
      const value = Number.isFinite(positive[index]) ? positive[index] : negative[index];
      const cls = value >= 0 ? 'up' : 'down';
      return `<div class="cbd-change-row ${cls}"><span>${esc(cbdCountryName(name))}</span><strong>${value >= 0 ? '+' : ''}${goldhubNumber(value)}</strong><i style="width:${Math.max(2, Math.abs(value) / maxChange * 100)}%"></i></div>`;
    }).join('');
    const column = data.columnChart?.[p]?.[cbdUi.period]?.[metric];
    const countryMap = data.countries || {};
    const columnRows = Object.entries(column?.data || {}).filter(([, value]) => Number.isFinite(value))
      .sort((a, b) => b[1] - a[1]).slice(0, 24);
    const columnPanel = {
      title: metricName,
      type: 'bar',
      unit: column?.unit || '',
      categories: columnRows.map(([iso]) => cbdCountryName(countryMap[iso]?.countryNameDefault || iso)),
      series: [{ name: metricName, data: columnRows.map(([, value]) => value) }],
    };
    const tableData = data.table?.[p]?.[cbdUi.period];
    return `<div class="cbd-row cbd-snapshot-controls">
        <label>日期<select id="cbdPeriodSelect">${dates.map(date => `<option value="${date}" ${date === cbdUi.period ? 'selected' : ''}>${cbdDateLabel(date)}</option>`).join('')}</select></label>
      </div>
      ${cbdUi.chartType === 'tree_map' ? `<div class="cbd-snapshot-grid"><section><h3>${esc(cbdDateLabel(cbdUi.period))}：${esc(metricName)}</h3><div class="cbd-treemap">${treeHtml}</div></section><section><h3>最大增持 / 减持</h3><div class="cbd-change-list">${changeHtml}</div></section></div>` : `<section class="goldhub-panel"><p class="goldhub-panel-title">${esc(cbdDateLabel(cbdUi.period))}：${esc(metricName)}</p><div class="goldhub-chart-stage">${goldhubChartSvg(columnPanel)}<div class="goldhub-chart-tooltip" role="status"></div></div></section>`}
      <section class="cbd-data-table"><h3>${esc(metricName)}：${esc(cbdDateLabel(cbdUi.period))}快照</h3>${cbdTableHtml(tableData)}</section>`;
  }

  function cbdDateRangeHtml(data) {
    const p = cbdUi.periodicity;
    const metric = cbdUi.metric;
    const line = data.linechart?.[p]?.[metric];
    if (!line?.data?.length) return '<p class="cbd-empty">当前区间暂无数据</p>';
    const ranked = line.data.slice().sort((a, b) => {
      const last = series => [...series.data].reverse().find(point => Number.isFinite(point[1]))?.[1] || 0;
      return last(b) - last(a);
    }).slice(0, 10);
    const timestamps = ranked[0].data.map(point => point[0]);
    const panel = {
      title: CBD_METRIC_NAMES[metric] || metric,
      type: 'line',
      unit: cbdMetricOptions(data.options).find(item => item.key === metric)?.unitName || '',
      categories: timestamps.map(timestamp => new Date(timestamp).toISOString().slice(0, 10)),
      series: ranked.map(series => ({
        name: cbdCountryName(data.countries?.[series.name]?.countryNameDefault || series.name),
        data: series.data.map(point => Number.isFinite(point[1]) ? point[1] : null),
      })),
    };
    const tableData = data.table?.[p]?.[metric];
    return `<div class="cbd-row cbd-range-controls"><label>开始<input id="cbdStartDate" type="date" value="${esc(cbdUi.startDate || data.options.selectedFrom)}"></label><label>结束<input id="cbdEndDate" type="date" value="${esc(cbdUi.endDate || data.options.selectedTo)}"></label><button id="cbdApplyRange" class="filter-chip active">更新区间</button></div>
      <section class="goldhub-panel"><p class="goldhub-panel-title">主要央行：${esc(panel.title)}</p><div class="goldhub-chart-stage">${goldhubChartSvg(panel)}<div class="goldhub-chart-tooltip" role="status"></div></div><div class="goldhub-legend">${panel.series.map((item, index) => `<span><i style="background:${GOLDHUB_COLORS[index % GOLDHUB_COLORS.length]}"></i>${esc(item.name)}</span>`).join('')}</div></section>
      <section class="cbd-data-table"><h3>区间明细</h3>${cbdTableHtml(tableData)}</section>`;
  }

  function cbdCompareHtml(data) {
    const p = cbdUi.periodicity;
    const metric = cbdUi.metric;
    const chart = data.columnChart?.[p]?.[metric];
    if (!chart?.series?.length) return '<p class="cbd-empty">当前日期暂无可比较数据</p>';
    const categories = chart.categories || [];
    const indexes = categories.map((name, index) => ({
      index,
      value: Math.max(...chart.series.map(series => Number(series.data[index]) || 0)),
    })).sort((a, b) => b.value - a.value).slice(0, 16).map(item => item.index);
    const panel = {
      title: CBD_METRIC_NAMES[metric] || metric,
      type: 'grouped',
      unit: chart.unit || cbdMetricOptions(data.options).find(item => item.key === metric)?.unitName || '',
      categories: indexes.map(index => cbdCountryName(data.countries?.[categories[index]]?.countryNameDefault || categories[index])),
      series: chart.series.map(series => ({
        name: cbdDateLabel(series.name),
        data: indexes.map(index => Number.isFinite(series.data[index]) ? series.data[index] : null),
      })),
    };
    const dates = cbdUi.selectedDates.length ? cbdUi.selectedDates : data.options.selectedDates;
    const tableData = data.table?.[p]?.[metric];
    return `<div class="cbd-row cbd-compare-controls">${dates.map((date, index) => `<label>日期${index + 1}<input class="cbdCompareDate" data-index="${index}" type="date" value="${esc(date)}"></label>`).join('')}<button id="cbdApplyCompare" class="filter-chip active">更新对比</button></div>
      <section class="goldhub-panel"><p class="goldhub-panel-title">${esc(panel.title)}跨期比较</p><div class="goldhub-chart-stage">${goldhubChartSvg(panel)}<div class="goldhub-chart-tooltip" role="status"></div></div><div class="goldhub-legend">${panel.series.map((item, index) => `<span><i style="background:${GOLDHUB_COLORS[index % GOLDHUB_COLORS.length]}"></i>${esc(item.name)}</span>`).join('')}</div></section>
      <section class="cbd-data-table"><h3>跨期明细</h3>${cbdTableHtml(tableData)}</section>`;
  }

  function cbdCorrelationHtml() {
    const chart = state.goldhubCharts?.charts?.centralBanks?.correlation;
    if (!chart?.rows?.length) return '';
    const width = 1000;
    const height = 660;
    const margin = { top: 38, right: 76, bottom: 72, left: 64 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const shareMax = Math.max(75, Math.ceil(Math.max(...chart.rows.flatMap(row => [row.reserveShare, row.usdShare])) / 5) * 5);
    const priceMax = Math.max(4000, Math.ceil(Math.max(...chart.rows.map(row => row.goldPrice)) / 1000) * 1000);
    const x = index => margin.left + index / (chart.rows.length - 1) * plotWidth;
    const yShare = value => margin.top + plotHeight - value / shareMax * plotHeight;
    const yPrice = value => margin.top + plotHeight - value / priceMax * plotHeight;
    const shareTicks = goldhubTicks(0, shareMax, 6);
    const priceTicks = goldhubTicks(0, priceMax, 6);
    const yearIndexes = Array.from(new Set(Array.from({ length: 8 }, (_, index) =>
      Math.round(index * (chart.rows.length - 1) / 7)
    )));
    const sharePath = chart.rows.map((row, index) =>
      `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yShare(row.reserveShare).toFixed(2)}`
    ).join(' ');
    const pricePath = chart.rows.map((row, index) =>
      `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yPrice(row.goldPrice).toFixed(2)}`
    ).join(' ');
    const usdPath = chart.rows.map((row, index) =>
      `${index ? 'L' : 'M'}${x(index).toFixed(2)},${yShare(row.usdShare).toFixed(2)}`
    ).join(' ');
    const last = chart.rows.at(-1);
    return `<section class="cbd-correlation-panel">
      <div class="cbd-correlation-head cbd-overview-card-head">
        <div><h3>${esc(chart.title)}</h3><p>${esc(chart.subtitle)}</p></div>
        <strong>${chart.correlationSince}年以来黄金储备占比与金价相关系数 ${chart.correlation >= 0 ? '+' : ''}${chart.correlation.toFixed(2)}</strong>
      </div>
      <div class="cbd-correlation-stage">
        <svg class="cbd-correlation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金价格与全球官方黄金储备、美元储备占比三线双轴图">
          ${shareTicks.map((tick, index) => `<line class="cbd-correlation-grid" x1="${margin.left}" x2="${width - margin.right}" y1="${yShare(tick)}" y2="${yShare(tick)}"></line>
            <text class="cbd-correlation-axis" x="${margin.left - 9}" y="${yShare(tick) + 4}" text-anchor="end">${tick.toFixed(0)}%</text>
            <text class="cbd-correlation-axis" x="${width - margin.right + 9}" y="${yShare(tick) + 4}">$${Math.round(priceTicks[index]).toLocaleString()}</text>`).join('')}
          ${yearIndexes.map(index => `<text class="cbd-correlation-axis" x="${x(index)}" y="${height - 16}" text-anchor="middle">${chart.rows[index].year}</text>`).join('')}
          <text class="cbd-correlation-axis-title" x="${margin.left}" y="20">全球官方黄金储备、美元储备占比</text>
          <text class="cbd-correlation-axis-title" x="${width - margin.right}" y="20" text-anchor="end">COMEX黄金年度均价（美元/盎司）</text>
          <path class="cbd-share-line" d="${sharePath}"></path>
          <path class="cbd-usd-line" d="${usdPath}"></path>
          <path class="cbd-price-line" d="${pricePath}"></path>
          ${chart.rows.map((row, index) => `<circle class="cbd-correlation-hit" cx="${x(index)}" cy="${yShare(row.reserveShare)}" r="8"
            tabindex="0" data-tip="${row.year}年 · 黄金储备占比 ${row.reserveShare.toFixed(2)}% · 美元储备占比 ${row.usdShare.toFixed(2)}% · COMEX黄金均价 $${row.goldPrice.toLocaleString()}"></circle>`).join('')}
          <text class="cbd-share-label" x="${x(chart.rows.length - 1) - 7}" y="${yShare(last.reserveShare) - 9}" text-anchor="end">${last.reserveShare.toFixed(1)}%</text>
          <text class="cbd-usd-label" x="${x(chart.rows.length - 1) - 7}" y="${yShare(last.usdShare) - 9}" text-anchor="end">${last.usdShare.toFixed(1)}%</text>
          <text class="cbd-price-label" x="${x(chart.rows.length - 1) - 7}" y="${yPrice(last.goldPrice) + 17}" text-anchor="end">$${Math.round(last.goldPrice).toLocaleString()}</text>
        </svg>
        <div class="goldhub-chart-tooltip" role="status"></div>
      </div>
      <div class="cbd-correlation-legend"><span><i class="share"></i>黄金储备占比</span><span><i class="usd"></i>美元储备占比</span><span><i class="price"></i>黄金年度均价</span></div>
    </section>`;
  }

  function cbdPurchaseChartsHtml() {
    const panels = state.goldhubCharts?.charts?.centralBanks?.purchasePanels;
    if (!panels?.length) return '';
    return panels.map(panel => `<section class="goldhub-panel cbd-purchase-panel">
      <div class="cbd-overview-card-head"><p class="goldhub-panel-title">${esc(panel.title)}</p><p>${esc(panel.subtitle || '')}</p></div>
      <div class="goldhub-chart-stage">${goldhubChartSvg(panel)}<div class="goldhub-chart-tooltip" role="status"></div></div>
      <div class="goldhub-legend">${panel.series.map((series, index) => `<span><i style="background:${GOLDHUB_COLORS[index % GOLDHUB_COLORS.length]}"></i>${esc(series.name)}</span>`).join('')}</div>
    </section>`).join('');
  }

  function renderCentralBanks() {
    const root = document.getElementById('goldhubChartPanels');
    const options = cbdPayload.options;
    const metrics = cbdMetricOptions(options);
    if (!metrics.some(item => item.key === cbdUi.metric)) {
      cbdUi.metric = metrics.find(item => item.key === 'gold_reserves_tns')?.key || metrics[0]?.key;
    }
    root.innerHTML = `<div class="cbd-dashboard">
      <div class="cbd-overview-grid">${cbdPurchaseChartsHtml()}${cbdCorrelationHtml()}</div>
      <p class="source-note cbd-purchase-source">数据来源：世界黄金协会 Goldhub / IMF IFS、IMF COFER、Yahoo Finance。全球年度净购金量截至2025年；主要国家2026年数据为截至2026年3月31日已公布变化，不代表全年；黄金储备占比按各国黄金储备市值合计 ÷ 官方总储备合计计算，美元份额采用COFER期末口径，价格为年度日收盘均值。</p>
      <div class="cbd-tabs">${[
        ['snapshot', '快照'], ['date_range', '日期区间'], ['compare_dates', '日期对比'],
      ].map(([key, label]) => `<button class="${cbdUi.page === key ? 'active' : ''}" data-cbd-page="${key}">${label}</button>`).join('')}</div>
      <div class="cbd-toolbar">
        ${cbdUi.page === 'snapshot' ? `<div class="cbd-segment"><button class="${cbdUi.chartType === 'tree_map' ? 'active' : ''}" data-cbd-chart="tree_map">树状图</button><button class="${cbdUi.chartType === 'column_chart' ? 'active' : ''}" data-cbd-chart="column_chart">柱状图</button></div>` : ''}
        <div class="cbd-segment"><button class="${cbdUi.periodicity === 'QTD_FULL' ? 'active' : ''}" data-cbd-periodicity="QTD_FULL">季度</button><button class="${cbdUi.periodicity === 'LAST_YEAR_END' ? 'active' : ''}" data-cbd-periodicity="LAST_YEAR_END">年度</button></div>
        <label class="cbd-metric-select">指标<select id="cbdMetricSelect">${metrics.map(item => `<option value="${item.key}" ${item.key === cbdUi.metric ? 'selected' : ''}>${esc(CBD_METRIC_NAMES[item.key] || item.name)}</option>`).join('')}</select></label>
      </div>
      <div id="cbdBody">${cbdUi.page === 'snapshot' ? cbdSnapshotHtml(cbdPayload) : cbdUi.page === 'date_range' ? cbdDateRangeHtml(cbdPayload) : cbdCompareHtml(cbdPayload)}</div>
    </div>`;
    bindCentralBankControls();
    root.querySelectorAll('.cbd-correlation-stage').forEach(bindGoldhubTooltips);
    root.querySelectorAll('.goldhub-chart-stage').forEach(bindGoldhubTooltips);
    const search = document.getElementById('cbdTableSearch');
    if (search) search.addEventListener('input', () => {
      const needle = search.value.trim().toLowerCase();
      root.querySelectorAll('.cbd-table tbody tr').forEach(row => {
        row.hidden = needle && !row.dataset.search.includes(needle);
      });
    });
  }

  function bindCentralBankControls() {
    document.querySelectorAll('[data-cbd-page]').forEach(button => button.addEventListener('click', () => {
      cbdUi.page = button.dataset.cbdPage;
      cbdUi.period = null;
      loadCentralBanks();
    }));
    document.querySelectorAll('[data-cbd-periodicity]').forEach(button => button.addEventListener('click', () => {
      cbdUi.periodicity = button.dataset.cbdPeriodicity;
      cbdUi.period = null;
      cbdUi.startDate = null;
      cbdUi.endDate = null;
      cbdUi.selectedDates = [];
      loadCentralBanks();
    }));
    document.querySelectorAll('[data-cbd-chart]').forEach(button => button.addEventListener('click', () => {
      cbdUi.chartType = button.dataset.cbdChart;
      renderCentralBanks();
    }));
    document.getElementById('cbdMetricSelect')?.addEventListener('change', event => {
      cbdUi.metric = event.target.value;
      renderCentralBanks();
    });
    document.getElementById('cbdPeriodSelect')?.addEventListener('change', event => {
      cbdUi.period = event.target.value;
      renderCentralBanks();
    });
    document.getElementById('cbdApplyRange')?.addEventListener('click', () => {
      cbdUi.startDate = document.getElementById('cbdStartDate').value;
      cbdUi.endDate = document.getElementById('cbdEndDate').value;
      loadCentralBanks();
    });
    document.getElementById('cbdApplyCompare')?.addEventListener('click', () => {
      cbdUi.selectedDates = [...document.querySelectorAll('.cbdCompareDate')].map(input => input.value).filter(Boolean);
      loadCentralBanks();
    });
  }

  async function loadCentralBanks() {
    const root = document.getElementById('goldhubChartPanels');
    root.innerHTML = '<div class="cbd-loading"><i class="ti ti-loader-2"></i> 正在同步世界黄金协会央行储备数据…</div>';
    const params = new URLSearchParams({ page: cbdUi.page, periodicity: cbdUi.periodicity });
    if (cbdUi.page === 'date_range') {
      if (cbdUi.startDate) params.set('startDate', cbdUi.startDate);
      if (cbdUi.endDate) params.set('endDate', cbdUi.endDate);
    }
    if (cbdUi.page === 'compare_dates') {
      params.set('groupBy', 'Country');
      if (cbdUi.selectedDates.length) params.set('selectedDates', cbdUi.selectedDates.join(','));
    }
    try {
      const response = await fetch(`api/goldhub/cbd?${params}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      cbdPayload = payload.chartData;
      cbdCacheMeta = payload.goldarCache || null;
      if (cbdUi.page === 'date_range') {
        cbdUi.startDate ||= cbdPayload.options.selectedFrom;
        cbdUi.endDate ||= cbdPayload.options.selectedTo;
      }
      if (cbdUi.page === 'compare_dates' && !cbdUi.selectedDates.length) {
        cbdUi.selectedDates = cbdPayload.options.selectedDates || [];
      }
      renderCentralBanks();
      updateCbdMeta();
    } catch (error) {
      root.innerHTML = `<p class="cbd-empty">央行储备数据暂时无法读取：${esc(error.message)}</p>`;
    }
  }

  function openGoldhubChart(chartId) {
    const chart = state.goldhubCharts?.charts?.[chartId];
    if (!chart) return;
    document.getElementById('goldhubChartTitle').textContent = chart.title;
    document.getElementById('goldhubChartSubtitle').textContent = chart.subtitle;
    document.getElementById('goldhubChartMeta').innerHTML =
      `<span>截至 ${esc(chart.asOf)}</span><span>${esc(chart.frequency)}</span><span>每日检查协会新版本</span>`;
    document.getElementById('goldhubChartPanels').innerHTML = chart.stock
      ? goldStockDiagram(chart.stock)
      : chart.panels.map(panel => `
      <section class="goldhub-panel">
        <p class="goldhub-panel-title">${esc(panel.title)}</p>
        <div class="goldhub-chart-stage">
          ${goldhubChartSvg(panel)}
          <div class="goldhub-chart-tooltip" role="status"></div>
        </div>
        <div class="goldhub-legend">${panel.series.map((item, index) =>
          `<span><i style="background:${GOLDHUB_COLORS[index % GOLDHUB_COLORS.length]}"></i>${esc(goldhubName(item.name))}</span>`
        ).join('')}</div>
      </section>
    `).join('');
    document.getElementById('goldhubChartSource').innerHTML =
      `数据来源：<a href="${esc(chart.sourceUrl)}" target="_blank" rel="noopener">世界黄金协会 Goldhub</a> · 仅重绘近期必要区间，原始数据及第三方内容版权归原权利人所有`;
    switchView('supply-chart');
    window.scrollTo(0, 0);
    if (chartId === 'centralBanks') {
      document.getElementById('goldhubChartSource').innerHTML =
        `数据来源：<a href="${esc(chart.sourceUrl)}" target="_blank" rel="noopener">世界黄金协会 Goldhub</a> · IMF IFS及世界黄金协会整理 · 月度与季度按协会计划更新`;
      loadCentralBanks();
      return;
    }
    document.querySelectorAll('#goldhubChartPanels .goldhub-chart-stage').forEach(bindGoldhubTooltips);
  }

  function goldStockDiagram(stock) {
    const total = stock.total;
    return `<section class="gold-stock-summary">
      <div class="gold-stock-total">
        <span>截至2025年底地上存量</span>
        <strong>${goldhubNumber(total)} 吨</strong>
        <small>若熔成纯金立方体，边长约 ${goldhubNumber(stock.cubeSideMetres)} 米</small>
      </div>
      <div>
        <div class="gold-stock-blocks" aria-label="地上黄金存量构成">
          ${stock.categories.map((item, index) => {
            const share = item.value / total * 100;
            return `<div class="gold-stock-block tone-${index}" style="flex:${share} 1 0">
              <span>${esc(item.name)}</span>
              <strong>${goldhubNumber(item.value)} 吨</strong>
              <small>${share.toFixed(0)}%</small>
            </div>`;
          }).join('')}
        </div>
        <div class="gold-underground">
          <div><span>地下储量（当前条件下可经济开采）</span><strong>${goldhubNumber(stock.reserves)} 吨</strong></div>
          <div><span>地下资源量（含推断、控制与探明资源）</span><strong>${goldhubNumber(stock.resources)} 吨</strong></div>
        </div>
      </div>
    </section>`;
  }

  function bindSupplyDemandCharts() {
    document.querySelectorAll('.sd-chart-node').forEach(button => {
      button.addEventListener('click', () => openGoldhubChart(button.dataset.chart));
    });
  }

  function renderEvents(filter) {
    const items = state.timeline.events.filter(e => !filter || filter === '全部' || e.type === filter);
    document.getElementById('eventsFull').innerHTML = items.map(e =>
      `<div class="event"><div class="year">${esc(e.year)}</div><div class="body"><span class="badge tag">${esc(e.type)}</span><p class="text">${esc(e.text)}</p></div></div>`
    ).join('');
  }

  function renderMonetaryTimeline() {
    const events = [
      ['1816年', '英国确立金本位', '英国通过《金本位制度法案》，正式确立以黄金定义英镑价值的制度框架。'],
      ['1870年代', '国际金本位形成', '主要工业国陆续采用金本位，跨境汇率围绕黄金平价保持相对稳定。'],
      ['1914年', '古典金本位中断', '第一次世界大战爆发，各国暂停黄金兑换并扩大纸币发行。'],
      ['1922年', '金汇兑本位', '热那亚会议推动以黄金及可兑换黄金的关键货币共同作为储备资产。'],
      ['1931年', '英镑脱离金本位', '英国停止英镑兑换黄金，国际金本位体系加速瓦解。'],
      ['1944年', '布雷顿森林体系建立', '美元按35美元/盎司与黄金挂钩，其他货币与美元建立固定但可调整的汇率。'],
      ['1961年', '伦敦黄金总库', '美国与欧洲多国央行联合干预伦敦黄金市场，试图维持35美元官价。'],
      ['1968年', '黄金双价制', '黄金总库解散，官方结算价格与私人市场价格分离。'],
      ['1971年', '尼克松冲击', '美国暂停美元对黄金兑换，美元与黄金的法定兑换承诺终止。'],
      ['1973年', '主要货币转向浮动', '布雷顿森林固定汇率安排实质结束，主要货币由市场决定汇率。'],
      ['1976年', '牙买加体系确立', 'IMF承认浮动汇率合法性并推动黄金非货币化，特别提款权地位上升。'],
      ['1999年', '欧元诞生', '欧洲统一货币启动，国际储备货币体系增加新的重要支柱。'],
      ['2008年', 'G20协调机制强化', '全球金融危机后，G20成为主要经济体宏观政策协调的重要平台。'],
      ['2016年', '人民币加入SDR', '人民币正式纳入特别提款权货币篮子，储备货币体系进一步多元化。'],
      ['2022年至今', '储备多元化加速', '地缘冲突与金融制裁强化储备安全讨论，央行购金与本币结算受到更多关注。'],
    ];
    document.getElementById('monetaryTimeline').innerHTML = events.map(([year, title, text]) => `
      <article class="monetary-event">
        <div class="monetary-event-key"><time>${esc(year)}</time><strong>${esc(title)}</strong></div>
        <p>${esc(text)}</p>
      </article>
    `).join('');
  }

  function renderEventFilters() {
    const types = ['全部', ...new Set(state.timeline.events.map(e => e.type))];
    document.getElementById('eventFilters').innerHTML = types.map((t, i) =>
      `<button class="filter-chip ${i === 0 ? 'active' : ''}" data-type="${esc(t)}">${esc(t)}</button>`
    ).join('');
    document.querySelectorAll('#eventFilters .filter-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#eventFilters .filter-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderEvents(btn.dataset.type);
      });
    });
    renderEvents('全部');
  }

  const REPORT_CAT_ORDER = ['全部', '宏观', '央行', '行业', '现货', '期货', '上市公司', '学术'];

  function renderReports(filter) {
    const cls = v => v === '看多' ? 'bull' : v === '看空' ? 'bear' : 'neutral';
    const items = state.reports.items.filter(r => !filter || filter === '全部' || r.cat === filter);
    document.getElementById('reportsList').innerHTML = items.map(r => `
      <div class="news-item">
        <a class="n-title" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>
        <p class="n-summary">${esc(r.summary)}</p>
        <div class="n-meta">
          <span>${esc(r.date)}</span>
          <span>${esc(r.org)}</span>
          ${r.source ? `<span class="badge tag">${esc(r.source)}</span>` : ''}
          <span class="badge tag">${esc(r.region)}</span>
          <span class="badge tag">${esc(r.cat)}</span>
          <span class="badge ${cls(r.view)}">${esc(r.view)}</span>
        </div>
      </div>`
    ).join('');
  }

  function renderReportFilters() {
    document.getElementById('reportsNote').textContent = state.reports.sourceNote || `更新时间：${state.reports.updatedAt}`;
    const present = new Set(state.reports.items.map(r => r.cat));
    const cats = REPORT_CAT_ORDER.filter(c => c === '全部' || present.has(c));
    document.getElementById('reportFilters').innerHTML = cats.map((c, i) =>
      `<button class="filter-chip ${i === 0 ? 'active' : ''}" data-cat="${esc(c)}">${esc(c)}</button>`
    ).join('');
    document.querySelectorAll('#reportFilters .filter-chip').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#reportFilters .filter-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderReports(btn.dataset.cat);
      });
    });
    renderReports('全部');
  }

  function renderFedCycle() {
    const data = state.fedCycle;
    const root = document.getElementById('fedCycleChart');
    if (!data?.rows?.length || !root) return;

    const latest = data.latest;
    const currentPeriod = data.periods[data.periods.length - 1];
    document.getElementById('fedCycleUpdated').textContent = `数据更新 ${data.updatedAt}`;
    const summary = [
      { label: '最新黄金价格', value: `$${latest.gold.toLocaleString()}`, note: '美元/盎司', icon: 'ti-coins' },
      { label: '有效联邦基金利率', value: `${latest.rate.toFixed(2)}%`, note: 'FRED DFF', icon: 'ti-percentage' },
      { label: '当前政策阶段', value: latest.stance, note: `目标区间 ${latest.targetLow.toFixed(2)}%–${latest.targetHigh.toFixed(2)}%`, icon: 'ti-building-bank' },
      { label: '本阶段黄金表现', value: `${currentPeriod.goldChange >= 0 ? '+' : ''}${currentPeriod.goldChange.toFixed(1)}%`, note: `${currentPeriod.start.slice(0, 7)} 至 ${currentPeriod.end.slice(0, 7)}`, icon: 'ti-chart-line' },
    ];
    document.getElementById('fedCycleSummary').innerHTML = summary.map(item => `
      <div class="fed-cycle-summary-item">
        <i class="ti ${item.icon}" aria-hidden="true"></i>
        <div><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.note)}</small></div>
      </div>
    `).join('');

    const width = 1200;
    const height = 590;
    const margin = { top: 82, right: 78, bottom: 50, left: 72 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const rows = data.rows.map(row => ({
      ...row,
      time: Date.parse(`${row.date}-01T00:00:00Z`),
    }));
    const minTime = rows[0].time;
    const maxTime = rows[rows.length - 1].time;
    const minGold = Math.floor(Math.min(...rows.map(row => row.gold)) / 500) * 500;
    const maxGold = Math.ceil(Math.max(...rows.map(row => row.gold)) / 500) * 500;
    const maxRate = Math.max(6, Math.ceil(Math.max(...rows.map(row => row.rate))));
    const x = time => margin.left + (time - minTime) / (maxTime - minTime) * plotWidth;
    const yGold = value => margin.top + plotHeight - (value - minGold) / (maxGold - minGold) * plotHeight;
    const yRate = value => margin.top + plotHeight - value / maxRate * plotHeight;
    const clampTime = time => Math.max(minTime, Math.min(maxTime, time));
    const goldPath = rows.map((row, index) => `${index ? 'L' : 'M'}${x(row.time).toFixed(1)},${yGold(row.gold).toFixed(1)}`).join(' ');
    const ratePath = rows.map((row, index) => {
      const px = x(row.time).toFixed(1);
      const py = yRate(row.rate).toFixed(1);
      if (!index) return `M${px},${py}`;
      return `H${px}V${py}`;
    }).join(' ');

    const goldTicks = Array.from({ length: 6 }, (_, index) => minGold + (maxGold - minGold) / 5 * index);
    const rateTicks = Array.from({ length: maxRate + 1 }, (_, index) => index);
    const yearStep = width < 900 ? 3 : 2;
    const startYear = new Date(minTime).getUTCFullYear();
    const endYear = new Date(maxTime).getUTCFullYear();
    const yearTicks = [];
    for (let year = Math.ceil(startYear / yearStep) * yearStep; year <= endYear; year += yearStep) yearTicks.push(year);

    const periodLayers = data.periods.map((period, index) => {
      const startX = x(clampTime(Date.parse(`${period.start}T00:00:00Z`)));
      const endX = x(clampTime(Date.parse(`${period.end}T00:00:00Z`)));
      const periodWidth = Math.max(2, endX - startX);
      const center = startX + periodWidth / 2;
      const shortStance = period.stance.replace('周期', '').replace('高利率', '高位');
      const compactDate = `${period.start.slice(2, 7).replace('-', '.')}—${period.end.slice(2, 7).replace('-', '.')}`;
      const compactDateX = index === data.periods.length - 2
        ? center - 5
        : index === data.periods.length - 1
          ? center + 5
          : center;
      let label = '';
      if (periodWidth >= 120) {
        label = `<text x="${center}" y="12" class="fed-cycle-period-date">${period.start.slice(0, 7)}—${period.end.slice(0, 7)}</text>
          <text x="${center}" y="31" class="fed-cycle-period-label">${esc(period.stance)}</text>
          <text x="${center}" y="50" class="fed-cycle-period-change">黄金 ${period.goldChange >= 0 ? '+' : ''}${period.goldChange.toFixed(1)}%</text>`;
      } else if (periodWidth >= 28) {
        label = `<text x="${compactDateX}" y="12" class="fed-cycle-period-date compact">${compactDate}</text>
          <text x="${center}" y="31" class="fed-cycle-period-label">${esc(shortStance)}</text>
          <text x="${center}" y="50" class="fed-cycle-period-change">${period.goldChange >= 0 ? '+' : ''}${period.goldChange.toFixed(1)}%</text>`;
      } else {
        label = `<text x="${center}" y="39" class="fed-cycle-period-index">${index + 1}</text>`;
      }
      return `<g class="fed-cycle-period fed-cycle-period-${period.tone}">
        <rect x="${startX}" y="${margin.top}" width="${periodWidth}" height="${plotHeight}"></rect>
        <line x1="${startX}" y1="${margin.top}" x2="${startX}" y2="${margin.top + plotHeight}"></line>
        ${label}
      </g>`;
    }).join('');

    const grid = goldTicks.map(value => {
      const py = yGold(value);
      return `<line x1="${margin.left}" y1="${py}" x2="${width - margin.right}" y2="${py}" class="fed-cycle-grid"/>
        <text x="${margin.left - 12}" y="${py + 4}" text-anchor="end" class="fed-cycle-axis">$${Math.round(value).toLocaleString()}</text>`;
    }).join('');
    const rightAxis = rateTicks.map(value => {
      const py = yRate(value);
      return `<text x="${width - margin.right + 12}" y="${py + 4}" class="fed-cycle-axis">${value}%</text>`;
    }).join('');
    const bottomAxis = yearTicks.map(year => {
      const px = x(Date.parse(`${year}-01-01T00:00:00Z`));
      return `<line x1="${px}" y1="${margin.top + plotHeight}" x2="${px}" y2="${margin.top + plotHeight + 5}" class="fed-cycle-tick"/>
        <text x="${px}" y="${margin.top + plotHeight + 24}" text-anchor="middle" class="fed-cycle-axis">${year}</text>`;
    }).join('');
    const lastRow = rows[rows.length - 1];

    root.innerHTML = `
      <div class="fed-cycle-chart-scroll">
        <svg class="fed-cycle-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金价格与有效联邦基金利率双轴时间序列图">
          ${periodLayers}
          ${grid}
          ${rightAxis}
          ${bottomAxis}
          <text x="${margin.left}" y="${margin.top - 8}" class="fed-cycle-axis-title">黄金价格（美元/盎司，左轴）</text>
          <text x="${width - margin.right}" y="${margin.top - 8}" text-anchor="end" class="fed-cycle-axis-title">有效联邦基金利率（右轴）</text>
          <path d="${goldPath}" class="fed-cycle-gold-line"></path>
          <path d="${ratePath}" class="fed-cycle-rate-line"></path>
          <line class="fed-cycle-focus-line" x1="0" x2="0" y1="${margin.top}" y2="${margin.top + plotHeight}"></line>
          <circle class="fed-cycle-focus-dot gold" r="4"></circle>
          <circle class="fed-cycle-focus-dot rate" r="4"></circle>
          <rect class="fed-cycle-hit" x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}"></rect>
          <g class="fed-cycle-end-label gold" transform="translate(${x(lastRow.time)},${yGold(lastRow.gold)})">
            <text x="-8" y="-9" text-anchor="end">黄金 $${lastRow.gold.toLocaleString()}</text>
          </g>
          <g class="fed-cycle-end-label rate" transform="translate(${x(lastRow.time)},${yRate(lastRow.rate)})">
            <text x="-8" y="16" text-anchor="end">DFF ${lastRow.rate.toFixed(2)}%</text>
          </g>
        </svg>
      </div>
      <div class="fed-cycle-tooltip" role="status" aria-live="polite"></div>`;

    const periodRoot = document.getElementById('fedCyclePeriods');
    periodRoot.innerHTML = data.periods.map((period, index) => `
      <article class="fed-cycle-period-card ${period.tone}">
        <span class="fed-cycle-period-number">${index + 1}</span>
        <div>
          <strong>${esc(period.stance)}</strong>
          <small>${period.start.slice(0, 7)}—${period.end.slice(0, 7)}</small>
          <p>利率 ${period.rateStart.toFixed(2)}% → ${period.rateEnd.toFixed(2)}%</p>
          <p>黄金 <b class="${period.goldChange >= 0 ? 'up' : 'down'}">${period.goldChange >= 0 ? '+' : ''}${period.goldChange.toFixed(1)}%</b></p>
        </div>
      </article>
    `).join('');
    document.getElementById('fedCycleSource').innerHTML = `数据来源：${data.sources.map(source =>
      `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}</a>`
    ).join(' · ')}<br>${esc(data.note)}`;

    const svg = root.querySelector('.fed-cycle-svg');
    const hit = svg.querySelector('.fed-cycle-hit');
    const focusLine = svg.querySelector('.fed-cycle-focus-line');
    const goldDot = svg.querySelector('.fed-cycle-focus-dot.gold');
    const rateDot = svg.querySelector('.fed-cycle-focus-dot.rate');
    const tooltip = root.querySelector('.fed-cycle-tooltip');
    const locateRow = event => {
      const rect = svg.getBoundingClientRect();
      const pointerX = (event.clientX - rect.left) / rect.width * width;
      const time = minTime + Math.max(0, Math.min(1, (pointerX - margin.left) / plotWidth)) * (maxTime - minTime);
      let nearest = rows[0];
      rows.forEach(row => {
        if (Math.abs(row.time - time) < Math.abs(nearest.time - time)) nearest = row;
      });
      return nearest;
    };
    const showInspection = event => {
      const row = locateRow(event);
      const px = x(row.time);
      const goldY = yGold(row.gold);
      const rateY = yRate(row.rate);
      focusLine.setAttribute('x1', px);
      focusLine.setAttribute('x2', px);
      goldDot.setAttribute('cx', px);
      goldDot.setAttribute('cy', goldY);
      rateDot.setAttribute('cx', px);
      rateDot.setAttribute('cy', rateY);
      [focusLine, goldDot, rateDot].forEach(node => node.classList.add('active'));
      tooltip.innerHTML = `<strong>${esc(row.date)}</strong><span>黄金 $${row.gold.toLocaleString()}</span><span>有效联邦基金利率 ${row.rate.toFixed(2)}%</span>`;
      tooltip.classList.add('active');
      const chartRect = root.getBoundingClientRect();
      tooltip.style.left = `${Math.min(chartRect.width - 230, Math.max(8, event.clientX - chartRect.left + 12))}px`;
      tooltip.style.top = `${Math.max(92, event.clientY - chartRect.top - 54)}px`;
    };
    hit.addEventListener('pointermove', showInspection);
    hit.addEventListener('click', showInspection);
    hit.addEventListener('pointerleave', () => {
      [focusLine, goldDot, rateDot].forEach(node => node.classList.remove('active'));
      tooltip.classList.remove('active');
    });
  }

  function renderMacroRelation(kind) {
    const isRealRate = kind === 'realRate';
    const isVix = kind === 'vix';
    const prefix = isRealRate ? 'realRate' : isVix ? 'vix' : 'dollarIndex';
    const data = state.macroRelations?.[kind];
    const root = document.getElementById(`${prefix}Chart`);
    if (!data?.rows?.length || !root) return;
    const updatedAt = state.macroRelations.updatedAt;
    document.getElementById(`${prefix}Updated`).textContent = `数据更新 ${updatedAt}`;

    const latest = data.latest;
    const summary = isRealRate ? [
      { label: '最新黄金价格', value: `$${latest.gold.toLocaleString()}`, note: '美元/盎司', icon: 'ti-coins' },
      { label: '10年期TIPS实际收益率', value: `${latest.real10y.toFixed(2)}%`, note: 'FRED DFII10', icon: 'ti-chart-line' },
      { label: '10年期美债名义收益率', value: `${latest.nominal10y.toFixed(2)}%`, note: 'FRED DGS10', icon: 'ti-percentage' },
      { label: '有效联邦基金利率', value: `${latest.fedFunds.toFixed(2)}%`, note: 'FRED DFF', icon: 'ti-building-bank' },
    ] : isVix ? [
      { label: '最新黄金价格', value: `$${latest.gold.toLocaleString()}`, note: '美元/盎司', icon: 'ti-coins' },
      { label: 'VIX指数', value: latest.vix.toFixed(2), note: 'CBOE收盘值', icon: 'ti-activity' },
      { label: '最新月份', value: latest.date, note: '月末最新可得值', icon: 'ti-calendar' },
      { label: '指标含义', value: '风险定价', note: '并非黄金方向信号', icon: 'ti-alert-triangle' },
    ] : [
      { label: '最新黄金价格', value: `$${latest.gold.toLocaleString()}`, note: '美元/盎司', icon: 'ti-coins' },
      { label: '广义美元指数', value: latest.dollar.toFixed(2), note: '2020年1月=100', icon: 'ti-currency-dollar' },
      { label: '最新月份', value: latest.date, note: '月末最新可得值', icon: 'ti-calendar' },
      { label: '长期关系', value: '通常负相关', note: '阶段性可同向', icon: 'ti-arrows-exchange' },
    ];
    document.getElementById(`${prefix}Summary`).innerHTML = summary.map(item => `
      <div class="fed-cycle-summary-item">
        <i class="ti ${item.icon}" aria-hidden="true"></i>
        <div><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.note)}</small></div>
      </div>
    `).join('');

    const series = isRealRate ? [
      { key: 'fedFunds', label: '有效联邦基金利率', cls: 'fed-funds', unit: '%' },
      { key: 'nominal10y', label: '10年期美债名义收益率', cls: 'nominal', unit: '%' },
      { key: 'real10y', label: '10年期TIPS实际收益率', cls: 'real', unit: '%' },
    ] : isVix
      ? [{ key: 'vix', label: 'CBOE VIX指数', cls: 'vix', unit: '' }]
      : [{ key: 'dollar', label: '美联储广义美元指数', cls: 'dollar', unit: '' }];
    document.getElementById(`${prefix}Legend`).innerHTML = [
      '<span><i class="macro-legend-line gold"></i>伦敦金</span>',
      ...series.map(item => `<span><i class="macro-legend-line ${item.cls}"></i>${esc(item.label)}</span>`),
    ].join('');

    const width = 1200;
    const height = 590;
    const margin = { top: isRealRate ? 124 : 52, right: 76, bottom: 48, left: 68 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const rows = data.rows.map(row => ({ ...row, time: Date.parse(`${row.date}-01T00:00:00Z`) }));
    const minTime = rows[0].time;
    const maxTime = rows[rows.length - 1].time;
    const goldValues = rows.map(row => row.gold);
    const minGold = Math.floor(Math.min(...goldValues) / 500) * 500;
    const maxGold = Math.ceil(Math.max(...goldValues) / 500) * 500;
    const secondaryValues = rows.flatMap(row => series.map(item => row[item.key])).filter(Number.isFinite);
    const secondaryPad = isRealRate ? 0.5 : 3;
    const minSecondary = isRealRate ? Math.floor(Math.min(...secondaryValues) - secondaryPad) : Math.floor((Math.min(...secondaryValues) - secondaryPad) / 5) * 5;
    const maxSecondary = isRealRate ? Math.ceil(Math.max(...secondaryValues) + secondaryPad) : Math.ceil((Math.max(...secondaryValues) + secondaryPad) / 5) * 5;
    const x = time => margin.left + (time - minTime) / (maxTime - minTime) * plotWidth;
    const yGold = value => margin.top + plotHeight - (value - minGold) / (maxGold - minGold) * plotHeight;
    const ySecondary = value => margin.top + plotHeight - (value - minSecondary) / (maxSecondary - minSecondary) * plotHeight;
    const pathFor = (key, y) => rows.map((row, index) => `${index ? 'L' : 'M'}${x(row.time).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');
    const goldTicks = Array.from({ length: 6 }, (_, index) => minGold + (maxGold - minGold) / 5 * index);
    const secondaryTicks = Array.from({ length: 6 }, (_, index) => minSecondary + (maxSecondary - minSecondary) / 5 * index);
    const startYear = new Date(minTime).getUTCFullYear();
    const endYear = new Date(maxTime).getUTCFullYear();
    const yearStep = isRealRate ? 3 : 2;
    const yearTicks = [];
    for (let year = Math.ceil(startYear / yearStep) * yearStep; year <= endYear; year += yearStep) yearTicks.push(year);
    const grid = goldTicks.map(value => {
      const py = yGold(value);
      return `<line x1="${margin.left}" y1="${py}" x2="${width - margin.right}" y2="${py}" class="fed-cycle-grid"/>
        <text x="${margin.left - 10}" y="${py + 4}" text-anchor="end" class="fed-cycle-axis">$${Math.round(value).toLocaleString()}</text>`;
    }).join('');
    const rightAxis = secondaryTicks.map(value => {
      const py = ySecondary(value);
      return `<text x="${width - margin.right + 10}" y="${py + 4}" class="fed-cycle-axis">${value.toFixed(isRealRate ? 1 : 0)}${isRealRate ? '%' : ''}</text>`;
    }).join('');
    const bottomAxis = yearTicks.map(year => {
      const px = x(Date.parse(`${year}-01-01T00:00:00Z`));
      return `<text x="${px}" y="${margin.top + plotHeight + 25}" text-anchor="middle" class="fed-cycle-axis">${year}</text>`;
    }).join('');
    const markerLayer = isRealRate ? data.annotations.map((item, index) => {
      const time = Math.max(minTime, Math.min(maxTime, Date.parse(`${item.date}-01T00:00:00Z`)));
      const row = rows.reduce((nearest, candidate) => Math.abs(candidate.time - time) < Math.abs(nearest.time - time) ? candidate : nearest, rows[0]);
      const px = x(row.time);
      const py = yGold(row.gold);
      const markerY = 72 + (index % 2) * 26;
      return `<g class="macro-marker" data-note="${item.id}">
        <line x1="${px}" y1="${markerY + 12}" x2="${px}" y2="${py - 6}"></line>
        <circle cx="${px}" cy="${py}" r="4"></circle>
        <circle class="macro-marker-badge" cx="${px}" cy="${markerY}" r="12"></circle>
        <text x="${px}" y="${markerY + 4}" text-anchor="middle">${item.id}</text>
      </g>`;
    }).join('') : isVix ? data.annotations.map((item, index) => {
      const time = Math.max(minTime, Math.min(maxTime, Date.parse(`${item.date}-01T00:00:00Z`)));
      const row = rows.reduce((nearest, candidate) => Math.abs(candidate.time - time) < Math.abs(nearest.time - time) ? candidate : nearest, rows[0]);
      const px = x(row.time);
      const py = ySecondary(row.vix);
      const labelY = 32 + (index % 3) * 18;
      return `<g class="macro-event-marker">
        <line x1="${px}" y1="${labelY + 5}" x2="${px}" y2="${py - 5}"></line>
        <circle cx="${px}" cy="${py}" r="3.5"></circle>
        <text x="${px}" y="${labelY}" text-anchor="middle">${esc(item.label)}</text>
      </g>`;
    }).join('') : '';

    root.innerHTML = `<div class="fed-cycle-chart-scroll">
      <svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${isRealRate ? '黄金与美国实际利率' : isVix ? '黄金与VIX指数' : '黄金与美元指数'}双轴时间序列图">
        ${grid}${rightAxis}${bottomAxis}
        <text x="${margin.left}" y="${margin.top - 10}" class="fed-cycle-axis-title">伦敦金（美元/盎司，左轴）</text>
        <text x="${width - margin.right}" y="${margin.top - 10}" text-anchor="end" class="fed-cycle-axis-title">${isRealRate ? '收益率（右轴）' : isVix ? 'VIX指数（右轴）' : '广义美元指数（右轴）'}</text>
        <path d="${pathFor('gold', yGold)}" class="macro-series gold"></path>
        ${series.map(item => `<path d="${pathFor(item.key, ySecondary)}" class="macro-series ${item.cls}"></path>`).join('')}
        ${markerLayer}
        <line class="fed-cycle-focus-line" x1="0" x2="0" y1="${margin.top}" y2="${margin.top + plotHeight}"></line>
        <circle class="fed-cycle-focus-dot gold" r="4"></circle>
        <rect class="fed-cycle-hit" x="${margin.left}" y="${margin.top}" width="${plotWidth}" height="${plotHeight}"></rect>
      </svg></div><div class="fed-cycle-tooltip" role="status" aria-live="polite"></div>`;

    if (isRealRate) {
      document.getElementById('realRateNotes').innerHTML = data.annotations.map(item => `
        <article class="macro-note-card" data-note="${item.id}">
          <span>${item.id}</span><div><strong>${esc(item.title)}</strong><p>${esc(item.text)}</p></div>
        </article>
      `).join('');
      root.querySelectorAll('.macro-marker').forEach(marker => {
        const select = active => {
          document.querySelectorAll('[data-note]').forEach(node => node.classList.toggle('active', active && node.dataset.note === marker.dataset.note));
        };
        marker.addEventListener('pointerenter', () => select(true));
        marker.addEventListener('pointerleave', () => select(false));
        marker.addEventListener('click', () => {
          const card = document.querySelector(`.macro-note-card[data-note="${marker.dataset.note}"]`);
          card?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          select(true);
        });
      });
    }
    document.getElementById(`${prefix}Source`).innerHTML = `数据来源：${data.sources.map(source =>
      `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}</a>`
    ).join(' · ')}<br>${esc(data.note)}`;

    const svg = root.querySelector('svg');
    const hit = svg.querySelector('.fed-cycle-hit');
    const focusLine = svg.querySelector('.fed-cycle-focus-line');
    const goldDot = svg.querySelector('.fed-cycle-focus-dot.gold');
    const tooltip = root.querySelector('.fed-cycle-tooltip');
    const inspect = event => {
      const rect = svg.getBoundingClientRect();
      const pointerX = (event.clientX - rect.left) / rect.width * width;
      const time = minTime + Math.max(0, Math.min(1, (pointerX - margin.left) / plotWidth)) * (maxTime - minTime);
      const row = rows.reduce((nearest, candidate) => Math.abs(candidate.time - time) < Math.abs(nearest.time - time) ? candidate : nearest, rows[0]);
      const px = x(row.time);
      focusLine.setAttribute('x1', px);
      focusLine.setAttribute('x2', px);
      goldDot.setAttribute('cx', px);
      goldDot.setAttribute('cy', yGold(row.gold));
      [focusLine, goldDot].forEach(node => node.classList.add('active'));
      tooltip.innerHTML = `<strong>${row.date}</strong><span>伦敦金 $${row.gold.toLocaleString()}</span>${series.map(item =>
        `<span>${esc(item.label)} ${row[item.key].toFixed(2)}${item.unit}</span>`
      ).join('')}`;
      tooltip.classList.add('active');
      const chartRect = root.getBoundingClientRect();
      tooltip.style.left = `${Math.min(chartRect.width - 230, Math.max(8, event.clientX - chartRect.left + 12))}px`;
      tooltip.style.top = `${Math.max(60, event.clientY - chartRect.top - 54)}px`;
    };
    hit.addEventListener('pointermove', inspect);
    hit.addEventListener('click', inspect);
    hit.addEventListener('pointerleave', () => {
      [focusLine, goldDot].forEach(node => node.classList.remove('active'));
      tooltip.classList.remove('active');
    });
  }

  function renderInflation() {
    const data = state.macroRelations?.inflation;
    const root = document.getElementById('inflationChart');
    if (!data?.rows?.length || !root) return;
    document.getElementById('inflationUpdated').textContent = `数据更新 ${state.macroRelations.updatedAt}`;
    const latest = data.latest;
    const first = data.rows[0];
    document.getElementById('inflationSummary').innerHTML = [
      { label: '全球CPI同比', value: `${latest.inflation.toFixed(1)}%`, note: `${latest.year} 最新可得`, icon: 'ti-chart-bar' },
      { label: '同年黄金均价', value: `$${latest.gold.toLocaleString()}`, note: '美元/盎司', icon: 'ti-coins' },
      { label: '数据覆盖', value: `${first.year}—${latest.year}`, note: `${data.rows.length}个年度`, icon: 'ti-calendar' },
      { label: '更新频率', value: '年度', note: '随世界银行发布', icon: 'ti-refresh' },
    ].map(item => `<div class="fed-cycle-summary-item"><i class="ti ${item.icon}"></i><div><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.note)}</small></div></div>`).join('');
    document.getElementById('inflationLegend').innerHTML = '<span><i class="macro-legend-box inflation"></i>全球CPI同比</span><span><i class="macro-legend-line gold"></i>伦敦金年度均价</span>';

    const width = 1200, height = 570;
    const margin = { top: 45, right: 76, bottom: 62, left: 65 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const maxInflation = Math.ceil(Math.max(...data.rows.map(row => row.inflation), 10));
    const minGold = Math.floor(Math.min(...data.rows.map(row => row.gold)) / 500) * 500;
    const maxGold = Math.ceil(Math.max(...data.rows.map(row => row.gold)) / 500) * 500;
    const slot = plotWidth / data.rows.length;
    const x = index => margin.left + slot * index + slot / 2;
    const yInflation = value => margin.top + plotHeight - value / maxInflation * plotHeight;
    const yGold = value => margin.top + plotHeight - (value - minGold) / (maxGold - minGold) * plotHeight;
    const goldPath = data.rows.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${yGold(row.gold).toFixed(1)}`).join(' ');
    const inflationTicks = Array.from({ length: 6 }, (_, index) => maxInflation / 5 * index);
    const goldTicks = Array.from({ length: 6 }, (_, index) => minGold + (maxGold - minGold) / 5 * index);
    root.innerHTML = `<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="全球CPI同比与伦敦金年度均价双轴图">
      ${inflationTicks.map((value, index) => {
        const py = yInflation(value);
        return `<line x1="${margin.left}" y1="${py}" x2="${width - margin.right}" y2="${py}" class="fed-cycle-grid"/><text x="${margin.left - 10}" y="${py + 4}" text-anchor="end" class="fed-cycle-axis">${value.toFixed(0)}%</text><text x="${width - margin.right + 10}" y="${py + 4}" class="fed-cycle-axis">$${Math.round(goldTicks[index]).toLocaleString()}</text>`;
      }).join('')}
      ${data.rows.map((row, index) => `<rect x="${x(index) - slot * .28}" y="${yInflation(row.inflation)}" width="${slot * .56}" height="${margin.top + plotHeight - yInflation(row.inflation)}" class="macro-inflation-bar"><title>${row.year} 全球CPI ${row.inflation.toFixed(1)}%</title></rect>`).join('')}
      <path d="${goldPath}" class="macro-series gold"></path>
      ${data.rows.map((row, index) => `<text x="${x(index)}" y="${margin.top + plotHeight + 24}" text-anchor="middle" class="fed-cycle-axis inflation-year">${row.year}</text>`).join('')}
      <text x="${margin.left}" y="${margin.top - 10}" class="fed-cycle-axis-title">全球CPI同比（左轴）</text>
      <text x="${width - margin.right}" y="${margin.top - 10}" text-anchor="end" class="fed-cycle-axis-title">伦敦金年度均价（右轴）</text>
    </svg></div>`;
    document.getElementById('inflationSource').innerHTML = `数据来源：${data.sources.map(source => `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}</a>`).join(' · ')}<br>${esc(data.note)}`;
  }

  function renderMonetarySystem() {
    const root = document.getElementById('monetarySystemChart');
    const history = state.goldHistory;
    if (!root || !history?.points?.length) return;
    const latestDaily = history.dailyPoints[history.dailyPoints.length - 1];
    document.getElementById('monetarySystemUpdated').textContent = `数据更新 ${history.updatedAt}`;
    const rows = [
      ...Array.from({ length: 14 }, (_, index) => ({ date: `${1920 + index}-01`, price: 20.67, official: true })),
      ...Array.from({ length: 34 }, (_, index) => ({ date: `${1934 + index}-01`, price: 35, official: true })),
      ...history.points.filter(point => point.date >= '1968-01'),
      { date: latestDaily.date.slice(0, 7), price: Number(latestDaily.close) },
    ].sort((a, b) => a.date.localeCompare(b.date));
    const summary = [
      { label: '最新伦敦金', value: `$${Number(latestDaily.close).toLocaleString()}`, note: latestDaily.date, icon: 'ti-coins' },
      { label: '1920年官价', value: '$20.67', note: '美元/盎司', icon: 'ti-lock' },
      { label: '布雷顿森林官价', value: '$35', note: '美元/盎司', icon: 'ti-building-bank' },
      { label: '自由定价以来', value: `+${((Number(latestDaily.close) / 35 - 1) * 100).toFixed(0)}%`, note: '以35美元为比较基准', icon: 'ti-chart-line' },
    ];
    document.getElementById('monetarySystemSummary').innerHTML = summary.map(item => `<div class="fed-cycle-summary-item"><i class="ti ${item.icon}"></i><div><span>${esc(item.label)}</span><strong>${esc(item.value)}</strong><small>${esc(item.note)}</small></div></div>`).join('');
    const width = 1200, height = 590;
    const margin = { top: 68, right: 48, bottom: 52, left: 70 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const minTime = Date.parse('1920-01-01T00:00:00Z');
    const maxTime = Date.parse(`${latestDaily.date}T00:00:00Z`);
    const minLog = Math.log10(10), maxLog = Math.log10(10000);
    const x = date => margin.left + (Date.parse(`${date}-01T00:00:00Z`) - minTime) / (maxTime - minTime) * plotWidth;
    const y = price => margin.top + plotHeight - (Math.log10(price) - minLog) / (maxLog - minLog) * plotHeight;
    const path = rows.map((row, index) => `${index ? 'L' : 'M'}${x(row.date).toFixed(1)},${y(row.price).toFixed(1)}`).join(' ');
    const regimes = [
      ['1920-01', '1934-01', '古典金本位余波', '官价约20.67美元'],
      ['1934-01', '1971-08', '黄金官价体系', '35美元官价与布雷顿森林'],
      ['1971-08', latestDaily.date.slice(0, 7), '黄金自由定价', '市场定价与信用货币时代'],
    ];
    const events = [
      ['1933-04', '金本位第一次解体'],
      ['1944-07', '布雷顿森林体系建立'],
      ['1968-03', '黄金双价制'],
      ['1971-08', '美元停止兑金'],
      ['1973-03', '主要货币转向浮动'],
      ['1976-01', '牙买加体系'],
      ['1999-01', '欧元诞生'],
      ['2008-09', '全球金融危机'],
      ['2022-02', '储备多元化加速'],
    ];
    const yTicks = [10, 100, 1000, 10000];
    const years = [1920, 1930, 1940, 1950, 1960, 1971, 1980, 1990, 2000, 2010, 2020, 2026].filter(year => year <= Number(latestDaily.date.slice(0, 4)));
    root.innerHTML = `<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与国际货币体系演变对数价格图">
      ${regimes.map(([start, end, label]) => `<rect x="${x(start)}" y="${margin.top}" width="${Math.max(2, x(end) - x(start))}" height="${plotHeight}" class="monetary-regime-bg"></rect><text x="${(x(start)+x(end))/2}" y="28" text-anchor="middle" class="monetary-regime-title">${esc(label)}</text>`).join('')}
      ${yTicks.map(value => `<line x1="${margin.left}" y1="${y(value)}" x2="${width-margin.right}" y2="${y(value)}" class="fed-cycle-grid"/><text x="${margin.left-10}" y="${y(value)+4}" text-anchor="end" class="fed-cycle-axis">$${value.toLocaleString()}</text>`).join('')}
      ${years.map(year => `<text x="${x(`${year}-01`)}" y="${margin.top+plotHeight+25}" text-anchor="middle" class="fed-cycle-axis">${year}</text>`).join('')}
      ${events.map(([date,label], index) => `<g class="monetary-system-event"><line x1="${x(date)}" y1="${margin.top}" x2="${x(date)}" y2="${margin.top+plotHeight}"></line><text x="${x(date)+(index%2?4:-4)}" y="${margin.top+18+(index%3)*16}" text-anchor="${index%2?'start':'end'}">${esc(label)}</text></g>`).join('')}
      <path d="${path}" class="macro-series gold monetary-price-line"></path>
      <circle cx="${x(latestDaily.date.slice(0,7))}" cy="${y(Number(latestDaily.close))}" r="4" class="monetary-latest-dot"></circle>
      <text x="${x(latestDaily.date.slice(0,7))-5}" y="${y(Number(latestDaily.close))-12}" text-anchor="end" class="monetary-latest-label">$${Number(latestDaily.close).toLocaleString()}</text>
    </svg></div>`;
    document.getElementById('monetarySystemNotes').innerHTML = regimes.map(([, , label, text]) => `<div><strong>${esc(label)}</strong><span>${esc(text)}</span></div>`).join('');
    document.getElementById('monetarySystemSource').innerHTML = `数据来源：<a href="${esc(history.sourceUrl)}" target="_blank" rel="noopener">${esc(history.source)}</a><br>1920—1933年展示20.67美元法定官价，1934—1967年展示35美元法定官价；1968年后使用LBMA黄金价格PM，曲线更新至最新可得交易日。`;
  }

  function renderUsdCredit() {
    const data = state.macroRelations?.usdCredit;
    const root = document.getElementById('usdCreditChart');
    if (!data?.rows?.length || !root) return;
    document.getElementById('usdCreditUpdated').textContent = `数据更新 ${state.macroRelations.updatedAt}`;
    const latest = data.latest;
    document.getElementById('usdCreditSummary').innerHTML = [
      ['美元当前购买力', `${latest.dollarPower.toFixed(1)}`, '1914年=100', 'ti-currency-dollar'],
      ['累计购买力损失', `-${(100-latest.dollarPower).toFixed(1)}%`, '美国CPI口径', 'ti-trending-down'],
      ['黄金实际购买力', `${latest.goldPower.toLocaleString()}`, '1914年=100', 'ti-coins'],
      ['最新年份', `${latest.year}`, '最新可得年度', 'ti-calendar'],
    ].map(([label,value,note,icon]) => `<div class="fed-cycle-summary-item"><i class="ti ${icon}"></i><div><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div></div>`).join('');
    document.getElementById('usdCreditLegend').innerHTML = '<span><i class="macro-legend-line dollar-power"></i>美元CPI购买力（左轴）</span><span><i class="macro-legend-line gold"></i>黄金实际购买力（右轴）</span>';
    const width=1200,height=570,margin={top:48,right:78,bottom:50,left:65};
    const plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
    const rows=data.rows;
    const maxGold=Math.ceil(Math.max(...rows.map(r=>r.goldPower))/1000)*1000;
    const x=i=>margin.left+i/(rows.length-1)*plotWidth;
    const yDollar=v=>margin.top+plotHeight-v/100*plotHeight;
    const yGold=v=>margin.top+plotHeight-v/maxGold*plotHeight;
    const path=(key,y)=>rows.map((r,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`).join(' ');
    const ticks=[0,20,40,60,80,100];
    const yearTicks=rows.filter(r=>r.year%10===0||r.year===latest.year);
    root.innerHTML=`<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与货币信用购买力对照图">
      ${ticks.map((v,i)=>`<line x1="${margin.left}" y1="${yDollar(v)}" x2="${width-margin.right}" y2="${yDollar(v)}" class="fed-cycle-grid"/><text x="${margin.left-10}" y="${yDollar(v)+4}" text-anchor="end" class="fed-cycle-axis">${v}</text><text x="${width-margin.right+10}" y="${yDollar(v)+4}" class="fed-cycle-axis">${Math.round(maxGold*i/5).toLocaleString()}</text>`).join('')}
      ${yearTicks.map(r=>`<text x="${x(rows.indexOf(r))}" y="${margin.top+plotHeight+25}" text-anchor="middle" class="fed-cycle-axis">${r.year}</text>`).join('')}
      <text x="${margin.left}" y="${margin.top-10}" class="fed-cycle-axis-title">美元购买力（1914=100，左轴）</text>
      <text x="${width-margin.right}" y="${margin.top-10}" text-anchor="end" class="fed-cycle-axis-title">黄金实际购买力（1914=100，右轴）</text>
      <path d="${path('dollarPower',yDollar)}" class="macro-series dollar-power"></path>
      <path d="${path('goldPower',yGold)}" class="macro-series gold"></path>
    </svg></div>`;
    const examples=[['1914','一双普通皮鞋'],['1930','约16罐番茄汤'],['1950','一件儿童玩具'],['1970','约3份快餐'],['1990','约4升牛奶'],['2000','一个汉堡'],['2020','一杯普通咖啡']];
    document.getElementById('usdPurchaseExamples').innerHTML='<strong>1美元能买什么（历史示意）</strong>'+examples.map(([year,text])=>`<span><b>${year}</b>${esc(text)}</span>`).join('');
    document.getElementById('usdCreditSource').innerHTML=`数据来源：${data.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>`).join(' · ')}<br>${esc(data.note)}`;
  }

  function renderUsDebt() {
    const data=state.macroRelations?.usDebt;
    const root=document.getElementById('usDebtChart');
    if(!data?.rows?.length||!root)return;
    document.getElementById('usDebtUpdated').textContent=`数据更新 ${state.macroRelations.updatedAt}`;
    const latest=data.latest,first=data.rows[0];
    document.getElementById('usDebtSummary').innerHTML=[
      ['美国联邦总债务',`$${latest.debt.toFixed(2)}万亿`,'FRED GFDEBTN','ti-building-bank'],
      ['最新黄金价格',`$${latest.gold.toLocaleString()}`,'美元/盎司','ti-coins'],
      ['债务累计增长',`+${((latest.debt/first.debt-1)*100).toFixed(0)}%`,`${first.date}以来`,'ti-chart-line'],
      ['最新月份',latest.date,'债务季度间沿用最近值','ti-calendar'],
    ].map(([label,value,note,icon])=>`<div class="fed-cycle-summary-item"><i class="ti ${icon}"></i><div><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div></div>`).join('');
    document.getElementById('usDebtLegend').innerHTML='<span><i class="macro-legend-line gold"></i>伦敦金（左轴）</span><span><i class="macro-legend-line debt"></i>美国联邦总债务（右轴）</span>';
    const width=1200,height=570,margin={top:48,right:78,bottom:50,left:70};
    const rows=data.rows,plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
    const minTime=Date.parse(`${rows[0].date}-01T00:00:00Z`),maxTime=Date.parse(`${rows.at(-1).date}-01T00:00:00Z`);
    const x=date=>margin.left+(Date.parse(`${date}-01T00:00:00Z`)-minTime)/(maxTime-minTime)*plotWidth;
    const maxGold=Math.ceil(Math.max(...rows.map(r=>r.gold))/1000)*1000,maxDebt=Math.ceil(Math.max(...rows.map(r=>r.debt))/10)*10;
    const yGold=v=>margin.top+plotHeight-v/maxGold*plotHeight,yDebt=v=>margin.top+plotHeight-v/maxDebt*plotHeight;
    const path=(key,y)=>rows.map((r,i)=>`${i?'L':'M'}${x(r.date).toFixed(1)},${y(r[key]).toFixed(1)}`).join(' ');
    const ticks=[0,1,2,3,4,5];
    const years=[];for(let year=1970;year<=Number(latest.date.slice(0,4));year+=10)years.push(year);
    root.innerHTML=`<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与美国联邦政府总债务双轴图">
      ${ticks.map(i=>`<line x1="${margin.left}" y1="${margin.top+plotHeight-i/5*plotHeight}" x2="${width-margin.right}" y2="${margin.top+plotHeight-i/5*plotHeight}" class="fed-cycle-grid"/><text x="${margin.left-10}" y="${margin.top+plotHeight-i/5*plotHeight+4}" text-anchor="end" class="fed-cycle-axis">$${Math.round(maxGold*i/5).toLocaleString()}</text><text x="${width-margin.right+10}" y="${margin.top+plotHeight-i/5*plotHeight+4}" class="fed-cycle-axis">$${(maxDebt*i/5).toFixed(0)}万亿</text>`).join('')}
      ${years.map(year=>`<text x="${x(`${year}-01`)}" y="${margin.top+plotHeight+25}" text-anchor="middle" class="fed-cycle-axis">${year}</text>`).join('')}
      <path d="${path('gold',yGold)}" class="macro-series gold"></path><path d="${path('debt',yDebt)}" class="macro-series debt"></path>
    </svg></div>`;
    document.getElementById('usDebtSource').innerHTML=`数据来源：${data.sources.map(s=>`<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)}</a>`).join(' · ')}<br>${esc(data.note)}`;
    renderGoldDebtScale();
  }

  function renderGoldDebtScale() {
    const data=state.macroRelations?.goldDebtScale;
    const root=document.getElementById('usDebtStockChart');
    if(!data?.rows?.length||!root)return;
    const latest=data.latest;
    document.getElementById('usDebtStockUpdated').textContent=`数据更新 ${state.macroRelations.updatedAt}`;
    document.getElementById('usDebtStockLegend').innerHTML='<span><i class="macro-legend-box stock-over-debt"></i>黄金规模超过美债</span><span><i class="macro-legend-line debt-stock"></i>存量美债规模</span><span><i class="macro-legend-line gold-stock"></i>存量黄金规模</span><span><i class="macro-legend-line gold-debt-ratio"></i>金债比（右轴）</span>';
    const width=1200,height=570,margin={top:48,right:78,bottom:55,left:70};
    const rows=data.rows,plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
    const maxValue=Math.max(...rows.flatMap(row=>[row.goldValue,row.debt]));
    const maxLeft=Math.max(5000,Math.ceil(maxValue/5000)*5000);
    const maxRatio=Math.max(3,Math.ceil(Math.max(...rows.map(row=>row.ratio))/0.5)*0.5);
    const x=index=>margin.left+index/(rows.length-1)*plotWidth;
    const yValue=value=>margin.top+plotHeight-value/maxLeft*plotHeight;
    const yRatio=value=>margin.top+plotHeight-value/maxRatio*plotHeight;
    const path=(key,y)=>rows.map((row,index)=>`${index?'L':'M'}${x(index).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');
    const leftTicks=Array.from({length:Math.round(maxLeft/5000)+1},(_,index)=>index*5000);
    const rightTicks=Array.from({length:Math.round(maxRatio/0.5)+1},(_,index)=>index*0.5);
    const yearIndex=new Map(rows.map((row,index)=>[row.year,index]));
    const firstYear=Math.ceil(rows[0].year/10)*10;
    const years=[];
    for(let year=firstYear;year<=latest.year;year+=10)if(yearIndex.has(year))years.push(year);
    if(!years.includes(latest.year))years.push(latest.year);
    const bands=[];
    let bandStart=null;
    rows.forEach((row,index)=>{
      if(row.ratio>1&&bandStart===null)bandStart=index;
      if((row.ratio<=1||index===rows.length-1)&&bandStart!==null){
        const end=row.ratio>1&&index===rows.length-1?index:index-1;
        bands.push({start:bandStart,end});
        bandStart=null;
      }
    });
    const bandRect=band=>{
      const start=band.start===0?margin.left:(x(band.start-1)+x(band.start))/2;
      const end=band.end===rows.length-1?width-margin.right:(x(band.end)+x(band.end+1))/2;
      return `<rect x="${start.toFixed(1)}" y="${margin.top}" width="${(end-start).toFixed(1)}" height="${plotHeight}" class="macro-stock-over-debt"><title>黄金规模超过美债：${rows[band.start].year}—${rows[band.end].year}</title></rect>`;
    };
    root.innerHTML=`<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="全球地上黄金存量市值、美国联邦总债务与金债比图">
      ${bands.map(bandRect).join('')}
      ${leftTicks.map(value=>`<line x1="${margin.left}" y1="${yValue(value)}" x2="${width-margin.right}" y2="${yValue(value)}" class="fed-cycle-grid"/><text x="${margin.left-10}" y="${yValue(value)+4}" text-anchor="end" class="fed-cycle-axis">${value.toLocaleString()}</text>`).join('')}
      ${rightTicks.map(value=>`<text x="${width-margin.right+10}" y="${yRatio(value)+4}" class="fed-cycle-axis">${value.toFixed(1)}</text>`).join('')}
      ${years.map(year=>`<text x="${x(yearIndex.get(year))}" y="${margin.top+plotHeight+27}" text-anchor="middle" class="fed-cycle-axis">${year}${year===latest.year&&latest.isCurrentYear?'*':''}</text>`).join('')}
      <text x="${margin.left}" y="${margin.top-16}" class="fed-cycle-axis-title">（十亿美元）</text>
      <text x="${width-margin.right}" y="${margin.top-16}" text-anchor="end" class="fed-cycle-axis-title">金债比（右轴）</text>
      <line x1="${margin.left}" y1="${yRatio(1)}" x2="${width-margin.right}" y2="${yRatio(1)}" class="macro-stock-threshold"/>
      <path d="${path('debt',yValue)}" class="macro-series debt-stock"></path>
      <path d="${path('goldValue',yValue)}" class="macro-series gold-stock"></path>
      <path d="${path('ratio',yRatio)}" class="macro-series gold-debt-ratio"></path>
    </svg></div>`;
    document.getElementById('usDebtStockSource').innerHTML=`数据来源：${data.sources.map(source=>`<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}</a>`).join(' · ')}<br>${esc(data.note)}`;
  }

  function renderDollarReserves() {
    const data = state.macroRelations?.dollarReserves;
    const root = document.getElementById('dollarReservesChart');
    if (!data?.rows?.length || !root) return;
    document.getElementById('dollarReservesUpdated').textContent = `数据更新 ${state.macroRelations.updatedAt}`;
    const latest = data.latest;
    const first = data.rows[0];
    document.getElementById('dollarReservesSummary').innerHTML = [
      ['美元储备份额', `${latest.share.toFixed(2)}%`, latest.period, 'ti-currency-dollar'],
      ['同期黄金均价', `$${latest.gold.toLocaleString()}`, '美元/盎司', 'ti-coins'],
      ['美元份额变化', `${(latest.share - first.share).toFixed(1)}个百分点`, `${first.period}以来`, 'ti-trending-down'],
      ['更新频率', '季度', 'IMF COFER', 'ti-refresh'],
    ].map(([label,value,note,icon]) => `<div class="fed-cycle-summary-item"><i class="ti ${icon}"></i><div><span>${esc(label)}</span><strong>${esc(value)}</strong><small>${esc(note)}</small></div></div>`).join('');
    document.getElementById('dollarReservesLegend').innerHTML = '<span><i class="macro-legend-line gold"></i>伦敦金均价（左轴）</span><span><i class="macro-legend-line reserve-share"></i>美元储备份额（右轴）</span>';
    const width=1200,height=570,margin={top:48,right:78,bottom:55,left:70};
    const rows=data.rows,plotWidth=width-margin.left-margin.right,plotHeight=height-margin.top-margin.bottom;
    const x=index=>margin.left+index/(rows.length-1)*plotWidth;
    const maxGold=Math.ceil(Math.max(...rows.map(row=>row.gold))/1000)*1000;
    const minShare=Math.floor(Math.min(...rows.map(row=>row.share))/5)*5-5;
    const maxShare=Math.ceil(Math.max(...rows.map(row=>row.share))/5)*5;
    const yGold=value=>margin.top+plotHeight-value/maxGold*plotHeight;
    const yShare=value=>margin.top+plotHeight-(value-minShare)/(maxShare-minShare)*plotHeight;
    const path=(key,y)=>rows.map((row,index)=>`${index?'L':'M'}${x(index).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');
    const ticks=[0,1,2,3,4,5];
    root.innerHTML=`<div class="fed-cycle-chart-scroll"><svg class="fed-cycle-svg macro-relation-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="黄金与美元储备份额双轴图">
      ${ticks.map(index=>{const py=margin.top+plotHeight-index/5*plotHeight;return `<line x1="${margin.left}" y1="${py}" x2="${width-margin.right}" y2="${py}" class="fed-cycle-grid"/><text x="${margin.left-10}" y="${py+4}" text-anchor="end" class="fed-cycle-axis">$${Math.round(maxGold*index/5).toLocaleString()}</text><text x="${width-margin.right+10}" y="${py+4}" class="fed-cycle-axis">${(minShare+(maxShare-minShare)*index/5).toFixed(0)}%</text>`}).join('')}
      ${rows.map((row,index)=>index%4===0||index===rows.length-1?`<text x="${x(index)}" y="${margin.top+plotHeight+25}" text-anchor="middle" class="fed-cycle-axis">${row.period}</text>`:'').join('')}
      <path d="${path('gold',yGold)}" class="macro-series gold"></path>
      <path d="${path('share',yShare)}" class="macro-series reserve-share"></path>
      <circle cx="${x(rows.length-1)}" cy="${yShare(latest.share)}" r="4" class="reserve-latest-dot"></circle>
    </svg></div>`;
    document.getElementById('dollarReservesSource').innerHTML=`数据来源：${data.sources.map(source=>`<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}</a>`).join(' · ')}<br>${esc(data.note)}`;
  }

  function openTopic(idx) {
    const t = state.topics.items[idx];
    document.getElementById('topicTitle').textContent = t.title;
    document.getElementById('topicDate').textContent = '专题 · ' + t.date;
    const sections = (t.sections || []).map(section => `
      <section class="topic-section">
        <h2>${esc(section.title)}</h2>
        ${(section.paragraphs || []).map(paragraph => `<p>${esc(paragraph)}</p>`).join('')}
        ${section.points?.length ? `<ul>${section.points.map(point => `<li>${esc(point)}</li>`).join('')}</ul>` : ''}
        ${section.scenarios?.length ? `<div class="topic-scenarios">${section.scenarios.map(scenario =>
          `<div><strong>${esc(scenario.label)}</strong><span>${esc(scenario.text)}</span></div>`
        ).join('')}</div>` : ''}
      </section>`
    ).join('');
    const sources = (t.sources || []).map(source =>
      `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)}<i class="ti ti-external-link"></i></a>`
    ).join('');
    document.getElementById('topicBody').innerHTML = `
      <p class="topic-lead">${esc(t.lead || t.summary)}</p>
      ${sections}
      ${sources ? `<div class="topic-sources"><p>资料来源</p>${sources}</div>` : ''}
      <p class="topic-disclaimer">以上为情景分析，不构成确定价格预测或投资建议。</p>`;

    const m = state.market;
    document.getElementById('topicStocks').innerHTML = m.stocks.domestic.slice(0, 4).map(s =>
      heatTile(s.name, '¥' + s.price, s.chg)
    ).join('');
    document.getElementById('topicFunds').innerHTML = m.funds.domestic.slice(0, 4).map(f =>
      heatTile(f.name, '¥' + f.price, f.chg)
    ).join('');
    const cls = v => v === '看多' ? 'bull' : v === '看空' ? 'bear' : 'neutral';
    document.getElementById('topicReports').innerHTML = state.reports.items.slice(0, 4).map(r =>
      `<div class="list-row"><span class="title">${esc(r.title)}</span><span class="badge ${cls(r.view)}">${esc(r.view)}</span></div>`
    ).join('');

    switchView('topic-detail');
    window.scrollTo(0, 0);
  }

  function switchView(view) {
    document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === view));
    document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + view));
  }

  function bindNav() {
    document.querySelectorAll('.nav-item').forEach(btn => {
      btn.addEventListener('click', () => switchView(btn.dataset.view));
    });
    document.getElementById('topicBack').addEventListener('click', () => switchView('overview'));
    document.getElementById('supplyChartBack').addEventListener('click', () => switchView('framework'));
    document.getElementById('fedCycleBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('realRateBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('dollarIndexBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('vixBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('inflationBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('monetarySystemBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('usdCreditBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('usDebtBack').addEventListener('click', () => switchView('logic'));
    document.getElementById('dollarReservesBack').addEventListener('click', () => switchView('logic'));
    document.querySelector('[data-framework-detail="fed-cycle"]').addEventListener('click', () => {
      renderFedCycle();
      switchView('fed-cycle');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="real-rate"]').addEventListener('click', () => {
      renderMacroRelation('realRate');
      switchView('real-rate');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="dollar-index"]').addEventListener('click', () => {
      renderMacroRelation('dollarIndex');
      switchView('dollar-index');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="dollar-reserves"]').addEventListener('click', () => {
      renderDollarReserves();
      switchView('dollar-reserves');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="central-banks"]').addEventListener('click', () => {
      openGoldhubChart('centralBanks');
    });
    document.querySelectorAll('[data-metric-detail]').forEach(button => {
      button.addEventListener('click', () => {
        const detail = button.dataset.metricDetail;
        if (detail === 'central-banks') {
          openGoldhubChart('centralBanks');
          return;
        }
        if (detail === 'us-debt') renderUsDebt();
        if (detail === 'real-rate') renderMacroRelation('realRate');
        if (detail === 'inflation') renderInflation();
        switchView(detail);
        window.scrollTo(0, 0);
      });
    });
    document.querySelectorAll('[data-metric-chart]').forEach(button => {
      button.addEventListener('click', () => openGoldhubChart(button.dataset.metricChart));
    });
    document.querySelector('[data-framework-detail="vix"]').addEventListener('click', () => {
      renderMacroRelation('vix');
      switchView('vix');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="inflation"]').addEventListener('click', () => {
      renderInflation();
      switchView('inflation');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="monetary-system"]').addEventListener('click', () => {
      renderMonetarySystem();
      switchView('monetary-system');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="usd-credit"]').addEventListener('click', () => {
      renderUsdCredit();
      switchView('usd-credit');
      window.scrollTo(0, 0);
    });
    document.querySelector('[data-framework-detail="us-debt"]').addEventListener('click', () => {
      renderUsDebt();
      switchView('us-debt');
      window.scrollTo(0, 0);
    });
    bindSupplyDemandCharts();
    document.getElementById('brandHome').addEventListener('click', () => switchView('overview'));
    document.getElementById('brandHome').addEventListener('keydown', e => { if (e.key === 'Enter') switchView('overview'); });
  }

  const THEME_KEY = 'goldar-theme';
  function applyTheme(mode) {
    const resolved = mode === 'system'
      ? (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
      : mode;
    document.documentElement.setAttribute('data-theme', resolved);
    document.querySelectorAll('.theme-btn').forEach(b => b.classList.toggle('active', b.dataset.mode === mode));
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY) || 'system';
    applyTheme(saved);
    document.querySelectorAll('.theme-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        localStorage.setItem(THEME_KEY, btn.dataset.mode);
        applyTheme(btn.dataset.mode);
      });
    });
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', () => {
      if ((localStorage.getItem(THEME_KEY) || 'system') === 'system') applyTheme('system');
    });
  }

  async function refreshNews() {
    try {
      state.news = await fetch('data/news.json').then(r => r.json());
      const activeChip = document.querySelector('#newsFilters .filter-chip.active');
      renderNewsFilters();
      if (activeChip) {
        const btn = document.querySelector(`#newsFilters .filter-chip[data-cat="${activeChip.dataset.cat}"]`);
        if (btn) { document.querySelectorAll('#newsFilters .filter-chip').forEach(b => b.classList.remove('active')); btn.classList.add('active'); renderNews(btn.dataset.cat); }
      }
      document.getElementById('overviewNewsList').innerHTML = state.news.items.filter(n => n.important).slice(0, 8).map(n =>
        `<div class="list-row"><a class="title n-title" href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a><span class="time">${esc(n.time)}</span></div>`
      ).join('');
    } catch (e) { console.error('[news] refresh failed', e); }
  }

  async function refreshMarket() {
    try {
      state.market = await fetch(`data/market.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      renderTicker();
      renderOverview();
      renderMarket();
      renderAllocation();
    } catch (e) { console.error('[market] refresh failed', e); }
  }

  async function refreshMarketChartHistory() {
    try {
      [state.marketChart, state.assetPerformance] = await Promise.all([
        fetch(`data/market-chart.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json()),
        fetch(`data/asset-performance.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json()),
      ]);
      renderTicker();
      renderOverview();
      renderMarketChart();
      renderAssetPerformance();
    } catch (e) { console.error('[market-chart] refresh failed', e); }
  }

  async function refreshReports() {
    try {
      state.reports = await fetch(`data/reports.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      const active = document.querySelector('#reportFilters .filter-chip.active')?.dataset.cat || '全部';
      renderReportFilters();
      const selected = document.querySelector(`#reportFilters .filter-chip[data-cat="${active}"]`);
      if (selected) {
        document.querySelectorAll('#reportFilters .filter-chip').forEach(button => button.classList.remove('active'));
        selected.classList.add('active');
        renderReports(active);
      }
    } catch (e) { console.error('[reports] refresh failed', e); }
  }

  async function refreshGoldhubCharts() {
    try {
      state.goldhubCharts = await fetch(`data/goldhub-charts.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      renderTradingVolumes();
    } catch (e) { console.error('[goldhub] refresh failed', e); }
  }

  async function refreshOptionsQuant() {
    try {
      state.optionsQuant = await fetch(`data/options-quant.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      renderOptionsQuant();
    } catch (e) { console.error('[options-quant] refresh failed', e); }
  }

  async function refreshQuantStrategy() {
    try {
      state.quantStrategy = await fetch(`data/quant-strategy.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json());
      const [decision, backtest] = await Promise.all([
        fetch(`data/strategy-decision.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
        fetch(`data/backtest.json?t=${Date.now()}`, { cache: 'no-store' }).then(r => r.json()).catch(() => null),
      ]);
      if (decision) state.strategyDecision = decision;
      if (backtest) state.backtest = backtest;
      renderStrategyDecision();
      renderStrategyBacktest();
      renderQuantStrategy();
    } catch (e) { console.error('[quant-strategy] refresh failed', e); }
  }

  function scheduleOptionsQuantRefresh() {
    const offsetMs = 8 * 60 * 60 * 1000;
    const now = Date.now();
    const beijingNow = new Date(now + offsetMs);
    let target = Date.UTC(
      beijingNow.getUTCFullYear(),
      beijingNow.getUTCMonth(),
      beijingNow.getUTCDate(),
      14,
      30,
      0,
      0
    );
    if (target <= now + offsetMs) target += 24 * 60 * 60 * 1000;
    setTimeout(async () => {
      await Promise.all([refreshOptionsQuant(), refreshQuantStrategy()]);
      scheduleOptionsQuantRefresh();
    }, target - (now + offsetMs));
  }

  async function init() {
    bindNav();
    bindOptionsTabs();
    initTheme();
    await loadAll();
    renderTicker();
    renderOverview();
    renderMarket();
    renderNewsFilters();
    renderSupplyDemand();
    renderFedCycle();
    renderMacroRelation('realRate');
    renderMacroRelation('dollarIndex');
    renderMacroRelation('vix');
    renderInflation();
    renderMonetarySystem();
    renderUsdCredit();
    renderUsDebt();
    renderDollarReserves();
    renderAllocation();
    renderOptionsQuant();
    renderStrategyDecision();
    renderQuantStrategy();
    renderStrategyBacktest();
    renderSignal();
    renderEventFilters();
    renderMonetaryTimeline();
    renderCalendar();
    renderMonthCalendar();
    renderReportFilters();
    setInterval(refreshMarket, 15 * 1000);
    setInterval(refreshMarketChartHistory, 5 * 60 * 1000);
    setInterval(() => { renderCalendar(); renderMonthCalendar(); }, 60 * 1000);
    setInterval(refreshNews, 30 * 60 * 1000);
    setInterval(refreshReports, 30 * 60 * 1000);
    setInterval(refreshGoldhubCharts, 6 * 60 * 60 * 1000);
    scheduleOptionsQuantRefresh();
  }

  init();
})();
