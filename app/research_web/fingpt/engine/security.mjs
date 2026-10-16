// 服务端出站边界：密钥、模型标识与账号签名链接不得进入 UI / 日志。
import { existsSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const privateValues = new Set();
export function registerPrivate(value) {
  if (typeof value === 'string' && value.length >= 6) privateValues.add(value);
}
export function refreshPrivateValues() {
  for (const [name, value] of Object.entries(process.env)) {
    if (/(?:KEY|TOKEN|SECRET|PASSWORD|MODEL)$/.test(name)) registerPrivate(value);
  }
  const file = path.join(process.env.IFIND_SKILL_DIR || path.join(os.homedir(), '.agents/skills/ifind-finance-data'), 'mcp_config.json');
  if (existsSync(file)) {
    try { registerPrivate(JSON.parse(readFileSync(file, 'utf8')).auth_token); } catch { /* 不打印配置内容 */ }
  }
}

export function safeUrl(value) {
  try {
    const u = new URL(value);
    if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password) return '';
    if ([...u.searchParams.keys()].some(k => /token|key|auth|sign|credential|password/i.test(k))) return '';
    if ([...privateValues].some(v => value.includes(v) || value.includes(encodeURIComponent(v)))) return '';
    return u.href;
  } catch { return ''; }
}

export function safeText(value) {
  let text = String(value ?? '');
  for (const v of [...privateValues].sort((a, b) => b.length - a.length)) {
    text = text.split(v).join('[REDACTED]').split(encodeURIComponent(v)).join('[REDACTED]');
  }
  return text.replace(/https?:\/\/[^\s<>"')\]]+/g, u => safeUrl(u) || '[账号链接已移除]')
    .replace(/\b(?:sk|tp)-[A-Za-z0-9_-]{12,}/g, '[REDACTED]');
}

export function publicData(value) {
  if (typeof value === 'string') return safeText(value);
  if (Array.isArray(value)) return value.map(publicData);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value)
      .filter(([key]) => !/token|api.?key|authorization|password|secret|pdfurl/i.test(key))
      .map(([key, v]) => [key, /^(?:url|href)$/i.test(key) ? safeUrl(String(v || '')) : publicData(v)]));
  }
  return value;
}

// 保留完整尾部 token，防止凭据在 SSE 分片边界被拆开后逃过过滤。
export function textFilter(emit) {
  let pending = '';
  // 尾部保留长度必须不小于最长私有值，才能在分片边界上拦住被拆开的凭据；
  // 在保住该不变量的前提下把下限压低，让推理流按小块实时出栈。
  const hold = Math.max(128, ...[...privateValues].map(x => encodeURIComponent(x).length + 1));
  return {
    push(text) {
      pending += text;
      if (pending.length < hold + 64) return;
      let cut = pending.length - hold;
      const prefix = pending.slice(0, cut);
      // 只在空白或中文断句处切分；凭据不含这些字符，所以不会在 token 或 URL 内切开。
      const boundary = Math.max(prefix.lastIndexOf(' '), prefix.lastIndexOf('\n'), prefix.lastIndexOf('。'), prefix.lastIndexOf('，'), prefix.lastIndexOf('；'), prefix.lastIndexOf('）'));
      if (boundary < 0) return;
      cut = boundary + 1;
      emit(safeText(pending.slice(0, cut)));
      pending = pending.slice(cut);
    },
    flush() { if (pending) emit(safeText(pending)); pending = ''; },
  };
}
