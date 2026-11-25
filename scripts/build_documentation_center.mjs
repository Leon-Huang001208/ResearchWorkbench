import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export const API_DOMAINS = ['sessions','datahub','assets','capabilities','mcp','events','ai-news','report-workflows','legacy-reports','automation','hot','knowledge','frameworks','operations','integrations','local-integrations','strategy','documentation'];
export const CENTER_DOCUMENT_NAMES = ['architecture','getting-started','guide-data','guide-skills','guide-mcp','reference-data','reference-skills','reference-mcp','reference-api','architecture-guide','design-weknora-datahub','operations-guide','troubleshooting','glossary','documentation-version',...API_DOMAINS.map(name=>'reference-api-'+name)];

export function renderDocumentationCenter(root, legacyArtifacts) {
  if(!fs.existsSync(path.join(root,'docs/manual/navigation.json')))return {};
  const generated=spawnSync(process.env.RWB_TEST_PYTHON || 'python3',['-X','utf8',fileURLToPath(new URL('./documentation_center.py',import.meta.url)),root],{input:JSON.stringify(legacyArtifacts)+'\n',encoding:'utf8',maxBuffer:32*1024*1024});
  if(generated.error || generated.status!==0)throw new Error('Documentation center generation failed: '+(generated.stderr || generated.error?.message || 'unknown error'));
  const result=JSON.parse(generated.stdout);
  const expected=new Set(['index.html','api-manual.html',...CENTER_DOCUMENT_NAMES.map(name=>name+'.html')]);
  const names=Object.keys(result);
  if(names.length!==expected.size || names.some(name=>!expected.has(name) || typeof result[name]!=='string'))throw new Error('Documentation center inventory mismatch');
  return Object.fromEntries(names.map(name=>['outputs/research-web-architecture/'+name,result[name]]));
}
