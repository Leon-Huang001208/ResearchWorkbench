/** Launcher-bound model backend; inherited records retain DSH's lock/lifecycle. */
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

export const MODEL_REF = 'RESEARCH_DSH_API_KEY';

const sources = new Set(['system-keychain', 'docker-private-file']);
function bridgeArguments(config) {
  const source = config.source === undefined ? 'system-keychain' : config.source;
  const args = ['-I', '-B', config.bridge, '--data-home', config.dataHome];
  if (!sources.has(source)) throw Error('model_credential_bridge_failed');
  if (source === 'system-keychain') {
    if (config.credentialRoot !== undefined || config.installationId !== undefined) throw Error('model_credential_bridge_failed');
  } else {
    if (typeof config.installationId !== 'string' || !/^[a-f0-9]{32}$/.test(config.installationId) ||
        config.credentialRoot !== `/run/rwb-secrets/private/models/${config.installationId}`) {
      throw Error('model_credential_bridge_failed');
    }
    args.push('--backend', source, '--credential-root', config.credentialRoot, '--installation-id', config.installationId);
  }
  return args;
}

export function processBridge(config, op, value) {
  return new Promise((resolve, reject) => {
    let args;
    try { args = bridgeArguments(config); }
    catch { reject(Error('model_credential_bridge_failed')); return; }
    const child = spawn(config.python, args, {
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
        if (!failed && code === 1 && result.ok === false && result.error === 'model_credential_commit_uncertain' &&
            config.source === 'docker-private-file') {
          reject(Error('model_credential_commit_uncertain')); return;
        }
        if (failed || code !== 0 || result.ok !== true) throw Error();
        resolve(result);
      } catch { reject(Error('model_credential_bridge_failed')); }
    });
    child.stdin.end(JSON.stringify({ op, ref: MODEL_REF, ...(op === 'set' ? { value } : {}) }));
  });
}

export function createProvider(LocalProvider, bridge, source = 'system-keychain') {
  return class ModelCredentialProvider extends LocalProvider {
    // The file provider's schema must not discard the launcher's private binding.
    static Config = undefined;
    constructor(ctx, config) {
      // Distinct file, used only for the existing Host authentication records.
      super(ctx, { path: config.recordsPath, watch: true });
    }
    async modelCall(ref, op, value) {
      if (ref !== MODEL_REF) throw Error('model_credential_ref_denied');
      if (!sources.has(source)) throw Error('model_credential_bridge_failed');
      try { return await bridge(op, value); }
      catch (error) {
        if (source === 'docker-private-file' && error?.message === 'model_credential_commit_uncertain') {
          this.ctx.logger.warn('model_credential_commit_uncertain');
          throw Error('model_credential_commit_uncertain');
        }
        this.ctx.logger.warn('model_credential_bridge_failed');
        throw Error('model_credential_bridge_failed');
      }
    }
    async resolve(ref) {
      const result = await this.modelCall(ref, 'resolve');
      if (result.source !== undefined && result.source !== source) throw Error('model_credential_bridge_failed');
      if (result.value === null) return undefined;
      if (typeof result.value !== 'string' || !result.value || result.value.length > 1024) {
        throw Error('model_credential_bridge_failed');
      }
      return { value: result.value, source };
    }
    async describe(ref) {
      const result = await this.modelCall(ref, 'describe');
      if (typeof result.configured !== 'boolean' || result.source !== source || result.writable !== true) {
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
  await ctx.plugin(createProvider(LocalProvider, (op, value) => processBridge(config, op, value), config.source), config);
}
