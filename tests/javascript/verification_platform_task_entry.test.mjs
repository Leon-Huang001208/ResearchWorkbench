/** Isolated thin-entry contract: the temporary library is a routing stub, not an installed runtime. */
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {spawnSync, execFileSync} from "node:child_process";
import {pathToFileURL} from "node:url";
import {createHash} from "node:crypto";

function fixture(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"rwb-task-entry-"));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  fs.mkdirSync(path.join(root,"scripts"));
  const script=path.join(root,"scripts/plan_verification.mjs");
  fs.copyFileSync(new URL("../../scripts/plan_verification.mjs",import.meta.url),script);
  const library=path.join(root,".agents/runtime/leon-engineering/lib/verification");fs.mkdirSync(library,{recursive:true});
  fs.writeFileSync(path.join(library,"index.mjs"),`
    import fs from 'node:fs'; import path from 'node:path';
    export class VerificationError extends Error {constructor(code,message){super(message);this.code=code;}}
    export const safeProjectRoot=root=>fs.realpathSync(root);
    export function safeRegularFile(root,file){const value=path.resolve(root,file);if(path.isAbsolute(file)||!value.startsWith(root+path.sep)||fs.lstatSync(value).isSymbolicLink())throw new VerificationError('PATH_ERROR','unsafe task input');return value;}
    export const planVerification=options=>({schemaVersion:3,delegated:'changed-files',options});
    export const planGitVerification=options=>({schemaVersion:options.task?4:3,delegated:'git-bound',options});
  `);
  const host={darwin:"macos",win32:"windows",linux:"linux"}[process.platform];
  const task={hostPlatform:host,taskKind:host==="macos"?"feature-development":"platform-adaptation",objective:"Thin entry contract",acceptanceScope:"Host only",candidateCommit:"1".repeat(40),candidateBaseCommit:"2".repeat(40),supplementalGateIds:[]};
  fs.writeFileSync(path.join(root,"task.json"),JSON.stringify(task));
  const run=args=>spawnSync(process.execPath,[script,"--project",root,...args],{encoding:"utf8"});
  return {root,script,task,run};
}

test("explicit base and task context delegate to Git-bound plan4 without writes",t=>{
  const f=fixture(t);const before=fs.readFileSync(path.join(f.root,"task.json"));const result=f.run(["--base","master","--task-context","task.json"]);
  assert.equal(result.status,0,result.stderr);const plan=JSON.parse(result.stdout);assert.equal(plan.schemaVersion,4);assert.equal(plan.delegated,"git-bound");assert.deepEqual(plan.options.task,f.task);assert.equal(plan.options.base,"master");assert.equal("changedFiles" in plan.options,false);assert.deepEqual(fs.readFileSync(path.join(f.root,"task.json")),before);assert.equal(fs.existsSync(path.join(f.root,"logs")),false);
});
test("original changed-file mode preserves its delegation and signal deduplication",t=>{
  const f=fixture(t);const result=f.run(["--changed-file","docs/example.md","--signal","validation_failure","--signal","validation_failure"]);
  assert.equal(result.status,0,result.stderr);const plan=JSON.parse(result.stdout);assert.equal(plan.schemaVersion,3);assert.equal(plan.delegated,"changed-files");assert.deepEqual(plan.options.changedFiles,["docs/example.md"]);assert.deepEqual(plan.options.signals,["validation_failure"]);
});
test("complete explicit changed files are forwarded to Git discovery, never silently discarded",t=>{
  const f=fixture(t);const result=f.run(["--base","master","--task-context","task.json","--changed-file","docs/example.md"]);
  assert.equal(result.status,0,result.stderr);assert.deepEqual(JSON.parse(result.stdout).options.changedFiles,["docs/example.md"]);
});
test("RWB ownership rejects feature development on Linux or Windows and mismatched adaptation host",async t=>{
  const f=fixture(t);const entry=await import(pathToFileURL(f.script));
  assert.throws(()=>entry.validateProjectTaskContext({...f.task,hostPlatform:"linux",taskKind:"feature-development"},"linux"),/macos/);
  assert.throws(()=>entry.validateProjectTaskContext({...f.task,hostPlatform:"windows",taskKind:"feature-development"},"windows"),/macos/);
  assert.throws(()=>entry.validateProjectTaskContext({...f.task,hostPlatform:"windows",taskKind:"platform-adaptation"},"macos"),/actual host/);
  assert.equal(entry.validateProjectTaskContext({...f.task,hostPlatform:"linux",taskKind:"platform-adaptation"},"linux").hostPlatform,"linux");
});
test("task context without base and duplicate singular options fail explicitly",t=>{
  const f=fixture(t);
  for(const args of [["--task-context","task.json","--changed-file","docs/x.md"],["--base","master","--base","master"],["--base","master","--task-context","task.json","--task-context","task.json"]])assert.notEqual(f.run(args).status,0);
});
test("unsafe context paths and symlinks fail closed",t=>{
  const f=fixture(t);fs.symlinkSync(path.join(f.root,"task.json"),path.join(f.root,"alias.json"));
  for(const file of ["../task.json","alias.json"])assert.notEqual(f.run(["--base","master","--task-context",file]).status,0);
});
test("an older runtime cannot silently discard explicit platform task context",t=>{
  const f=fixture(t);const file=path.join(f.root,".agents/runtime/leon-engineering/lib/verification/index.mjs");
  fs.writeFileSync(file,fs.readFileSync(file,"utf8").replace("schemaVersion:options.task?4:3","schemaVersion:3"));
  const result=f.run(["--base","master","--task-context","task.json"]);assert.notEqual(result.status,0);assert.equal(JSON.parse(result.stderr).error.code,"RUNTIME_ERROR");
});

function managedFixture(t) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),"rwb-managed-task-entry-"));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  const host={darwin:"macos",win32:"windows",linux:"linux"}[process.platform],other=host==="macos"?"windows":"macos";
  fs.mkdirSync(path.join(root,"scripts"));fs.mkdirSync(path.join(root,".agents/runtime"),{recursive:true});fs.mkdirSync(path.join(root,"docs"));
  for(const file of ["plan_verification.mjs","validate_verification_receipt.mjs"])fs.copyFileSync(new URL(`../../scripts/${file}`,import.meta.url),path.join(root,"scripts",file));
  const installed=new URL("../../.agents/runtime/leon-engineering/",import.meta.url);
  fs.cpSync(installed,path.join(root,".agents/runtime/leon-engineering"),{recursive:true});
  const manifest=JSON.parse(fs.readFileSync(new URL("manifest.json",installed)));
  for(const [file,digest] of Object.entries(manifest.files)) {
    assert.equal(createHash("sha256").update(fs.readFileSync(path.join(root,".agents/runtime/leon-engineering",file))).digest("hex"),digest,`copied installed runtime drift: ${file}`);
  }
  const item=(lane,platforms,value)=>({level:"L1",lane,gate:"merge",platforms,value});
  const selection={risk:"local-only",minimumLevel:"L1",reason:"fixture_documentation",impact:["documentation"],coupling:"low",platforms:["linux","macos","windows"].filter(platform=>[host,other].includes(platform)),tests:["fixture-local"],documentation:[],ci:["fixture-host","fixture-other"],realMachine:[]};
  const policy={schemaVersion:3,riskOrder:["docs-only","local-only","full-delivery"],levelOrder:["L0","L1","L2","L3","L4"],platformOrder:["generic","linux","macos","windows","cross-platform","real-machine-required"],statusOrder:["PASS","FAIL","SKIPPED","NOT_REQUIRED","NOT_RUN","BLOCKED","MANUAL_REQUIRED"],escalation:{highCouplingImpactThreshold:2,targetLevel:"L3"},catalogs:{tests:{"fixture-local":item("local",["generic"],"fixture only; never executed")},documentation:{},ci:{"fixture-host":item("ci",[host],".github/workflows/fixture-host.yml"),"fixture-other":item("ci",[other],".github/workflows/fixture-other.yml")},realMachine:{}},rules:[{id:"fixture-docs",...selection,match:{files:[],prefixes:["docs/"],segments:[],suffixes:[]}}],fallback:{...selection,risk:"full-delivery",minimumLevel:"L4",coupling:"high",reason:"unknown_path",impact:["unknown-boundary"]}};
  fs.writeFileSync(path.join(root,".agents/verification-policy.json"),JSON.stringify(policy));fs.writeFileSync(path.join(root,"docs/example.md"),"base\n");fs.writeFileSync(path.join(root,"evidence.json"),JSON.stringify({fixture:true,nativeValidation:false}));
  const git=args=>execFileSync("git",["-C",root,...args],{encoding:"utf8"}).trim();git(["init","-q"]);git(["config","user.email","fixture@example.invalid"]);git(["config","user.name","Fixture"]);git(["add","."]);git(["commit","-qm","fixture base"]);const base=git(["rev-parse","HEAD"]);
  fs.writeFileSync(path.join(root,"docs/example.md"),"candidate\n");git(["add","."]);git(["commit","-qm","fixture candidate"]);const head=git(["rev-parse","HEAD"]);
  const task={hostPlatform:host,taskKind:host==="macos"?"feature-development":"platform-adaptation",objective:"Synthetic managed-runtime integration",acceptanceScope:"Fixture validator only; no native acceptance",candidateCommit:head,candidateBaseCommit:base,supplementalGateIds:[]};
  fs.writeFileSync(path.join(root,".git/task.json"),JSON.stringify(task));
  const run=args=>spawnSync(process.execPath,[path.join(root,"scripts/plan_verification.mjs"),"--project",root,"--base",base,"--task-context",".git/task.json",...args],{encoding:"utf8"});
  return {root,host,other,manifest,task,git,run};
}

test("formally installed runtime supports real Git binding and synthetic receipt3 host/aggregate separation",t=>{
  const f=managedFixture(t),before=f.git(["status","--porcelain"]),result=f.run([]);assert.equal(result.status,0,result.stderr);const p=JSON.parse(result.stdout);
  assert.equal(p.schemaVersion,4);assert.equal(p.binding.frameworkCommit,f.manifest.sourceCommit);assert.equal(p.binding.headCommit,f.task.candidateCommit);assert.deepEqual(p.changedFiles,["docs/example.md"]);assert.equal(f.git(["status","--porcelain"]),before);
  const receipt={schemaVersion:3,binding:p.binding,task:p.task,changeSummary:p.changeSummary,changedFiles:p.changedFiles,plannedLevel:p.requiredLevel,actualLevel:p.requiredLevel,components:p.components,platforms:p.platforms,impact:p.impact,executed:p.local.map(gate=>({id:gate.id,level:gate.level,status:"PASS",durationSeconds:0,source:"runner",runnerPlatform:f.host,evidence:"evidence.json"})),external:p.ci.map(gate=>gate.id==="fixture-host"?{id:gate.id,status:"PASS",source:"ci",evidence:"evidence.json",runnerPlatform:f.host,runId:"fixture-run",workflow:gate.value,candidateCommit:f.task.candidateCommit,checkoutCommit:f.task.candidateCommit,expectedCheckoutCommit:f.task.candidateCommit,checkoutKind:"candidate-head"}:{id:gate.id,status:"NOT_RUN",source:"ci",evidence:"evidence.json"}),realMachine:[],result:"PASS",mergeReady:false,releaseReady:false,hostAcceptance:"PASS",aggregateAcceptance:"NOT_READY",platformHandoffs:[{platform:f.other,status:"NOT_RUN",gateIds:["fixture-other"]}],uncoveredRisks:["external_gate_not_run:fixture-other"],escalation:{required:false,targetLevel:null,reasons:[]}};
  const records=path.join(f.root,".git/leon-engineering/verification");fs.mkdirSync(records,{recursive:true});const planFile=path.join(records,"plan.json"),receiptFile=path.join(records,"receipt.json");fs.writeFileSync(planFile,JSON.stringify(p));fs.writeFileSync(receiptFile,JSON.stringify(receipt));
  const validated=spawnSync(process.execPath,[path.join(f.root,"scripts/validate_verification_receipt.mjs"),"--project",f.root,"--plan",planFile,"--receipt",receiptFile],{encoding:"utf8"});assert.equal(validated.status,0,validated.stderr);const status=JSON.parse(validated.stdout);assert.equal(status.hostAcceptance,"PASS");assert.equal(status.aggregateAcceptance,"NOT_READY");assert.equal(status.releaseReady,false);
});
test("managed Git entry discovers uncommitted paths and refuses a truncated explicit changed set",t=>{
  const f=managedFixture(t);fs.writeFileSync(path.join(f.root,"docs/uncommitted.md"),"untracked\n");const discovered=f.run([]);assert.equal(discovered.status,0,discovered.stderr);const p=JSON.parse(discovered.stdout);assert.ok(p.changeSet.entries.some(entry=>entry.path==="docs/uncommitted.md" && entry.origin==="untracked"));assert.notEqual(f.run(["--changed-file","docs/example.md"]).status,0);
});
