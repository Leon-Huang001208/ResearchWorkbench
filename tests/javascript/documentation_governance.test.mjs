import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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

test('current-product entry explains both Web runtimes without changing the Native default', () => {
  const readme = readFileSync(path.join(repositoryRoot, 'README.md'), 'utf8');
  const installation = readFileSync(path.join(repositoryRoot, 'docs/research-web-installation.md'), 'utf8');
  for (const text of [readme, installation]) {
    assert.match(text, /--runtime docker/);
    assert.match(text, /--runtime native/);
    assert.match(text, /默认[^\n]*Native|无参数[^\n]*Native/);
    assert.match(text, /--stop-current/);
    const dockerPrerequisite = text.match(/^- Docker[^\n]*/m)?.[0];
    assert.ok(dockerPrerequisite, 'Docker prerequisite must be explicit');
    assert.match(dockerPrerequisite, /宿主 Python 3\.12/);
    assert.match(dockerPrerequisite, /无需宿主 Node|不要求宿主 Node/);
    assert.match(dockerPrerequisite, /无需全局第三方 Python 包|不要求全局第三方 Python 包/);
    assert.doesNotMatch(text, /宿主不需全局 Python\/Node 包/);
    const blocks = [...text.matchAll(/```(?:bash|bat)\n([^]*?)```/g)].map(match => match[1]);
    for (const extension of ['sh', 'cmd']) {
      const dockerBlock = blocks.find(block => new RegExp(`setup-web\\.${extension} --runtime docker`).test(block));
      const nativeBlock = blocks.find(block => new RegExp(`setup-web\\.${extension} --runtime native`).test(block));
      assert.ok(dockerBlock && nativeBlock && dockerBlock !== nativeBlock,
        `${extension} examples must be mutually exclusive`);
    }
  }
  assert.match(readme, /\.\/rwb web doctor/);
  assert.match(installation, /rwb\.cmd runtime use docker/);
  assert.match(installation, /docker_credentials_acl_unverified/);
  assert.match(installation, /\.\/rwb web restart --force --no-open/);
  assert.doesNotMatch(installation, /\.\/rwb web restart --no-open/);
  assert.match(installation, /--force[^\n]*中断研究|中断研究[^\n]*--force/);
  assert.match(installation, /--follow[^\n]*300 秒[^\n]*64 KiB/);
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
