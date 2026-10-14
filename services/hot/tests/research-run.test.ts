import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateRunTransition} from '../src/research-run.ts';

test('research lifecycle never turns unknown execution back into automatic submission',()=>{
  for(const [from,to] of [['prepared','session_creating'],['session_creating','session_outcome_unknown'],
    ['session_outcome_unknown','session_ready'],['session_ready','snapshot_ready'],
    ['snapshot_ready','execution_starting'],['execution_starting','execution_outcome_unknown'],
    ['execution_outcome_unknown','running'],['running','completed']])assert.doesNotThrow(()=>validateRunTransition(from,to));
  for(const [from,to] of [['prepared','running'],['execution_outcome_unknown','execution_starting'],
    ['completed','execution_starting'],['abandoned','prepared']])assert.throws(()=>validateRunTransition(from,to),/hot_research_transition_invalid/);
});
