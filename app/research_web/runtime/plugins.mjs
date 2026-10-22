/** Reviewed instructions from the immutable, per-session plugin snapshot.
 * No independent model or agent loop; delegation uses the authorized native subagent.
 * Agent templates can be passed to DSH's existing subagent tool by the model;
 * this adapter never claims native Claude/Codex model/tool/permission parity.
 */
import { constants, openSync, fstatSync, readFileSync, closeSync, lstatSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';

export const name = 'research-plugin-instructions';
export const inject = ['tools'];
const ID = /^[A-Za-z0-9_-]{1,128}$/u;

function readIndex(root) {
  if (typeof root !== 'string' || !isAbsolute(root) || resolve(root) !== root) throw new Error('plugin_index_identity_invalid');
  for (const path of [root, join(root, 'plugins')]) if (lstatSync(path).isSymbolicLink() || !lstatSync(path).isDirectory()) throw new Error('plugin_index_unsafe');
  const fd = openSync(join(root, 'plugins/index.json'), constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const stat = fstatSync(fd);
    if (!stat.isFile() || stat.nlink !== 1 || stat.size > 8 * 1024 * 1024 || (stat.mode & 0o077) || (process.getuid && stat.uid !== process.getuid())) throw new Error('plugin_index_unsafe');
    return JSON.parse(readFileSync(fd, 'utf8'));
  } finally { closeSync(fd); }
}

function authorizedComponent(config, args, exec) {
  const snapshot = readSnapshot(config.researchRoot, exec?.agent?.session?.header?.id);
  const plugin = snapshot.plugins.find(row => row.name === args.plugin);
  const current = readIndex(config.researchRoot);
  const row = current.versions?.[plugin?.digest];
  if (!plugin || !['enabled', 'superseded'].includes(row?.state) || row?.review?.digest !== plugin.digest || JSON.stringify(row.review.permissions) !== JSON.stringify(row.permissions)) throw new Error('plugin_authorization_revoked');
  if (row.managed_approval && !(config.approvalRoots || []).some(root => {
    try { const index = readIndex(root); const approved = index.versions?.[plugin.digest]; return ['enabled', 'superseded'].includes(approved?.state) && approved?.review?.digest === plugin.digest && JSON.stringify(approved.review.permissions) === JSON.stringify(row.permissions); } catch { return false; }
  })) throw new Error('plugin_source_authorization_revoked');
  const component = plugin.components.find(item => item.key === args.component && item.kind === args.kind && item.ready && typeof item.instructions === 'string');
  if (!component) throw new Error('plugin_component_unavailable');
  return { plugin, component, row };
}

export function readSnapshot(root, session) {
  if (typeof root !== 'string' || !isAbsolute(root) || resolve(root) !== root || !ID.test(session ?? '')) throw new Error('plugin_snapshot_identity_invalid');
  const folder = join(root, 'plugins', 'sessions');
  for (const path of [root, join(root, 'plugins'), folder]) {
    const entry = lstatSync(path);
    if (!entry.isDirectory() || entry.isSymbolicLink()) throw new Error('plugin_snapshot_unsafe');
  }
  const fd = openSync(join(folder, `${session}.json`), constants.O_RDONLY | constants.O_NOFOLLOW);
  try {
    const entry = fstatSync(fd);
    if (!entry.isFile() || entry.nlink !== 1 || entry.size > 4 * 1024 * 1024 || (process.getuid && entry.uid !== process.getuid()) || (entry.mode & 0o077)) throw new Error('plugin_snapshot_unsafe');
    const result = JSON.parse(readFileSync(fd, 'utf8'));
    if (!Array.isArray(result.plugins)) throw new Error('plugin_snapshot_invalid');
    return result;
  } finally { closeSync(fd); }
}

export function apply(ctx, config = {}) {
  if (!ctx?.tools?.register) throw new Error('plugin_tools_unavailable');
  ctx.tools.register({
    name: 'rwb_plugin_instructions',
    description: 'Read reviewed plugin command or agent instruction templates for this session. Agent templates use the existing DSH subagent tool; host-specific model, tools and permission overrides are unsupported. No execution or new permission is granted.',
    parameters: { type: 'object', properties: { plugin: { type: 'string' }, component: { type: 'string' }, kind: { type: 'string', enum: ['command', 'agent'] } }, required: ['plugin', 'component', 'kind'], additionalProperties: false },
    output: { schema: { type: 'object', properties: { instructions: { type: 'string' }, plugin_digest: { type: 'string' }, support: { type: 'string' }, execution: { type: 'string' } }, required: ['instructions', 'plugin_digest', 'support', 'execution'], additionalProperties: false }, render(_args, value) { return [{ type: 'text', text: value.instructions }]; } },
    async execute(args, exec) {
      try {
        const { plugin, component } = authorizedComponent(config, args, exec);
        ctx.logger.info('research_plugin_instructions_read');
        return { instructions: component.instructions, plugin_digest: plugin.digest, support: component.support, execution: 'existing_dsh_primitives_only' };
      } catch (error) {
        ctx.logger.warn('research_plugin_instructions_denied');
        throw new Error('plugin_instructions_unavailable', { cause: error });
      }
    },
  });
  ctx.tools.register({
    name: 'rwb_plugin_agent',
    description: 'Delegate to a reviewed plugin Agent through the existing DSH subagent tool. Preserves the caller model, existing tools, authorization, depth and cancellation; no host-specific overrides.',
    parameters: { type: 'object', properties: { plugin: { type: 'string' }, component: { type: 'string' }, task: { type: 'string', minLength: 1, maxLength: 10000 } }, required: ['plugin', 'component', 'task'], additionalProperties: false },
    output: { schema: { type: 'object', properties: { result_json: { type: 'string' } }, required: ['result_json'], additionalProperties: false }, render(_args, value) { return [{ type: 'text', text: value.result_json }]; } },
    async execute(args, exec) {
      try {
        const { plugin, component, row } = authorizedComponent(config, { ...args, kind: 'agent' }, exec);
        if (!row.review.permissions.includes('agents:delegate') || typeof ctx.tools.execute !== 'function' || !exec.agent || !exec.signal || !exec.token) throw new Error('plugin_agent_delegate_denied');
        const result = await ctx.tools.execute({ name: 'subagent', callId: `${exec.callId}:plugin-agent`, rootCallId: exec.rootCallId || exec.callId, parent: exec.token, agent: exec.agent, signal: exec.signal, arguments: { description: `${plugin.name} ${component.key}`.slice(0, 100), prompt: `${component.instructions}\n\nUser task:\n${args.task}`, run_in_background: false } });
        if (result.isError) throw new Error('plugin_agent_native_dispatch_denied');
        ctx.logger.info('research_plugin_agent_delegated');
        return { result_json: JSON.stringify(result) };
      } catch (error) {
        ctx.logger.warn('research_plugin_agent_denied');
        throw new Error('plugin_agent_unavailable', { cause: error });
      }
    },
  });
}
