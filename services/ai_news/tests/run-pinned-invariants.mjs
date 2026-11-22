#!/usr/bin/env node
// Opt-in PostgreSQL acceptance runner. Creates and drops only a new uniquely owned *_test DB.
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { randomUUID,createHash } from 'node:crypto';
import { mkdirSync,openSync,closeSync,readFileSync,writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { loadConfig,environment,verifyOrigin } from '../runtime.mjs';
const [flag,bootstrap,...rest]=process.argv.slice(2);
const reportsOnly=rest.length===1&&rest[0]==='--reports-only';
if(flag!=='--config'||!bootstrap||(rest.length&&!reportsOnly))throw new Error('usage_config_required');
const root=path.resolve(import.meta.dirname,'..'),vendor=path.join(root,'vendor/aihot');
const c=loadConfig(bootstrap),base=environment(c);verifyOrigin();
const database=`rwb_ai_news_inv_${randomUUID().replaceAll('-','').slice(0,12)}_test`;
const url=new URL(base.DATABASE_URL);url.pathname='/postgres';
const postgres=(await import(pathToFileURL(path.join(vendor,'node_modules/postgres/src/index.js')).href)).default;
const admin=postgres(url.href,{max:1,onnotice:()=>{}});
const logs=path.join(root,'logs');mkdirSync(logs,{recursive:true});
const log=path.join(logs,reportsOnly?'pinned-pg-editions.log':'pinned-pg-invariants.log'),fd=openSync(log,'w',0o600);
const tests=reportsOnly?['tests/reports.test.ts','tests/report-recovery.test.ts']:['tests/materials.test.ts','tests/processing-recovery.test.ts','tests/events.test.ts','tests/publication.test.ts','tests/publication-date-correction.test.ts','tests/ingest.test.ts','tests/dajiala.test.ts','tests/x-article.test.ts','tests/receipts.test.ts'];
let created=false,code=1;
try{
  await admin`CREATE DATABASE ${admin(database)}`;created=true;url.pathname='/'+database;
  const env={PATH:base.PATH,HOME:base.HOME,DATABASE_URL:url.href,AIHOT_CREDENTIALS_DIR:'/nonexistent-rwb-test-credentials',NODE_OPTIONS:`--import=${path.join(import.meta.dirname,'deny-external.mjs')}`,MODEL_CALLS_ENABLED:'true',COLLECT_ENABLED:'true',FEISHU_CONTENT_PUSH_ENABLED:'false',FEISHU_INTERNAL_ENABLED:'false',INDEXNOW_SUBMIT_ENABLED:'false',LOG_LEVEL:'error'};
  code=await new Promise((resolve,reject)=>{
    const child=spawn(process.execPath,['--test-global-setup=tests/databases.ts','--import','./tests/databases.ts','--test','--test-concurrency=2','--test-timeout=120000','--test-skip-pattern=an unknown outcome is released automatically once',...tests],{cwd:vendor,env,stdio:['ignore',fd,fd]});
    child.on('error',reject);child.on('exit',value=>resolve(value??1));
  });
}finally{
  closeSync(fd);
  // This exact name was generated in memory for this run; do not drop any other test/template DB.
  if(created)await admin`DROP DATABASE ${admin(database)}`;
  await admin.end();
}
const bytes=readFileSync(log),lines=bytes.toString().trim().split('\n');
const summary={schemaVersion:1,pin:'26d436497d9ddba9e7dd88eed255cfe0105ce368',exitCode:code,networkPolicy:'real sockets loopback only; external DNS denied; synthetic provider keys only',database:'fresh uniquely named *_test created and dropped; original host DB untouched',tests,excluded:reportsOnly?[]:['upstream auto-release-once expectation intentionally conflicts with RWB manual reconciliation policy; patched zero-call unknown proof is separate'],summary:lines.filter(line=>/^ℹ (tests|pass|fail|skipped|duration_ms)/.test(line)).slice(-8),logSha256:createHash('sha256').update(bytes).digest('hex')};
writeFileSync(path.join(logs,reportsOnly?'pinned-pg-editions.json':'pinned-pg-invariants.json'),JSON.stringify(summary,null,2)+'\n',{mode:0o600});
console.log(JSON.stringify(summary));process.exitCode=code;
