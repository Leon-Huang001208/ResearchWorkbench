import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseEvidenceSelection,evidenceChunk} from '../src/research-evidence.ts';

const id='11111111-1111-4111-8111-111111111111';
test('research evidence requires an explicit immutable brief version and bounded unique selection',()=>{
  assert.deepEqual(parseEvidenceSelection({briefId:id,version:1,materialIds:[id]}),{briefId:id,version:1,materialIds:[id]});
  const invalid:Parameters<typeof parseEvidenceSelection>[0][]=[{briefId:id,materialIds:[id]},{briefId:id,version:0,materialIds:[id]},
    {briefId:id,version:1,materialIds:[]},{briefId:id,version:1,materialIds:[id,id]},
    {briefId:id,version:1,materialIds:[id],url:'https://example.com/'}];
  for(const params of invalid) {
    assert.throws(()=>parseEvidenceSelection(params),/hot_research_selection_invalid/);
  }
});
test('original chunks preserve every binary byte and cannot silently truncate or skip positions',()=>{
  const bytes=Buffer.from('原始资料🙂\u0000'.repeat(9000));
  const parts:Buffer[]=[];let offset=0;
  while(offset<bytes.length){
    const chunk=evidenceChunk(bytes,offset);
    assert.equal(chunk.offset,offset);assert.equal(chunk.totalBytes,bytes.length);
    const part=Buffer.from(chunk.dataBase64,'base64');assert.ok(part.length<=32768);
    parts.push(part);offset+=part.length;
    assert.equal(chunk.nextOffset,offset<bytes.length?offset:null);
  }
  assert.deepEqual(Buffer.concat(parts),bytes);
  for(const value of [-1,0.5,bytes.length+1])assert.throws(()=>evidenceChunk(bytes,value),/hot_research_offset_invalid/);
});
