import assert from 'node:assert/strict';
import test from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';

const checkerURL = new URL('../../scripts/check_research_architecture.mjs', import.meta.url);
const atlasURL = new URL('../../scripts/build_research_web_api_atlas.mjs', import.meta.url);
const mapPath = 'docs/architecture/research-web/architecture-map.json';
const source = 'app/research_web/main.py';
const document = 'docs/module.md';
const review = 'docs/architecture/research-web/review-record.md';
const ids = ['01-deployment', '02-module-dependencies', '03-research-sequence', '04-data-file-flow', '05-capability-flow', '06-run-state', '07-delivery-state', '08-iteration-docs', '09-report-workflow-sequence', '10-excel-report-dataflow'];
const hash = value => ({ sha256: createHash('sha256').update(value).digest('hex'), bytes: Buffer.byteLength(value) });

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'research-doc-check-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (file, value) => { fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true }); fs.writeFileSync(path.join(root, file), typeof value === 'string' ? value : JSON.stringify(value)); };
  const read = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
  write(source, '@app.get("/api/research/runtime")\nasync def runtime():\n    return {}\n');
  write(document, '# Module\n\n[Source](../app/research_web/main.py)\n');
  write('tests/check.py', '# fixture test');
  write(review, '<!-- architecture-review {"group":"runtime","structure":"unchanged","reason":"Only error text changed; API and runtime relationships are unchanged.","diagrams":[]} -->');
  write('docs/architecture/research-web/README.md', '# Current architecture\n\n[Module](../../module.md)');
  const artifactRoot = 'outputs/research-web-architecture';
  const human = [];
  const diagrams = ids.map(id => {
    const spec = `docs/architecture/research-web/diagrams/${id}.json`;
    const artifact = `${artifactRoot}/${id}.html`;
    const receipt = `${artifactRoot}/${id}.receipt.json`;
    const visualReceipt = `${artifactRoot}/${id}.visual-check.json`;
    const graph = JSON.stringify({ schema_version: 1, diagram_type: 'architecture', components: [{ id: 'node' }], connections: [{ id: 'edge', from: 'node', to: 'node' }] });
    const html = '<!doctype html><title>Fixture diagram</title>';
    write(spec, graph); write(artifact, html);
    write(receipt, { schemaVersion: 1, command: 'deliver', ok: true, input: `/different/checkout/${spec}`, output: `/different/checkout/${artifact}`, specification: hash(graph), artifact: hash(html), validation: { checkCount: 9, checksPassed: 9, compositionProfile: 'showcase', compositionStatus: 'pass', errors: 0, warnings: 0 } });
    const viewports = [[1440,900],[1600,1000],[1920,1080],[2048,1320]].map(([width,height]) => ({ width,height,ok:true,overflowX:false,overflowY:false,innerWidth:width,innerHeight:height,scrollWidth:width,scrollHeight:height }));
    const screenshots = ['1440x900.dark','2048x1320.light'].map(size => ({ file: `${id}.${size}.png`, ok: true }));
    screenshots.forEach(capture => write(`${artifactRoot}/${capture.file}`, 'fixture image bytes'));
    write(visualReceipt, { schemaVersion:1,command:'visual-check',ok:true,status:'pass',visualReview:'pending',artifact:hash(html),containment:{status:'pass',viewports},captures:{status:'pass',screenshots} });
    human.push({id,status:'reviewed',reviewer:'fixture reviewer',date:'2026-09-03',notes:'Fixture review only, never production evidence.',artifactSha256:hash(html).sha256,specificationSha256:hash(graph).sha256,captures:screenshots.map(capture=>capture.file)});
    return {id,source:spec,artifact,receipt,visualReceipt,evidence:[{subjects:['node','edge'],source,contains:'async def runtime'}]};
  });
  write(`${artifactRoot}/index.html`, ids.map(id=>`<a href="${id}.html">${id}</a>`).join(''));
  const visualReview='docs/architecture/research-web/visual-review.json';
  write(visualReview,{schemaVersion:1,diagrams:human});
  write(mapPath,{schemaVersion:1,canonicalEntry:'docs/architecture/research-web/README.md',reviewRecord:review,visualReview,artifactRoot,groups:[{id:'runtime',sources:[source],documents:[document],diagrams:ids,tests:['tests/check.py']}],diagrams,apis:[{method:'GET',path:'/api/research/runtime',declaredPath:'/api/research/runtime',prefix:'',source}]});
  return {root,write,read};
}

async function check(f, changedFiles=[]) {
  assert.ok(fs.existsSync(checkerURL), 'repository-owned architecture checker must exist');
  const {checkResearchArchitecture} = await import(checkerURL);
  return checkResearchArchitecture({projectRoot:f.root,changedFiles});
}

test('portable offline fixture validates ten diagrams and ignores development absolute paths', async t => {
  assert.deepEqual((await check(fixture(t))).violations, []);
});

test('API Atlas distinguishes unique operations from overlapping source declarations', t => {
  const f=fixture(t); const map=f.read(mapPath);
  map.apis.push({...map.apis[0],source:'app/research_web/compat.py'});
  f.write('app/research_web/compat.py','@router.get("/runtime")\nasync def compatibility_runtime(): pass\n');
  f.write(mapPath,map);
  const result=spawnSync(process.execPath,[atlasURL.pathname,f.root],{encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  const html=fs.readFileSync(path.join(f.root,'outputs/research-web-architecture/api-atlas.html'),'utf8');
  assert.match(html,/<span>唯一接口<\/span><b>1<\/b>/);
  assert.match(html,/<span>源码声明<\/span><b>2<\/b>/);
});

for (const file of [source,'app/research_web/runtime/guard.mjs','app/research_web/ui/styles.css','app/research_web/skills/demo/SKILL.md','app/research_web/runtime/research.cordis.yml']) {
  test(`changed source requires module documentation and review: ${file}`, async t => {
    const f=fixture(t); if(file!==source) {f.write(file,'changed'); const map=f.read(mapPath); map.groups[0].sources.push(file); f.write(mapPath,map);}
    const codes=(await check(f,[file])).violations.map(v=>v.code);
    assert.ok(codes.includes('module_document_not_changed')); assert.ok(codes.includes('review_not_changed'));
  });
}

test('explicit unchanged reason permits unchanged diagrams, but changed structure requires graph changes',async t=>{
  const f=fixture(t); assert.deepEqual((await check(f,[source,document,review])).violations,[]);
  f.write(review,'<!-- architecture-review {"group":"runtime","structure":"changed","reason":"Runtime now has a new API relationship.","diagrams":["01-deployment"]} -->');
  assert.ok((await check(f,[source,document,review])).violations.some(v=>v.code==='structure_diagram_not_changed'));
});

const mutations = [
  ['old HTML after graph change','specification_hash',f=>f.write(f.read(mapPath).diagrams[0].source, {components:[{id:'new-node'}]})],
  ['changed HTML without new receipt','artifact_hash',f=>f.write(f.read(mapPath).diagrams[0].artifact,'changed')],
  ['stale API','api_inventory',f=>{const m=f.read(mapPath);m.apis[0].path='/api/research/deleted';f.write(mapPath,m);} ],
  ['new API omitted','api_inventory',f=>f.write(source,'@app.get("/api/research/runtime")\nasync def runtime(): pass\n@app.post("/api/research/new")\nasync def new(): pass')],
  ['wrong API prefix','api_inventory',f=>{const m=f.read(mapPath);m.apis[0].prefix='/wrong';f.write(mapPath,m);} ],
  ['unmounted router','api_unmounted',f=>{const m=f.read(mapPath);const s='app/research_web/routes.py';f.write(s,'router = APIRouter(prefix="/api/research")\n@router.get("/hidden")\nasync def hidden(): pass');m.groups[0].sources.push(s);m.apis.push({method:'GET',source:s,path:'/api/research/hidden',prefix:'/api/research',declaredPath:'/hidden'});f.write(mapPath,m);} ],
  ['missing source','reference_missing',f=>{const m=f.read(mapPath);m.groups[0].sources.push('app/research_web/missing.py');f.write(mapPath,m);} ],
  ['missing test','reference_missing',f=>{const m=f.read(mapPath);m.groups[0].tests=['tests/missing.py'];f.write(mapPath,m);} ],
  ['broken document link','link_missing',f=>f.write(document,'[broken](missing.md)')],
  ['broken document anchor','link_anchor_missing',f=>f.write(document,'[broken](#nonexistent)')],
  ['broken HTML entry link','link_missing',f=>f.write('outputs/research-web-architecture/index.html','<a href="missing.html">bad</a>')],
  ['unmapped new research module','source_unmapped',f=>f.write('app/research_web/unknown.py','new_module = True')],
  ['missing graph subject evidence','subject_unmapped',f=>{const m=f.read(mapPath);m.diagrams[0].evidence[0].subjects=['node'];f.write(mapPath,m);} ],
  ['stale human review hash','human_review',f=>{const m=f.read(mapPath);const h=f.read(m.visualReview);h.diagrams[0].artifactSha256='stale';f.write(m.visualReview,h);} ],
  ['duplicate human capture is not two reviewed screenshots','human_review',f=>{const m=f.read(mapPath);const h=f.read(m.visualReview);h.diagrams[0].captures.fill(h.diagrams[0].captures[0]);f.write(m.visualReview,h);} ],
  ['missing screenshot','reference_missing',f=>fs.unlinkSync(path.join(f.root,'outputs/research-web-architecture/01-deployment.1440x900.dark.png'))],
  ['only three viewports','visual_receipt',f=>{const p=f.read(mapPath).diagrams[0].visualReceipt;const v=f.read(p);v.containment.viewports.pop();f.write(p,v);} ],
  ['showcase warning','delivery_validation',f=>{const p=f.read(mapPath).diagrams[0].receipt;const v=f.read(p);v.validation.warnings=1;f.write(p,v);} ],
  ['incomplete diagram inventory','diagram_inventory',f=>{const m=f.read(mapPath);m.diagrams.pop();f.write(mapPath,m);} ],
  ['symlink reference','reference_unsafe',f=>{fs.unlinkSync(path.join(f.root,document));fs.symlinkSync(path.join(f.root,source),path.join(f.root,document));}],
];
for(const [name,code,mutate] of mutations) test(name,async t=>{const f=fixture(t);mutate(f);const result=await check(f);assert.ok(result.violations.some(v=>v.code===code),JSON.stringify(result));});

test('Git base includes committed, unstaged and untracked sources; invalid base fails closed',async t=>{
  const f=fixture(t); const git=(...args)=>{const result=spawnSync('git',args,{cwd:f.root,encoding:'utf8'});assert.equal(result.status,0,result.stderr);};
  git('init','-q');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture');
  f.write('app/research_web/unknown.py','unknown = True');
  const {collectChangedFiles}=await import(checkerURL);
  assert.ok(collectChangedFiles(f.root,'HEAD').includes('app/research_web/unknown.py'));
  assert.throws(()=>collectChangedFiles(f.root,'missing-base'),/git/i);
});

test('project constraints delegates to the same architecture gate',async t=>{
  const f=fixture(t);f.write('.agents/project-constraints.json',{schemaVersion:1,researchArchitectureMap:mapPath});
  const {checkProjectConstraints}=await import('../../.agents/project-constraints.mjs');
  assert.deepEqual(checkProjectConstraints({projectRoot:f.root}).violations,[]);
  f.write(source,'@app.get("/api/research/deleted")\nasync def runtime(): pass');
  assert.ok(checkProjectConstraints({projectRoot:f.root}).violations.some(v=>v.code==='api_inventory'));
});

test('settings contains a fixed read-only architecture entry with opener isolation',()=>{
  const settings=fs.readFileSync(new URL('../../app/research_web/ui/settings.mjs',import.meta.url),'utf8');
  assert.match(settings,/href="\/api\/research\/documentation\/index\.html"/);
  assert.match(settings,/target="_blank" rel="noopener noreferrer"/);
});

for (const value of [null, false, 0, '', [], 'not a map']) {
  test(`invalid top-level map fails closed: ${JSON.stringify(value)}`, async t => {
    const f=fixture(t);f.write(mapPath,JSON.stringify(value));
    assert.ok((await check(f)).violations.some(item=>item.code==='map_schema'));
    const result=spawnSync(process.execPath,[checkerURL.pathname,'--project',f.root,'--changed-file',source],{encoding:'utf8'});
    assert.equal(result.status,1);
  });
}

for (const declaration of [
  '@app.get(path="/api/research/hidden")',
  '@app.get(summary="Hidden", path="/api/research/hidden")',
  '@app.get(\n    tags=["local", "docs"],\n    path="/api/research/hidden",\n)',
]) test(`keyword API cannot bypass inventory: ${declaration}`,async t=>{
  const f=fixture(t);f.write(source,`${fs.readFileSync(path.join(f.root,source),'utf8')}\n${declaration}\nasync def hidden(): pass\n`);
  assert.ok((await check(f)).violations.some(item=>item.code==='api_inventory' && item.message.includes('/api/research/hidden')));
});

test('a mapped keyword API remains valid',async t=>{
  const f=fixture(t);f.write(source,'@app.get(path="/api/research/runtime", tags=["research"])\nasync def runtime(): pass\n');
  assert.deepEqual((await check(f)).violations,[]);
});

for (const declaration of ['@app.get(PATH)', '@app.get(path=f"/api/research/{name}")', '@app.api_route("/api/research/hidden", methods=["GET"])']) {
  test(`unsupported API declaration fails explicitly: ${declaration}`,async t=>{
    const f=fixture(t);f.write(source,`${fs.readFileSync(path.join(f.root,source),'utf8')}\n${declaration}\nasync def hidden(): pass\n`);
    assert.ok((await check(f)).violations.some(item=>item.code==='api_declaration_unsupported'));
  });
}

for(const [field,suffix] of [['artifact','.html'],['receipt','.receipt.json'],['visualReceipt','.visual-check.json']]) {
  for(const value of [`outputs/research-web-architecture/../outside${suffix}`,`outputs/research-web-architecture/wrong-name${suffix}`]) {
    test(`fixed artifact boundary rejects ${field}: ${value}`,async t=>{
      const f=fixture(t);const map=f.read(mapPath);const original=map.diagrams[0][field];
      f.write(value,fs.readFileSync(path.join(f.root,original),'utf8'));map.diagrams[0][field]=value;f.write(mapPath,map);
      assert.ok((await check(f)).violations.some(item=>item.code==='artifact_boundary'));
    });
  }
}

function runCI(f,base,head) {
  const workflow=fs.readFileSync(new URL('../../.github/workflows/project-constraints.yml',import.meta.url),'utf8');
  const body=workflow.split('      - name: Enforce project constraints')[1].split('        run: |\n')[1].split('\n').map(line=>line.replace(/^          /,'')).join('\n');
  const script=body.replaceAll('${{ github.event.before }}',base).replaceAll('${{ github.event.pull_request.base.sha }}',base);
  f.write('.agents/project-constraints.mjs','console.log(JSON.stringify(process.argv.slice(2)));');
  return spawnSync('bash',['-c',script],{cwd:f.root,encoding:'utf8',env:{...process.env,GITHUB_EVENT_NAME:'push',GITHUB_WORKSPACE:f.root,GITHUB_SHA:head,RUNNER_TEMP:f.root}});
}

test('actual CI shell stops when git diff cannot resolve the base',t=>{
  const f=fixture(t);const result=runCI(f,'missing-base','HEAD');
  assert.notEqual(result.status,0,'git failure must not become zero changed files and a successful gate');
  assert.doesNotMatch(result.stdout,/--project/,'the downstream checker must not run with partial input');
});

test('actual CI shell preserves NUL-delimited filenames as single arguments',t=>{
  const f=fixture(t);const git=(...args)=>{const result=spawnSync('git',args,{cwd:f.root,encoding:'utf8'});assert.equal(result.status,0,result.stderr);return result.stdout.trim();};
  git('init','-q');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','base');const base=git('rev-parse','HEAD');
  const filename='app/research_web/space and\nnewline.mjs';f.write(filename,'export const value = 1;');git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','change');
  const result=runCI(f,base,'HEAD');assert.equal(result.status,0,result.stderr);
  assert.deepEqual(JSON.parse(result.stdout),['--project',f.root,'--changed-file',filename]);
});
