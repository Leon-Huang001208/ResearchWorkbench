/** Fixed model refs use OS Keychain; inherited records retain DSH's lock/lifecycle. */
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export const MODEL_REF = 'RESEARCH_DSH_API_KEY';
export const COMPATIBLE_REF = 'RESEARCH_COMPAT_API_KEY';
const MODEL_REFS = new Set([MODEL_REF, COMPATIBLE_REF]);

export function processBridge(config, op, value, ref = MODEL_REF) {
  if (!MODEL_REFS.has(ref)) return Promise.reject(Error('model_credential_ref_denied'));
  return new Promise((resolve, reject) => {
    const child = spawn(config.python, ['-I', '-B', config.bridge, '--data-home', config.dataHome], {
      cwd: '/', env: { PATH: '/usr/bin:/bin', LANG: 'en_US.UTF-8' }, stdio: ['pipe', 'pipe', 'pipe'],
    });
    let output = '';
    let failed = false;
    child.stdout.setEncoding('utf8');
    const timer = setTimeout(() => { failed = true; child.kill('SIGKILL'); }, 20000);
    child.on('error', () => { failed = true; });
    child.stdin.on('error', () => { failed = true; });
    child.stdout.on('data', chunk => {
      output += chunk;
      if (output.length > 8192) { failed = true; child.kill('SIGKILL'); }
    });
    // Drain but never forward secret-bearing backend diagnostics.
    child.stderr.resume();
    child.on('close', code => {
      clearTimeout(timer);
      try {
        const result = JSON.parse(output);
        if (failed || code !== 0 || result.ok !== true) throw Error();
        resolve(result);
      } catch { reject(Error('model_credential_bridge_failed')); }
    });
    child.stdin.end(JSON.stringify({ op, ref, ...(op === 'set' ? { value } : {}) }));
  });
}

export function createProvider(LocalProvider, bridge) {
  return class ModelCredentialProvider extends LocalProvider {
    // The file provider's schema must not discard the launcher's private binding.
    static Config = undefined;
    constructor(ctx, config) {
      // Distinct file, used only for the existing Host authentication records.
      super(ctx, { path: config.recordsPath, watch: true });
    }
    readRecord(key) {
      if (MODEL_REFS.has(key)) throw Error('model_credential_record_denied');
      return super.readRecord(key);
    }
    modifyRecord(key, mutate) {
      if (MODEL_REFS.has(key)) throw Error('model_credential_record_denied');
      return super.modifyRecord(key, mutate);
    }
    async modelCall(ref, op, value) {
      if (!MODEL_REFS.has(ref)) throw Error('model_credential_ref_denied');
      try { return await bridge(op, value, ref); }
      catch {
        this.ctx.logger.warn('model_credential_bridge_failed');
        throw Error('model_credential_bridge_failed');
      }
    }
    async resolve(ref) {
      const result = await this.modelCall(ref, 'resolve');
      if (result.value === null) return undefined;
      if (typeof result.value !== 'string' || !result.value || result.value.length > 1024) {
        throw Error('model_credential_bridge_failed');
      }
      return { value: result.value, source: 'system-keychain' };
    }
    async describe(ref) {
      const result = await this.modelCall(ref, 'describe');
      if (typeof result.configured !== 'boolean' || result.source !== 'system-keychain' || result.writable !== true) {
        throw Error('model_credential_bridge_failed');
      }
      return { configured: result.configured, source: result.source, writable: true };
    }
    async set(ref, value) {
      if (typeof value !== 'string' || !value || value.length > 1024) throw Error('model_credential_request_invalid');
      await this.modelCall(ref, 'set', value);
      this.notifyUpdated(ref);
    }
    async unset(ref) {
      await this.modelCall(ref, 'unset');
      this.notifyUpdated(ref);
    }
  };
}

export async function apply(ctx, config) {
  // This path is bound exclusively by the owned launcher to the pinned build.
  const { default: LocalProvider } = await import(pathToFileURL(config.localProvider).href);
  await ctx.plugin(createProvider(LocalProvider, (op, value, ref) => processBridge(config, op, value, ref)), config);
}
