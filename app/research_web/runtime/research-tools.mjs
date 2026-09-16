/** DSH native research tool. No model-provided paths, environment, or executables. */
import { spawn } from 'node:child_process';
import { constants } from 'node:fs';
import { mkdir, open, realpath, lstat } from 'node:fs/promises';
import { isAbsolute, join, resolve, dirname, basename } from 'node:path';

export const name = 'research-tools';
export const inject = ['tools', 'sessions'];
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const METHOD_IDS = new Set(['socratic-clarification','dual-layer-explanation','reverse-engineering','horizontal-vertical-analysis','fact-checking','expert-perspectives','first-principles','cross-domain-transfer','steelman-comparison','minimal-experiment']);
const METHOD_SOURCES = new Set(['required','user-selected','recommended','model-supplemented']);
let scriptRunning = false;
let scriptPoisoned = false;
const scriptWaiters = [];

function releaseScriptSlot() {
  if (!scriptRunning) return;
  scriptRunning = false;
  while (scriptWaiters.length) {
    const waiter = scriptWaiters.shift();
    if (waiter.done) continue;
    waiter.done = true;
    clearTimeout(waiter.timer);
    waiter.signal.removeEventListener('abort', waiter.abort);
    scriptRunning = true;
    waiter.resolve(releaseScriptSlot);
    return;
  }
}

function acquireScriptSlot(signal, waitSeconds, logger) {
  const queuedAt = Date.now();
  if (scriptPoisoned) {
    logger.warn('research_script_queue outcome=runtime_busy wait_ms=0');
    return Promise.resolve(null);
  }
  if (!scriptRunning) {
    scriptRunning = true;
    logger.info('research_script_queue outcome=started wait_ms=0');
    return Promise.resolve(releaseScriptSlot);
  }
  return new Promise((resolveSlot, reject) => {
    const waiter = {
      done: false,
      signal,
      resolve(release) {
        logger.info(`research_script_queue outcome=started wait_ms=${Date.now() - queuedAt}`);
        resolveSlot(release);
      },
      abort() {},
      timer: undefined,
    };
    const remove = () => {
      const index = scriptWaiters.indexOf(waiter);
      if (index >= 0) scriptWaiters.splice(index, 1);
    };
    waiter.abort = () => {
      if (waiter.done) return;
      waiter.done = true;
      clearTimeout(waiter.timer);
      remove();
      logger.info(`research_script_queue outcome=cancelled wait_ms=${Date.now() - queuedAt}`);
      reject(new Error('research script cancelled while queued'));
    };
    waiter.timer = setTimeout(() => {
      if (waiter.done) return;
      waiter.done = true;
      remove();
      signal.removeEventListener('abort', waiter.abort);
      logger.info(`research_script_queue outcome=runtime_busy wait_ms=${Date.now() - queuedAt}`);
      resolveSlot(null);
    }, waitSeconds * 1000);
    signal.addEventListener('abort', waiter.abort, { once: true });
    scriptWaiters.push(waiter);
    if (signal.aborted) waiter.abort();
  });
}

/** Validate immutable DSH lineage; a cold/missing ancestor fails closed. */
export async function trustedDirectory(ctx, exec, config) {
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
  const queueWaitSeconds = config.queueWaitSeconds ?? 60;
  const maxOutputBytes = config.maxOutputBytes ?? 65536;
  const spawnProcess = typeof ctx.spawnProcess === 'function' ? ctx.spawnProcess : spawn;
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 60 || !Number.isFinite(queueWaitSeconds) || queueWaitSeconds <= 0 || queueWaitSeconds > 60 || !Number.isSafeInteger(maxOutputBytes) || maxOutputBytes < 1 || maxOutputBytes > 1048576) {
    throw new Error('research-tools execution limits are invalid');
  }
  ctx.tools.register({
    name: 'research_run_script',
    description: 'Run Python in this research session. Read inputs/resources; write outputs/tmp. Network, host files, and subprocesses are unavailable.',
    parameters: { type: 'object', properties: { code: { type: 'string', description: 'Nonempty Python source, at most 65536 UTF-8 bytes; enforced before execution.' } }, required: ['code'], additionalProperties: false },
    output: {
      schema: { type: 'object', properties: { status: { type: 'string' }, stdout: { type: 'string' }, stderr: { type: 'string' }, exit_code: { oneOf: [{ type: 'integer' }, { type: 'null' }] }, error: { oneOf: [{ type: 'string' }, { type: 'null' }] } }, required: ['status', 'stdout', 'stderr', 'exit_code', 'error'], additionalProperties: false },
      render(_args, value) { return [{ type: 'text', text: JSON.stringify(value) }]; },
    },
    async execute(args, exec) {
      if (!args || Object.keys(args).length !== 1 || typeof args.code !== 'string' || !args.code.trim() || Buffer.byteLength(args.code) > 65536) throw new Error('research script accepts only bounded code');
      exec.signal.throwIfAborted();
      const release = await acquireScriptSlot(exec.signal, queueWaitSeconds, ctx.logger);
      if (release === null) return { status: 'failed', stdout: '', stderr: '', exit_code: null, error: 'runtime_busy' };
      let childSpawned = false;
      try {
        const cwd = await trustedDirectory(ctx, exec, config);
        exec.signal.throwIfAborted();
        ctx.logger.info('research_script_run outcome=started');
        return await new Promise((resolveResult, reject) => {
        const child = spawnProcess(config.python, ['-I', '-S', '-B', config.runnerPath, '--research-root', config.researchRoot, '--python', config.python, '--session', cwd, '--timeout', String(timeoutSeconds), '--max-output', String(maxOutputBytes)], {
          cwd, env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8', LC_ALL: 'en_US.UTF-8' }, stdio: ['pipe', 'pipe', 'pipe'],
        });
        childSpawned = true;
        const output = [];
        let bytes = 0;
        let stopReason;
        let forceStop;
        let settled = false;
        let slotReleased = false;
        const releaseAfterClose = () => {
          if (slotReleased) return;
          slotReleased = true;
          scriptPoisoned = false;
          release();
        };
        const stop = reason => {
          if (settled) return;
          stopReason ??= reason;
          child.kill('SIGTERM');
          forceStop ??= setTimeout(() => {
            scriptPoisoned = true;
            ctx.logger.error('research_script_run outcome=poisoned');
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
        child.on('error', () => {
          cleanup();
          scriptPoisoned = true;
          ctx.logger.error('research_script_run outcome=poisoned');
          if (settled) return;
          settled = true;
          reject(new Error('research supervisor could not start'));
        });
        child.on('close', code => {
          cleanup();
          releaseAfterClose();
          if (settled) return;
          settled = true;
          if (stopReason || code !== 0) { ctx.logger.warn('research_script_supervisor_failed'); reject(new Error(stopReason ?? 'research supervisor failed')); return; }
          try {
            const result = JSON.parse(Buffer.concat(output).toString('utf8'));
            if (!result || typeof result.status !== 'string' || typeof result.stdout !== 'string' || typeof result.stderr !== 'string' || !(result.error === null || typeof result.error === 'string') || !(result.exit_code === null || Number.isSafeInteger(result.exit_code))) throw new Error('invalid response');
            if (Buffer.byteLength(result.stdout) + Buffer.byteLength(result.stderr) > maxOutputBytes) throw new Error('invalid response size');
            ctx.logger.info('research_script_run outcome=%s', result.status);
            resolveResult(result);
          } catch { ctx.logger.error('research_script_protocol_failed'); reject(new Error('research supervisor returned an invalid response')); }
        });
        child.stdin.end(JSON.stringify({ code: args.code }));
        if (exec.signal.aborted) onAbort();
        });
      } finally {
        if (!childSpawned) release();
      }
    },
  });
  ctx.tools.register({
    name: 'rwb_record_method_use',
    description: 'Record bounded Research Workbench method identity for the current research session. This grants no data, file, network, or execution authority.',
    parameters: { type: 'object', properties: { method_id: { type: 'string', enum: [...METHOD_IDS] }, version: { type: 'string', pattern: '^\\d+\\.\\d+\\.\\d+$' }, source: { type: 'string', enum: [...METHOD_SOURCES] } }, required: ['method_id','version','source'], additionalProperties: false },
    output: {
      schema: { type: 'object', properties: { recorded: { type: 'boolean' }, method_id: { type: 'string' }, version: { type: 'string' }, source: { type: 'string' } }, required: ['recorded','method_id','version','source'], additionalProperties: false },
      render(_args, value) { return [{ type: 'text', text: JSON.stringify(value) }]; },
    },
    async execute(args, exec) {
      if (!args || Object.keys(args).sort().join(',') !== 'method_id,source,version' || !METHOD_IDS.has(args.method_id) || !METHOD_SOURCES.has(args.source) || !/^\d+\.\d+\.\d+$/.test(args.version)) throw new Error('method trace accepts only bounded method identity');
      const cwd = await trustedDirectory(ctx, exec, config);
      const traceDir = join(cwd, '.rwb');
      await mkdir(traceDir, { recursive: true, mode: 0o700 });
      if (await realpath(traceDir) !== traceDir) throw new Error('method trace directory is unsafe');
      const traceFile = join(traceDir, 'method-trace.jsonl');
      const value = { method_id: args.method_id, version: args.version, source: args.source };
      const line = `${JSON.stringify(value)}\n`;
      let handle;
      try {
        handle = await open(traceFile, constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT | (constants.O_NOFOLLOW ?? 0), 0o600);
        const current = await handle.stat();
        if (!current.isFile() || current.size + Buffer.byteLength(line) > 65536) throw new Error('method trace file is unsafe');
        await handle.write(line, null, 'utf8');
        await handle.sync();
      } finally {
        await handle?.close();
      }
      ctx.logger.info('research_method_recorded method_id=%s', args.method_id);
      return { recorded: true, ...value };
    },
  });
}
