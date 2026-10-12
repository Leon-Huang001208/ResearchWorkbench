/** Minimal pinned DSH model context. Existing credential bridge remains the only key resolver. */
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {realpath,readFile} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {processBridge,MODEL_REF} from '../../../app/research_web/runtime/model-credentials.mjs';
import {safeModelText} from './credential-safety.mjs';

export async function createNativeDsh(config){
  if(process.platform!=='darwin')throw Error('hot_dsh_native_platform_required');
  const contract=JSON.parse(await readFile(new URL('../../../runtimes/research_web.json',import.meta.url),'utf8'));
  const pin=contract.dsh?.commit;
  if(contract.schema_version!==1||typeof pin!=='string'||!/^[a-f0-9]{40}$/.test(pin))throw Error('hot_dsh_build_binding_invalid');
  const source=await realpath(config.source);
  if(source!==resolve(config.source)||source.split('/').at(-1)!==pin)throw Error('hot_dsh_build_binding_invalid');
  const git=promisify(execFile);
  const {stdout}=await git('git',['rev-parse','HEAD'],{cwd:source,timeout:5000});
  if(stdout.trim()!==pin)throw Error('hot_dsh_build_binding_invalid');
  const {stdout:changes}=await git('git',['status','--porcelain','--untracked-files=no'],{cwd:source,timeout:5000});
  if(changes.trim())throw Error('hot_dsh_build_binding_invalid');
  const credential=await processBridge(config.credentials,'describe');
  if(credential.configured!==true)throw Error('hot_dsh_model_unconfigured');
  const llmPath=join(source,'packages/llm/llm/lib/index.js'),require=createRequire(pathToFileURL(llmPath));
  const {Context}=await import(pathToFileURL(require.resolve('@deepseek-ai/cordis')));
  const {default:LlmRuntime}=await import(pathToFileURL(llmPath));
  const {default:CredentialProvider}=await import(pathToFileURL(join(source,'packages/credentials/credentials/lib/index.js')));
  const provider=await import(pathToFileURL(join(source,'packages/llm/llm-deepseek-api-key/lib/index.js')));
  const {PUBLIC_BASE_URL}=await import(pathToFileURL(join(source,'packages/llm/llm-deepseek/lib/index.js')));
  const ctx=new Context(),llm=await ctx.plugin(LlmRuntime),secrets=new Set();let route,credentialsFiber;
  try{
    class NativeCredentials extends CredentialProvider {
    async resolve(ref){
      if(ref!==MODEL_REF)throw Error('hot_dsh_credential_ref_denied');
      const result=await processBridge(config.credentials,'resolve');
      if(typeof result.value!=='string'||!result.value)throw Error('hot_dsh_model_unconfigured');
      secrets.add(result.value);return {value:result.value,source:'system-keychain'};
    }
    async describe(ref){if(ref!==MODEL_REF)throw Error('hot_dsh_credential_ref_denied');return processBridge(config.credentials,'describe');}
    async set(){throw Error('hot_dsh_credential_write_denied');}
    async unset(){throw Error('hot_dsh_credential_write_denied');}
    async readRecord(){throw Error('hot_dsh_credential_ref_denied');}
    async describeRecord(){throw Error('hot_dsh_credential_ref_denied');}
    async listRecords(){return [];}
    async modifyRecord(){throw Error('hot_dsh_credential_write_denied');}
    }
    credentialsFiber=await ctx.plugin(NativeCredentials);
    route=await ctx.plugin(provider,{baseURL:PUBLIC_BASE_URL,apiKeyEnv:MODEL_REF,thinking:'disabled',maxTokens:512,
      retryPolicy:{mode:'normal',maxRetries:0},streamIdleTimeoutMs:30000});
    return {runtime:ctx.llm,
      safeOutput:text=>safeModelText(text,secrets),
      async close(){secrets.clear();await route.dispose();await credentialsFiber.dispose();await llm.dispose();}};
  }catch{secrets.clear();if(route)await route.dispose();if(credentialsFiber)await credentialsFiber.dispose();await llm.dispose();throw Error('hot_dsh_context_failed');}
}
