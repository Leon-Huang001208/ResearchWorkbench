// 同花顺 iFinD MCP（自然语言取数）：复用本机技能 ~/.agents/skills/ifind-finance-data/call-node.js（密钥在其 mcp_config.json，不读取不打印）
import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const DIR = () => process.env.IFIND_SKILL_DIR || path.join(os.homedir(), '.agents/skills/ifind-finance-data');
let mod = null;
export const ifindMcpEnabled = () => existsSync(path.join(DIR(), 'call-node.js')) && existsSync(path.join(DIR(), 'mcp_config.json'));
function load() { mod ||= createRequire(import.meta.url)(path.join(DIR(), 'call-node.js')); return mod; }

// 免费版并发上限 2/s：简单信号量 + 间隔
let active = 0; const queue = [];
const MAX = Number(process.env.IFIND_MCP_CONCURRENCY || 2);
async function slot() { if (active >= MAX) await new Promise(r => queue.push(r)); active++; }
function release() { setTimeout(() => { active--; queue.shift()?.(); }, 500); }

export async function ifindCall(serverType, tool, params) {
  await slot();
  try {
    const r = await load().call(serverType, tool, params);
    if (!r?.ok) throw new Error(`iFinD MCP ${serverType}/${tool} 失败`);
    const res = r.data?.result;
    if (res?.isError) throw new Error(`iFinD MCP 返回错误`);
    const text = (res?.content || []).map(c => c.text || '').join('\n');
    let payload = text;
    try { const j = JSON.parse(text); if (j.code !== undefined && j.code !== 1 && j.code !== 0 && j.code !== 200) throw new Error(`iFinD MCP：${j.msg || j.code}`); payload = typeof j.data === 'string' ? j.data : JSON.stringify(j.data ?? j); } catch (e) { if (/^iFinD MCP/.test(e.message)) throw e; }
    if (!payload || /^\s*(null|\[\]|\{\})\s*$/.test(payload)) throw new Error('iFinD MCP 返回空数据');
    return payload;
  } finally { release(); }
}
