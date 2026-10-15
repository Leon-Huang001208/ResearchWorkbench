import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeReport,periodicReportRenderer} from '../src/periodic-report.ts';
import {sha256} from '../src/material.ts';

test('report adapter binds input and exact bounded bytes without accepting unknown state',()=>{
  const data=Buffer.from('synthetic report response'),inputHash='a'.repeat(64);
  const valid={protocol:'rwb-hot-report/v1',state:'completed',inputHash,format:'docx',bytes:data.length,sha256:sha256(data),data:data.toString('base64')};
  assert.deepEqual(decodeReport(valid,inputHash),data);
  for(const bad of [{...valid,inputHash:'b'.repeat(64)},{...valid,state:'unknown'},{...valid,sha256:'0'.repeat(64)},
    {...valid,bytes:5242881},{...valid,data:valid.data+'!'},{...valid,format:'md'}])assert.throws(()=>decodeReport(bad,inputHash),/hot_periodic_report_invalid/);
  assert.throws(()=>periodicReportRenderer('python'),/hot_periodic_report_unavailable/);
});

test('aborted one-shot admission never creates a subprocess',async()=>{
  const abort=new AbortController();abort.abort();
  await assert.rejects(periodicReportRenderer('/absent/should-not-start')({},abort.signal),{name:'AbortError'});
});
