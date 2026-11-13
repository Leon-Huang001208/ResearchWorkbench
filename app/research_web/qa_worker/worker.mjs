// Private, single-turn transport. The Research Web Host owns authorization and storage.
import { runAgent, TurnError } from './agent.mjs';

const FRAME_BYTES = 1024 * 1024;
const OUTPUT_BYTES = 16 * FRAME_BYTES;
const TOOL_NAME = /^[a-zA-Z0-9_-]{1,64}$/;
const TOOL_ID = /^[a-zA-Z0-9_.:-]{1,128}$/;
const MODES = new Set(['quick', 'deep', 'agent']);
const decoder = new TextDecoder('utf-8', { fatal: true });

class ProtocolError extends Error {}
class HostError extends Error {
  constructor(code) {
    super(code);
    this.code = code;
  }
}

const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

async function* readFrames() {
  let pieces = [];
  let bytes = 0;
  for await (const chunk of process.stdin) {
    let offset = 0;
    while (offset < chunk.length) {
      const newline = chunk.indexOf(10, offset);
      const piece = chunk.subarray(offset, newline < 0 ? chunk.length : newline);
      bytes += piece.length;
      if (bytes > FRAME_BYTES) throw new ProtocolError();
      pieces.push(piece);
      if (newline < 0) break;
      let frame;
      try {
        frame = JSON.parse(decoder.decode(Buffer.concat(pieces, bytes)));
      } catch {
        throw new ProtocolError();
      }
      if (!isObject(frame)) throw new ProtocolError();
      pieces = [];
      bytes = 0;
      offset = newline + 1;
      yield frame;
    }
  }
  if (bytes) throw new ProtocolError();
}

let written = 0;
function writeFrame(frame) {
  const line = JSON.stringify(frame) + '\n';
  const bytes = Buffer.byteLength(line);
  if (bytes > FRAME_BYTES || written + bytes > OUTPUT_BYTES) throw new ProtocolError();
  written += bytes;
  process.stdout.write(line);
}

function startFrame(frame) {
  if (frame?.type !== 'start' || !MODES.has(frame.mode) ||
      typeof frame.question !== 'string' || !frame.question.trim() || frame.question.length > 100_000 ||
      !Array.isArray(frame.tools) || frame.tools.length > 32) {
    throw new ProtocolError();
  }
  const names = new Set();
  for (const item of frame.tools) {
    const fn = item?.function;
    if (item?.type !== 'function' || typeof fn?.name !== 'string' || !TOOL_NAME.test(fn.name) ||
        names.has(fn.name) || !isObject(fn.parameters)) throw new ProtocolError();
    names.add(fn.name);
  }
  const { history = [], framework = null } = frame;
  if (!Array.isArray(history) || history.length > 32 || history.some(message =>
    !['user', 'assistant'].includes(message?.role) || typeof message.content !== 'string')) {
    throw new ProtocolError();
  }
  if (framework !== null && (
    !isObject(framework) || typeof framework.name !== 'string' || typeof framework.text !== 'string' ||
    JSON.stringify(framework).length > 32_000
  )) throw new ProtocolError();
  return frame;
}

function modelResult(value) {
  if (typeof value.content !== 'string' || value.content.length > 128_000 ||
      (value.reasoningContent !== undefined &&
        (typeof value.reasoningContent !== 'string' || value.reasoningContent.length > 128_000)) ||
      !Array.isArray(value.toolCalls) || value.toolCalls.length > 8) throw new ProtocolError();
  const ids = new Set();
  for (const item of value.toolCalls) {
    const fn = item?.function;
    if (item?.type !== 'function' || typeof item.id !== 'string' || !TOOL_ID.test(item.id) ||
        ids.has(item.id) || typeof fn?.name !== 'string' || !TOOL_NAME.test(fn.name) ||
        typeof fn.arguments !== 'string' || fn.arguments.length > 32_768) throw new ProtocolError();
    ids.add(item.id);
  }
  return value;
}

const frames = readFrames();
let nextCall = 0;
async function request(method, params, onContent) {
  const id = ++nextCall;
  writeFrame({ type: 'call', id, method, params });
  let streamed = 0;
  while (true) {
    const { value: frame, done } = await frames.next();
    if (done || frame.id !== id) throw new ProtocolError();
    if (frame.type === 'delta' && method === 'model' && typeof frame.content === 'string') {
      streamed += frame.content.length;
      if (streamed > 128_000) throw new ProtocolError();
      onContent?.(frame.content);
      continue;
    }
    if (frame.type === 'result' && isObject(frame.result)) return frame.result;
    if (frame.type === 'error' && isObject(frame.error)) {
      throw new HostError(typeof frame.error.code === 'string' && /^[a-z0-9_]{1,80}$/.test(frame.error.code)
        ? frame.error.code : 'qa_host_call_failed');
    }
    throw new ProtocolError();
  }
}

try {
  const { value } = await frames.next();
  const start = startFrame(value);
  await runAgent({
    ...start,
    emit: (event, data) => writeFrame({ type: 'event', event, data }),
    async chatStream({ onContent, ...params }) {
      return modelResult(await request('model', params, onContent));
    },
    async runTool(name, args, toolCallId) {
      try {
        return await request('tool', { name, arguments: args, toolCallId });
      } catch (error) {
        if (error instanceof HostError) return { errorCode: error.code };
        throw error;
      }
    },
  });
  writeFrame({ type: 'done' });
} catch (error) {
  const code = error instanceof ProtocolError ? 'qa_worker_protocol'
    : error instanceof HostError ? error.code
      : error instanceof TurnError ? error.message : 'qa_worker_failed';
  process.stdout.write(JSON.stringify({ type: 'failed', code }) + '\n');
  process.exitCode = 1;
} finally {
  process.stdin.destroy();
}
