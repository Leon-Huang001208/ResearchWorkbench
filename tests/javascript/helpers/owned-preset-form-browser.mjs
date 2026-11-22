/** File-only fresh Chrome checks the actual renderer/controller submit contract. */
import assert from 'node:assert/strict';
import {writeFile,mkdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {join} from 'node:path';

const root=process.argv[2];
if(!root)throw Error('owned_evidence_root_required');
const moduleUrl=new URL('../../../app/research_web/ui/scenarios.mjs',import.meta.url).href;
const cases=[
  {id:'company-one',scene:'owned-company-evidence',preset:'company_one_pager',query:'公司问题',question:'',valid:true,sends:1},
  {id:'company-fundamental',scene:'owned-company-evidence',preset:'fundamental_analysis',query:'基本面问题',question:'',valid:true,sends:1},
  {id:'research-outline',scene:'owned-research-prep',preset:'research_outline',query:'调研问题',question:'',valid:true,sends:1},
  {id:'old-required',scene:'company-onepager',question:'',valid:false,sends:0},
  {id:'owned-no-preset',scene:'owned-company-evidence',question:'',valid:false,sends:0},
  {id:'owned-empty-query',scene:'owned-company-evidence',preset:'company_one_pager',query:'',question:'',valid:false,sends:0},
  {id:'owned-foreign-preset',scene:'owned-company-evidence',preset:'research_outline',query:'错配问题',question:'',valid:false,sends:0},
  {id:'owned-url-query',scene:'owned-company-evidence',preset:'company_one_pager',query:'https://example.com',question:'',valid:false,sends:0},
  {id:'owned-conflict',scene:'owned-company-evidence',preset:'company_one_pager',query:'新问题',question:'原问题',valid:true,sends:0},
];
const script=`
import {createScenarioController,renderScenarioPanel} from ${JSON.stringify(moduleUrl)};
const results=[];
for(const value of ${JSON.stringify(cases)}){
 let handoffs=0,previewCalls=0,submitEvents=0,pending=Promise.resolve();
 const row={id:value.scene,source_selection_kind:value.scene.startsWith('owned-')?'owned-method':undefined,name:'Case',description:'',coverage:[],steps:[],examples:[{question:'Example'}],expected_artifacts:[],required_inputs:[],capabilities:[{id:value.scene,version:1,available:true}]};
 const c=createScenarioController({storage:null,makeID:()=> 'isolated-browser-form',api:{scenarioCatalog:async()=>({items:[row]}),scenarioPrepare:async()=>{previewCalls++;return {method_qualification:{kind:'owned-method',status:'incomplete',missing:[]}};},handoff:async()=>{handoffs++;return {state:'prepared',session_id:'target',mode:'fingpt',draft:'draft',scenario_context:{scenario:{inputs:{as_of:'2026-10-28',subject:{identity:'600600.SH'}}},requirements:[]}};}}});
 await c.open({scenario:value.scene,subject:{kind:'stock',identity:'600600.SH'},as_of:'2026-10-28',question:value.question});
 if(value.preset){c.edit('question_preset',value.preset);c.edit('preset_query',value.query);}
 await c.preview();
 document.querySelector('#panel').innerHTML=renderScenarioPanel(c.state);
 const form=document.querySelector('[data-scenario-form]'),question=document.querySelector('#scenario-question');
 const before={id:value.id,formValid:form.checkValidity(),questionRequired:question.required,questionValueMissing:question.validity.valueMissing,noValidate:form.noValidate};
 form.addEventListener('submit',event=>{submitEvents++;pending=c.handle(event);});
 document.querySelector('[data-scenario-freeze]').click();await pending;
 results.push({...before,previewCalls,submitEvents,handoffs,controllerError:c.state.error});
}
document.querySelector('#evidence').textContent=JSON.stringify(results);
`;
const html=join(root,'form-cases.html');
await writeFile(html,'<!doctype html><meta charset="utf-8"><div id="panel"></div><pre id="evidence">PENDING</pre><script type="module">'+script+'</script>');
const profile=join(root,'chrome-profile');await mkdir(profile);
const args=['--headless','--disable-gpu','--disable-background-networking','--disable-component-update','--disable-default-apps','--no-default-browser-check','--no-first-run','--disable-sync','--disable-extensions','--metrics-recording-only','--host-resolver-rules=MAP * ~NOTFOUND','--allow-file-access-from-files','--user-data-dir='+profile,'--virtual-time-budget=4000','--dump-dom',new URL('file://'+html).href];
const child=spawnSync('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',args,{encoding:'utf8',timeout:20000,maxBuffer:2*1024*1024});
await writeFile(join(root,'browser-dom.html'),child.stdout||'');await writeFile(join(root,'browser-stderr.log'),child.stderr||'');
assert.equal(child.status,0,child.error?.message||'isolated_chrome_failed');
const text=child.stdout.match(/<pre id="evidence">([^<]*)<\/pre>/)?.[1];
assert.ok(text&&text!=='PENDING','browser_module_did_not_complete');
const results=JSON.parse(text.replaceAll('&quot;','"').replaceAll('&amp;','&').replaceAll('&lt;','<').replaceAll('&gt;','>'));
for(const [index,result] of results.entries()){
 const expected=cases[index];assert.equal(result.formValid,expected.valid,expected.id);assert.equal(result.handoffs,expected.sends,expected.id);assert.equal(result.noValidate,false);
 assert.equal(result.submitEvents,expected.valid?1:0,expected.id);
 if(expected.sends){assert.equal(result.questionRequired,false);assert.equal(result.previewCalls,1);}
 if(expected.id==='owned-conflict')assert.match(result.controllerError,/冲突/);
}
await writeFile(join(root,'browser-results.json'),JSON.stringify(results,null,2));
console.log(JSON.stringify({status:'PASS',cases:results.length,positive:3,negative:6,fileOnly:true,freshProfile:true}));
