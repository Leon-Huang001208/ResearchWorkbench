// 服务端环境加载（不依赖 dotenv）
//  - 本地开发：明文 .env.local（gitignore，chmod 600）
//  - 服务器：加密的 .env.enc（AES-256-GCM），解密密钥不在仓库：
//      1) systemd LoadCredentialEncrypted=alphadesk_key → $CREDENTIALS_DIRECTORY/alphadesk_key（优先）
//      2) ALPHADESK_KEY_FILE 指定的 root-only 文件（chmod 600）
//    明文只在内存中解析为 process.env，不落盘、不打印。
import { readFileSync, existsSync } from 'node:fs';
import { createDecipheriv, createCipheriv, randomBytes } from 'node:crypto';
import path from 'node:path';

function parse(text) {
  for (const line of text.split(/\r?\n/)) {
    const m = line.match(/^\s*([A-Za-z_][\w]*)\s*=\s*(.*?)\s*$/);
    if (m && !line.trim().startsWith('#') && process.env[m[1]] === undefined) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

export function loadEnv(file) {
  if (existsSync(file)) parse(readFileSync(file, 'utf8'));
}

function readKey() {
  const cand = [];
  if (process.env.CREDENTIALS_DIRECTORY) cand.push(path.join(process.env.CREDENTIALS_DIRECTORY, 'alphadesk_key'));
  if (process.env.ALPHADESK_KEY_FILE) cand.push(process.env.ALPHADESK_KEY_FILE);
  for (const f of cand) if (existsSync(f)) {
    const raw = readFileSync(f, 'utf8').trim();
    const key = Buffer.from(raw, /^[0-9a-f]{64}$/i.test(raw) ? 'hex' : 'base64');
    if (key.length === 32) return key;
    throw new Error('alphadesk_key 长度不是 32 字节');
  }
  return null;
}

// 格式：ADENC1:<base64(iv12 | tag16 | ciphertext)>
export function encryptText(plain, key) {
  const iv = randomBytes(12);
  const c = createCipheriv('aes-256-gcm', key, iv);
  const ct = Buffer.concat([c.update(plain, 'utf8'), c.final()]);
  return 'ADENC1:' + Buffer.concat([iv, c.getAuthTag(), ct]).toString('base64') + '\n';
}
export function decryptText(blob, key) {
  const b = Buffer.from(String(blob).trim().replace(/^ADENC1:/, ''), 'base64');
  const d = createDecipheriv('aes-256-gcm', key, b.subarray(0, 12));
  d.setAuthTag(b.subarray(12, 28));
  return Buffer.concat([d.update(b.subarray(28)), d.final()]).toString('utf8');
}

export function loadEncryptedEnv(file) {
  if (!existsSync(file)) return false;
  const key = readKey();
  if (!key) { console.error('[env] 找到 .env.enc 但没有解密密钥（alphadesk_key），跳过'); return false; }
  try { parse(decryptText(readFileSync(file, 'utf8'), key)); key.fill(0); return true; }
  catch { console.error('[env] .env.enc 解密失败（密钥不匹配或文件损坏）'); return false; }
}
