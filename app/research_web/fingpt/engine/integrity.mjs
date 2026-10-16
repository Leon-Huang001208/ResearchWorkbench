// 只比较同一标的、同一单位的总市值；不把流通市值或缺失值当作总市值。
export function marketCapCheck(primary, realtime) {
  if (!(primary > 0) || !(realtime > 0)) return { status: '口径存疑', reason: '缺少可比的总市值，无法交叉验证' };
  const difference = Math.abs(primary - realtime) / realtime;
  return { status: difference > .05 ? '口径存疑' : '已交叉验证', differencePct: +(difference * 100).toFixed(2),
    primaryYi: primary, realtimeYi: realtime,
    reason: difference > .05 ? '总市值相差超过5%，仅采用实时行情口径' : '同标的总市值差异不超过5%' };
}
export function extremePercentile(text) {
  return /分位[^\n]*?(?:[:：|=]|为)\s*(?:100(?:\.0+)?|0(?:\.0+)?)\s*(?:%|\||,|，|\n|$)/m.test(text)
    || /(?:percentile|分位)[^\n]{0,50}?["':：\s|](?:100(?:\.0+)?|0(?:\.0+)?)\s*(?:%|[|,}\n]|$)/im.test(text);
}
export function totalCapYi(text) {
  // 叙述和 JSON：必须有总市值及明确单位。
  const direct = text.match(/总市值["\s:：|]*(?:为|约)?\s*([\d,.]+)\s*(万亿|亿|万|元)/);
  if (direct) return Number(direct[1].replaceAll(',', '')) * ({ 万亿: 10000, 亿: 1, 万: .0001, 元: 1e-8 }[direct[2]]);
  const lines = text.split('\n');
  for (let i = 0; i < lines.length - 1; i++) {
    const headers = lines[i].split('|'); const col = headers.findIndex(h => /总市值.*亿/.test(h));
    if (col < 0) continue;
    const values = lines.slice(i + 1).filter(l => l.includes('|') && !/^[\s|:-]+$/.test(l));
    // 多标的表格不能猜测行归属。
    if (values.length !== 1) return null;
    const n = Number(values[0].split('|')[col]?.replace(/[,\s]/g, ''));
    if (n > 0) return n;
  }
  return null;
}
