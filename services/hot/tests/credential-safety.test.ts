import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeModelText} from '../src/credential-safety.mjs';
test('escaped JSON keys and values cannot reflect a credential',()=>{
  const secret='synthetic-private-key',secrets=new Set([secret]);
  const escaped=[...secret].map(char=>'\\u'+char.charCodeAt(0).toString(16).padStart(4,'0')).join('');
  assert.equal(safeModelText('{"value":"'+escaped+'"}',secrets),false);
  assert.equal(safeModelText('{"'+escaped+'":"ok"}',secrets),false);
  assert.equal(safeModelText(JSON.stringify({summary:'safe public facts'}),secrets),true);
});
