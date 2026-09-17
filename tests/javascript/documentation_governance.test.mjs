import assert from 'node:assert/strict';
import {mkdir, mkdtemp, writeFile} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';

import {checkDocumentationGovernance} from '../../scripts/check_documentation_governance.mjs';

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');

async function fixture({readme='[Guide](docs/guide.md#details)', guide='# Guide\n\n## Details\n', extraRules=[], authorities=[]}={}) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'rwb-doc-governance-'));
  await mkdir(path.join(root, 'docs'), {recursive:true});
  const manifest = {
    schemaVersion:1,
    statuses:['current','generated','historical','package-internal','cleanup-candidate'],
    rules:[
      ...extraRules,
      {exact:'README.md',status:'current',purpose:'entry'},
      {prefix:'docs/',status:'current',purpose:'docs'},
    ],
    authorities:[
      {topic:'overview',path:'README.md'},
      ...authorities,
    ],
    forbiddenCurrentPatterns:[{id:'retired',text:'python auto_ingest_service.py'}],
  };
  await writeFile(path.join(root, 'README.md'), readme);
  await writeFile(path.join(root, 'docs/guide.md'), guide);
  await writeFile(path.join(root, 'docs/documentation-governance.json'), JSON.stringify(manifest));
  return root;
}

test('repository Markdown governance is complete', () => {
  const result = checkDocumentationGovernance({projectRoot:repositoryRoot});
  assert.deepEqual(result.violations, []);
  assert.ok(result.files > 400);
});

test('valid classification, authority, link and anchor pass', async () => {
  const root = await fixture();
  const result = checkDocumentationGovernance({
    projectRoot:root,
    markdownFiles:['README.md','docs/guide.md'],
  });
  assert.deepEqual(result.violations, []);
});

test('unclassified Markdown fails closed', async () => {
  const root = await fixture();
  const result = checkDocumentationGovernance({
    projectRoot:root,
    markdownFiles:['README.md','docs/guide.md','outside.md'],
  });
  assert.ok(result.violations.some(item => item.code === 'markdown_unclassified'));
});

test('duplicate authority topic fails closed', async () => {
  const root = await fixture({authorities:[{topic:'overview',path:'docs/guide.md'}]});
  const result = checkDocumentationGovernance({
    projectRoot:root,
    markdownFiles:['README.md','docs/guide.md'],
  });
  assert.ok(result.violations.some(item => item.code === 'authority_duplicate'));
});

test('broken relative link and anchor fail closed', async () => {
  const missingLinkRoot = await fixture({readme:'[Missing](docs/missing.md)'});
  const missingLink = checkDocumentationGovernance({
    projectRoot:missingLinkRoot,
    markdownFiles:['README.md','docs/guide.md'],
  });
  assert.ok(missingLink.violations.some(item => item.code === 'link_missing'));

  const missingAnchorRoot = await fixture({readme:'[Missing](docs/guide.md#absent)'});
  const missingAnchor = checkDocumentationGovernance({
    projectRoot:missingAnchorRoot,
    markdownFiles:['README.md','docs/guide.md'],
  });
  assert.ok(missingAnchor.violations.some(item => item.code === 'anchor_missing'));
});

test('retired command in current documentation fails closed', async () => {
  const root = await fixture({readme:'python auto_ingest_service.py'});
  const result = checkDocumentationGovernance({
    projectRoot:root,
    markdownFiles:['README.md','docs/guide.md'],
  });
  assert.ok(result.violations.some(item => item.code === 'retired_content_current'));
});

test('archived Markdown requires an explicit historical banner', async () => {
  const root = await fixture({extraRules:[{prefix:'docs/archive/',status:'historical',purpose:'history'}]});
  await mkdir(path.join(root, 'docs/archive'), {recursive:true});
  await writeFile(path.join(root, 'docs/archive/old.md'), '# Old');
  const result = checkDocumentationGovernance({
    projectRoot:root,
    markdownFiles:['README.md','docs/guide.md','docs/archive/old.md'],
  });
  assert.ok(result.violations.some(item => item.code === 'historical_banner_missing'));
});
