/** AlphaFoundry's project-managed DSH Host bridge (DSH v0.1.1-rc.2). */

import { createHash, randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { join } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import type {} from '@deepseek-ai/dsh-agent'
import type {} from '@deepseek-ai/dsh-host-webserver'
import type {} from '@deepseek-ai/dsh-skill'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { SessionId } from '@deepseek-ai/dsh-session'
import { defineTool, type ParameterSchemaSpec, type ValueSchemaSpec } from '@deepseek-ai/dsh-tools'

export const name = 'alphafoundry-runtime-bridge'
export const inject = ['webServer', 'agents', 'sessions', 'skills', 'tools']

const BRIDGE_PREFIX = '/alphafoundry/bridge/v1'
const MAX_BODY_BYTES = 256 * 1024

type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
type JsonObject = Record<string, Json>

interface CapabilitySpec {
  capability_id: string
  version: string
  description: string
  input_schema: JsonObject
  output_schema: JsonObject
  timeout_seconds: number
  idempotency_key: string
}

interface DeploymentManifest {
  schema_version: 'alphafoundry-dsh-deployment/v1'
  tools: CapabilitySpec[]
  skills: CapabilitySpec[]
}

export interface AlphaFoundryDshConfig {
  /** Directory containing the deployment command's alphafoundry-manifest.json. */
  deploymentPath?: string
  /** Must be a loopback AlphaFoundry API origin. */
  apiBaseUrl?: string
  /** Credentials are usually supplied through environment variables. */
  bridgeToken?: string
  toolToken?: string
  /** Exact AlphaFoundry UI origin allowed to consume one-time browser launches. */
  uiOrigin?: string
}

interface ResolvedConfig {
  deploymentPath: string
  apiBaseUrl: string
  bridgeToken: string
  toolToken: string
  uiOrigin: string
}

interface Execution {
  executionId: string
  runId: string
  sessionId: string
  agent: {
    followup(message: unknown): void
    whenIdle(): Promise<void>
    cancel(reason: { kind: 'user' }): void
    session: { events: readonly unknown[] }
  } | undefined
  result: JsonObject | undefined
  completed: Map<string, JsonObject>
  events: BridgeEvent[]
}

interface BridgeEvent {
  event_id: string
  event_type: string
  run_id: string
  sequence: number
  occurred_at: string
  payload: JsonObject
}

/** Register the bridge's two directions: runtime tools and structured skill result. */
export function apply(ctx: Context, config: AlphaFoundryDshConfig = {}): void {
  const resolved = resolveConfig(config)
  const manifest = loadManifest(resolved.deploymentPath)
  const executions = new Map<string, Execution>()
  const runs = new Map<string, string>()

  registerCoreTools(ctx, resolved, manifest.tools)
  ctx.tools.register(defineSubmitSkillResultTool(manifest.skills, executions))

  ctx.webServer.register({
    kind: 'prefix',
    path: BRIDGE_PREFIX,
    handler: async (req, res) => {
      try {
        await routeBridgeRequest(ctx, req, res, resolved, manifest, executions, runs)
      } catch (error) {
        ctx.logger.warn(`AlphaFoundry bridge request failed: ${errorMessage(error)}`)
        sendJson(res, 500, { error: 'bridge_internal_error' })
      }
    },
  })
  // The script carries no credentials. It accepts only opaque, one-time ids from
  // the configured AlphaFoundry UI origin and asks its own loopback host to consume.
  ctx.webServer.tapIndex(html => html.replace('</head>', `${fingptFrameScript(resolved.uiOrigin)}</head>`))
  registerFinGPTSessionSync(ctx, resolved)
  // Ensure the declared DSH Skill registry is a hard dependency of this bundle.
  void ctx.skills
  ctx.logger.info('AlphaFoundry DSH bridge loaded')
}

async function routeBridgeRequest(
  ctx: Context,
  req: IncomingMessage,
  res: ServerResponse,
  config: ResolvedConfig,
  manifest: DeploymentManifest,
  executions: Map<string, Execution>,
  runs: Map<string, string>,
): Promise<void> {
  const requestUrl = new URL(req.url ?? '/', 'http://127.0.0.1')
  const path = requestUrl.pathname
  const launchMatch = new RegExp(`^${BRIDGE_PREFIX}/fingpt/launches/([^/]+)$`).exec(path)
  // This endpoint is intentionally browser-facing: it accepts no secret and consumes
  // a short-lived one-time launch id only from the DSH frame itself. The frame checks
  // the exact AlphaFoundry parent origin before it ever performs this request.
  if (req.method === 'POST' && launchMatch !== null) {
    if (!isLoopback(req) || !isDshFrameOrigin(req)) {
      sendJson(res, 403, { error: 'forbidden' })
      return
    }
    const launchId = launchMatch[1]
    if (launchId === undefined) return sendJson(res, 404, { error: 'not_found' })
    const launch = await consumeFinGPTLaunch(config, decodeURIComponent(launchId))
    const execution = createExecution(`fingpt:${launch.task_id}`)
    executions.set(execution.executionId, execution)
    runs.set(execution.runId, execution.executionId)
    const agent = await ensureAgent(ctx, execution)
    agent.followup(createUserMessage({ content: [{ type: 'text', text: launch.prompt }], source: { kind: 'user' } }))
    appendEvent(execution, 'FinGPTLaunchAccepted', { task_id: launch.task_id })
    sendJson(res, 202, { accepted: true, dsh_session_id: execution.sessionId })
    return
  }
  if (!isLoopback(req) || !hasBearer(req, config.bridgeToken)) {
    sendJson(res, 403, { error: 'forbidden' })
    return
  }
  if (req.method === 'GET' && path === `${BRIDGE_PREFIX}/health`) {
    sendJson(res, 200, {
      runtime: 'dsh',
      protocol_version: 'alphafoundry.io/v1',
      tools: manifest.tools.map(item => item.capability_id),
      skills: manifest.skills.map(item => item.capability_id),
      capabilities: { skills: true, workflow: false, streaming: true, cancellation: true, resume: true },
    })
    return
  }
  if (req.method === 'POST' && path === `${BRIDGE_PREFIX}/sessions`) {
    const body = await readJsonBody(req)
    const runId = requiredString(body, 'run_id')
    const execution = createExecution(runId)
    executions.set(execution.executionId, execution)
    runs.set(runId, execution.executionId)
    appendEvent(execution, 'RuntimeSessionCreated', {})
    sendJson(res, 201, { execution_id: execution.executionId, resumable: true })
    return
  }
  const eventsMatch = new RegExp(`^${BRIDGE_PREFIX}/runs/([^/]+)/events$`).exec(path)
  if (req.method === 'GET' && eventsMatch !== null) {
    const runPathId = eventsMatch[1]
    if (runPathId === undefined) return sendJson(res, 404, { error: 'not_found' })
    const execution = executions.get(runs.get(decodeURIComponent(runPathId)) ?? '')
    const afterSequence = Number(requestUrl.searchParams.get('after_sequence') ?? '-1')
    const events = execution?.events.filter(item => item.sequence > afterSequence) ?? []
    if (req.headers.accept?.includes('text/event-stream')) {
      sendSse(res, events)
    } else {
      sendJson(res, 200, { events: events as unknown as Json })
    }
    return
  }
  const resumeMatch = new RegExp(`^${BRIDGE_PREFIX}/runs/([^/]+)/resume$`).exec(path)
  if (req.method === 'POST' && resumeMatch !== null) {
    const runPathId = resumeMatch[1]
    if (runPathId === undefined) return sendJson(res, 404, { error: 'not_found' })
    const runId = decodeURIComponent(runPathId)
    const execution = await resumeExecution(ctx, runId, executions, runs)
    sendJson(res, 200, { execution_id: execution.executionId, resumable: true })
    return
  }
  const taskMatch = new RegExp(`^${BRIDGE_PREFIX}/executions/([^/]+)/tasks$`).exec(path)
  if (req.method === 'POST' && taskMatch !== null) {
    const executionPathId = taskMatch[1]
    if (executionPathId === undefined) return sendJson(res, 404, { error: 'not_found' })
    const execution = executions.get(decodeURIComponent(executionPathId))
    if (execution === undefined) return sendJson(res, 404, { error: 'execution_not_found' })
    const task = await readJsonBody(req)
    const result = await runTask(ctx, execution, task, manifest.skills)
    sendJson(res, 200, { result })
    return
  }
  const cancelMatch = new RegExp(`^${BRIDGE_PREFIX}/executions/([^/]+)/cancel$`).exec(path)
  if (req.method === 'POST' && cancelMatch !== null) {
    const executionPathId = cancelMatch[1]
    if (executionPathId === undefined) return sendJson(res, 404, { error: 'not_found' })
    const execution = executions.get(decodeURIComponent(executionPathId))
    if (execution === undefined) return sendJson(res, 404, { error: 'execution_not_found' })
    execution.agent?.cancel({ kind: 'user' })
    await execution.agent?.whenIdle()
    appendEvent(execution, 'RuntimeCancelled', {})
    sendJson(res, 202, { execution_id: execution.executionId, status: 'cancelled' })
    return
  }
  sendJson(res, 404, { error: 'not_found' })
}

interface FinGPTLaunch { task_id: string, prompt: string }

async function consumeFinGPTLaunch(config: ResolvedConfig, launchId: string): Promise<FinGPTLaunch> {
  const response = await fetch(`${config.apiBaseUrl}/api/v2/fingpt/launches/${encodeURIComponent(launchId)}/consume`, {
    method: 'POST', headers: { authorization: `Bearer ${config.toolToken}` },
  })
  if (!response.ok) throw new Error('FinGPT launch is invalid or expired')
  const payload = await response.json() as { task_id?: unknown, prompt?: unknown }
  if (typeof payload.task_id !== 'string' || typeof payload.prompt !== 'string') throw new Error('FinGPT launch response is invalid')
  return { task_id: payload.task_id, prompt: payload.prompt }
}

function registerFinGPTSessionSync(ctx: Context, config: ResolvedConfig): void {
  const emitter = ctx as unknown as { on: (event: string, listener: (...payload: unknown[]) => void) => void }
  const outbox = new FinGPTSyncOutbox(config)
  // Session events are a metadata stream. The sanitizer below never forwards user or
  // assistant message content, therefore AlphaFoundry cannot become a transcript copy.
  emitter.on('session/created', session => outbox.enqueue('session/created', session))
  emitter.on('session/event', (session, event) => outbox.enqueue('session/event', { session, event }))
}

class FinGPTSyncOutbox {
  private readonly pending = new Map<string, JsonObject>()
  private retryTimer: NodeJS.Timeout | undefined

  constructor(private readonly config: ResolvedConfig) {}

  enqueue(eventType: string, raw: unknown): void {
    const event = sanitizeSessionEvent(eventType, raw)
    if (event === undefined) return
    const key = String(event.event_key)
    this.pending.set(key, event)
    void this.flush()
  }

  private async flush(): Promise<void> {
    for (const [key, event] of this.pending) {
      try {
        const response = await fetch(`${this.config.apiBaseUrl}/api/v2/fingpt/dsh-events`, {
          method: 'POST',
          headers: { authorization: `Bearer ${this.config.toolToken}`, 'content-type': 'application/json' },
          body: JSON.stringify(event),
        })
        if (!response.ok) throw new Error('FinGPT sync endpoint rejected event')
        this.pending.delete(key)
      } catch {
        // DSH's append-only log remains the recovery source. The local outbox retries
        // metadata sync but never blocks an interactive DSH turn.
        this.scheduleRetry()
        return
      }
    }
  }

  private scheduleRetry(): void {
    if (this.retryTimer !== undefined) return
    this.retryTimer = setTimeout(() => {
      this.retryTimer = undefined
      void this.flush()
    }, 2_000)
  }
}

function sanitizeSessionEvent(eventType: string, raw: unknown): JsonObject | undefined {
  if (typeof raw !== 'object' || raw === null) return undefined
  const value = raw as Record<string, unknown>
  const session = typeof value.session === 'object' && value.session !== null ? value.session as Record<string, unknown> : value
  const sessionId = typeof session.sessionId === 'string' ? session.sessionId : typeof session.session_id === 'string' ? session.session_id : typeof session.id === 'string' ? session.id : undefined
  if (sessionId === undefined) return undefined
  const inner = typeof value.event === 'object' && value.event !== null ? value.event as Record<string, unknown> : value
  const kind = typeof inner.type === 'string' ? inner.type : eventType
  const rawSequence = value.sequence ?? inner.sequence
  const sequence = typeof rawSequence === 'number' && Number.isInteger(rawSequence) ? rawSequence : -1
  const payload: JsonObject = {}
  if (kind.includes('tool') && typeof inner.name === 'string') payload.tool_name = inner.name
  if (kind === 'turn/end' && typeof inner.reason === 'string') payload.reason = inner.reason
  return { session_id: sessionId, event_key: createHash('sha256').update(JSON.stringify({ sessionId, eventType, kind, sequence })).digest('hex'), event_type: kind, sequence, metadata: { status: kind === 'turn/end' ? 'idle' : 'active' }, payload }
}

function fingptFrameScript(uiOrigin: string): string {
  const origin = JSON.stringify(uiOrigin).replace(/</g, '\\u003c')
  return `<script>(function(){var parentOrigin=${origin};function ready(){window.parent!==window&&window.parent.postMessage({type:'alphafoundry.fingpt.ready'},parentOrigin)}ready();window.addEventListener('message',function(e){if(e.origin!==parentOrigin||!e.data)return;if(e.data.type==='alphafoundry.fingpt.ping'){ready();return}if(e.data.type!=='alphafoundry.fingpt.launch'||typeof e.data.launchId!=='string')return;fetch('${BRIDGE_PREFIX}/fingpt/launches/'+encodeURIComponent(e.data.launchId),{method:'POST',credentials:'same-origin'}).then(function(r){return r.json().then(function(v){return {ok:r.ok,v:v}})}).then(function(x){window.parent.postMessage({type:'alphafoundry.fingpt.launch-result',ok:x.ok,sessionId:x.v.dsh_session_id||null},parentOrigin)}).catch(function(){window.parent.postMessage({type:'alphafoundry.fingpt.launch-result',ok:false},parentOrigin)})});}())</script>`
}

function isDshFrameOrigin(req: IncomingMessage): boolean {
  const origin = req.headers.origin
  const host = req.headers.host
  if (typeof origin !== 'string' || typeof host !== 'string') return false
  try {
    const parsed = new URL(origin)
    return parsed.protocol === 'http:' && parsed.host === host && ['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)
  } catch {
    return false
  }
}

async function runTask(
  ctx: Context,
  execution: Execution,
  task: JsonObject,
  skills: CapabilitySpec[],
): Promise<JsonObject> {
  const skillId = requiredString(task, 'skill_id')
  const skill = skills.find(item => item.capability_id === skillId)
  if (skill === undefined) throw new Error(`Skill is not allowlisted: ${skillId}`)
  const payload = requiredObject(task, 'payload')
  const outputSchema = requiredObject(task, 'output_schema')
  assertSchemaEquals(outputSchema, skill.output_schema, 'output_schema')
  const agent = await ensureAgent(ctx, execution)
  execution.result = undefined
  appendEvent(execution, 'SkillStarted', { skill_id: skillId })
  const idempotencyKey = requiredString(task, 'idempotency_key')
  if (idempotencyKey !== skill.idempotency_key) throw new Error('idempotency_key does not match deployed skill contract')
  const replayKey = `${skillId}:${idempotencyKey}`
  const completed = execution.completed.get(replayKey)
  if (completed !== undefined) return completed
  const timeoutSeconds = requiredPositiveInteger(task, 'timeout_seconds')
  agent.followup(createUserMessage({
    content: [{ type: 'text', text: taskPrompt(execution.executionId, skill, payload) }],
    source: { kind: 'user' },
  }))
  await waitForIdleWithinTimeout(agent, timeoutSeconds)
  if (execution.result === undefined) throw new Error(`Skill ${skillId} did not submit a structured result`)
  validateObject(execution.result, skill.output_schema, 'Skill result')
  appendEvent(execution, 'SkillCompleted', { skill_id: skillId })
  execution.completed.set(replayKey, execution.result)
  return execution.result
}

async function waitForIdleWithinTimeout(agent: NonNullable<Execution['agent']>, timeoutSeconds: number): Promise<void> {
  let timer: NodeJS.Timeout | undefined
  try {
    await Promise.race([
      agent.whenIdle(),
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(() => {
          agent.cancel({ kind: 'user' })
          reject(new Error(`Skill execution exceeded ${timeoutSeconds} seconds`))
        }, timeoutSeconds * 1000)
      }),
    ])
  } finally {
    if (timer !== undefined) clearTimeout(timer)
  }
}

async function ensureAgent(ctx: Context, execution: Execution): Promise<NonNullable<Execution['agent']>> {
  if (execution.agent !== undefined) return execution.agent
  // Bridge-created sessions do not pass through DSH Web's persisted model selector.
  // Pin the documented AlphaFoundry runtime route so the deployment persona can
  // resolve {{model}} and every skill execution has a complete LLM target.
  const handle = await ctx.agents.create({
    sessionId: SessionId(execution.sessionId),
    meta: { cwd: process.cwd() },
    agentOptions: { provider: 'deepseek-official', model: 'deepseek-v4-flash' },
  })
  execution.agent = handle.agent
  return handle.agent
}

async function resumeExecution(
  ctx: Context,
  runId: string,
  executions: Map<string, Execution>,
  runs: Map<string, string>,
): Promise<Execution> {
  const known = runs.get(runId)
  if (known !== undefined && executions.has(known)) return executions.get(known)!
  const execution = createExecution(runId)
  const handle = await ctx.agents.resume({ resumeSessionId: SessionId(execution.sessionId) })
  execution.agent = handle.agent
  executions.set(execution.executionId, execution)
  runs.set(runId, execution.executionId)
  appendEvent(execution, 'RuntimeResumed', {})
  return execution
}

function defineSubmitSkillResultTool(
  skills: CapabilitySpec[],
  executions: Map<string, Execution>,
) {
  return defineTool({
    name: 'alphafoundry_submit_skill_result',
    description: 'Submit the only accepted structured result for an AlphaFoundry DSH skill.',
    parameters: {
      execution_id: { type: 'string', required: true },
      skill_id: { type: 'string', required: true },
      result: { type: 'object', required: true, additionalProperties: true },
    },
    output: {
      schema: {
        type: 'object',
        properties: { accepted: { type: 'boolean', required: true } },
        additionalProperties: false,
      },
      render: (_args, value) => [{ type: 'text', text: value.accepted ? 'AlphaFoundry structured result accepted.' : 'Result rejected.' }],
    },
    async execute(args) {
      const input = assertObject(args, 'submit skill result input')
      const execution = executions.get(requiredString(input, 'execution_id'))
      const skillId = requiredString(input, 'skill_id')
      const skill = skills.find(item => item.capability_id === skillId)
      if (execution === undefined || skill === undefined) throw new Error('Unknown AlphaFoundry execution or skill')
      const result = requiredObject(input, 'result')
      validateObject(result, skill.output_schema, 'Skill result')
      execution.result = result
      appendEvent(execution, 'SkillResultSubmitted', { skill_id: skillId })
      return { accepted: true }
    },
  })
}

function registerCoreTools(ctx: Context, config: ResolvedConfig, specs: CapabilitySpec[]): void {
  for (const spec of specs) {
    const parameters = toDshParameters(spec.input_schema) as unknown as ParameterSchemaSpec
    const outputSchema = toDshValueSchema(spec.output_schema) as unknown as ValueSchemaSpec
    ctx.tools.register(defineTool({
      // DSH sends tool names to DeepSeek as OpenAI function names, which only
      // permit letters, digits, underscores and hyphens.  Keep the canonical
      // dotted capability ID in the Core manifest and expose a wire-safe alias
      // only at this adapter boundary.
      name: dshToolName(spec.capability_id),
      description: `${spec.description} (AlphaFoundry ${spec.version})`,
      parameters,
      output: {
        schema: outputSchema,
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
      },
      async execute(args, execution) {
        const input = assertObject(args, 'DSH tool input')
        validateObject(input, spec.input_schema, 'DSH tool input')
        const response = await fetch(`${config.apiBaseUrl}/api/v2/runtime-tools/${encodeURIComponent(spec.capability_id)}`, {
          method: 'POST',
          headers: { 'content-type': 'application/json', authorization: `Bearer ${config.toolToken}` },
          body: JSON.stringify({
            run_id: requiredString(input, 'run_id'),
            execution_id: requiredString(input, 'execution_id'),
            correlation_id: randomUUID(),
            input: {},
          }),
          signal: execution.signal,
        })
        if (!response.ok) throw new Error(`AlphaFoundry tool ${spec.capability_id} failed: HTTP ${response.status}`)
        const output = assertObject(await response.json() as Json, 'AlphaFoundry tool output')
        validateObject(output, spec.output_schema, 'AlphaFoundry tool output')
        return output as never
      },
    }))
  }
}

function resolveConfig(config: AlphaFoundryDshConfig): ResolvedConfig {
  const deploymentPath = config.deploymentPath ?? process.env.ALPHAFOUNDRY_DSH_DEPLOYMENT_PATH ?? ''
  const apiBaseUrl = config.apiBaseUrl ?? process.env.ALPHAFOUNDRY_BACKEND_URL ?? ''
  const bridgeToken = config.bridgeToken ?? process.env.ALPHAFOUNDRY_DSH_BRIDGE_TOKEN ?? ''
  const toolToken = config.toolToken ?? process.env.ALPHAFOUNDRY_DSH_TOOL_TOKEN ?? ''
  const uiOrigin = config.uiOrigin ?? process.env.ALPHAFOUNDRY_UI_ORIGIN ?? 'http://127.0.0.1:8767'
  if (!deploymentPath || !apiBaseUrl || !bridgeToken || !toolToken) throw new Error('AlphaFoundry DSH bridge configuration is incomplete')
  const parsed = new URL(apiBaseUrl)
  if (parsed.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname)) throw new Error('AlphaFoundry API URL must be loopback HTTP')
  const ui = new URL(uiOrigin)
  if (ui.protocol !== 'http:' || !['127.0.0.1', 'localhost', '[::1]'].includes(ui.hostname)) throw new Error('AlphaFoundry UI origin must be loopback HTTP')
  return { deploymentPath, apiBaseUrl: apiBaseUrl.replace(/\/$/, ''), bridgeToken, toolToken, uiOrigin: ui.origin }
}

function loadManifest(deploymentPath: string): DeploymentManifest {
  const raw = JSON.parse(readFileSync(join(deploymentPath, 'alphafoundry-manifest.json'), 'utf8')) as DeploymentManifest
  if (raw.schema_version !== 'alphafoundry-dsh-deployment/v1' || !Array.isArray(raw.tools) || !Array.isArray(raw.skills)) throw new Error('Invalid AlphaFoundry deployment manifest')
  return raw
}

function createExecution(runId: string): Execution {
  const digest = createHash('sha256').update(runId).digest('hex')
  return { executionId: `dsh-${digest.slice(0, 32)}`, runId, sessionId: `af-${digest.slice(0, 32)}`, agent: undefined, result: undefined, completed: new Map(), events: [] }
}

function appendEvent(execution: Execution, eventType: string, payload: JsonObject): void {
  execution.events.push({ event_id: `dsh_evt_${randomUUID().replaceAll('-', '')}`, event_type: eventType, run_id: execution.runId, sequence: execution.events.length, occurred_at: new Date().toISOString(), payload })
}

function taskPrompt(executionId: string, skill: CapabilitySpec, payload: JsonObject): string {
  return `Execute the AlphaFoundry skill \`${skill.capability_id}\`. First load its SKILL.md via the skill tool. The supplied payload is the authoritative output of AlphaFoundry's native market Tools for this workflow step. Do NOT call market or news tools again, and do not fetch data outside the payload. Analyze only the supplied payload. You MUST finish by calling alphafoundry_submit_skill_result with execution_id=${executionId}, skill_id=${skill.capability_id}, and a JSON result matching this schema: ${JSON.stringify(skill.output_schema)}. Payload: ${JSON.stringify(payload)}`
}

function isLoopback(req: IncomingMessage): boolean {
  return ['127.0.0.1', '::1', '::ffff:127.0.0.1'].includes(req.socket.remoteAddress ?? '')
}

function hasBearer(req: IncomingMessage, expected: string): boolean {
  return req.headers.authorization === `Bearer ${expected}`
}

async function readJsonBody(req: IncomingMessage): Promise<JsonObject> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of req) {
    const data = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
    size += data.length
    if (size > MAX_BODY_BYTES) throw new Error('Request body exceeds limit')
    chunks.push(data)
  }
  return assertObject(JSON.parse(Buffer.concat(chunks).toString('utf8')) as Json, 'request body')
}

function sendJson(res: ServerResponse, status: number, value: JsonObject): void {
  res.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' })
  res.end(JSON.stringify(value))
}

function sendSse(res: ServerResponse, events: BridgeEvent[]): void {
  res.writeHead(200, {
    'content-type': 'text/event-stream; charset=utf-8',
    'cache-control': 'no-cache, no-store',
    connection: 'keep-alive',
    'x-accel-buffering': 'no',
  })
  for (const event of events) {
    res.write(`id: ${event.sequence}\nevent: ${event.event_type}\ndata: ${JSON.stringify(event)}\n\n`)
  }
  res.end()
}

function requiredString(value: JsonObject, key: string): string {
  const item = value[key]
  if (typeof item !== 'string' || item.length === 0) throw new Error(`${key} must be a non-empty string`)
  return item
}

function requiredPositiveInteger(value: JsonObject, key: string): number {
  const item = value[key]
  if (typeof item !== 'number' || !Number.isInteger(item) || item <= 0 || item > 900) throw new Error(`${key} must be an integer between 1 and 900`)
  return item
}

function requiredObject(value: JsonObject, key: string): JsonObject { return assertObject(value[key], key) }
function assertObject(value: unknown, label: string): JsonObject {
  if (value === null || Array.isArray(value) || typeof value !== 'object') throw new Error(`${label} must be an object`)
  return value as JsonObject
}
function errorMessage(error: unknown): string { return error instanceof Error ? error.message : String(error) }

function assertSchemaEquals(actual: JsonObject, expected: JsonObject, label: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`${label} does not match deployed skill contract`)
}

function toDshParameters(schema: JsonObject): Record<string, JsonObject> {
  const properties = assertObject(schema.properties ?? {}, 'input_schema.properties')
  const required = new Set(Array.isArray(schema.required) ? schema.required.filter(item => typeof item === 'string') : [])
  return Object.fromEntries(Object.entries(properties).map(([key, value]) => [key, { ...toDshValueSchema(assertObject(value, key)), required: required.has(key) }]))
}

function dshToolName(capabilityId: string): string {
  const name = capabilityId.replace(/[^a-zA-Z0-9_-]/g, '_')
  if (!/^[a-zA-Z0-9_-]+$/.test(name)) throw new Error(`Invalid DSH tool name for ${capabilityId}`)
  return name
}

function toDshValueSchema(schema: JsonObject): JsonObject {
  const type = schema.type
  if (typeof type !== 'string' || !['string', 'number', 'integer', 'boolean', 'array', 'object'].includes(type)) throw new Error('Only explicit JSON Schema types are supported')
  const result: JsonObject = { type }
  if (typeof schema.description === 'string') result.description = schema.description
  if (Array.isArray(schema.enum)) result.enum = schema.enum
  if (type === 'array' && schema.items !== undefined) result.items = toDshValueSchema(assertObject(schema.items, 'array items'))
  if (type === 'object') {
    result.properties = Object.fromEntries(Object.entries(assertObject(schema.properties ?? {}, 'object properties')).map(([key, value]) => [key, toDshValueSchema(assertObject(value, key))]))
    result.additionalProperties = schema.additionalProperties === true
  }
  return result
}

function validateObject(value: JsonObject, schema: JsonObject, label: string): void {
  const properties = assertObject(schema.properties ?? {}, `${label} schema properties`)
  const required = new Set(Array.isArray(schema.required) ? schema.required.filter(item => typeof item === 'string') : [])
  for (const key of required) if (!(key in value)) throw new Error(`${label} misses required field ${key}`)
  if (schema.additionalProperties !== true) for (const key of Object.keys(value)) if (!(key in properties)) throw new Error(`${label} contains undeclared field ${key}`)
  for (const [key, item] of Object.entries(value)) {
    const definition = properties[key]
    if (definition === undefined) continue
    const expected = assertObject(definition, `${label}.${key}`).type
    if (expected === 'string' && typeof item !== 'string') throw new Error(`${label}.${key} must be string`)
    if ((expected === 'number' || expected === 'integer') && (typeof item !== 'number' || !Number.isFinite(item))) throw new Error(`${label}.${key} must be number`)
    if (expected === 'boolean' && typeof item !== 'boolean') throw new Error(`${label}.${key} must be boolean`)
    if (expected === 'array' && !Array.isArray(item)) throw new Error(`${label}.${key} must be array`)
    if (expected === 'object') validateObject(assertObject(item, `${label}.${key}`), assertObject(definition, `${label}.${key} schema`), `${label}.${key}`)
  }
}
