/** DSH native research tool. No model-provided paths, environment, or executables. */
import { spawn } from 'node:child_process';
import { realpath, lstat } from 'node:fs/promises';
import { isAbsolute, join, resolve, dirname, basename } from 'node:path';

export const name = 'alphafoundry-research-tools';
export const inject = ['tools', 'sessions'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Validate immutable DSH lineage; a cold/missing ancestor fails closed. */
async function trustedDirectory(ctx, exec, config) {
  let session = exec.agent?.session;
  if (!session?.header?.cwd || !session.header.id) throw new Error('trusted agent session is required');
  const cwd = session.header.cwd;
  const root = await realpath(config.researchRoot);
  const expected = join(root, 'sessions', basename(cwd));
  if (!isAbsolute(cwd) || !UUID.test(basename(cwd)) || resolve(cwd) !== cwd || cwd !== expected || await realpath(cwd) !== cwd) {
    throw new Error('trusted session directory is outside the research root');
  }
  if ((await lstat(dirname(cwd))).isSymbolicLink()) throw new Error('trusted session parent must not be a symlink');
  const seen = new Set();
  while (session.header.parentSession !== undefined) {
    if (seen.size >= 16 || seen.has(session.header.id)) throw new Error('trusted session ancestry is invalid');
    seen.add(session.header.id);
    const parent = ctx.sessions?.get(session.header.parentSession);
    if (!parent || parent.header.cwd !== cwd) throw new Error('trusted child session does not share its ancestor workspace');
    session = parent;
  }
  return cwd;
}

/** Register a bounded, kernel-confined native tool without widening host tools. */
export function apply(ctx, config) {
  for (const key of ['python', 'runnerPath', 'researchRoot']) {
    if (typeof config?.[key] !== 'string' || !isAbsolute(config[key])) throw new Error(`research-tools requires absolute ${key}`);
  }
  const timeoutSeconds = config.timeoutSeconds ?? 15;
  const maxOutputBytes = config.maxOutputBytes ?? 65536;
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 60 || !Number.isSafeInteger(maxOutputBytes) || maxOutputBytes < 1 || maxOutputBytes > 1048576) {
    throw new Error('research-tools execution limits are invalid');
  }
  ctx.tools.register({
    name: 'af_run_script',
    description: 'Run Python in this research session. Read inputs/resources; write outputs/tmp. Network, host files, and subprocesses are unavailable.',
    parameters: { type: 'object', properties: { code: { type: 'string', description: 'Nonempty Python source, at most 65536 UTF-8 bytes; enforced before execution.' } }, required: ['code'], additionalProperties: false },
    output: {
      schema: { type: 'object', properties: { status: { type: 'string' }, stdout: { type: 'string' }, stderr: { type: 'string' }, exit_code: { oneOf: [{ type: 'integer' }, { type: 'null' }] }, error: { oneOf: [{ type: 'string' }, { type: 'null' }] } }, required: ['status', 'stdout', 'stderr', 'exit_code', 'error'], additionalProperties: false },
      render(_args, value) { return [{ type: 'text', text: JSON.stringify(value) }]; },
    },
    async execute(args, exec) {
      if (!args || Object.keys(args).length !== 1 || typeof args.code !== 'string' || !args.code.trim() || Buffer.byteLength(args.code) > 65536) throw new Error('research script accepts only bounded code');
      exec.signal.throwIfAborted();
      const cwd = await trustedDirectory(ctx, exec, config);
      exec.signal.throwIfAborted();
      ctx.logger.info('research_script_started');
      return await new Promise((resolveResult, reject) => {
        const child = spawn(config.python, ['-I', '-S', '-B', config.runnerPath, '--research-root', config.researchRoot, '--python', config.python, '--session', cwd, '--timeout', String(timeoutSeconds), '--max-output', String(maxOutputBytes)], {
          cwd, env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8', LC_ALL: 'en_US.UTF-8' }, stdio: ['pipe', 'pipe', 'pipe'],
        });
        const output = [];
        let bytes = 0;
        let stopReason;
        let forceStop;
        let settled = false;
        const stop = reason => {
          if (settled) return;
          stopReason ??= reason;
          child.kill('SIGTERM');
          forceStop ??= setTimeout(() => {
            child.kill('SIGKILL');
            cleanup();
            if (!settled) { settled = true; reject(new Error('research supervisor teardown could not be confirmed')); }
          }, 2000);
        };
        const onAbort = () => stop('research script cancelled');
        exec.signal.addEventListener('abort', onAbort, { once: true });
        const deadline = setTimeout(() => stop('research supervisor deadline exceeded'), (timeoutSeconds + 8) * 1000);
        const cleanup = () => { clearTimeout(deadline); clearTimeout(forceStop); exec.signal.removeEventListener('abort', onAbort); };
        child.stdout.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > maxOutputBytes * 6 + 8192) { stop('research supervisor output exceeded its cap'); return; }
          output.push(chunk);
        });
        child.stderr.on('data', () => {});
        child.stdin.on('error', () => stop('research supervisor rejected its input'));
        child.on('error', () => { cleanup(); settled = true; ctx.logger.error('research_script_spawn_failed'); reject(new Error('research supervisor could not start')); });
        child.on('close', code => {
          cleanup();
          if (settled) return;
          settled = true;
          if (stopReason || code !== 0) { ctx.logger.warn('research_script_supervisor_failed'); reject(new Error(stopReason ?? 'research supervisor failed')); return; }
          try {
            const result = JSON.parse(Buffer.concat(output).toString('utf8'));
            if (!result || typeof result.status !== 'string' || typeof result.stdout !== 'string' || typeof result.stderr !== 'string' || !(result.error === null || typeof result.error === 'string') || !(result.exit_code === null || Number.isSafeInteger(result.exit_code))) throw new Error('invalid response');
            if (Buffer.byteLength(result.stdout) + Buffer.byteLength(result.stderr) > maxOutputBytes) throw new Error('invalid response size');
            ctx.logger.info('research_script_finished status=%s', result.status);
            resolveResult(result);
          } catch { ctx.logger.error('research_script_protocol_failed'); reject(new Error('research supervisor returned an invalid response')); }
        });
        child.stdin.end(JSON.stringify({ code: args.code }));
        if (exec.signal.aborted) onAbort();
      });
    },
  });
}
