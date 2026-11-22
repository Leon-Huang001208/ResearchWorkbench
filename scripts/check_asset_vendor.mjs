#!/usr/bin/env node
/** Verify the two reviewed local chart distributions without network or package installs. */
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const expected = new Map([['echarts', '5.5.0'], ['chart.js', '4.4.7']]);
export function verifyAssetVendors(project = process.cwd()) {
  const root = path.resolve(project, 'app/research_web/ui/vendor');
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'asset-vendor-lock.json'), 'utf8'));
  if (lock.schema_version !== 1 || !Array.isArray(lock.packages) || lock.packages.length !== 2) throw new Error('asset_vendor_manifest_invalid');
  const seen = new Set(), files = [];
  for (const pkg of lock.packages) {
    if (expected.get(pkg.package) !== pkg.version || seen.has(pkg.package) || !pkg.source?.startsWith(`https://registry.npmjs.org/${pkg.package}/-/`) || !/^sha512-[A-Za-z0-9+/]{86}==$/.test(pkg.npm_integrity || '')) throw new Error('asset_vendor_identity_invalid');
    seen.add(pkg.package);
    for (const [name, hash, size] of [[pkg.file, pkg.sha256, pkg.bytes], [pkg.license_file, pkg.license_sha256], ...(pkg.notice_file ? [[pkg.notice_file, pkg.notice_sha256]] : [])]) {
      if (typeof name !== 'string' || name !== path.basename(name) || !/^[a-f0-9]{64}$/.test(hash || '')) throw new Error('asset_vendor_path_invalid');
      const filename = path.join(root, name); const info = fs.lstatSync(filename);
      if (!info.isFile() || info.isSymbolicLink() || info.size > 2_000_000) throw new Error('asset_vendor_file_invalid');
      const actual = crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');
      if (actual !== hash || size !== undefined && info.size !== size) throw new Error('asset_vendor_digest_mismatch');
      files.push({ file: name, sha256: actual, bytes: info.size });
    }
  }
  return { status: 'PASS', packages: [...seen], files };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const started = Date.now(); let record;
  try { record = verifyAssetVendors(); }
  catch (error) { record = { status: 'FAIL', code: error.message }; process.exitCode = 1; }
  record.durationMs = Date.now() - started;
  try { fs.mkdirSync('logs', { recursive: true }); fs.appendFileSync('logs/asset-vendor-verification.jsonl', JSON.stringify(record) + '\n'); }
  catch { record = { status: 'FAIL', code: 'asset_vendor_log_failed' }; process.exitCode = 1; }
  process.stdout.write(JSON.stringify(record) + '\n');
}
