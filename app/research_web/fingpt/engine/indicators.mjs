function sma(vals, n) {
  const out = [];
  let sum = 0;
  for (let i = 0; i < vals.length; i++) {
    sum += vals[i];
    if (i >= n) sum -= vals[i - n];
    out.push(i >= n - 1 ? sum / n : null);
  }
  return out;
}
function ema(vals, n) {
  const k = 2 / (n + 1);
  const out = [];
  let prev = vals[0] ?? 0;
  for (let i = 0; i < vals.length; i++) {
    prev = i === 0 ? vals[0] : vals[i] * k + prev * (1 - k);
    out.push(prev);
  }
  return out;
}
function macd(closes) {
  const e12 = ema(closes, 12);
  const e26 = ema(closes, 26);
  const dif = closes.map((_, i) => e12[i] - e26[i]);
  const dea = ema(dif, 9);
  const hist = dif.map((d, i) => (d - dea[i]) * 2);
  return { dif, dea, hist };
}
function rsi(closes, n = 14) {
  const out = [null];
  let gain = 0, loss = 0;
  for (let i = 1; i < closes.length; i++) {
    const ch = closes[i] - closes[i - 1];
    if (i <= n) {
      gain += Math.max(ch, 0) / n;
      loss += Math.max(-ch, 0) / n;
      out.push(i === n ? 100 - 100 / (1 + (loss === 0 ? 100 : gain / loss)) : null);
    } else {
      gain = (gain * (n - 1) + Math.max(ch, 0)) / n;
      loss = (loss * (n - 1) + Math.max(-ch, 0)) / n;
      out.push(100 - 100 / (1 + (loss === 0 ? 100 : gain / loss)));
    }
  }
  return out;
}
function summarizeTech(rows) {
  const closes = rows.map((r2) => r2[4]);
  const ma5 = sma(closes, 5), ma20 = sma(closes, 20), ma60 = sma(closes, 60);
  const { dif, dea, hist } = macd(closes);
  const r = rsi(closes);
  const i = closes.length - 1;
  const price = closes[i];
  const chgPct = (closes[i] / closes[i - 1] - 1) * 100;
  const v5 = ma5[i], v20 = ma20[i], v60 = ma60[i];
  const trend = v5 > v20 && v20 > v60 ? "\u591A\u5934\u6392\u5217" : v5 < v20 && v20 < v60 ? "\u7A7A\u5934\u6392\u5217" : "\u7F20\u7ED5";
  const signals = [];
  const crossUp = dif[i] > dea[i] && dif[i - 1] <= dea[i - 1];
  const crossDown = dif[i] < dea[i] && dif[i - 1] >= dea[i - 1];
  if (crossUp) signals.push("MACD \u91D1\u53C9");
  if (crossDown) signals.push("MACD \u6B7B\u53C9");
  if (dif[i] > dea[i] && hist[i] > hist[i - 1]) signals.push("\u7EA2\u67F1\u6269\u5F20");
  if (r[i] > 70) signals.push("RSI \u8D85\u4E70\u533A");
  if (r[i] < 30) signals.push("RSI \u8D85\u5356\u533A");
  if (price > v20 && closes[i - 1] <= ma20[i - 1]) signals.push("\u7AD9\u4E0A MA20");
  if (price < v20 && closes[i - 1] >= ma20[i - 1]) signals.push("\u8DCC\u7834 MA20");
  if (signals.length === 0) signals.push(trend === "\u591A\u5934\u6392\u5217" ? "\u8D8B\u52BF\u5EF6\u7EED\u4E2D" : "\u65E0\u663E\u8457\u4FE1\u53F7");
  return {
    ma5: v5,
    ma20: v20,
    ma60: v60,
    price,
    chgPct,
    macdDif: dif[i],
    macdDea: dea[i],
    macdHist: hist[i],
    rsi14: r[i],
    aboveMa20: price > v20,
    trend,
    signals
  };
}
export {
  ema,
  macd,
  rsi,
  sma,
  summarizeTech
};
