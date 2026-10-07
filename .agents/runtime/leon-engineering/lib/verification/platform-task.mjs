import {fail} from './errors.mjs';
import {execFileSync} from 'node:child_process';
import {LEVEL_ORDER, PLATFORM_ORDER, STATUS_ORDER} from './policy.mjs';

const NATIVE=['macos','linux','windows'];
const SHA=/^[a-f0-9]{40}$/;
const TASK_KEYS=['hostPlatform','taskKind','objective','acceptanceScope','candidateCommit','candidateBaseCommit','supplementalGateIds'];
function exact(value,keys,label) {
  if(!value || typeof value!=='object' || Array.isArray(value) || Object.keys(value).length!==keys.length || Object.keys(value).some(key=>!keys.includes(key))) fail('RECEIPT_ERROR',`invalid ${label} keys`);
}
export function normalizePlatformTask(task) {
  const value={...task,supplementalGateIds:task?.supplementalGateIds ?? []};
  exact(value,TASK_KEYS,'platform task');
  if(!NATIVE.includes(value.hostPlatform) || !['feature-development','platform-adaptation'].includes(value.taskKind) || !SHA.test(value.candidateCommit) || !SHA.test(value.candidateBaseCommit) || ['objective','acceptanceScope'].some(key=>typeof value[key]!=='string' || !value[key].trim()) || !Array.isArray(value.supplementalGateIds) || value.supplementalGateIds.some(id=>typeof id!=='string' || !id) || new Set(value.supplementalGateIds).size!==value.supplementalGateIds.length) fail('ARGUMENT_ERROR','invalid platform task context');
  return Object.fromEntries(TASK_KEYS.map(key=>[key,value[key]]));
}

export function applyPlatformTask(plan,policy,input) {
  if(plan.schemaVersion!==3) fail('PLAN_ERROR','platform tasks require policy v3');
  const task=normalizePlatformTask(input);
  const result={...plan,schemaVersion:4,task};
  for(const category of ['tests','documentation','ci','realMachine']) result[category]=[...plan[category]];
  for(const id of task.supplementalGateIds) {
    const matches=['tests','documentation','ci','realMachine'].filter(category=>policy.catalogs[category].has(id));
    if(matches.length!==1) fail('PLAN_ERROR','supplemental gate must identify one registered validation');
    const category=matches[0],entry=policy.catalogs[category].get(id);
    if(!result[category].some(item=>item.id===id)) result[category].push({id,level:entry.level,lane:entry.lane,gate:entry.gate,platforms:[...entry.platforms],category,value:entry.value});
  }
  const values=[...result.tests,...result.documentation,...result.ci,...result.realMachine];
  result.requiredLevel=LEVEL_ORDER[Math.max(LEVEL_ORDER.indexOf(plan.requiredLevel),...values.map(item=>LEVEL_ORDER.indexOf(item.level)))];
  result.platforms=PLATFORM_ORDER.filter(platform=>plan.platforms.includes(platform) || values.some(item=>item.platforms.includes(platform)));
  result.validationsByLevel=Object.fromEntries(LEVEL_ORDER.map(level=>[level,values.filter(item=>item.level===level)]));
  result.local=values.filter(item=>item.lane==='local');
  result.receiptTemplate={plannedLevel:result.requiredLevel,changedFiles:result.changedFiles,requiredValidationIds:result.local.map(item=>item.id),externalGateIds:result.ci.map(item=>item.id),releaseGateIds:result.realMachine.map(item=>item.id)};
  return result;
}

const baseKeys=['schemaVersion','binding','changeSummary','changedFiles','plannedLevel','actualLevel','components','platforms','impact','executed','external','realMachine','result','mergeReady','releaseReady','uncoveredRisks','escalation','task','hostAcceptance','platformHandoffs','aggregateAcceptance'];
function nativeTargets(gate,host) {
  const targets=gate.platforms.filter(platform=>NATIVE.includes(platform));
  return targets.length?targets:[host];
}
function status(items) {return items.some(item=>item.status==='FAIL')?'FAIL':items.every(item=>item.status==='PASS')?'PASS':items.every(item=>item.status==='NOT_RUN')?'NOT_RUN':'BLOCKED';}
function platformEvidence(gate,item,platform) {
  // A local result applies only to the native runner that actually produced it.
  return gate.lane==='local' && item.runnerPlatform!==platform?{status:'NOT_RUN'}:item;
}
function verifyMergePreview(projectRoot,checkout,task) {
  if(typeof projectRoot!=='string' || !SHA.test(checkout)) fail('RECEIPT_ERROR','CI merge preview cannot be verified locally');
  let contents;
  try {
    const type=execFileSync('git',['-C',projectRoot,'cat-file','-t',checkout],{encoding:'utf8',maxBuffer:1024,stdio:['ignore','pipe','ignore']}).trim();
    if(type!=='commit') fail('RECEIPT_ERROR','CI merge preview object must be a commit');
    contents=execFileSync('git',['-C',projectRoot,'cat-file','-p',checkout],{encoding:'utf8',maxBuffer:1024*1024,stdio:['ignore','pipe','ignore']});
  }
  catch {fail('RECEIPT_ERROR','CI merge preview commit is unavailable locally');}
  const header=contents.split('\n\n')[0];
  const parents=[...header.matchAll(/^parent ([a-f0-9]{40})$/gm)].map(match=>match[1]);
  if(!/^tree [a-f0-9]{40}$/m.test(header) || JSON.stringify(parents)!==JSON.stringify([task.candidateBaseCommit,task.candidateCommit])) fail('RECEIPT_ERROR','CI merge preview actual parents do not match base and candidate');
}

export function validatePlatformReceipt(receipt,plan,checkEvidence,projectRoot) {
  if(!plan.binding || !plan.changeSet) fail('RECEIPT_ERROR','platform acceptance requires a Git-bound plan');
  exact(receipt,plan.binding?baseKeys:baseKeys.filter(key=>key!=='binding'),'platform receipt');
  if(receipt.schemaVersion!==3) fail('RECEIPT_ERROR','platform plan requires receipt v3');
  for(const key of ['task','changeSummary','changedFiles','components','platforms','impact',...(plan.binding?['binding']:[])]) if(JSON.stringify(receipt[key])!==JSON.stringify(plan[key])) fail('RECEIPT_ERROR',`receipt ${key} does not match plan`);
  if(receipt.plannedLevel!==plan.requiredLevel || !LEVEL_ORDER.includes(receipt.actualLevel) || LEVEL_ORDER.indexOf(receipt.actualLevel)<LEVEL_ORDER.indexOf(plan.requiredLevel)) fail('RECEIPT_ERROR','invalid verification level');
  if(!Array.isArray(receipt.uncoveredRisks) || receipt.uncoveredRisks.some(item=>typeof item!=='string') || new Set(receipt.uncoveredRisks).size!==receipt.uncoveredRisks.length) fail('RECEIPT_ERROR','invalid uncovered risks');
  const gates=[...plan.tests,...plan.documentation,...plan.ci,...plan.realMachine];
  const evidence=new Map();
  for(const [field,lane,source] of [['executed','local','runner'],['external','ci','ci'],['realMachine','real-machine','manual']]) {
    if(!Array.isArray(receipt[field])) fail('RECEIPT_ERROR','invalid evidence collection');
    const expected=gates.filter(gate=>gate.lane===lane);
    if(receipt[field].length!==expected.length) fail('RECEIPT_ERROR','missing validation evidence');
    for(const item of receipt[field]) {
      const gate=expected.find(gate=>gate.id===item.id);
      if(!gate || evidence.has(item.id) || item.source!==source || !STATUS_ORDER.includes(item.status) || item.status==='NOT_REQUIRED') fail('RECEIPT_ERROR','invalid validation evidence');
      let keys=['id','status','source','evidence'];
      if(lane==='local') {
        keys.push('level','durationSeconds','runnerPlatform');
        if(item.level!==gate.level || !Number.isFinite(item.durationSeconds) || item.durationSeconds<0 || !NATIVE.includes(item.runnerPlatform)) fail('RECEIPT_ERROR','invalid local runner');
      }
      if(item.status==='PASS') {
        const targets=nativeTargets(gate,plan.task.hostPlatform);
        if(lane==='ci') {
          if(!plan.binding || plan.changeSet.entries.some(entry=>entry.origin!=='committed')) fail('RECEIPT_ERROR','CI cannot certify an unbound or uncommitted candidate');
          keys.push('runnerPlatform','runId','workflow','candidateCommit','checkoutCommit','expectedCheckoutCommit','checkoutKind');
          if(!NATIVE.includes(item.runnerPlatform) || targets.length!==1 || item.runnerPlatform!==targets[0] || typeof item.runId!=='string' || !item.runId || item.workflow!==gate.value || item.candidateCommit!==plan.task.candidateCommit || !SHA.test(item.checkoutCommit) || item.checkoutCommit!==item.expectedCheckoutCommit || !['candidate-head','merge-preview','mainline'].includes(item.checkoutKind)) fail('RECEIPT_ERROR','invalid CI runner or checkout identity');
          if(item.checkoutKind==='merge-preview') {
            keys.push('headCommit','baseCommit');
            if(item.headCommit!==plan.task.candidateCommit || item.baseCommit!==plan.task.candidateBaseCommit) fail('RECEIPT_ERROR','CI merge preview is unrelated to candidate');
            verifyMergePreview(projectRoot,item.checkoutCommit,plan.task);
          } else if(item.checkoutCommit!==plan.task.candidateCommit) fail('RECEIPT_ERROR','CI checkout is not the candidate');
        } else if(lane==='real-machine') {
          keys.push('machinePlatform');
          if(targets.length!==1 || item.machinePlatform!==targets[0]) fail('RECEIPT_ERROR','wrong native machine');
        } else if(item.runnerPlatform!==plan.task.hostPlatform || (gate.platforms.some(platform=>NATIVE.includes(platform)) && !gate.platforms.includes(item.runnerPlatform))) fail('RECEIPT_ERROR','local validation belongs to another host');
      }
      exact(item,keys,'validation evidence');checkEvidence(item.evidence);evidence.set(item.id,item);
      if(item.status==='NOT_RUN' && lane!=='local' && !receipt.uncoveredRisks.includes(`${lane==='ci'?'external_gate_not_run':'real_machine_not_run'}:${item.id}`)) fail('RECEIPT_ERROR','unrun gate must remain an uncovered risk');
      if(item.status==='MANUAL_REQUIRED' && lane==='real-machine' && !receipt.uncoveredRisks.includes(`real_machine_manual_required:${item.id}`)) fail('RECEIPT_ERROR','manual gate must remain an uncovered risk');
    }
  }
  const hostGates=gates.filter(gate=>nativeTargets(gate,plan.task.hostPlatform).includes(plan.task.hostPlatform));
  const hostItems=hostGates.map(gate=>platformEvidence(gate,evidence.get(gate.id),plan.task.hostPlatform));
  const hostAcceptance=hostItems.length?status(hostItems):'NOT_RUN';
  // Cross-platform impact has unknown native coverage unless each target has its own gates.
  // Generic validation alone remains scoped to the current host.
  const handoffs=NATIVE.filter(platform=>platform!==plan.task.hostPlatform && (plan.platforms.includes('cross-platform') || plan.platforms.includes(platform) || gates.some(gate=>nativeTargets(gate,plan.task.hostPlatform).includes(platform)))).map(platform=>{
    const platformGates=gates.filter(gate=>nativeTargets(gate,plan.task.hostPlatform).includes(platform));
    return {platform,status:platformGates.length?status(platformGates.map(gate=>platformEvidence(gate,evidence.get(gate.id),platform))):'NOT_RUN',gateIds:platformGates.map(gate=>gate.id)};
  });
  const mergeReady=gates.filter(gate=>gate.gate==='merge').every(gate=>evidence.get(gate.id).status==='PASS');
  const releaseReady=mergeReady && gates.every(gate=>evidence.get(gate.id).status==='PASS') && handoffs.every(handoff=>handoff.status==='PASS');
  const aggregateAcceptance=releaseReady?'READY':'NOT_READY';
  const result=hostAcceptance==='PASS'?'PASS':hostAcceptance==='FAIL'?'FAIL':'BLOCKED';
  if(receipt.hostAcceptance!==hostAcceptance || receipt.aggregateAcceptance!==aggregateAcceptance || receipt.mergeReady!==mergeReady || receipt.releaseReady!==releaseReady || receipt.result!==result || JSON.stringify(receipt.platformHandoffs)!==JSON.stringify(handoffs)) fail('RECEIPT_ERROR','platform acceptance is inconsistent with evidence');
  exact(receipt.escalation,['required','targetLevel','reasons'],'escalation');
  const minimumEscalation=Math.min(LEVEL_ORDER.indexOf(plan.requiredLevel)+1,LEVEL_ORDER.length-1);
  if(!Array.isArray(receipt.escalation.reasons) || receipt.escalation.reasons.some(reason=>typeof reason!=='string') || receipt.escalation.required!==(result==='FAIL') || (result==='FAIL'?LEVEL_ORDER.indexOf(receipt.escalation.targetLevel)<minimumEscalation:receipt.escalation.targetLevel!==null)) fail('RECEIPT_ERROR','invalid platform escalation');
  return {schemaVersion:3,valid:true,result,hostAcceptance,platformHandoffs:handoffs,aggregateAcceptance,mergeReady,releaseReady};
}
