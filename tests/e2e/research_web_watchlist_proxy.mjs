/** Inert owned proxy sink. Seatbelt must reject outbound even to this local fixture. */
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createServer } from 'node:http';
import { mkdir, mkdtemp, readFile, writeFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'logs/watchlist-quality-proxy'); await mkdir(output, { recursive: true });
const root = await mkdtemp('/tmp/rwb-watchlist-quality-proxy-'), info = await stat(root);
await writeFile(path.join(output,'root-identity.json'),JSON.stringify({root,uid:process.getuid(),pid:process.pid,dev:info.dev,inode:info.ino,task:'seek-watchlist-import-20261028-8eb1123d'}));
let connections = 0, requests = 0;
const sink = createServer((_request, response) => { requests++; response.writeHead(502); response.end('inert fixture: no forwarding'); });
sink.on('connection', () => { connections++; });
await new Promise(resolve => sink.listen(0, '127.0.0.1', resolve));
const address = sink.address(); assert.ok(address && typeof address === 'object'); assert.notEqual(address.port,29758);
const proxy = `http://127.0.0.1:${address.port}`;
const cleanEnvironment = { ...process.env };
for (const key of Object.keys(cleanEnvironment)) if (['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','FTP_PROXY','NO_PROXY','RESEARCH_CREDENTIAL_HOME'].includes(key.toUpperCase())) delete cleanEnvironment[key];
const challengeKeys = ['HTTP_PROXY','http_proxy','HtTpS_pRoXy','https_proxy','ALL_PROXY','all_proxy','FTP_PROXY','ftp_proxy','NO_PROXY','no_proxy'];
const challengedEnvironment = { ...cleanEnvironment, RESEARCH_CREDENTIAL_HOME: path.join(root,'must-not-be-inherited') };
for (const key of challengeKeys) challengedEnvironment[key] = key.toUpperCase()==='NO_PROXY' ? '' : proxy;
const profile = path.join(project,'tests/e2e/watchlist-loopback.sb');
const run = (program,args,env) => new Promise((resolve,reject) => {
  const process = spawn(program,args,{cwd:project,env,stdio:['ignore','pipe','pipe']}); let stdout='',stderr='';
  process.stdout.on('data',data=>{stdout+=data;}); process.stderr.on('data',data=>{stderr+=data;});process.on('error',reject);process.on('exit',code=>resolve({code,stdout,stderr}));
});
const result = { profile_sha256:createHash('sha256').update(await readFile(profile)).digest('hex'), proxy_sink:proxy, credentials_home:'owned nonexistent sentinel', inherited_keys_challenged:[...challengeKeys,'RESEARCH_CREDENTIAL_HOME'], runs:[] };
try {
  const native = await run('/usr/bin/sandbox-exec',['-f',profile,'/usr/bin/curl','-v','--connect-timeout','1','--max-time','1','-o','/dev/null','http://198.51.100.1:9/'],challengedEnvironment);
  await writeFile(path.join(output,'native.stderr'),native.stderr);
  assert.equal(native.code,7); assert.match(native.stderr,/Operation not permitted/); assert.match(native.stderr,/127\.0\.0\.1/);
  assert.equal(connections,0); assert.equal(requests,0); result.native_proxy_negative={code:native.code,kernel_denied:true,sink_connections:connections,sink_requests:requests};
  if (process.env.RWB_WATCHLIST_RUN_BROWSERS==='1') {
    for (const file of ['tests/e2e/research_web_watchlist_import.mjs','tests/e2e/research_web_watchlist_import_lists.mjs']) {
      const child = await run(process.execPath,[file],{...challengedEnvironment,RWB_WATCHLIST_E2E_EPOCH:'quality-inbound'});
      await writeFile(path.join(output,path.basename(file)+'.log'),child.stdout+child.stderr);
      assert.equal(child.code,0,child.stdout+child.stderr); result.runs.push({file,code:child.code});
    }
  }
  assert.equal(connections,0,'no Host or browser may contact the inert proxy'); assert.equal(requests,0);
  result.status='PASS'; result.sink_connections=connections; result.sink_requests=requests; result.external_forwarding=0;
} catch (error) { result.status='FAIL';result.error=error.stack;process.exitCode=1; }
finally { await new Promise(resolve=>sink.close(resolve)); await writeFile(path.join(output,'result.json'),JSON.stringify(result,null,2)); }
console.log(JSON.stringify(result));
