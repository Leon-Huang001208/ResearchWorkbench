const dates = ['04/03', '05/01', '05/29', '06/26', '07/24', '08/21', '09/03'];
const points = (values) => values.map((value, index) => ({ date: dates[index], value }));
const source = [{ name: 'Offline test fixture', url: 'https://example.invalid/test-fixture', observed_at: '2026-09-03', unit: 'mixed', method: 'offline test fixture', proxy: true }];
const block = (key, label, score, values, secondValues, unit = '十亿美元') => ({
  as_of: '2026-09-03', fetched_at: '2026-09-03T16:00:00+08:00', status: 'fixture', sources: source, gaps: [], key, label, score,
  summary: `${label}的确定性测试摘要`,
  metrics: [{ label, value: String(values.at(-1)), direction: score >= 0 ? '改善' : '收紧', interpretation: `${label}需要结合其他维度确认`, proxy: false }],
  series: [{ label, unit, points: points(values) }, { label: `${label}辅助`, unit, points: points(secondValues) }],
});

export function dollarTestData() {
  const quantity_q = block('Q', '总量水库', 0.2, [5720, 5780, 5740, 5810, 5890, 5940, 5990], [3120, 3160, 3110, 3180, 3210, 3260, 3320]);
  quantity_q.series[0].label = '净流动性代理';
  const price_p = block('P', '资金价格', -0.1, [4.12, 4.08, 4.01, 3.98, 4.05, 4.11, 4.03], [4.25, 4.31, 4.28, 4.35, 4.29, 4.22, 4.19], '%');
  price_p.series[0].label = '2Y'; price_p.series[1].label = '10Y';
  const fiscal_g = block('g', '财政水流', 0.1, [820, 790, 760, 745, 730, 720, 710], [86, 101, 92, 118, 95, 110, 126]);
  fiscal_g.series[0].label = 'TGA'; fiscal_g.series[1].label = '国债结算';
  const plumbing_m = block('M', '融资管道', 0, [1, 2, 1, 2, 4, 2, 3], [22, 27, 24, 31, 29, 35, 48], 'bp');
  plumbing_m.series[0].label = 'SOFR−IORB';
  const cross_border_x = block('X', '跨境美元', -0.2, [118.6, 119.2, 118.9, 119.8, 120.3, 120.9, 121.4], [3260, 3255, 3272, 3280, 3276, 3288, 3290], '指数');
  cross_border_x.series[0].label = '广义美元'; cross_border_x.series[1].label = '外国官方托管';
  return {
    framework: {
      slug: 'dollar', name: '美元流动性框架', domain: 'macro', version: '1.0.0', source_revision: '2c210b45577905c0e8ec5f9c061e7069a6cb3b96',
      question: '美元流动性正在通过哪些水库、价格和管道变化？', chain: ['Q', 'P', 'g', 'M', 'X'], counter_evidence: ['融资管道与总量背离'], method: '五维标准化测试模型。',
      sections: [['overview', '总览'], ['quantity', 'Q 总量水库'], ['price', 'P 资金价格'], ['fiscal', 'g 财政水流'], ['plumbing', 'M 融资管道'], ['cross-border', 'X 跨境美元'], ['evidence', '传导与证据']].map(([id, label]) => ({ id, label, question: `${label}的关键研究问题` })),
    },
    snapshot: {
      schema_version: 1, revision: '1'.repeat(64), as_of: '2026-09-03', fetched_at: '2026-09-03T16:00:00+08:00', status: '待核验', coverage: 72,
      quantity_q, price_p, fiscal_g, plumbing_m, cross_border_x,
      research_state: { label: '待核验', score: null, known_subtotal: 0, possible_low: -0.2, possible_high: 0.2, confidence: 58, supports: ['准备金边际回升'], drags: ['实际利率仍高'], next_check: '补齐稳定的跨币种基差。' },
      transmission: { as_of: '2026-09-03', fetched_at: '2026-09-03T16:00:00+08:00', status: 'fixture', sources: source, gaps: [], links: [{ source: '准备金', target: '风险资产', state: '边际支撑', explanation: '仍需融资价格确认' }, { source: '实际利率', target: '黄金', state: '约束', explanation: '机会成本仍高' }, { source: '广义美元', target: '海外融资', state: '偏紧', explanation: '偿付压力抬升' }] },
      events: [{ date: '每周四', type: '总量', title: 'Fed H.4.1', impact: '更新资产负债表', status: '周期性' }],
      evidence: [{ date: '2026-09-03', source: 'FRED', observation: '准备金边际回升', use: 'Q', quality: '测试样例', url: 'https://example.invalid/test-fixture' }],
      gaps: [{ id: 'cross-currency-basis', label: '稳定跨币种基差序列不可得', severity: 'high', next_check: '接入可审计来源' }],
    },
  };
}
