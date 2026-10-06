/** Loaded before the pinned CLI, inside the same owned Runtime process. */
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { StringDecoder } from 'node:string_decoder';
import { createAuthOutputSink, writeBootstrapAuth } from './auth-output.mjs';

const authFile = process.env.RESEARCH_RUNTIME_AUTH;
const home = process.env.DSH_HOME;
const source = process.env.RESEARCH_DSH_SOURCE;
const state = process.env.RWB_RUNTIME_STATE || resolve(home || '/', '..');
const port = Number(process.env.RESEARCH_RUNTIME_PORT);
if (!authFile || !home || !source || !Number.isInteger(port) || port < 1 || port > 65535 ||
    authFile !== resolve(state, 'auth.json')) throw Error('runtime_auth_handoff_binding_invalid');
const metadata = {
  authority: `127.0.0.1:${port}`, cwd: process.cwd(), pid: process.pid,
  source_commit: 'c919b2a460753859665db3f60143d525fb9140cf',
  version: JSON.parse(readFileSync(join(source, 'package.json'), 'utf8')).version,
};
for (const stream of [process.stdout, process.stderr]) {
  const original = stream.write.bind(stream);
  const decoder = new StringDecoder('utf8');
  const sink = createAuthOutputSink(port, token => writeBootstrapAuth(authFile, metadata, token), text => original(text));
  stream.write = (chunk, encoding, callback) => {
    try { sink(typeof chunk === 'string' ? chunk : decoder.write(chunk)); }
    catch { throw Error('runtime_auth_handoff_failed'); }
    const done = typeof encoding === 'function' ? encoding : callback;
    if (typeof done === 'function') queueMicrotask(done);
    return true;
  };
}
