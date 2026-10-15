import{test}from'node:test';import assert from'node:assert/strict';import{readFile}from'node:fs/promises';
import{evaluateCorpus}from'../scripts/evaluate-corpus.ts';
import{sha256}from'../src/material.ts';import{canonicalGroupingInput}from'../src/processing.ts';
const corpus=JSON.parse(await readFile(new URL('../evaluation/real-corpus-v1.json',import.meta.url),'utf8'));
test('real frozen corpus distinguishes receipt replay, rules and uncovered relationships without paid calls',()=>{
 const result=evaluateCorpus(corpus);assert.equal(result.state,'PASS_RETROSPECTIVE_REPLAY_WITH_EXPLICIT_GAPS');
 assert.equal(result.modelReceiptCases,3);assert.equal(result.rules.length,5);assert.equal(result.newModelCalls,0);assert.equal(result.independentAccuracy,null);
 assert.equal(result.unrunRelationships.length,4);assert.ok(result.rules.some(row=>row.id==='macro-account'&&row.insufficientContext));
 assert.equal(result.partitionScope,'primary_occurrences_only');assert.equal(result.storedReceiptContextDisjoint,false);assert.ok(result.candidateContextOverlap.some(row=>row.sampleId==='ai-embeddinggemma'));
});
test('event and material overlap, tampered receipt and score drift cannot yield a green evaluation',()=>{
 const overlap=structuredClone(corpus);overlap.samples.find((x:any)=>x.split==='development').eventGroups.push(overlap.samples.find((x:any)=>x.split==='holdout').eventGroups[0]);assert.throws(()=>evaluateCorpus(overlap),/evaluation_split_overlap/);
 const reused=structuredClone(corpus);const target=reused.samples.find((x:any)=>x.split==='holdout');target.material.material_id=reused.samples.find((x:any)=>x.split==='development').material.material_id;target.materialSnapshotHash=sha256(canonicalGroupingInput(target.material));assert.throws(()=>evaluateCorpus(reused),/evaluation_material_overlap/);
 const tampered=structuredClone(corpus);tampered.samples.find((x:any)=>x.receipt).receipt.response.text='{}';assert.throws(()=>evaluateCorpus(tampered),/evaluation_receipt_invalid/);
 const drift=structuredClone(corpus);drift.samples[0].expectedScores.ai.relevance=99;assert.equal(evaluateCorpus(drift).state,'FAIL');
 const reference=structuredClone(corpus);reference.referenceCases[3].split='development';reference.referenceCases[3].eventGroups=['unrelated-label'];assert.throws(()=>evaluateCorpus(reference),/evaluation_split_overlap/);
 const source=structuredClone(corpus);source.samples[0].material.operator='unverified operator';source.samples[0].materialSnapshotHash=sha256(canonicalGroupingInput(source.samples[0].material));assert.throws(()=>evaluateCorpus(source),/evaluation_source_invalid/);
 const material=structuredClone(corpus);material.samples[0].material.excerpt+=' modified';assert.throws(()=>evaluateCorpus(material),/evaluation_material_integrity_invalid/);
});
