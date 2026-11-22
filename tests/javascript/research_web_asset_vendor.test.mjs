import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { verifyAssetVendors } from '../../scripts/check_asset_vendor.mjs';

test('reviewed chart distributions and attribution are fully pinned', () => {
  const result = verifyAssetVendors();
  assert.equal(result.status, 'PASS'); assert.deepEqual(result.packages, ['echarts', 'chart.js']);
  assert.ok(result.files.length >= 4);
});
for (const failure of ['changed-library', 'missing-license', 'escape-path', 'changed-version']) test(`vendor lock rejects ${failure}`, () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'rwb-asset-vendor-'));
  const target = path.join(root, 'app/research_web/ui/vendor');
  try {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.cpSync('app/research_web/ui/vendor', target, { recursive: true });
    const lockPath = path.join(target, 'asset-vendor-lock.json'); const lock = JSON.parse(fs.readFileSync(lockPath));
    if (failure === 'changed-library') fs.appendFileSync(path.join(target, lock.packages[0].file), '\n// changed');
    if (failure === 'missing-license') fs.unlinkSync(path.join(target, lock.packages[0].license_file));
    if (failure === 'escape-path') lock.packages[0].file = '../outside.js';
    if (failure === 'changed-version') lock.packages[0].version = 'next';
    fs.writeFileSync(lockPath, JSON.stringify(lock));
    assert.throws(() => verifyAssetVendors(root));
  } finally { fs.rmSync(root, { recursive: true }); }
});
