#!/usr/bin/env node
/** Offline source → documentation → diagram evidence gate. No Archify installation required. */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

export const MAP_PATH = 'docs/architecture/research-web/architecture-map.json';
const ARTIFACT_ROOT = 'outputs/research-web-architecture';
const REQUIRED_DIAGRAMS = [
  '01-deployment',
  '02-module-dependencies',
  '03-research-sequence',
  '04-data-file-flow',
  '05-capability-flow',
  '06-run-state',
  '07-delivery-state',
  '08-iteration-docs',
  '09-report-workflow-sequence',
  '10-excel-report-dataflow',
];
const VIEWPORTS = ['1440x900', '1600x1000', '1920x1080', '2048x1320'];
const GRAPH_FIELDS = {architecture:['components','connections'],sequence:['participants','messages'],dataflow:['nodes','flows'],lifecycle:['states','transitions'],workflow:['nodes','edges']};
const SOURCE_EXTENSIONS = /\.(?:py|[cm]?js|css|html|md|json|ya?ml|toml|sh|txt)$/i;

function relative(value) {
  if (typeof value !== 'string' || !value || path.isAbsolute(value) || value.includes('\\') || /[\x00-\x1f]/.test(value)) throw new Error('unsafe repository-relative path');
  const normalized = path.posix.normalize(value);
  if (normalized === '..' || normalized.startsWith('../') || normalized === '.') throw new Error('unsafe repository-relative path');
  return normalized;
}

function target(root, value) {
  const normalized = relative(value);
  let current = root;
  for (const part of normalized.split('/').filter(Boolean)) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error('symbolic link is not permitted');
  }
  return current;
}

function walk(root, directory) {
  const directoryPath = target(root, directory);
  return fs.readdirSync(directoryPath, {withFileTypes:true}).flatMap(entry => {
    if (entry.name === '__pycache__' || entry.name === '.DS_Store') return [];
    const file = `${directory.replace(/\/$/,'')}/${entry.name}`;
    if (entry.isSymbolicLink()) return [file]; // Validation must reject rather than follow it.
    return entry.isDirectory() ? walk(root,file) : [file];
  });
}

export function collectChangedFiles(projectRoot, base) {
  const git = args => {
    try { return execFileSync('git',args,{cwd:projectRoot,encoding:'utf8',stdio:['ignore','pipe','pipe']}).split('\0').filter(Boolean); }
    catch { throw new Error('git change detection failed; check the project and base revision'); }
  };
  const files = [...git(['diff','--name-only','-z']),...git(['diff','--cached','--name-only','-z']),...git(['ls-files','--others','--exclude-standard','-z'])];
  if (base) files.push(...git(['diff','--name-only','-z',base,'HEAD','--']));
  return [...new Set(files)].sort();
}

const matches = (file, patterns) => patterns.some(pattern => pattern.endsWith('/') ? file.startsWith(pattern) : file === pattern);
const digest = bytes => ({sha256:createHash('sha256').update(bytes).digest('hex'),bytes:bytes.length});
const sameHash = (record, actual) => record?.sha256 === actual.sha256 && record?.bytes === actual.bytes;

function pythonCallArguments(content, start) {
  const args=[];const stack=['('];let argument='',quote='';
  for(let index=start;index<content.length;index++) {
    const character=content[index];
    if(quote) {
      if(character==='\\') {argument+=content.slice(index,index+2);index++;continue;}
      if(content.startsWith(quote,index)) {argument+=quote;index+=quote.length-1;quote='';}
      else argument+=character;
      continue;
    }
    if(character==='"' || character==="'") {
      quote=content.startsWith(character.repeat(3),index)?character.repeat(3):character;
      argument+=quote;index+=quote.length-1;continue;
    }
    if(character==='#') {while(index<content.length && content[index]!=='\n')index++;argument+=' ';continue;}
    if('([{'.includes(character))stack.push(character);
    else if(')]}'.includes(character)) {
      if(stack.pop()!=={')':'(',']':'[','}':'{'}[character])throw new Error('unbalanced Python declaration');
      if(!stack.length) {if(argument.trim())args.push(argument.trim());return args;}
    } else if(character===',' && stack.length===1) {args.push(argument.trim());argument='';continue;}
    argument+=character;
  }
  throw new Error('unterminated Python declaration');
}

export function checkResearchArchitecture({projectRoot,changedFiles=[]}) {
  const root = fs.realpathSync(projectRoot);
  const checkedFiles = [...new Set(changedFiles.map(relative))];
  const changed = new Set(checkedFiles);
  const violations = [];
  const issue = (code,file,message) => violations.push({code,path:file,message});
  const read = (file,kind='file') => {
    try {
      const resolved = target(root,file);
      const stat = fs.statSync(resolved);
      if (kind === 'directory') { if (!stat.isDirectory()) throw new Error('expected directory'); return resolved; }
      if (!stat.isFile()) throw new Error('expected regular file');
      return fs.readFileSync(resolved);
    } catch(error) {
      issue(error.code === 'ENOENT' ? 'reference_missing' : 'reference_unsafe',file,String(error.code || error.message));
      return null;
    }
  };
  const json = file => {
    const bytes = read(file); if (!bytes) return null;
    try { return JSON.parse(bytes.toString('utf8')); }
    catch { issue('invalid_json',file,'Expected valid JSON'); return null; }
  };
  const map = json(MAP_PATH);
  if (!map || typeof map!=='object' || Array.isArray(map)) {
    issue('map_schema',MAP_PATH,'Architecture map must be a non-null object');
    return {checkedFiles,violations};
  }
  if (map.schemaVersion !== 1 || map.artifactRoot !== ARTIFACT_ROOT || !Array.isArray(map.groups) || !map.groups.length || !Array.isArray(map.apis) || !map.apis.length || !Array.isArray(map.diagrams)) {
    issue('map_schema',MAP_PATH,'Expected schema 1, nonempty groups/API inventory, and the fixed artifact root');
    return {checkedFiles,violations};
  }
  const textFiles = new Set([map.canonicalEntry]);
  const reviewText = read(map.reviewRecord)?.toString('utf8') || '';
  const reviews = new Map();
  for (const match of reviewText.matchAll(/<!--\s*architecture-review\s+(\{[^]*?\})\s*-->/g)) {
    try { const entry=JSON.parse(match[1]); reviews.set(entry.group,entry); }
    catch { issue('review_invalid',map.reviewRecord,'Invalid architecture-review JSON marker'); }
  }
  const groups=[];
  for (const group of map.groups) {
    if (!group.id || !['sources','documents','tests','diagrams'].every(key=>Array.isArray(group[key]) && group[key].length && group[key].every(value=>typeof value==='string' && value.length))) {
      issue('map_schema',MAP_PATH,'Each group requires id and nonempty sources/documents/tests/diagrams'); continue;
    }
    groups.push(group);
    for (const file of group.sources) read(file,file.endsWith('/')?'directory':'file');
    for (const file of group.tests) read(file);
    for (const file of group.documents) {read(file);textFiles.add(file);}
    for (const id of group.diagrams) if (!map.diagrams.some(diagram=>diagram.id===id)) issue('diagram_inventory',MAP_PATH,`Unknown group diagram: ${id}`);
    if (!checkedFiles.some(file=>matches(file,group.sources))) continue;
    for (const document of group.documents) if (!changed.has(document)) issue('module_document_not_changed',document,`Source changed in ${group.id}`);
    if (!changed.has(map.reviewRecord)) issue('review_not_changed',map.reviewRecord,`Source changed in ${group.id}`);
    const review=reviews.get(group.id);
    if (!review || !['changed','unchanged'].includes(review.structure) || typeof review.reason!=='string' || review.reason.trim().length<12 || !Array.isArray(review.diagrams)) {
      issue('review_invalid',map.reviewRecord,`Missing meaningful structure decision for ${group.id}`); continue;
    }
    if (review.structure==='changed') {
      if (!review.diagrams.length) issue('structure_diagram_not_changed',map.reviewRecord,`No affected diagrams for ${group.id}`);
      for (const id of review.diagrams) {
        const diagram=map.diagrams.find(item=>item.id===id);
        if (!group.diagrams.includes(id) || !diagram || !changed.has(diagram.source)) issue('structure_diagram_not_changed',map.reviewRecord,`Expected changed graph source: ${id}`);
      }
    }
  }
  let researchFiles=[];
  try {researchFiles=walk(root,'app/research_web');} catch {issue('reference_missing','app/research_web','Research source tree unavailable');}
  for (const file of new Set([...researchFiles,...checkedFiles.filter(file=>file.startsWith('app/research_web/'))])) {
    if (!SOURCE_EXTENSIONS.test(file)) continue;
    if (!groups.some(group=>matches(file,group.sources))) issue('source_unmapped',file,'Research source is not assigned to a documentation group');
  }

  // Scan actual declarations independently of the inventory, so additions cannot be silently omitted.
  const actualAPIs=[];
  const mainSource='app/research_web/main.py';
  const mainCode=read(mainSource)?.toString('utf8') || '';
  const mountedSources=new Set([mainSource]);
  for (const match of mainCode.matchAll(/^from\s+\.(\w+(?:\.\w+)*)\s+import\s+router(?:\s+as\s+(\w+))?\s*$/gm)) {
    const alias=match[2] || 'router';
    if (new RegExp(`app\\.include_router\\(\\s*${alias}\\s*\\)`).test(mainCode)) mountedSources.add(`app/research_web/${match[1].replaceAll('.','/')}.py`);
  }
  for (const source of researchFiles.filter(file=>file.endsWith('.py'))) {
    const content=read(source)?.toString('utf8');if (!content) continue;
    const prefixes=new Map([...content.matchAll(/^(\w+)\s*=\s*APIRouter\(\s*prefix\s*=\s*["']([^"']*)["']/gm)].map(match=>[match[1],match[2]]));
    for (const match of content.matchAll(/^\s*@\s*(\w+(?:\.\w+)*)\s*\.\s*(get|post|put|patch|delete|head|options|api_route|route|websocket)\s*\(/gm)) {
      if (!mountedSources.has(source)) issue('api_unmounted',source,'API source is not directly mounted by the Research Web entrypoint');
      try {
        if(['api_route','route','websocket'].includes(match[2]))throw new Error('unsupported route decorator');
        const args=pythonCallArguments(content,match.index+match[0].length);
        const pathArgument=args.find(argument=>/^path\s*=/.test(argument));
        const pathLiteral=(pathArgument?pathArgument.replace(/^path\s*=\s*/,''):args[0]) || '';
        const literal=pathLiteral.match(/^(["'])([^"'\\\r\n]*)\1$/);
        if(!literal)throw new Error('route path must be an unescaped literal');
        const declaredPath=literal[2];
        const prefix=prefixes.get(match[1]) || '';
        actualAPIs.push({source,method:match[2].toUpperCase(),path:prefix+declaredPath,declaredPath,prefix});
      } catch {
        issue('api_declaration_unsupported',source,'Unsupported HTTP declaration; use a literal positional/path keyword or extend the checked parser');
      }
    }
  }
  const apiKey = api => JSON.stringify([api.source,api.method,api.path,api.declaredPath,api.prefix]);
  const actualSet=new Set(actualAPIs.map(apiKey));const declaredSet=new Set(map.apis.map(apiKey));
  if (declaredSet.size!==map.apis.length) issue('api_inventory',MAP_PATH,'Duplicate API declarations');
  for (const api of map.apis) if (!actualSet.has(apiKey(api))) issue('api_inventory',api.source,`Stale or invalid API: ${api.method} ${api.path}`);
  for (const api of actualAPIs) if (!declaredSet.has(apiKey(api))) issue('api_inventory',api.source,`API missing from inventory: ${api.method} ${api.path}`);

  const ids=map.diagrams.map(diagram=>diagram.id);
  if (ids.length!==REQUIRED_DIAGRAMS.length || new Set(ids).size!==REQUIRED_DIAGRAMS.length || REQUIRED_DIAGRAMS.some(id=>!ids.includes(id))) issue('diagram_inventory',MAP_PATH,`Exactly the ${REQUIRED_DIAGRAMS.length} required diagrams must be delivered`);
  const human=json(map.visualReview);
  for (const diagram of map.diagrams) {
    const expected={artifact:'.html',receipt:'.receipt.json',visualReceipt:'.visual-check.json'};
    const validPaths=REQUIRED_DIAGRAMS.includes(diagram.id) && Object.entries(expected).every(([field,suffix])=>{
      try {const canonical=`${ARTIFACT_ROOT}/${diagram.id}${suffix}`;return diagram[field]===canonical && relative(diagram[field])===canonical;}
      catch {return false;}
    });
    if(!validPaths) {issue('artifact_boundary',MAP_PATH,`Require fixed canonical output filenames: ${diagram.id}`);continue;}
    const specBytes=read(diagram.source);const artifactBytes=read(diagram.artifact);
    const receipt=json(diagram.receipt);const visual=json(diagram.visualReceipt);
    const graph=json(diagram.source);
    if (specBytes && receipt && !sameHash(receipt.specification,digest(specBytes))) issue('specification_hash',diagram.receipt,'Specification bytes/hash are stale');
    if (artifactBytes && receipt && !sameHash(receipt.artifact,digest(artifactBytes))) issue('artifact_hash',diagram.receipt,'HTML bytes/hash are stale');
    const validation=receipt?.validation;
    if (receipt?.schemaVersion!==1 || receipt?.ok!==true || receipt?.command!=='deliver' || validation?.checkCount!==9 || validation?.checksPassed!==9 || validation?.compositionProfile!=='showcase' || validation?.compositionStatus!=='pass' || validation?.errors!==0 || validation?.warnings!==0) issue('delivery_validation',diagram.receipt,'Require deliver, showcase 9/9, zero errors and warnings');
    const fields=GRAPH_FIELDS[graph?.diagram_type];
    if (!fields || !fields.every(field=>Array.isArray(graph[field]) && graph[field].length)) issue('graph_schema',diagram.source,'Unknown or empty graph nodes/relationships');
    else {
      const subjects=fields.flatMap(field=>graph[field].map(item=>item.id));const subjectSet=new Set(subjects);const mapped=new Set();
      if (subjects.some(id=>typeof id!=='string' || !id) || subjectSet.size!==subjects.length) issue('graph_schema',diagram.source,'Subjects require unique IDs');
      const nodes=new Set(graph[fields[0]].map(item=>item.id));
      for (const relation of graph[fields[1]]) if (!nodes.has(relation.from) || !nodes.has(relation.to)) issue('graph_schema',diagram.source,`Unknown relationship endpoint: ${relation.id}`);
      for (const evidence of diagram.evidence || []) {
        const code=read(evidence.source)?.toString('utf8');
        if (evidence.contains && !code?.includes(evidence.contains)) issue('evidence_stale',evidence.source,'Missing evidence declaration');
        for (const subject of evidence.subjects || []) {
          mapped.add(subject);if (!subjectSet.has(subject)) issue('evidence_stale',diagram.source,`Unknown evidence subject: ${subject}`);
        }
      }
      for (const subject of subjects) if (!mapped.has(subject)) issue('subject_unmapped',diagram.source,`No source evidence for ${subject}`);
    }
    const viewports=visual?.containment?.viewports || [];
    const viewportOK=viewport=>viewport.ok===true && viewport.overflowX===false && viewport.overflowY===false && viewport.innerWidth===viewport.width && viewport.innerHeight===viewport.height && viewport.scrollWidth<=viewport.innerWidth && viewport.scrollHeight<=viewport.innerHeight;
    if (visual?.schemaVersion!==1 || visual?.command!=='visual-check' || visual?.ok!==true || visual?.status!=='pass' || visual?.containment?.status!=='pass' || visual?.captures?.status!=='pass' || !artifactBytes || !sameHash(visual.artifact,digest(artifactBytes)) || VIEWPORTS.some(size=>!viewports.some(viewport=>`${viewport.width}x${viewport.height}`===size && viewportOK(viewport)))) issue('visual_receipt',diagram.visualReceipt,'Require current artifact hash and successful containment at all four viewports');
    const captures=visual?.captures?.screenshots || [];
    const captureNames=new Set();
    for (const capture of captures) {
      if (typeof capture.file!=='string' || path.posix.basename(capture.file)!==capture.file || capture.ok!==true) {issue('visual_receipt',diagram.visualReceipt,'Invalid capture reference');continue;}
      captureNames.add(capture.file);read(`${ARTIFACT_ROOT}/${capture.file}`);
    }
    const reviewsForDiagram=human?.diagrams?.filter(item=>item.id===diagram.id) || [];
    const review=reviewsForDiagram[0];
    if (reviewsForDiagram.length!==1 || review?.status!=='reviewed' || !review?.reviewer || !review?.date || !review?.notes || !artifactBytes || !specBytes || review.artifactSha256!==digest(artifactBytes).sha256 || review.specificationSha256!==digest(specBytes).sha256 || !Array.isArray(review.captures) || new Set(review.captures).size<2 || review.captures.some(file=>!captureNames.has(file))) issue('human_review',map.visualReview,`Require explicit same-hash human screenshot review: ${diagram.id}`);
  }

  // Restrict link checking to current canonical/module Markdown and the generated entry, not legacy docs.
  try {for (const file of walk(root,path.posix.dirname(map.canonicalEntry))) if(file.endsWith('.md')) textFiles.add(file);} catch {issue('reference_missing',map.canonicalEntry,'Canonical documentation tree unavailable');}
  textFiles.add(`${ARTIFACT_ROOT}/index.html`);
  for (const file of textFiles) {
    const bytes=read(file);if(!bytes)continue;
    const content=bytes.toString('utf8').replace(/```[^]*?```/g,'');
    const links=file.endsWith('.html') ? [...content.matchAll(/(?:href|src)=["']([^"']+)["']/g)].map(match=>match[1]) : [...content.matchAll(/!?\[[^\]]*\]\(<?([^\s)>]+)>?(?:\s+["'][^]*?["'])?\)/g)].map(match=>match[1]);
    for (const link of links) {
      if (/^(?:https?:|mailto:|data:)/i.test(link))continue;
      if (/^[a-z][a-z\d+.-]*:/i.test(link) || link.startsWith('//')) {issue('link_unsafe',file,'Unsupported link protocol');continue;}
      try {
        const [pathname,anchor]=decodeURIComponent(link).split('#');
        const destination=relative(path.posix.join(path.posix.dirname(file),pathname.split('?')[0] || path.posix.basename(file)));
        const resolved=target(root,destination);
        if (anchor && fs.statSync(resolved).isFile()) {
          const targetText=fs.readFileSync(resolved,'utf8');
          const headings=[...targetText.matchAll(/^#{1,6}\s+(.+)$/gm)].map(match=>match[1].trim().toLowerCase().replace(/[^\p{L}\p{N}_\s-]/gu,'').replace(/\s/g,'-'));
          if (!headings.includes(anchor) && !targetText.includes(`id="${anchor}"`) && !targetText.includes(`id='${anchor}'`)) issue('link_anchor_missing',file,`Missing anchor: ${link}`);
        }
      } catch {issue('link_missing',file,`Unresolvable local link: ${link}`);}
    }
  }
  return {schemaVersion:1,checkedFiles,violations};
}

export function writeCheckLog(projectRoot,result) {
  const root=fs.realpathSync(projectRoot);
  const directory=path.join(root,'logs');
  if (!fs.existsSync(directory)) fs.mkdirSync(directory);
  target(root,'logs');
  const file=path.join(directory,'research-architecture-check.jsonl');
  if (fs.existsSync(file)) target(root,'logs/research-architecture-check.jsonl');
  fs.appendFileSync(file,JSON.stringify({timestamp:new Date().toISOString(),event:'research_architecture_checked',checkedCount:result.checkedFiles.length,violationCount:result.violations.length,codes:[...new Set(result.violations.map(item=>item.code))]})+'\n',{flag:'a',mode:0o600});
}

function main(args) {
  let projectRoot=process.cwd(),base;const files=[];
  for(let index=0;index<args.length;index++) {
    const argument=args[index];
    if(argument==='--help'){process.stdout.write('Usage: node scripts/check_research_architecture.mjs [--project PATH] [--base REV] [--changed-file PATH ...]\n');return;}
    if(!['--project','--base','--changed-file'].includes(argument) || !args[index+1] || args[index+1].startsWith('--')) throw new Error('invalid arguments; use --help');
    const value=args[++index];if(argument==='--project')projectRoot=value;else if(argument==='--base')base=value;else files.push(value);
  }
  const changedFiles=base || !files.length ? [...new Set([...collectChangedFiles(projectRoot,base),...files])] : files;
  const result=checkResearchArchitecture({projectRoot,changedFiles});
  writeCheckLog(projectRoot,result);
  process.stdout.write(JSON.stringify(result,null,2)+'\n');
  if(result.violations.length)process.exitCode=1;
}

if(process.argv[1]===fileURLToPath(import.meta.url)) {
  try {main(process.argv.slice(2));}
  catch(error){process.stderr.write(`research architecture check failed: ${error.message}\n`);process.exitCode=1;}
}
