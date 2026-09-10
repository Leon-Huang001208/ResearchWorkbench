/** Research Workbench's loopback-only, live-claim Tabbit adapter. */
import { randomUUID } from 'node:crypto';
import { existsSync } from 'node:fs';

export const name = 'research-tabbit-adapter';
export const inject = ['tabbit'];

const PLUGIN_VERSION = '0.3.4';
const MINIMUM_BROWSER_VERSION = '1.9.0';
const MAX_BODY_BYTES = 64 * 1024;
const MAX_TABS = 8;
const MAX_PAGE_CHARS = 60_000;
const MAX_TOTAL_CHARS = 120_000;
const TOKEN_TTL_MS = 10 * 60 * 1000;
const INSTANCE = /^[A-F0-9]{16}$/u;
const MARKER = /@\[([^\]\r\n]{1,80})\]\(rwb-tabbit:([a-zA-Z0-9-]{1,160})\)/gu;

class AdapterError extends Error {
  constructor(code, status = 400) {
    super(code);
    this.code = code;
    this.status = status;
  }
}

export function fairPageLimit(count) {
  return Math.min(MAX_PAGE_CHARS, Math.floor(MAX_TOTAL_CHARS / Math.max(1, count)));
}

function short(value, size) {
  return String(value ?? '').replace(/[^a-zA-Z0-9]/gu, '').slice(0, size).toLowerCase().padEnd(size, '0');
}

export function taskName(sessionId, requestId) {
  return `rwb-mention-${short(sessionId, 4)}-${short(requestId, 8)}`;
}

export function buildExtractionCode(count) {
  const pageLimit = fairPageLimit(count);
  return `const selected = pages();
if (selected.length !== ${count}) throw new Error('claimed page count mismatch');
return await Promise.all(selected.map(async (candidate) => {
  const title = await candidate.title();
  const url = candidate.url();
  const text = await candidate.evaluate(() => document.body?.innerText ?? document.documentElement?.innerText ?? '');
  const normalized = String(text ?? '');
  return { title, url, text: normalized.slice(0, ${pageLimit}), truncated: normalized.length > ${pageLimit} };
}));`;
}

function cleanTitle(value) {
  return String(value ?? '').replace(/[\r\n]+/gu, ' ').trim().slice(0, 80) || 'tab';
}

function xml(value) {
  return String(value).replace(/&/gu, '&amp;').replace(/"/gu, '&quot;').replace(/</gu, '&lt;');
}

function sessionMatches(agentId, sessionId) {
  const actual = String(agentId ?? '');
  return actual === sessionId || actual.replace(/^session-/u, '') === sessionId.replace(/^session-/u, '');
}

function pluginMessage(entry, uuid) {
  const note = entry.truncated ? '\n[content truncated by Research Workbench]' : '';
  return Object.freeze({
    id: uuid(),
    role: 'user',
    source: {
      kind: 'plugin',
      plugin: 'research-tabbit-adapter',
      form: 'notice',
      summary: `Live Tabbit context: ${cleanTitle(entry.title)}`.slice(0, 120),
    },
    content: [{
      type: 'text',
      text: `<browser-tab source="live-claim" url="${xml(entry.url)}" title="${xml(entry.title)}">\n${xml(entry.text)}${note}\n</browser-tab>`,
    }],
  });
}

function hostAllowed(req) {
  const host = String(req.headers.host ?? '').toLowerCase();
  return host === 'localhost' || host.startsWith('localhost:') ||
    host === '127.0.0.1' || host.startsWith('127.0.0.1:') ||
    host === '[::1]' || host.startsWith('[::1]:');
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    'content-type': 'application/json; charset=utf-8',
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
  });
  res.end(body);
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > MAX_BODY_BYTES) throw new AdapterError('request_too_large', 413);
    chunks.push(chunk);
  }
  try {
    const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('object required');
    return value;
  } catch (error) {
    if (error instanceof AdapterError) throw error;
    throw new AdapterError('invalid_json');
  }
}

function numericVersion(value) {
  const match = String(value ?? '').match(/^v?(\d+(?:\.\d+)*)/u);
  return match ? match[1].split('.').map(Number) : undefined;
}

function versionAtLeast(value, minimum = MINIMUM_BROWSER_VERSION) {
  const left = numericVersion(value);
  const right = numericVersion(minimum);
  if (!left || !right) return false;
  const length = Math.max(left.length, right.length);
  for (let index = 0; index < length; index += 1) {
    if ((left[index] ?? 0) !== (right[index] ?? 0)) return (left[index] ?? 0) > (right[index] ?? 0);
  }
  return true;
}

async function installations() {
  try {
    const module = await import(new URL('../dsh-tabbit/lib/installer/detect.js', import.meta.url));
    return await module.detectTabbitInstallations({ minimumVersion: MINIMUM_BROWSER_VERSION });
  } catch {
    return { installations: [], supportedInstallations: [] };
  }
}

function stableError(error) {
  if (error instanceof AdapterError) return error;
  const code = typeof error?.code === 'string' ? error.code.toLowerCase().replace(/_/gu, '-') : '';
  if (code.includes('instance')) return new AdapterError('instance_selection_required', 409);
  if (code.includes('endpoint') || code.includes('browser')) return new AdapterError('browser_offline', 503);
  return new AdapterError('tabbit_runtime_error', 503);
}

export function createTabbitRuntime(ctx, config = {}, dependencies = {}) {
  const now = dependencies.now ?? Date.now;
  const uuid = dependencies.uuid ?? randomUUID;
  const pathExists = dependencies.existsSync ?? existsSync;
  const detectInstallations = dependencies.installations ?? installations;
  const stash = new Map();
  const grants = new Set();

  function canonicalSessionId(value) {
    return String(value ?? '').replace(/^session-/u, '');
  }

  function hasGrant(agentId) {
    return grants.has(canonicalSessionId(agentId));
  }

  function resolvedInstanceId() {
    try {
      return ctx.tabbit.resolveExecutionInstance()?.id;
    } catch {
      return undefined;
    }
  }

  function sweep() {
    const cutoff = now() - TOKEN_TTL_MS;
    for (const [token, entry] of stash) if (entry.createdAt < cutoff) stash.delete(token);
  }

  async function status() {
    if (config.browserEnabled === false) {
      return { status: 'disabled', pluginVersion: PLUGIN_VERSION, browserVersion: null, launcherPresent: false, onlineInstances: 0, selectedInstance: null, instances: [] };
    }
    const launcherPresent = pathExists(ctx.tabbit.launcherPath());
    const all = ctx.tabbit.instances();
    const online = all.filter((item) => item.online);
    const detected = await detectInstallations();
    const browserVersion = detected.installations.map((item) => item.version).find(Boolean) ?? null;
    const selectedInstance = resolvedInstanceId() ?? (online.length === 1 ? online[0].id : null);
    let state = 'ready';
    if (!launcherPresent) state = 'launcher_missing';
    else if (detected.installations.length > 0 && !detected.installations.some((item) => versionAtLeast(item.version))) state = 'unsupported_version';
    else if (online.length === 0) state = 'browser_offline';
    else if (online.length > 1 && !selectedInstance) state = 'instance_selection_required';
    return {
      status: state,
      pluginVersion: PLUGIN_VERSION,
      browserVersion,
      launcherPresent,
      onlineInstances: online.length,
      selectedInstance,
      instances: all.map((item) => ({ id: item.id, name: item.appName, online: item.online })),
    };
  }

  function decideAccess(sessionId, decision = 'approve') {
    if (typeof sessionId !== 'string' || sessionId.length < 1 || sessionId.length > 160) throw new AdapterError('invalid_session');
    const canonical = canonicalSessionId(sessionId);
    if (decision === 'deny') {
      grants.delete(canonical);
      return { accepted: false };
    }
    if (decision !== 'approve') throw new AdapterError('tabbit_access_rejected', 403);
    ctx.tabbit.grantPageAccess(sessionId);
    ctx.tabbit.grantPageAccess(`session-${sessionId}`);
    grants.add(canonical);
    return { accepted: true };
  }

  async function listTabs({ sessionId, instanceId }) {
    if (!hasGrant(sessionId)) throw new AdapterError('tabbit_page_access_required', 403);
    if (instanceId !== undefined && !INSTANCE.test(instanceId)) throw new AdapterError('tabbit_instance_invalid');
    const online = ctx.tabbit.instances().filter((item) => item.online);
    const selected = instanceId ?? resolvedInstanceId() ?? (online.length === 1 ? online[0].id : undefined);
    const value = await ctx.tabbit.listAllTabs({ ...(selected ? { instanceId: selected } : {}), timeoutMs: 15_000 });
    return { instanceId: selected ?? null, tabs: value.tabs, truncated: value.truncated === true };
  }

  async function extract(input) {
    const { sessionId, requestId, instanceId, tabIds } = input;
    if (!hasGrant(sessionId) && dependencies.allowUngrant !== true) throw new AdapterError('tabbit_page_access_required', 403);
    if (!INSTANCE.test(instanceId)) throw new AdapterError('tabbit_instance_invalid');
    if (!Array.isArray(tabIds) || tabIds.length < 1 || tabIds.length > MAX_TABS || tabIds.some((id) => !Number.isSafeInteger(id) || id < 0)) throw new AdapterError('tabbit_tabs_invalid');
    if (new Set(tabIds).size !== tabIds.length) throw new AdapterError('tabbit_duplicate_tab');
    const client = ctx.tabbit.client();
    const resolved = client.resolvedInstanceId();
    if (resolved !== undefined && resolved !== instanceId) throw new AdapterError('tabbit_instance_mismatch', 409);
    const inventory = await ctx.tabbit.listAllTabs({ instanceId, timeoutMs: 15_000 });
    const expectedTabs = tabIds.map((tabId) => inventory.tabs.find((tab) =>
      tab?.tabId === tabId && tab.state === 'available' && typeof tab.title === 'string' &&
      typeof tab.url === 'string' && (tab.url.startsWith('http://') || tab.url.startsWith('https://'))));
    if (expectedTabs.some((tab) => tab === undefined)) throw new AdapterError('tabbit_tab_unavailable', 409);
    const identities = expectedTabs.map((tab) => `${tab.url}\u0000${tab.title}`);
    if (new Set(identities).size !== identities.length) throw new AdapterError('tabbit_extract_ambiguous', 409);
    const task = taskName(sessionId, requestId);
    let outcome;
    let finishFailure;
    const started = now();
    try {
      outcome = await client.evaluate({
        task,
        code: buildExtractionCode(tabIds.length),
        readOnly: true,
        claimTabs: [...tabIds],
        timeoutMs: 60_000,
        maxResultBytes: 1_500_000,
      });
    } finally {
      try {
        await client.finishTask(task, { keep: true });
      } catch {
        finishFailure = new AdapterError('tabbit_finish_failed', 503);
      }
    }
    if (finishFailure) throw finishFailure;
    if (outcome?.status !== 'succeeded' || !Array.isArray(outcome.result?.value) || outcome.result.value.length !== tabIds.length) throw new AdapterError('tabbit_extract_failed', 503);
    const unordered = outcome.result.value.map((raw) => {
      if (!raw || typeof raw !== 'object' || typeof raw.title !== 'string' || typeof raw.url !== 'string' || typeof raw.text !== 'string' || !raw.url.startsWith('http://') && !raw.url.startsWith('https://')) throw new AdapterError('tabbit_extract_invalid', 503);
      return { title: cleanTitle(raw.title), url: raw.url, text: raw.text, truncated: raw.truncated === true };
    });
    const entries = expectedTabs.map((expected) => {
      const index = unordered.findIndex((entry) => entry.url === expected.url && entry.title === cleanTitle(expected.title));
      if (index < 0) throw new AdapterError('tabbit_extract_invalid', 503);
      return unordered.splice(index, 1)[0];
    });
    sweep();
    const markers = entries.map((entry, index) => {
      const token = uuid();
      stash.set(token, { ...entry, sessionId, createdAt: now() });
      return { tabId: tabIds[index], marker: `@[${entry.title.replace(/\]/gu, '）')}](rwb-tabbit:${token})` };
    });
    ctx.logger.info('Research Tabbit live extraction completed: count=%d duration_ms=%d', markers.length, Math.max(0, now() - started));
    return { markers };
  }

  async function expand(payload, next) {
    const decision = await next();
    if (decision.kind !== 'enter') return decision;
    sweep();
    const tokens = [];
    for (const message of decision.messages) {
      if (message.role !== 'user' || message.source?.kind !== 'user') continue;
      for (const block of message.content) {
        if (block.type !== 'text') continue;
        for (const match of block.text.matchAll(MARKER)) tokens.push(match[2]);
      }
    }
    if (tokens.length === 0) return decision;
    if (new Set(tokens).size !== tokens.length) return { kind: 'reject', reason: 'Research Tabbit token was reused.' };
    const entries = tokens.map((token) => stash.get(token));
    if (entries.some((entry) => !entry || !sessionMatches(payload.agent?.id, entry.sessionId))) return { kind: 'reject', reason: 'Research Tabbit context token is expired, consumed, or belongs to another session.' };
    for (const token of tokens) stash.delete(token);
    let cursor = 0;
    const expanded = [];
    for (const message of decision.messages) {
      if (message.role !== 'user' || message.source?.kind !== 'user') { expanded.push(message); continue; }
      let matched = false;
      const content = message.content.map((block) => {
        if (block.type !== 'text') return block;
        return { ...block, text: block.text.replace(MARKER, (_whole, title) => { matched = true; return `@"${cleanTitle(title).replace(/"/gu, "'")}"`; }) };
      });
      expanded.push(matched ? Object.freeze({ ...message, content }) : message);
      const localCount = message.content.reduce((count, block) => count + (block.type === 'text' ? [...block.text.matchAll(MARKER)].length : 0), 0);
      for (let index = 0; index < localCount; index += 1) expanded.push(pluginMessage(entries[cursor++], uuid));
    }
    return { ...decision, messages: expanded };
  }

  function register() {
    ctx.on('agent/pre-step', expand);
    ctx.on('tools/pre-execute', async (execution, next) => {
      const tabbitTool = execution.name === 'tabbit_browser';
      const fetchTool = execution.name === 'web_fetch' && config.webFetchEnabled === true;
      if (!tabbitTool && !fetchTool) return next();
      const downstream = await next();
      if (downstream.kind !== 'allow') return downstream;
      if (!hasGrant(execution.agent?.id)) {
        return { kind: 'ask', reason: 'Allow this Research Workbench session to access Tabbit Browser pages?' };
      }
      if (fetchTool || execution.arguments?.read_only === true) return downstream;
      return { kind: 'ask', reason: 'Tabbit browser code may change pages or accounts. Approve this write-capable operation?' };
    });
    ctx.on('tools/result', (execution, result) => {
      const tabbitTool = execution.name === 'tabbit_browser';
      const fetchTool = execution.name === 'web_fetch' && config.webFetchEnabled === true;
      if ((tabbitTool || fetchTool) && result.isError !== true && execution.agent?.id !== undefined) {
        grants.add(canonicalSessionId(execution.agent.id));
      }
    });
    ctx.inject(['webServer'], (webCtx) => {
      const routes = [
        ['GET', '/research/tabbit/status', async () => status()],
        ['POST', '/research/tabbit/access', async (req) => {
          const body = await readJson(req);
          return decideAccess(body.sessionId, body.decision);
        }],
        ['GET', '/research/tabbit/tabs', async (req) => {
          const url = new URL(req.url, 'http://localhost');
          return await listTabs({ sessionId: url.searchParams.get('session') ?? '', instanceId: url.searchParams.get('instance') ?? undefined });
        }],
        ['POST', '/research/tabbit/live-extract', async (req) => extract(await readJson(req))],
      ];
      for (const [method, path, operation] of routes) {
        webCtx.webServer.register({ kind: 'exact', path, handler: async (req, res) => {
          if (!hostAllowed(req)) return sendJson(res, 403, { error: 'forbidden' });
          if (req.method !== method) return sendJson(res, 405, { error: 'method_not_allowed' });
          try {
            sendJson(res, 200, await operation(req));
          } catch (error) {
            const safe = stableError(error);
            ctx.logger.warn('Research Tabbit route failed: route=%s code=%s', path, safe.code);
            sendJson(res, safe.status, { error: safe.code });
          }
        } });
      }
    });
  }

  return { stash, grants, status, grantAccess: (sessionId) => decideAccess(sessionId), decideAccess, listTabs, extract, expand, register };
}

export function apply(ctx, config = {}) {
  createTabbitRuntime(ctx, config).register();
}
