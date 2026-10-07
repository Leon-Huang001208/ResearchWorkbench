/** Real managed validator with synthetic evidence; these fixtures prove no native or remote acceptance. */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {execFileSync,spawnSync} from "node:child_process";
import {pathToFileURL} from "node:url";

const summaryURL=new URL("../../scripts/summarize_verification_delivery.mjs",import.meta.url);
async function fixture(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"rwb-delivery-summary-"));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  fs.mkdirSync(path.join(root,".agents/runtime"),{recursive:true});fs.mkdirSync(path.join(root,"scripts"));fs.mkdirSync(path.join(root,"docs"));
  fs.cpSync(new URL("../../.agents/runtime/leon-engineering/",import.meta.url),path.join(root,".agents/runtime/leon-engineering"),{recursive:true});
  if(fs.existsSync(summaryURL))fs.copyFileSync(summaryURL,path.join(root,"scripts/summarize_verification_delivery.mjs"));
  const host={darwin:"macos",win32:"windows",linux:"linux"}[process.platform],other=host==="macos"?"windows":"macos";
  const selection={risk:"local-only",minimumLevel:"L1",reason:"fixture_docs",impact:["docs"],coupling:"low",platforms:["linux","macos","windows"].filter(p=>[host,other].includes(p)),tests:["local"],documentation:[],ci:["host-ci","other-ci"],realMachine:[]};
  const ci=platform=>({level:"L1",lane:"ci",gate:"merge",platforms:[platform],value:`.github/workflows/${platform}.yml`});
  const policy={schemaVersion:3,riskOrder:["docs-only","local-only","full-delivery"],levelOrder:["L0","L1","L2","L3","L4"],platformOrder:["generic","linux","macos","windows","cross-platform","real-machine-required"],statusOrder:["PASS","FAIL","SKIPPED","NOT_REQUIRED","NOT_RUN","BLOCKED","MANUAL_REQUIRED"],escalation:{highCouplingImpactThreshold:2,targetLevel:"L3"},catalogs:{tests:{local:{level:"L1",lane:"local",gate:"merge",platforms:["generic"],value:"fixture only; never executed"}},documentation:{},ci:{"host-ci":ci(host),"other-ci":ci(other)},realMachine:{}},rules:[{id:"docs",...selection,match:{files:[],prefixes:["docs/"],segments:[],suffixes:[]}}],fallback:{...selection,risk:"full-delivery",minimumLevel:"L4",reason:"unknown_path",coupling:"high"}};
  fs.writeFileSync(path.join(root,".agents/verification-policy.json"),JSON.stringify(policy));fs.writeFileSync(path.join(root,"docs/example.md"),"base\n");fs.writeFileSync(path.join(root,"evidence.json"),JSON.stringify({fixture:true,nativeAcceptance:false}));
  const git=args=>execFileSync("git",["-C",root,...args],{encoding:"utf8"}).trim();git(["init","-q"]);git(["config","user.email","fixture@example.invalid"]);git(["config","user.name","Fixture"]);git(["add","."]);git(["commit","-qm","base"]);const base=git(["rev-parse","HEAD"]);fs.writeFileSync(path.join(root,"docs/example.md"),"candidate\n");git(["add","."]);git(["commit","-qm","candidate"]);const head=git(["rev-parse","HEAD"]);
  const library=await import(pathToFileURL(path.join(root,".agents/runtime/leon-engineering/lib/verification/index.mjs")));
  const task={hostPlatform:host,taskKind:host==="macos"?"feature-development":"platform-adaptation",objective:"Synthetic delivery summary",acceptanceScope:"Fixture validator only",candidateCommit:head,candidateBaseCommit:base,supplementalGateIds:[]};const plan=library.planGitVerification({projectRoot:root,base,task});
  const receipt={schemaVersion:3,binding:plan.binding,task:plan.task,changeSummary:plan.changeSummary,changedFiles:plan.changedFiles,plannedLevel:plan.requiredLevel,actualLevel:plan.requiredLevel,components:plan.components,platforms:plan.platforms,impact:plan.impact,executed:plan.local.map(g=>({id:g.id,level:g.level,status:"PASS",durationSeconds:0,source:"runner",runnerPlatform:host,evidence:"evidence.json"})),external:plan.ci.map(g=>g.id==="host-ci"?{id:g.id,status:"PASS",source:"ci",evidence:"evidence.json",runnerPlatform:host,runId:"fixture-run",workflow:g.value,candidateCommit:head,checkoutCommit:head,expectedCheckoutCommit:head,checkoutKind:"candidate-head"}:{id:g.id,status:"NOT_RUN",source:"ci",evidence:"evidence.json"}),realMachine:[],result:"PASS",mergeReady:false,releaseReady:false,hostAcceptance:"PASS",aggregateAcceptance:"NOT_READY",platformHandoffs:[{platform:other,status:"NOT_RUN",gateIds:["other-ci"]}],uncoveredRisks:["external_gate_not_run:other-ci"],escalation:{required:false,targetLevel:null,reasons:[]}};
  const delivery={candidateCommit:head,branch:git(["symbolic-ref","--short","HEAD"]),pr:null,mergeCommit:null,runtimeUpdated:false,sourceRevision:base,reportCommit:null,diagramIdentities:[]};
  const write=(file,value)=>fs.writeFileSync(path.join(root,".git",file),JSON.stringify(value));write("plan.json",plan);write("receipt.json",receipt);write("delivery.json",delivery);
  const run=(extra=[])=>spawnSync(process.execPath,[path.join(root,"scripts/summarize_verification_delivery.mjs"),"--project",root,"--plan",".git/plan.json","--receipt",".git/receipt.json","--delivery",".git/delivery.json",...extra],{encoding:"utf8"});
  return {root,plan,receipt,delivery,write,run,git};
}

test("summary retains mechanical host PASS and aggregate NOT_READY with recorded identities",async t=>{
  const f=await fixture(t),before=f.git(["status","--porcelain"]),result=f.run();assert.equal(result.status,0,result.stderr);const summary=JSON.parse(result.stdout);assert.equal(summary.hostAcceptance,"PASS");assert.equal(summary.aggregateAcceptance,"NOT_READY");assert.equal(summary.mergeReady,false);assert.equal(summary.runtimeUpdated,false);assert.equal(summary.candidateCommit,f.plan.task.candidateCommit);assert.deepEqual(summary.changedFiles,f.plan.changedFiles);assert.equal(summary.deliveryMetadataVerified,false);assert.equal(f.git(["status","--porcelain"]),before);assert.equal(fs.existsSync(path.join(f.root,"logs")),false);
});
test("metadata cannot change candidate or override acceptance",async t=>{
  const f=await fixture(t);
  for(const delivery of [{...f.delivery,candidateCommit:"0".repeat(40)},{...f.delivery,hostAcceptance:"PASS"},{...f.delivery,aggregateAcceptance:"READY"},{...f.delivery,command:"arbitrary"}]){f.write("delivery.json",delivery);assert.notEqual(f.run().status,0);}
});
test("unsafe metadata paths and symlinks fail without echoing contents",async t=>{
  const f=await fixture(t);fs.symlinkSync(path.join(f.root,".git/delivery.json"),path.join(f.root,".git/alias.json"));
  for(const file of ["../outside.json",".git/alias.json"]){const args=[path.join(f.root,"scripts/summarize_verification_delivery.mjs"),"--project",f.root,"--plan",".git/plan.json","--receipt",".git/receipt.json","--delivery",file];const result=spawnSync(process.execPath,args,{encoding:"utf8"});assert.notEqual(result.status,0);assert.equal(JSON.parse(result.stderr).error.code,"PATH_ERROR");}
});
test("unbound and legacy receipts cannot be repainted as platform PASS",async t=>{
  const f=await fixture(t);const plan=structuredClone(f.plan),receipt=structuredClone(f.receipt);delete plan.binding;delete plan.changeSet;delete receipt.binding;f.write("plan.json",plan);f.write("receipt.json",receipt);assert.notEqual(f.run().status,0);f.write("plan.json",f.plan);f.write("receipt.json",{...f.receipt,schemaVersion:2});assert.notEqual(f.run().status,0);
});
test("recorded merge and runtime metadata do not override aggregate readiness",async t=>{
  const f=await fixture(t);f.write("delivery.json",{...f.delivery,pr:"https://github.com/Leon-Huang001208/ResearchWorkbench/pull/123",mergeCommit:"3".repeat(40),runtimeUpdated:true});const result=f.run();assert.equal(result.status,0,result.stderr);const summary=JSON.parse(result.stdout);assert.equal(summary.runtimeUpdated,true);assert.equal(summary.aggregateAcceptance,"NOT_READY");assert.equal(summary.releaseReady,false);assert.equal(summary.deliveryMetadataVerified,false);
});
test("malformed input and unknown nested identities produce stable redacted JSON errors",async t=>{
  const f=await fixture(t),sentinel="PRIVATE_PAYLOAD_MUST_NOT_APPEAR";fs.writeFileSync(path.join(f.root,".git/delivery.json"),`invalid JSON ${sentinel}`);const invalid=f.run();assert.notEqual(invalid.status,0);assert.equal(JSON.parse(invalid.stderr).error.code,"INPUT_ERROR");assert.equal(invalid.stderr.includes(sentinel),false);
  f.write("delivery.json",{...f.delivery,diagramIdentities:[{id:"overview",specificationSha256:"1".repeat(64),artifactSha256:"2".repeat(64),hostAcceptance:"PASS"}]});assert.notEqual(f.run().status,0);
});
