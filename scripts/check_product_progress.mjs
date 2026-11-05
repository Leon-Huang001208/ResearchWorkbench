#!/usr/bin/env node
/** Check bundled progress and render only its owned Changelog section. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { validateProgress, changelogSection } from '../app/research_web/ui/progress.mjs';

export function checkProductProgress(root, { write = false, base = '' } = {}) {
  const source = path.join(root, 'app/research_web/ui/progress-data.json');
  const data = validateProgress(JSON.parse(fs.readFileSync(source, 'utf8')));
  const destination = path.join(root, 'docs/CHANGELOG.md');
  const original = fs.readFileSync(destination, 'utf8');
  const section = changelogSection(data);
  const start = '<!-- product-progress:generated:start -->';
  const end = '<!-- product-progress:generated:end -->';
  const count = marker => original.split(marker).length - 1;
  if (count(start) !== count(end) || count(start) > 1 || original.indexOf(start) > original.indexOf(end)) throw new Error('progress_changelog_markers_invalid');
  const updated = original.includes(start) ? original.slice(0, original.indexOf(start)) + section + original.slice(original.indexOf(end) + end.length) : original.replace(/^# Changelog\r?\n/, `# Changelog\n\n${section}\n`);
  if (base) {
    if (!/^[a-f0-9]{40}$/.test(base)) throw new Error('progress_base_invalid');
    const changed = execFileSync('/usr/bin/git', ['diff', '--name-only', base, '--'], { cwd: root, encoding: 'utf8' }).trim().split('\n');
    const userFacing = changed.some(file => /^app\/research_web\//.test(file));
    if (userFacing && !changed.includes('app/research_web/ui/progress-data.json')) {
      const reports = changed.filter(file => /^\.ai\/reports\/.*\.md$/.test(file));
      const explained = reports.some(file => /^Product-Progress: not-required — .{12,}$/m.test(fs.readFileSync(path.join(root, file), 'utf8')));
      if (!explained) throw new Error('progress_update_or_explanation_required');
    }
  }
  if (updated !== original) {
    if (!write) throw new Error('progress_changelog_out_of_date');
    fs.writeFileSync(destination, updated);
  }
  return { status: 'PASS', asOf: data.asOf, features: data.features.length, releases: data.releases.length };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  try {
    const args = process.argv.slice(2); let write = false; let base = '';
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--write') write = true;
      else if (args[i] === '--base' && args[i + 1]) base = args[++i];
      else throw new Error('progress_argument_invalid');
    }
    const result = checkProductProgress(root, { write, base });
    console.log(JSON.stringify(result));
    if (write) {
      fs.mkdirSync(path.join(root, 'logs'), { recursive: true });
      fs.appendFileSync(path.join(root, 'logs/product-progress.jsonl'), `${JSON.stringify({ event: 'progress_changelog_generated', ...result })}\n`);
    }
  } catch (error) {
    console.error(JSON.stringify({ status: 'FAIL', code: error.message.startsWith('progress_') ? error.message : 'progress_check_failed' }));
    process.exitCode = 1;
  }
}
