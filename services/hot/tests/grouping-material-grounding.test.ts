import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assertMaterialAnchoredDecision,groupingSourceReferences,type GroupingPacket} from '../src/processing.ts';

const packet={material:{title:'Bank resolution plan review',excerpt:'Credit Suisse and BNP Paribas resolution deficiencies.'},candidates:[]} as unknown as GroupingPacket;
test('an unrelated candidate comparison cannot publish a new branded event',()=>{
 assert.throws(()=>assertMaterialAnchoredDecision({parts:[{relation:'different_event',candidateId:null,title:'OpenAI AI Jam Session',reason:'This candidate is unrelated to the bank material.'}]},packet),/hot_grouping_output_unreported_entity/);
});
test('material brand matching tolerates spaces and case without importing candidate facts',()=>{
 assert.doesNotThrow(()=>assertMaterialAnchoredDecision({parts:[{relation:'different_event',candidateId:null,title:'CreditSuisse resolution deficiencies',reason:'The material describes this bank.'}]},packet));
 assert.doesNotThrow(()=>assertMaterialAnchoredDecision({parts:[{relation:'different_event',candidateId:null,title:'OpenAI launch',reason:'Reported.'}]},{...packet,material:{...packet.material,excerpt:'Open AI launch.'}}));
});
test('literal source citations are normalized without accepting credentials or unbounded references',()=>{
 assert.deepEqual(groupingSourceReferences('Source: https://www.federalreserve.gov/a.htm?utm_source=x。 https://federalreserve.gov/a.htm https://user:secret@example.com/'),['url:https://federalreserve.gov/a.htm']);
 assert.equal(groupingSourceReferences(Array.from({length:30},(_,i)=>'https://example.com/'+i).join(' ')).length,20);
});
