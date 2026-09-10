/** Register immutable MCP bindings backed by Research Web's private loopback host. */
import {
  closeSync,
  constants as fsConstants,
  fstatSync,
  lstatSync,
  openSync,
  readFileSync,
} from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

export const name = 'research-mcp-adapter';
export const inject = ['tools'];

const CONTROL_BYTES = 4096;
const SCHEMA_BYTES = 64 * 1024;
const DEFAULT_REQUEST_BYTES = 256 * 1024;
const DEFAULT_RESPONSE_BYTES = 1024 * 1024;
const DEFAULT_TIMEOUT_MS = 60_000;
const MAX_REQUEST_BYTES = 1024 * 1024;
const MAX_RESPONSE_BYTES = 4 * 1024 * 1024;
const MAX_TIMEOUT_MS = 120_000;
const MAX_BINDINGS = 256;
const MAX_DEPTH = 32;
const MAX_NODES = 8192;
const TOKEN = /^[A-Za-z0-9_-]{43,128}$/u;
const INSTALLATION = /^mcp-installation-[a-f0-9]{32}$/u;
const IDENTIFIER = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$/u;
const DIGEST = /^[a-f0-9]{64}$/u;

function fail(code) {
  throw new Error(`Research MCP adapter ${code}`);
}

function privateIdentity(path, identity, kind) {
  if (kind === 'file') {
    if (!identity.isFile() || identity.isSymbolicLink() || identity.nlink !== 1) {
      fail('control file is invalid');
    }
    if (identity.size < 2 || identity.size > CONTROL_BYTES) fail('control file is invalid');
  } else if (!identity.isDirectory() || identity.isSymbolicLink()) {
    fail('control directory is invalid');
  }
  if (process.platform !== 'win32' && (identity.mode & 0o077) !== 0) {
    fail(`control ${kind} permissions are invalid`);
  }
  if (typeof process.getuid === 'function' && identity.uid !== process.getuid()) {
    fail(`control ${kind} owner is invalid`);
  }
}

function sameIdentity(left, right) {
  return left.dev === right.dev && left.ino === right.ino && left.size === right.size;
}

function loopbackOrigin(value) {
  if (typeof value !== 'string' || value.length > 256 || /[\u0000-\u001f\u007f]/u.test(value)) {
    fail('control URL is invalid');
  }
  let url;
  try {
    url = new URL(value);
  } catch {
    fail('control URL is invalid');
  }
  if (
    url.protocol !== 'http:' ||
    !['127.0.0.1', '[::1]'].includes(url.hostname) ||
    !url.port ||
    url.username ||
    url.password ||
    url.pathname !== '/' ||
    url.search ||
    url.hash ||
    value !== url.origin
  ) {
    fail('control URL is invalid');
  }
  return url.origin;
}

function readControl(researchRoot) {
  if (typeof researchRoot !== 'string' || !isAbsolute(researchRoot)) {
    fail('requires an absolute researchRoot');
  }
  const root = resolve(researchRoot);
  const folder = join(root, '.control');
  const path = join(folder, 'mcp-runtime.json');
  let directory;
  let before;
  try {
    directory = lstatSync(folder);
    before = lstatSync(path);
  } catch {
    fail('control file is unavailable');
  }
  privateIdentity(folder, directory, 'directory');
  privateIdentity(path, before, 'file');

  let descriptor;
  let raw;
  try {
    descriptor = openSync(path, fsConstants.O_RDONLY | (fsConstants.O_NOFOLLOW ?? 0));
    const opened = fstatSync(descriptor);
    privateIdentity(path, opened, 'file');
    if (!sameIdentity(before, opened)) fail('control file changed before open');
    raw = readFileSync(descriptor);
  } catch (error) {
    if (String(error?.message ?? '').startsWith('Research MCP adapter ')) throw error;
    fail('control file is unavailable');
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
  }
  let after;
  try {
    after = lstatSync(path);
  } catch {
    fail('control file changed during read');
  }
  if (raw.length > CONTROL_BYTES || !sameIdentity(before, after)) {
    fail('control file changed during read');
  }

  let value;
  try {
    value = JSON.parse(raw.toString('utf8'));
  } catch {
    fail('control file is invalid');
  }
  if (!plainObject(value)) fail('control file is invalid');
  const keys = Object.keys(value).sort();
  const expected = value.version === undefined ? ['token', 'url'] : ['token', 'url', 'version'];
  if (
    keys.length !== expected.length ||
    keys.some((key, index) => key !== expected[index]) ||
    (value.version !== undefined && value.version !== 1) ||
    typeof value.token !== 'string' ||
    !TOKEN.test(value.token)
  ) {
    fail('control file is invalid');
  }
  return Object.freeze({ url: loopbackOrigin(value.url), token: value.token });
}

function plainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const prototype = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
}

function validateJson(root, maximum, code) {
  const stack = [[root, 0]];
  const seen = new Set();
  let nodes = 0;
  while (stack.length > 0) {
    const [value, depth] = stack.pop();
    nodes += 1;
    if (nodes > MAX_NODES || depth > MAX_DEPTH) fail(code);
    if (Array.isArray(value)) {
      if (seen.has(value)) fail(code);
      seen.add(value);
      for (const child of value) stack.push([child, depth + 1]);
    } else if (plainObject(value)) {
      if (seen.has(value)) fail(code);
      seen.add(value);
      for (const [key, child] of Object.entries(value)) {
        if (['__proto__', 'prototype', 'constructor'].includes(key)) fail(code);
        stack.push([child, depth + 1]);
      }
    } else if (
      value !== null &&
      typeof value !== 'string' &&
      typeof value !== 'boolean' &&
      !(typeof value === 'number' && Number.isFinite(value))
    ) {
      fail(code);
    }
  }
  let encoded;
  try {
    encoded = JSON.stringify(root);
  } catch {
    fail(code);
  }
  if (Buffer.byteLength(encoded) > maximum) fail(code);
  return encoded;
}

function immutableJson(value, maximum, code) {
  return deepFreeze(JSON.parse(validateJson(value, maximum, code)));
}

function deepFreeze(value) {
  if (value && typeof value === 'object' && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

function validateBindings(raw) {
  if (!Array.isArray(raw) || raw.length > MAX_BINDINGS) fail('bindings are invalid');
  const names = new Set();
  return raw.map((candidate) => {
    if (!plainObject(candidate)) fail('binding is invalid');
    const allowed = new Set([
      'name', 'installation_id', 'version', 'tool_name', 'schema_sha256', 'description', 'input_schema',
    ]);
    if (Object.keys(candidate).some(key => !allowed.has(key))) fail('binding is invalid');
    const { name: toolNamespace, installation_id: installationId, version, tool_name: toolName } = candidate;
    if (typeof toolNamespace === 'string' && names.has(toolNamespace)) {
      fail('duplicate binding is invalid');
    }
    if (
      typeof toolNamespace !== 'string' ||
      typeof installationId !== 'string' ||
      !INSTALLATION.test(installationId) ||
      typeof version !== 'string' ||
      !IDENTIFIER.test(version) ||
      typeof toolName !== 'string' ||
      !IDENTIFIER.test(toolName) ||
      toolNamespace !== `mcp__${installationId}__${toolName}` ||
      typeof candidate.schema_sha256 !== 'string' ||
      !DIGEST.test(candidate.schema_sha256) ||
      typeof candidate.description !== 'string' ||
      Buffer.byteLength(candidate.description) > 4096 ||
      candidate.description.includes('\u0000') ||
      !plainObject(candidate.input_schema) ||
      candidate.input_schema.type !== 'object'
    ) {
      fail('binding is invalid');
    }
    names.add(toolNamespace);
    return Object.freeze({
      name: toolNamespace,
      installationId,
      version,
      toolName,
      schemaSha256: candidate.schema_sha256,
      description: candidate.description,
      inputSchema: immutableJson(candidate.input_schema, SCHEMA_BYTES, 'binding schema is invalid'),
    });
  });
}

function checkedLimit(value, fallback, maximum, code) {
  const selected = value ?? fallback;
  if (!Number.isSafeInteger(selected) || selected < 1 || selected > maximum) fail(code);
  return selected;
}

async function responseBytes(response, maximum) {
  const length = response.headers.get('content-length');
  if (length !== null && (!/^\d+$/u.test(length) || Number(length) > maximum)) {
    fail('response is too large');
  }
  if (!response.body || typeof response.body.getReader !== 'function') fail('response is invalid');
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maximum) {
      await reader.cancel().catch(() => {});
      fail('response is too large');
    }
    chunks.push(Buffer.from(value));
  }
  return Buffer.concat(chunks, size);
}

function executionIdentity(exec) {
  const callId = exec?.callId;
  const sessionId = exec?.agent?.session?.header?.id;
  if (
    typeof callId !== 'string' ||
    typeof sessionId !== 'string' ||
    !IDENTIFIER.test(callId) ||
    !IDENTIFIER.test(sessionId)
  ) {
    fail('execution identity is invalid');
  }
  if (!(exec.signal instanceof AbortSignal)) fail('execution signal is invalid');
  return { callId, sessionId };
}

async function proxyCall(ctx, control, binding, args, exec, limits) {
  const { callId, sessionId } = executionIdentity(exec);
  if (!plainObject(args)) fail('tool arguments are invalid');
  validateJson(args, limits.requestBytes, 'tool arguments are invalid');
  const body = JSON.stringify({
    call_id: callId,
    session_id: sessionId,
    installation_id: binding.installationId,
    version: binding.version,
    tool_name: binding.toolName,
    schema_sha256: binding.schemaSha256,
    arguments: args,
  });
  if (Buffer.byteLength(body) > limits.requestBytes) fail('request is too large');

  exec.signal.throwIfAborted();
  const controller = new AbortController();
  const abort = () => controller.abort(exec.signal.reason);
  exec.signal.addEventListener('abort', abort, { once: true });
  const deadline = setTimeout(() => controller.abort(new Error('mcp_call_timeout')), limits.timeoutMs);
  ctx.logger.info('research_mcp_tool_started');
  try {
    const response = await fetch(`${control.url}/api/research/internal/mcp/tools/call`, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'accept': 'application/json',
        'X-Research-MCP-Key': control.token,
      },
      body,
      redirect: 'error',
      credentials: 'omit',
      cache: 'no-store',
      signal: controller.signal,
    });
    if (!response.ok || response.status !== 200) fail('host request failed');
    const contentType = response.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase();
    if (contentType !== 'application/json') fail('host response is invalid');
    let envelope;
    try {
      envelope = JSON.parse((await responseBytes(response, limits.responseBytes)).toString('utf8'));
    } catch (error) {
      if (String(error?.message ?? '').startsWith('Research MCP adapter ')) throw error;
      fail('host response is invalid');
    }
    if (!plainObject(envelope) || envelope.status !== 'complete' || !plainObject(envelope.result)) {
      fail('host response is invalid');
    }
    const resultJson = validateJson(envelope.result, limits.responseBytes, 'host response is invalid');
    ctx.logger.info('research_mcp_tool_finished');
    return { result_json: resultJson };
  } catch (error) {
    ctx.logger.warn('research_mcp_tool_failed');
    if (String(error?.message ?? '').startsWith('Research MCP adapter ')) throw error;
    throw new Error('Research MCP adapter host request failed');
  } finally {
    clearTimeout(deadline);
    exec.signal.removeEventListener('abort', abort);
  }
}

export function apply(ctx, config = {}) {
  if (!ctx?.tools || typeof ctx.tools.register !== 'function') fail('tool registry is invalid');
  if (!plainObject(config)) fail('configuration is invalid');
  const bindings = validateBindings(config.bindings);
  const limits = Object.freeze({
    requestBytes: checkedLimit(
      config.maxRequestBytes,
      DEFAULT_REQUEST_BYTES,
      MAX_REQUEST_BYTES,
      'request limit is invalid',
    ),
    responseBytes: checkedLimit(
      config.maxResponseBytes,
      DEFAULT_RESPONSE_BYTES,
      MAX_RESPONSE_BYTES,
      'response limit is invalid',
    ),
    timeoutMs: checkedLimit(
      config.timeoutMs,
      DEFAULT_TIMEOUT_MS,
      MAX_TIMEOUT_MS,
      'timeout is invalid',
    ),
  });
  // The adapter is present in the stable preset even while MCP Runtime is
  // disabled. Do not require a control secret until at least one binding is
  // activated for the next DSH start.
  if (bindings.length === 0) return;
  const control = readControl(config.researchRoot);
  for (const binding of bindings) {
    ctx.tools.register({
      name: binding.name,
      description: binding.description,
      parameters: binding.inputSchema,
      async execute(args, exec) {
        return await proxyCall(ctx, control, binding, args, exec, limits);
      },
    });
  }
}
