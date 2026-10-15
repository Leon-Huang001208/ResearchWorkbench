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
async function defaultAdmission(ctx, exec, config) {
  const { nativeAdmission } = await import('./public-data.mjs');
  return nativeAdmission(ctx, exec, config);
}

async function defaultDraftClient(ctx, exec, config, args) {
  const { executeAutomationDraft } = await import('./public-data.mjs');
  return executeAutomationDraft(ctx, exec, config, args);
}


async function defaultActionClient(ctx, exec, config, args) {
  const { executeAutomationAction } = await import('./public-data.mjs');
  return executeAutomationAction(ctx, exec, config, args);
}
const taskSchema = { type: 'object', properties: {
  schema_version: {type:'integer',enum:[1]}, description:{type:'string',minLength:1,maxLength:100000},
  model_provider:{type:'string'},model_id:{type:'string'},output_requirements:{type:'string'},
  approved_data_sources:{type:'array',minItems:1,maxItems:3,items:{type:'string',enum:['datahub','web','uploads']}},
  approved_tools:{type:'array',maxItems:64,items:{type:'string'}},
},required:['description','model_provider','model_id','output_requirements','approved_data_sources','approved_tools'],additionalProperties:false};

function requireMatchingResearchTemplate(ctx, body) {
  if (body.research_task && Object.hasOwn(body, 'input_template') && body.input_template !== body.research_task.description) {
    ctx.logger.warn('automation_research_description_conflict');
    throw Error('research_task_description_conflict: omit input_template or match research_task.description exactly');
  }
}

export function apply(ctx, config, spawnProcess = spawn, admissionClient = defaultAdmission, draftClient = defaultDraftClient, actionClient = defaultActionClient) {
  for (const key of ['python', 'runnerPath', 'researchRoot']) {
    if (typeof config?.[key] !== 'string' || !isAbsolute(config[key])) throw new Error(`research-tools requires absolute ${key}`);
  }
  const timeoutSeconds = config.timeoutSeconds ?? 15;
  const queueWaitSeconds = config.queueWaitSeconds ?? 60;
  const maxOutputBytes = config.maxOutputBytes ?? 65536;
  // Cordis service getters reject undeclared services. Only own data overrides are safe.
  const spawnOverride = Object.getOwnPropertyDescriptor(ctx, 'spawnProcess');
  if (spawnProcess === spawn && typeof spawnOverride?.value === 'function') spawnProcess = spawnOverride.value;
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0 || timeoutSeconds > 60 || !Number.isFinite(queueWaitSeconds) || queueWaitSeconds <= 0 || queueWaitSeconds > 60 || !Number.isSafeInteger(maxOutputBytes) || maxOutputBytes < 1 || maxOutputBytes > 1048576) {
    throw new Error('research-tools execution limits are invalid');
  }
  ctx.tools.register({
    name: 'rwb_prepare_automation',
    description: 'Propose a research_task schedule without selecting a Skill, or an existing locked capability schedule. For research_task omit input_template: the Host derives it from research_task.description; if supplied it must match that description exactly. NEVER saves, enables or runs. Use ask_user_question for missing details; the confirmation card creates and enables research tasks only after a human click. List tasks first. Weekdays 0-4 means Monday-Friday, not a trading calendar.',
    parameters: { type: 'object', properties: {
      name: { type: 'string', minLength: 1, maxLength: 160 },
      target_kind: { type: 'string', enum: ['skill', 'workflow', 'report_workflow','research_task'] },
      research_task: taskSchema,
      target_id: { type: 'string' }, target_version: { type: 'integer', minimum: 1 },
      input_template: { type: 'string', minLength: 1, maxLength: 100000, description: 'For research_task omit this field; it is derived from research_task.description. If supplied, match description exactly, never summarize or rewrite. Required for legacy capability tasks.' },
      output_formats: { type: 'array', maxItems: 7, items: { type: 'string', enum: ['md','html','docx','xlsx','pptx','png','pdf'] } },
      schedule: { type: 'object', properties: {
        kind: { type: 'string', enum: ['once','daily','weekly','monthly'] }, timezone: { type: 'string' },
        once_at: { type: 'string' }, weekdays: {type:'array',minItems:1,maxItems:7,items:{type:'integer',minimum:0,maximum:6}}, weekday: { type: 'integer', minimum: 0, maximum: 6 },
        day: { type: 'integer', minimum: 1, maximum: 31 }, hour: { type: 'integer', minimum: 0, maximum: 23 }, minute: { type: 'integer', minimum: 0, maximum: 59 },
      }, required: ['kind','timezone'], additionalProperties: false },
    }, required: ['name','target_kind','schedule'], additionalProperties: false },
    output: { schema: { type: 'object', properties: { result_json: { type: 'string' } }, required: ['result_json'], additionalProperties: false }, render(_args, value) { return [{ type: 'text', text: value.result_json }]; } },
    async execute(args, exec) {
      const allowed = new Set(['name','target_kind','target_id','target_version','input_template','output_formats','schedule','research_task']);
      if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(key => !allowed.has(key)) || Buffer.byteLength(JSON.stringify(args)) > 110000) throw Error('draft_arguments_invalid');
      if (args.target_kind === 'research_task') requireMatchingResearchTemplate(ctx, args);
      exec.signal.throwIfAborted();
      const scope = await admissionClient(ctx, { ...exec, name: 'rwb_prepare_automation' }, config);
      if (!scope.admitted) throw Error('draft_scope_unverified');
      try {
        const result = await draftClient(ctx, exec, config, args);
        ctx.logger.info('automation_draft_proposed');
        return { result_json: JSON.stringify(result) };
      } catch (error) {
        ctx.logger.warn('automation_draft_proposal_failed');
        throw error;
      }
    },
  });
  for (const [name, operation, description, properties, required] of [
    ['rwb_list_automations','list','Query real schedule definitions, IDs, versions and latest Run statuses/summaries/artifacts before creating, updating or checking a trial. Pass automation_id for one task. Does not mutate anything.',{automation_id:{type:'string'}},[]],
    ['rwb_prepare_automation_update','prepare_update','Propose changes to the SAME task ID using expected_version. Ask for clarification for ambiguous increases; only include explicitly changed fields. For research_task changes provide the new research_task and omit input_template; Host derives it from description. If also supplied it must match description exactly. Do not change input_template alone for a research_task. NEVER applies changes.',{
      automation_id:{type:'string'},body:{type:'object',properties:{
        expected_version:{type:'integer',minimum:1},name:{type:'string'},input_template:{type:'string',description:'For research_task omit: derived from new research_task.description. If supplied, include research_task and match description exactly. Legacy capability tasks may change only this field.'},research_task:taskSchema,
        output_formats:{type:'array',items:{type:'string',enum:['md','html','docx','xlsx','pptx','png','pdf']}},
        schedule:{type:'object',properties:{kind:{type:'string',enum:['once','daily','weekly','monthly']},timezone:{type:'string'},once_at:{type:'string'},weekday:{type:'integer'},weekdays:{type:'array',items:{type:'integer',minimum:0,maximum:6}},day:{type:'integer'},hour:{type:'integer'},minute:{type:'integer'}},required:['kind','timezone'],additionalProperties:false},
      },required:['expected_version'],additionalProperties:false}},['automation_id','body']],
    ['rwb_run_automation','run','Start a manual trial ONLY when the latest human explicitly requested it, or answered the immediately pending trial question. An ambiguous increase never authorizes this. Uses separate DSH session; response is queued, not completed. Never changes the next schedule time.',{automation_id:{type:'string'}},['automation_id']],
  ]) {
    ctx.tools.register({name,description,parameters:{type:'object',properties,required,additionalProperties:false},
      output:{schema:{type:'object',properties:{result_json:{type:'string'}},required:['result_json'],additionalProperties:false},render(_args,value){return[{type:'text',text:value.result_json}];}},
      async execute(args,exec){
        if(!args || typeof args!=='object' || Array.isArray(args) || Object.keys(args).some(key=>!Object.hasOwn(properties,key)) || required.some(key=>!(key in args)) || Buffer.byteLength(JSON.stringify(args))>110000) throw Error('automation_arguments_invalid');
        if (operation === 'prepare_update' && args.body && typeof args.body === 'object') requireMatchingResearchTemplate(ctx, args.body);
        exec.signal.throwIfAborted();
        if(!(await admissionClient(ctx,{...exec,name},config)).admitted) throw Error('automation_scope_unverified');
        try {const result=await actionClient(ctx,exec,config,{operation,...args});ctx.logger.info('automation_chat_action_returned');return {result_json:JSON.stringify(result)};}
        catch(error){ctx.logger.warn('automation_chat_action_failed');throw error;}
      },
    });
  }
  ctx.tools.register({
    name: 'research_document_operation',
    description: 'Read, generate or precisely modify owned DOCX/XLSX/PPTX files. Use file_id, never host paths. Writes create a new version; modifications require expected_sha256 from read. File Excel preserves formulas but does not recalculate. PPT generation requires an owned template. Native mode never silently falls back.',
    parameters: { type: 'object', properties: {
      format: { type: 'string', enum: ['docx', 'xlsx', 'pptx'] },
      operation: { type: 'string', enum: ['read', 'generate', 'modify'] },
      mode: { type: 'string', enum: ['file', 'native'] },
      file_id: { type: 'string' }, expected_sha256: { type: 'string' }, output_name: { type: 'string' },
      content: { type: 'object', description: 'DOCX title/paragraphs/tables; XLSX sheets with name/rows; PPT uses registered template and shape_text changes.' },
      changes: { type: 'array', maxItems: 100, items: { type: 'object' }, description: 'paragraph index/text; table_cell table/row/column/text; cell sheet/cell/value; shape_text slide (1-based)/shape_id/text.' },
    }, required: ['format', 'operation', 'mode'], additionalProperties: false },
    output: { schema: { type: 'object', properties: { result_json: { type: 'string' } }, required: ['result_json'], additionalProperties: false }, render(_args, value) { return [{ type: 'text', text: value.result_json }]; } },
    async execute(args, exec) {
      const allowed = new Set(['format', 'operation', 'mode', 'file_id', 'expected_sha256', 'output_name', 'content', 'changes']);
      if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).some(key => !allowed.has(key)) || Buffer.byteLength(JSON.stringify(args)) > 48000) throw Error('document_arguments_invalid');
      exec.signal.throwIfAborted();
      const scope = await admissionClient(ctx, { ...exec, name: 'research_document_operation' }, config);
      if (!scope.admitted) throw Error('document_scope_unverified');
      const { executeDocumentTool } = await import('./public-data.mjs');
      ctx.logger.info('document_operation_run outcome=started');
      const result = await executeDocumentTool(ctx, exec, config, args);
      ctx.logger.info('document_operation_run outcome=returned');
      return { result_json: JSON.stringify(result) };
    },
  });
  ctx.tools.register({
    name: 'research_run_script',
    description: 'Run Python in this research session using known relative paths only: read inputs/resources; write outputs/tmp. Do not call os.getcwd(), Path.resolve(), Path.absolute(), absolute-path conversion, or directory enumeration. Network, host files, and subprocesses are unavailable. After PermissionError use known relative paths directly; never repeat denied directory introspection.',
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
        const scope = await admissionClient(ctx, { ...exec, name: 'research_run_script' }, config);
        if (!scope.admitted || !Array.isArray(scope.read_paths) || scope.read_paths.length > 320 ||
            !scope.read_paths.every(path => typeof path === 'string' && /^(resources\/capabilities\/[a-z0-9_-]+\/[1-9][0-9]*|inputs\/datasets\/[0-9a-f-]{36})$/.test(path))) throw Error('research_script_scope_unverified');
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
            if (result.status === 'failed' && /(?:^|\n)PermissionError:/.test(result.stderr)) {
              const hint = 'sandbox_permission_denied: 请直接使用已知的 inputs/、resources/、outputs/ 相对路径，不调用 os.getcwd()、Path.resolve()、Path.absolute() 或枚举目录；不要重试已被拒绝的目录探测。';
              result.error = result.error ? `${result.error}\n${hint}` : hint;
              ctx.logger.warn('research_script_permission_recovery_hint');
            }
            ctx.logger.info('research_script_run outcome=%s', result.status);
            resolveResult(result);
          } catch { ctx.logger.error('research_script_protocol_failed'); reject(new Error('research supervisor returned an invalid response')); }
        });
        child.stdin.end(JSON.stringify({ code: args.code, read_paths: scope.read_paths }));
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
