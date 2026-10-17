// No SSR/site process: use upstream Fastify, publication layer and all original domain handlers.
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { controlRoute } from './control.mjs';
import { chronologyModule } from './chronicle.mjs';
const root = process.env.RWB_ENGINE_ROOT;
if (!root || !path.isAbsolute(root)) throw new Error('engine_root_invalid');
const load = file => import(pathToFileURL(path.join(root, file)).href);
const [{ buildApp }, { installModules }, { SERVER_MODULES }, { assertProductionSecrets, config }, { closeDb }, { passwordLogin, sessionPrincipal, SESSION_COOKIE }, { startHeartbeat }] = await Promise.all([
  load('apps/api/src/app.ts'), load('packages/backend/src/modules.ts'), load('site/modules/server.ts'), load('packages/backend/src/config.ts'), load('packages/backend/src/db.ts'), load('packages/backend/src/admin/auth.ts'), load('packages/backend/src/operations/heartbeat.ts'),
]);
const {sql}=await load('packages/backend/src/db.ts');
installModules([...SERVER_MODULES,chronologyModule(sql)]);
assertProductionSecrets([['auth', 'SESSION_SECRET'], ['auth', 'IMG_PROXY_SIGN_SECRET']]);
const app = await buildApp();
const [{listSources},{runsOverview}] = await Promise.all([
  load('packages/backend/src/admin/sources.ts'),load('packages/backend/src/admin/runs.ts'),
]);
let session;
async function invoke(route) {
  if (!session) {
    const login = await passwordLogin(config.adminPassword, '/admin', 'rwb-local-manager');
    const cookie = `${SESSION_COOKIE}=${encodeURIComponent(login.token)}`;
    const principal = await sessionPrincipal(cookie);
    if (!principal || principal.dev) throw new Error('internal_session_failed');
    session = { cookie, csrf: principal.csrf };
  }
  const response = await app.inject({ ...route, headers: { 'x-rwb-ai-news-token': process.env.RWB_AI_NEWS_TOKEN, cookie: session.cookie, 'x-csrf-token': session.csrf } });
  if (response.statusCode === 401) session = undefined;
  return response;
}
app.get('/internal/rwb/status', async (_req, reply) => {
  try {
    const [sources, runs] = await Promise.all([listSources({}), runsOverview()]);
    return reply.header('Cache-Control', 'no-store').send({ ok: true, engine: '26d436497d9ddba9e7dd88eed255cfe0105ce368', collectionEnabled: process.env.COLLECT_ENABLED === 'true', modelCallsEnabled: process.env.MODEL_CALLS_ENABLED === 'true', configuredPending: ['x_search', 'mp_account'], sources, runs });
  } catch {app.log.error({event:'engine_status_failed'});return reply.code(503).send({ok:false,error:'engine_status_unavailable'});}
});
app.post('/internal/rwb/control', async (req, reply) => {
  let route;
  try { route = controlRoute(req.body?.action, req.body?.input); }
  catch { return reply.code(400).send({ error: 'control_action_not_allowed' }); }
  const response = await invoke(route);
  return reply.code(response.statusCode >= 200 && response.statusCode < 300 ? 200 : response.statusCode).header('Cache-Control', 'no-store').type('application/json').send(response.body || '{}');
});
await app.listen({ host: '127.0.0.1', port: config.apiPort });
const heartbeat = startHeartbeat(`api:${config.apiPort}`);
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  try { clearInterval(heartbeat); await app.close(); await closeDb(); }
  catch { console.error(JSON.stringify({ level: 'error', event: 'shutdown_failed' })); process.exitCode = 1; }
}
process.on('SIGTERM', stop); process.on('SIGINT', stop);
