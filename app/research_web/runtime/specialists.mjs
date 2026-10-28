/** Business-ledger adapter over DSH's native continuation service; no execution loop. */
import { randomUUID } from 'node:crypto';
import { basename, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';
import { trustedDirectory } from './research-tools.mjs';
import { privateControl, boundedJson, nativeAdmission } from './public-data.mjs';

export const name = 'research-specialists';
export const inject = ['tools', 'sessions', 'subagents', 'llm'];
const ID = /^[A-Za-z0-9_.:-]{1,160}$/;
const NODE = /^[a-z][a-z0-9_-]{0,63}$/;
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i;
const OUTPUT_LIMIT = 4096;
const RESULT_KEYS = 'artifact_ids,as_of_date,conclusion,evidence_ids,limitations';
const TERMINALS = new Set(['completed', 'aborted', 'error', 'max-tokens', 'refusal']);

/** Fixed authenticated Host route; all execution identities originate from DSH. */
export async function specialistControl(ctx, exec, config, operation, payload, nativeActor) {
  const cwd = await trustedDirectory(ctx, exec, config);
  const agentId = nativeActor ?? exec.agent?.session?.header?.id;
  if (!ID.test(agentId ?? '') || !ID.test(exec.callId ?? '')) throw Error('specialist_native_identity_invalid');
  if (!['guard', 'status', 'plan', 'reserve', 'dispatch', 'accepted', 'submission_unknown', 'terminal', 'cancel', 'model_request', 'model_usage'].includes(operation)) throw Error('specialist_operation_invalid');
  const callId = `${agentId}:${exec.callId}:${operation}`;
  if (callId.length > 200) throw Error('specialist_native_identity_invalid');
  const control = await privateControl(config.researchRoot);
  const signal = operation === 'terminal' || operation === 'submission_unknown' || operation === 'model_usage'
    ? AbortSignal.timeout(4000) : AbortSignal.any([exec.signal, AbortSignal.timeout(4000)]);
  const response = await fetch(`${control.url}/api/research/internal/data/specialist-control`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Research-Data-Key': control.token },
    body: JSON.stringify({ session_id: basename(cwd), operation, payload, agent_id: agentId, call_id: callId }),
    redirect: 'error', credentials: 'omit', signal,
  });
  const value = await boundedJson(response, signal);
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('specialist_control_invalid');
  return value;
}

/** Model text is a candidate result; the Host independently verifies cited evidence. */
export function parseSpecialistResult(blocks) {
  if (!Array.isArray(blocks) || !blocks.length || blocks.some(block => block?.type !== 'text' || typeof block.text !== 'string')) throw Error('specialist_result_invalid');
  const text = blocks.map(block => block.text).join('\n');
  if (Buffer.byteLength(text) > 262144) throw Error('specialist_result_limit');
  let value;
  try { value = JSON.parse(text); } catch { throw Error('specialist_result_invalid'); }
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join(',') !== RESULT_KEYS ||
      typeof value.conclusion !== 'string' || !value.conclusion.trim() || value.conclusion.length > 64000 ||
      typeof value.as_of_date !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:T.{1,48})?$/.test(value.as_of_date) ||
      !['evidence_ids', 'limitations', 'artifact_ids'].every(key => Array.isArray(value[key]) && value[key].length <= 256 && value[key].every(item => typeof item === 'string' && item.length > 0 && item.length <= 2000))) throw Error('specialist_result_invalid');
  return value;
}

function requireKeys(args, keys) {
  if (!args || typeof args !== 'object' || Array.isArray(args) || Object.keys(args).sort().join(',') !== [...keys].sort().join(',')) throw Error('specialist_arguments_invalid');
}

/** Reserve conservative text-request units, without persisting messages or claiming pricing. */
export function modelReservation(options) {
  if (!Number.isSafeInteger(options.maxTokens) || options.maxTokens < 1 || options.maxTokens > OUTPUT_LIMIT ||
      !Array.isArray(options.messages) || (options.tools !== undefined && !Array.isArray(options.tools))) throw Error('specialist_model_bound_invalid');
  const visit = value => {
    if (!value || typeof value !== 'object') return;
    if (['image', 'audio', 'file'].includes(value.type)) throw Error('specialist_model_text_only');
    for (const child of Object.values(value)) visit(child);
  };
  visit(options.messages);
  const bytes = Buffer.byteLength(JSON.stringify({ messages: options.messages, tools: options.tools ?? [] }));
  if (bytes > 4 * 1024 * 1024) throw Error('specialist_model_input_limit');
  // This is a conservative admission unit for supported text requests, not a
  // provider-independent tokenizer or a monetary maximum. Exact usage remains authoritative.
  return bytes + 4096 + 64 * (options.messages.length + (options.tools?.length ?? 0)) + options.maxTokens;
}

async function* boundedProvider(next, owner, deadline, current) {
  const iterator = next()[Symbol.asyncIterator]();
  let timer, aborted;
  const expire = () => {
    if (current() && !owner.signal.aborted) {
      try { owner.agent.cancel({ kind: 'hook', reason: 'specialist_budget_expired' }, { keepInbox: true }); }
      catch { owner.logger.warn('specialist_transport_cancel_unconfirmed'); }
    }
  };
  const halt = new Promise((_, reject) => {
    aborted = () => reject(Error('specialist_model_aborted'));
    owner.signal.addEventListener('abort', aborted, { once: true });
    timer = setTimeout(() => {
      reject(Error('specialist_budget_expired'));
      expire();
    }, Math.max(0, deadline - performance.now()));
  });
  void halt.catch(() => {});
  try {
    while (true) {
      owner.signal.throwIfAborted();
      if (performance.now() >= deadline) { expire(); throw Error('specialist_budget_expired'); }
      const item = await Promise.race([iterator.next(), halt]);
      owner.signal.throwIfAborted();
      if (performance.now() >= deadline) { expire(); throw Error('specialist_budget_expired'); }
      if (item.done) return;
      yield item.value;
    }
  } finally {
    clearTimeout(timer);
    owner.signal.removeEventListener('abort', aborted);
    if (iterator.return) void Promise.resolve(iterator.return()).catch(() => {});
  }
}

export function apply(ctx, config, dependencies = {}) {
  if (!config || !isAbsolute(config.researchRoot ?? '') || !isAbsolute(config.nativeLlmModule ?? '') ||
      typeof ctx.subagents?.startContinuable !== 'function' || typeof ctx.on !== 'function') throw Error('specialist_runtime_unavailable');
  const control = dependencies.control ?? specialistControl;
  const admission = dependencies.admission ?? nativeAdmission;
  const children = new Map();
  const owners = new WeakMap();
  const latest = new WeakMap();
  const collaboration = new Set();
  const toolTimers = new Map();
  const currentSignals = new WeakMap();
  let nativeLlm = dependencies.nativeLlm;
  const request = (exec, op, payload = {}, actor) => control(ctx, exec, config, op, payload, actor);
  const cancelInvalidated = (state, exec) => {
    for (const id of state.operation_result?.cancel_attempt_ids ?? []) {
      const attempt = state.attempts?.[id];
      if (!attempt || !UUID.test(attempt.child_id ?? '')) throw Error('specialist_cancel_identity_invalid');
      ctx.subagents.interrupt(attempt.child_id, { kind: 'ancestor', agent: exec.agent });
      ctx.logger.info('specialist_cancel_requested');
    }
  };
  const register = (name, description, properties, required, execute) => ctx.tools.register({
    name, description, parameters: { type: 'object', properties, required, additionalProperties: false },
    output: { schema: { type: 'object', properties: { result_json: { type: 'string' } }, required: ['result_json'], additionalProperties: false },
      render(_args, value) { return [{ type: 'text', text: value.result_json }]; } },
    async execute(args, exec) {
      try {
        if (!(await admission(ctx, { ...exec, name, arguments: args }, config)).admitted) throw Error('specialist_scope_denied');
        const value = await execute(args, exec);
        ctx.logger.info('specialist_tool_completed tool=%s', name);
        return { result_json: JSON.stringify(value) };
      } catch (error) { ctx.logger.warn('specialist_tool_failed tool=%s', name); throw error; }
    },
  });
  register('specialist_plan', 'Submit or revise a business DAG for Host validation. Use published roles and the exact current version. At most two automatic revisions; cancellation requests do not prove a node stopped.',
    { nodes: { type: 'array', items: { type: 'object', properties: {
      id: { type: 'string' }, role: { type: 'string', enum: ['orchestrator', 'industry', 'quant', 'review'] },
      input: { type: 'object' }, depends_on: { type: 'array', items: { type: 'string' } }, skills: { type: 'array', items: { type: 'string' } },
    }, required: ['id', 'role', 'input', 'depends_on', 'skills'], additionalProperties: false } }, expected_version: { type: 'integer' } }, ['nodes', 'expected_version'],
    async (args, exec) => {
      requireKeys(args, ['nodes', 'expected_version']);
      if (!Array.isArray(args.nodes) || args.nodes.length > 32 || !Number.isSafeInteger(args.expected_version) || args.expected_version < 0) throw Error('specialist_arguments_invalid');
      const state = await request(exec, 'plan', args); cancelInvalidated(state, exec); return state;
    });
  register('specialist_status', 'Read this research task\'s authoritative plan, attempts, evidence gaps and budget. Observation never retries model work.', {}, [],
    async (args, exec) => { requireKeys(args, []); return request(exec, 'status'); });
  register('specialist_cancel', 'Request cancellation of one admitted attempt. It remains pending until a native terminal event or history reconciliation confirms the outcome.',
    { attempt_id: { type: 'string' } }, ['attempt_id'], async (args, exec) => {
      requireKeys(args, ['attempt_id']); if (!ID.test(args.attempt_id)) throw Error('specialist_arguments_invalid');
      const state = await request(exec, 'cancel', args);
      const attempt = state.attempts?.[args.attempt_id];
      if (!attempt || !UUID.test(attempt.child_id ?? '')) throw Error('specialist_cancel_identity_invalid');
      ctx.subagents.interrupt(attempt.child_id, { kind: 'ancestor', agent: exec.agent });
      return state;
    });
  register('specialist_run', 'Execute one ready DAG node using a fresh native DSH child. The Host durably reserves its identity first. Never retry an accepted or unknown attempt; use current expected_version.',
    { node_id: { type: 'string' }, expected_version: { type: 'integer' } }, ['node_id', 'expected_version'], async (args, exec) => {
      requireKeys(args, ['node_id', 'expected_version']);
      if (!NODE.test(args.node_id) || !Number.isSafeInteger(args.expected_version) || args.expected_version < 1) throw Error('specialist_arguments_invalid');
      const state = await request(exec, 'reserve', { ...args, max_tokens: OUTPUT_LIMIT });
      const reserved = state.operation_result;
      if (state.replayed === true || reserved?.replayed === true) throw Error('specialist_reservation_replay');
      if (!reserved || !ID.test(reserved.attempt_id ?? '') || !UUID.test(reserved.child_id ?? '') ||
          reserved.parent_session_id !== exec.agent?.session?.header?.id || typeof reserved.prompt !== 'string' || !reserved.prompt ||
          Buffer.byteLength(reserved.prompt) > 131072 || reserved.max_tokens !== OUTPUT_LIMIT) throw Error('specialist_reservation_invalid');
      exec.signal.throwIfAborted();
      // A reserved identity alone proves no dispatch intent. Persist the intent
      // separately before entering native code, so recovery can distinguish a
      // pre-dispatch crash from an accepted-or-unknown submission.
      const dispatched = await request(exec, 'dispatch', { attempt_id: reserved.attempt_id, child_id: reserved.child_id });
      if (dispatched.replayed === true || dispatched.operation_result?.replayed === true) throw Error('specialist_dispatch_replay');
      const binding = { attemptId: reserved.attempt_id, childId: reserved.child_id, exec, runId: undefined };
      children.set(reserved.child_id, binding);
      try {
        const accepted = await ctx.subagents.startContinuable({ provider: 'spawn', childId: reserved.child_id, label: args.node_id,
          request: { parent: exec.agent, prompt: [{ type: 'text', text: reserved.prompt }], maxDepth: 1, agentOptions: { maxTokens: OUTPUT_LIMIT } }, signal: exec.signal });
        if (accepted.childId !== reserved.child_id || !ID.test(accepted.messageId ?? '')) throw Error('specialist_acceptance_identity_invalid');
        return await request(exec, 'accepted', { attempt_id: reserved.attempt_id, child_id: reserved.child_id, message_id: accepted.messageId });
      } catch (error) {
        try { await request(exec, 'submission_unknown', { attempt_id: reserved.attempt_id, child_id: reserved.child_id }); }
        catch { ctx.logger.warn('specialist_unknown_observation_unconfirmed'); }
        throw Error('specialist_submission_unknown', { cause: error });
      }
    });

  ctx.on('subagent/start', info => {
    const binding = children.get(info?.id);
    if (binding && ID.test(info.runId ?? '') && binding.runId === undefined) binding.runId = info.runId;
  });
  ctx.on('subagent/end', async info => {
    const binding = children.get(info?.id);
    if (!binding || binding.runId === undefined || info.runId !== binding.runId || !TERMINALS.has(info.stopReason)) return;
    children.delete(info.id);
    const payload = { attempt_id: binding.attemptId, child_id: info.id, run_id: info.runId, stop_reason: info.stopReason };
    if (info.stopReason === 'completed') {
      try { payload.result = parseSpecialistResult(info.lastAssistantMessage); }
      catch { payload.stop_reason = 'invalid_output'; }
    }
    try {
      await request({ ...binding.exec, callId: `terminal:${info.runId}` }, 'terminal', payload, info.id);
      ctx.logger.info('specialist_native_terminal_recorded outcome=%s', payload.stop_reason);
    } catch { ctx.logger.warn('specialist_native_terminal_unconfirmed'); }
  });

  // Keep hooks scoped to this preset generation: composeFrom joins children
  // to the parent's generation. Global listeners would also affect other
  // presets/retained generations and could reserve the same request twice.
  // A collaboration node must originate from the durable ledger. Raw native
  // delegation or waking an old child would bypass graph identity/invalidation.
  ctx.on('tools/pre-execute', async (exec, next) => {
    const decision = await next();
    if (!exec.agent || ['deny', 'cancel'].includes(decision.kind)) return decision;
    try {
      const scope = await request(exec, 'guard');
      if (scope.collaboration === false) return decision;
      const rawDelegate = ['subagent', 'rwb_plugin_agent'].includes(exec.name) ||
        (exec.name === 'send_message' && exec.agent.session.header.parentSession === undefined);
      const observation = ['specialist_status', 'specialist_cancel', 'interrupt_agent', 'list_agents'].includes(exec.name);
      if (scope.collaboration !== true || rawDelegate || (!scope.admitted && !observation)) return { kind: 'deny', reason: 'specialist_bound_execution_required' };
      if (observation) return decision;
      if (!Number.isSafeInteger(scope.remaining_ms) || scope.remaining_ms < 1 || scope.remaining_ms > 1800000 || !exec.signal) return { kind: 'deny', reason: 'specialist_deadline_unverified' };
      const key = `${exec.agent.session.header.id}:${exec.callId}`;
      clearTimeout(toolTimers.get(key));
      currentSignals.set(exec.agent, exec.signal);
      const timer = setTimeout(() => {
        toolTimers.delete(key);
        if (currentSignals.get(exec.agent) === exec.signal && !exec.signal.aborted) {
          try { exec.agent.cancel({ kind: 'hook', reason: 'specialist_budget_expired' }, { keepInbox: true }); }
          catch { ctx.logger.warn('specialist_tool_cancel_unconfirmed'); }
        }
      }, scope.remaining_ms);
      timer.unref?.();
      toolTimers.set(key, timer);
      return decision;
    } catch { ctx.logger.warn('specialist_tool_scope_unconfirmed'); return { kind: 'deny', reason: 'specialist_scope_unverified' }; }
  }, { prepend: true });
  ctx.on('tools/result', exec => {
    const key = `${exec.agent?.session?.header?.id}:${exec.callId}`;
    clearTimeout(toolTimers.get(key)); toolTimers.delete(key);
  });

  ctx.on('agent/request', async (payload, next) => {
    const resolved = await next();
    const exec = { agent: payload.agent, signal: payload.signal, callId: `model:${payload.turn}:${payload.step}` };
    const scope = await request(exec, 'guard');
    if (scope.collaboration === false) return resolved;
    if (scope.collaboration === true) collaboration.add(payload.agent.session.header.id);
    if (scope.collaboration !== true || scope.admitted !== true || !payload.signal || typeof payload.agent?.cancel !== 'function' ||
        !Number.isSafeInteger(payload.turn) || payload.turn < 1 || !Number.isSafeInteger(payload.step) || payload.step < 1) throw Error('specialist_model_scope_denied');
    const frozen = scope.model;
    if (!frozen || typeof frozen.model_provider !== 'string' || typeof frozen.model !== 'string' ||
        resolved.provider !== frozen.model_provider || resolved.model !== frozen.model) throw Error('specialist_model_changed');
    currentSignals.set(payload.agent, payload.signal);
    const previous = owners.get(payload.signal);
    const sameStep = previous?.agent === payload.agent && previous.turn === payload.turn && previous.step === payload.step;
    const owner = sameStep ? previous : { ...exec, signal: payload.signal, requestId: randomUUID(), turn: payload.turn, step: payload.step, submitted: false, logger: ctx.logger };
    owners.set(payload.signal, owner); latest.set(payload.agent, owner);
    return { ...resolved, maxTokens: Math.min(resolved.maxTokens ?? OUTPUT_LIMIT, OUTPUT_LIMIT) };
  }, { prepend: true });

  ctx.on('agent/request-error', async (payload, next) => {
    if (collaboration.has(payload.agent?.session?.header?.id)) {
      ctx.logger.warn('specialist_model_retry_requires_confirmation');
      return undefined;
    }
    return next();
  }, { prepend: true });

  ctx.on('llm/stream', async function* (options, next) {
    const owner = owners.get(options.signal);
    if (!owner) {
      if (collaboration.has(options.sessionId)) throw Error('specialist_model_identity_unknown');
      yield* next(); return;
    }
    nativeLlm ??= await import(pathToFileURL(config.nativeLlmModule).href);
    if (latest.get(owner.agent) !== owner || owner.agent.session.header.id !== options.sessionId ||
        !nativeLlm.isAgentLoopRequest?.(options)) throw Error('specialist_model_identity_unknown');
    if (owner.submitted) throw Error('specialist_model_request_replay');
    const reservedTokens = modelReservation(options);
    // Retain this local fence even when the Host reply is lost. Its durable
    // reservation also remains unknown; neither layer replays provider work.
    owner.submitted = true;
    const began = performance.now();
    const state = await request(owner, 'model_request', { request_id: owner.requestId, reserved_tokens: reservedTokens, turn: owner.turn, step: owner.step });
    if (state.replayed === true || state.operation_result?.replayed === true) throw Error('specialist_model_request_replay');
    const remaining = state.operation_result?.remaining_ms ?? Math.floor(((state.deadline ?? state.deadline_at) * 1000) - Date.now());
    if (!Number.isSafeInteger(remaining) || remaining < 1 || remaining > 1800000) throw Error('specialist_budget_expired');
    owner.signal.throwIfAborted();
    let usage, completed = false;
    try {
      for await (const chunk of boundedProvider(next, owner, began + remaining, () => latest.get(owner.agent) === owner)) {
        if (chunk.type === 'usage' && Number.isSafeInteger(chunk.usage?.inputTokens) && chunk.usage.inputTokens >= 0 &&
            Number.isSafeInteger(chunk.usage?.outputTokens) && chunk.usage.outputTokens >= 0) usage = chunk.usage;
        yield chunk;
      }
      completed = true;
    } finally {
      if (completed && usage) {
        try { await request({ ...owner, callId: `usage:${owner.requestId}` }, 'model_usage', { request_id: owner.requestId, input_tokens: usage.inputTokens, output_tokens: usage.outputTokens }); }
        catch { ctx.logger.warn('specialist_model_usage_unconfirmed'); }
      } else ctx.logger.warn('specialist_model_usage_unknown');
    }
  }, { prepend: true });
}
