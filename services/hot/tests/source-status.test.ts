import {test} from 'node:test';import assert from 'node:assert/strict';import{sourceEligibility}from'../src/source-status.ts';
const catalog=[{id:'fed',operator:'Federal Reserve',url:'https://www.federalreserve.gov/feeds/press_all.xml',channelHint:'macro',official:true}];
test('eligibility distinguishes enabled frozen data from actual scheduled source, with fail-closed permission',()=>{
 const row={id:'fed',operator:'Federal Reserve',enabled:true,adapter:'frozen_acceptance_subset',catalog_id:null};
 assert.equal(sourceEligibility(row,catalog,true).collection_state,'awaiting_catalog');
 assert.equal(sourceEligibility(row,catalog,false).catalog_activation_allowed,false);
 assert.equal(sourceEligibility({...row,operator:'different'},catalog,true).collection_state,'catalog_mismatch');
 assert.equal(sourceEligibility({...row,adapter:'public_feed',catalog_id:'fed'},catalog,true).collection_state,'scheduled');
 assert.equal(sourceEligibility({...row,adapter:'public_feed',catalog_id:'fed',enabled:false},catalog,true).collection_state,'paused');
});
