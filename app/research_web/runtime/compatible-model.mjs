/** One text/streaming OpenAI-compatible route; fixed DSH owns the agent loop. */
import { pathToFileURL } from 'node:url';
import { isAbsolute } from 'node:path';
import { COMPATIBLE_REF } from './model-credentials.mjs';
import { readModelConnection } from './public-data.mjs';
export { COMPATIBLE_REF };
export const inject = ['llm'];
const MAX_WIRE = 1024 * 1024;
const MAX_TEXT = 65536;

export function validateConnection(value) {
  if (!value || value.provider !== 'openai-compatible' || value.protocol !== 'openai-completions' ||
      !['none', 'api_key'].includes(value.credential_mode) ||
      typeof value.model !== 'string' || !/^[a-zA-Z0-9._:/-]{1,100}$/.test(value.model) ||
      typeof value.base_url !== 'string' || value.base_url.length > 2048 ||
      /[\x00-\x20\x7f-\x9f?#]/.test(value.base_url)) throw Error('compatible_connection_invalid');
  let url;
  try { url = new URL(value.base_url); } catch { throw Error('compatible_connection_invalid'); }
  const local = ['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname);
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.port === '0' || (url.protocol === 'http:' && !local) || (value.credential_mode === 'none' && !local) ||
      (value.revision !== undefined && (typeof value.revision !== 'string' || !/^[0-9a-f]{32}$/.test(value.revision)))) throw Error('compatible_connection_invalid');
  return Object.freeze({ ...value, base_url: url.href.replace(/\/$/, '') });
}

function requestMessages(options) {
  if (!Array.isArray(options.messages) || options.messages.length > 2000) throw Error('compatible_messages_invalid');
  const messages = [];
  if (options.system !== undefined) {
    if (typeof options.system !== 'string') throw Error('compatible_messages_invalid');
    messages.push({ role: 'system', content: options.system });
  }
  for (const message of options.messages) {
    if (!message || !['system', 'developer', 'user', 'assistant'].includes(message.role)) throw Error('compatible_text_only');
    let content = message.content;
    if (Array.isArray(content)) {
      const parts = [];
      for (const block of content) {
        if (block?.type === 'text' && typeof block.text === 'string') parts.push(block.text);
        else if (block?.type === 'reasoning' && message.role === 'assistant') continue;
        else if (['tool-addition', 'tool-removal'].includes(block?.type) && message.role === 'developer') continue;
        else throw Error('compatible_text_only');
      }
      content = parts.join('\n');
    }
    if (typeof content !== 'string') throw Error('compatible_messages_invalid');
    if (content) messages.push({ role: message.role === 'developer' ? 'system' : message.role, content });
  }
  if (!messages.length) throw Error('compatible_messages_invalid');
  return messages;
}

/** No retries or redirects. Keyless mode never consults the credential seam. */
export async function* streamCompletion(rawConnection, options, dependencies = {}) {
  let reader;
  let signal;
  try {
    const connection = validateConnection(rawConnection);
    if (options.model !== connection.model) throw Error('compatible_model_unavailable');
    options.signal?.throwIfAborted();
    const attribution = dependencies.attributionHeaders?.() || {};
    if (Object.keys(attribution).some(key => ['authorization', 'cookie', 'proxy-authorization'].includes(key.toLowerCase()))) throw Error('compatible_attribution_invalid');
    const headers = { ...attribution, 'Content-Type': 'application/json', Accept: 'text/event-stream' };
    if (connection.credential_mode === 'api_key') {
      let key;
      try { key = await dependencies.resolveKey?.(); }
      catch { throw Error('compatible_credentials_unavailable'); }
      if (typeof key !== 'string' || !key || key.length > 1024 || /[\r\n]/.test(key)) throw Error('compatible_credentials_missing');
      headers.Authorization = `Bearer ${key}`;
    }
    const body = JSON.stringify({ model: connection.model, messages: requestMessages(options), stream: true,
      max_tokens: Math.min(Number.isInteger(options.maxTokens) && options.maxTokens > 0 ? options.maxTokens : 1024, 4096) });
    if (Buffer.byteLength(body) > 262144) throw Error('compatible_request_too_large');
    const timeout = AbortSignal.timeout(90000);
    signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;
    signal.throwIfAborted();
    const response = await (dependencies.fetch || globalThis.fetch)(`${connection.base_url}/chat/completions`, {
      method: 'POST', headers, body, redirect: 'error', signal,
    });
    if (!response.ok || !response.headers.get('content-type')?.toLowerCase().startsWith('text/event-stream') || !response.body) {
      await response.body?.cancel(); throw Error('compatible_http_failed');
    }
    reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8', { fatal: true });
    let buffer = '', text = '', received = 0, started = false, done = false, finish;
    while (!done) {
      signal.throwIfAborted();
      const part = await reader.read();
      signal.throwIfAborted();
      if (part.done) break;
      received += part.value.byteLength;
      if (received > MAX_WIRE) throw Error('compatible_response_too_large');
      buffer += decoder.decode(part.value, { stream: true });
      if (buffer.length > MAX_WIRE) throw Error('compatible_response_too_large');
      let boundary;
      while ((boundary = buffer.search(/\r?\n\r?\n/)) !== -1) {
        signal.throwIfAborted();
        const separator = buffer.slice(boundary).match(/^\r?\n\r?\n/)[0];
        const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + separator.length);
        const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).trimStart()).join('\n');
        if (!data) continue;
        if (data === '[DONE]') { done = true; break; }
        let value; try { value = JSON.parse(data); } catch { throw Error('compatible_stream_invalid'); }
        if (!value || value.error || !Array.isArray(value.choices) || value.choices.length > 1) throw Error('compatible_stream_invalid');
        if (!value.choices.length) continue; // Optional usage frame, not proof of success.
        const choice = value.choices[0];
        if (choice.index !== 0 || !choice.delta || typeof choice.delta !== 'object' || Array.isArray(choice.delta) || choice.delta.tool_calls) throw Error('compatible_text_only');
        if (choice.delta.content !== undefined && choice.delta.content !== null) {
          if (typeof choice.delta.content !== 'string' || finish) throw Error('compatible_stream_invalid');
          if (choice.delta.content) {
            if (!started) { started = true; yield { type: 'block-start', index: 0, blockType: 'text' }; }
            signal.throwIfAborted();
            text += choice.delta.content;
            if (Buffer.byteLength(text) > MAX_TEXT) throw Error('compatible_response_too_large');
            yield { type: 'text-delta', index: 0, text: choice.delta.content };
            signal.throwIfAborted();
          }
        }
        if (choice.finish_reason != null) {
          if (!['stop', 'length'].includes(choice.finish_reason) || finish) throw Error('compatible_finish_invalid');
          finish = choice.finish_reason;
        }
      }
    }
    if (!done || !finish || !started) throw Error('compatible_stream_incomplete');
    signal.throwIfAborted();
    yield { type: 'block-end', index: 0, block: { type: 'text', text } };
    signal.throwIfAborted();
    yield { type: 'finish', reason: { kind: finish === 'length' ? 'max-tokens' : 'stop' } };
  } catch (error) {
    dependencies.logger?.warn('research_compatible_generation_failed');
    if (options.signal?.aborted) throw Error('compatible_generation_cancelled');
    if (signal?.aborted) throw Error('compatible_generation_timeout');
    if (error instanceof Error && /^compatible_[a-z_]+$/.test(error.message)) throw error;
    // Network, SDK or supplier diagnostics may contain URLs, headers or payloads.
    throw Error('compatible_http_failed');
  } finally {
    if (reader) { try { await reader.cancel(); } catch { dependencies.logger?.warn('research_compatible_stream_cleanup_failed'); } }
  }
}

/** Existing native adapter interface; no second agent loop or credential store. */
export function createAdapter(Base, dependencies) {
  const generation = value => JSON.stringify([value.provider, value.protocol, value.base_url, value.model, value.credential_mode, value.revision ?? null]);
  const read = async signal => {
    signal?.throwIfAborted();
    const value = await dependencies.readConnection(signal);
    signal?.throwIfAborted();
    if (value === null) throw Error('compatible_connection_missing');
    return validateConnection(value);
  };
  const metadata = (provider, model) => {
    if (provider !== 'openai-compatible' || typeof model !== 'string' || !/^[a-zA-Z0-9._:/-]{1,100}$/.test(model)) throw Error('compatible_model_unavailable');
    return { provider, id: model, name: model, inputModalities: ['text'] };
  };
  return new class extends Base {
    providerInfo() { return { id: 'openai-compatible', name: 'OpenAI 兼容 · 文本/流式' }; }
    providerRetryPolicy() { return { mode: 'normal', maxRetries: 0, retryableCodes: [], initialDelayMs: 1000, maxDelayMs: 1000, jitterRatio: 0 }; }
    async listModels() {
      try {
        const value = await dependencies.readConnection();
        if (value === null) throw Error('compatible_connection_missing');
        const connection = validateConnection(value);
        return [{ provider: 'openai-compatible', id: connection.model, name: connection.model, inputModalities: ['text'] }];
      } catch { dependencies.logger?.warn('research_compatible_catalog_unavailable'); throw Error('compatible_catalog_unavailable'); }
    }
    async prepareCall(provider, model, signal) {
      const info = metadata(provider, model);
      const value = await read(signal);
      let key;
      if (value.credential_mode === 'api_key') {
        try { key = await dependencies.resolveKey?.(); }
        catch { throw Error('compatible_credentials_unavailable'); }
        if (typeof key !== 'string' || !key || key.length > 1024) throw Error('compatible_credentials_missing');
        if (generation(value) !== generation(await read(signal))) throw Error('compatible_connection_changed');
      }
      const connection = validateConnection({ ...value, model });
      return {
        model: info,
        stream: async function* (options) {
          if (generation(value) !== generation(await read(options.signal))) throw Error('compatible_connection_changed');
          yield* streamCompletion(connection, options, { ...dependencies, resolveKey: async () => key });
        },
      };
    }
    async resolveModel(provider, model, signal) { const info = metadata(provider, model); await read(signal); return info; }
    async *stream(options) { yield* (await this.prepareCall(options.provider, options.model, options.signal)).stream(options); }
  }();
}

export async function apply(ctx, config) {
  if (typeof config.nativeLlmModule !== 'string' || !isAbsolute(config.nativeLlmModule) || typeof config.dataHome !== 'string' || !isAbsolute(config.dataHome)) throw Error('compatible_binding_invalid');
  const { LlmAdapter, attributionHeaders } = await import(pathToFileURL(config.nativeLlmModule).href);
  const adapter = createAdapter(LlmAdapter, {
    logger: ctx.logger,
    attributionHeaders,
    readConnection: signal => readModelConnection(config.dataHome, signal),
    resolveKey: async () => {
      const credentials = ctx.get('credentials');
      if (!credentials) throw Error('compatible_credentials_unavailable');
      return (await credentials.resolve(COMPATIBLE_REF))?.value;
    },
  });
  ctx.effect(() => ctx.llm.registerAdapter(['openai-compatible'], adapter));
}
