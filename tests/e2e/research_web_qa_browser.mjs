import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { resolve, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const module = process.env.RESEARCH_PLAYWRIGHT_MODULE;
assert.ok(module, 'Provide an existing playwright-core module');
const { chromium } = await import(pathToFileURL(module));
const ui = fileURLToPath(new URL('../../app/research_web/ui/', import.meta.url));
const dist = resolve(process.env.RWB_QA_BROWSER_DIST || resolve(ui, 'qa-dist'));
const id = 'qa-fixture';
const raw = '<script>window.injected = true</script>';
const specialist = { id: 'specialist-fixture', mode: 'fingpt', research_mode: 'specialist', status: 'idle', messages: [], files: [] };
const retired = { id: 'retired-fixture', title: '已退役旧问答', mode: 'fingpt', research_mode: 'quick' };
const results = { create: [], prompts: [], idempotencyKeys: [] };
const detail = {
  id, title: '新问答夹具', mode: 'fingpt', research_mode: 'quick', status: 'idle',
  execution_engine: 'alphadesk', model: '隔离模型', source_scope: ['datahub', 'web', 'uploads'],
  files: [], messages: [], qa_events: [],
};
const catalog = { runtime: { execution_engine: 'alphadesk', connected: true, credential_configured: true, model: '隔离模型' } };
let created = false;
const server = createServer(async (req, res) => {
  const { pathname } = new URL(req.url, 'http://127.0.0.1');
  const json = (value, status = 200) => {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(value));
  };
  try {
    if (pathname === '/api/research/runtime') return json(catalog.runtime);
    if (pathname === '/api/research/sessions' && req.method === 'GET') return json({ items: [retired, specialist, ...(created ? [detail] : [])] });
    if (pathname === '/api/research/sessions' && req.method === 'POST') {
      results.create.push(await body(req));
      created = true;
      detail.research_mode = results.create.at(-1).research_mode;
      return json(detail, 201);
    }
    if (pathname === '/api/research/sessions/' + retired.id) return json({ error: { code: 'fingpt_retired', message: '已退役' } }, 410);
    if (pathname === '/api/research/sessions/' + specialist.id) return json(specialist);
    if (pathname === '/api/research/sessions/' + id) return json(detail);
    if (pathname === '/api/research/sessions/' + id + '/messages') {
      const prompt = await body(req);
      results.prompts.push(prompt);
      results.idempotencyKeys.push(req.headers['idempotency-key']);
      const append = (event, data) => detail.qa_events.push({ seq: detail.qa_events.length + 1, event, data });
      append('question', { content: prompt.text, mode: prompt.research_mode });
      append('_qa', { content: '答复 [S1]\n\n' + raw });
      append('answer_source', { content: [{ id: 'S1', title: '已核对的资料', asof: '2026-11-13', url: 'javascript:alert(1)' }] });
      append('task_end', { status: 'completed' });
      detail.status = 'completed';
      return json({ accepted: true }, 202);
    }
    if (pathname.startsWith('/api/research/') && pathname.endsWith('/events')) {
      res.writeHead(200, { 'Content-Type': 'text/event-stream' });
      return res.end(`event: snapshot\ndata: ${JSON.stringify(pathname.includes(specialist.id) ? specialist : detail)}\n\n`);
    }
    if (pathname.startsWith('/api/research/')) return json({ items: [] });
    let path;
    if (pathname === '/') path = resolve(ui, 'index.html');
    else if (pathname.startsWith('/static/qa-dist/')) path = resolve(dist, pathname.slice('/static/qa-dist/'.length));
    else if (pathname.startsWith('/static/')) path = resolve(ui, pathname.slice('/static/'.length));
    if (!path || (!path.startsWith(ui) && !path.startsWith(dist + sep))) return json({}, 404);
    const type = path.endsWith('.html') ? 'text/html' : path.endsWith('.css') ? 'text/css' : path.endsWith('.json') ? 'application/json' : /\.[m]?js$/.test(path) ? 'text/javascript' : 'application/octet-stream';
    const data = await readFile(path);
    res.writeHead(200, { 'Content-Type': type, 'Content-Security-Policy': "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:" });
    res.end(data);
  } catch (error) {
    json({ error: { message: error.code || 'fixture failure' } }, 404);
  }
});

async function body(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

server.listen(0, '127.0.0.1');
await once(server, 'listening');
let browser;
try {
  browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 } });
  const origin = `http://127.0.0.1:${server.address().port}`;
  await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error" && !message.text().includes("status of 410")) errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400 && response.status() !== 410) errors.push(`${response.status()} ${new URL(response.url()).pathname}`); });

  await page.goto(`${origin}/#/fingpt?session=${retired.id}`);
  try { await page.waitForURL('**/#/qa', { timeout: 6000 }); }
  catch (error) { throw new Error(JSON.stringify({ failure: error.message, errors, page: await page.locator("body").innerText() })); }

  await page.getByRole('heading', { name: '从一个问题，开始研究' }).waitFor();
  await page.getByRole('button', { name: '深度研究', exact: true }).click();
  await page.locator('#prompt').fill('首轮研究问题');
  await page.locator('#composer button[type="submit"]').click();
  await page.getByRole('button', { name: '查看来源 S1' }).waitFor();
  assert.equal(results.create[0].research_mode, 'deep');
  assert.equal(results.prompts[0].text, '首轮研究问题');
  assert.ok(results.idempotencyKeys[0]);
  await page.getByRole('button', { name: '查看来源 S1' }).click();
  await page.locator('#src-S1').getByText('已核对的资料').waitFor();
  assert.equal(await page.locator('#src-S1 a').count(), 0);
  assert.equal(await page.evaluate(() => window.injected), undefined);
  await page.reload();
  await page.getByText('首轮研究问题', { exact: true }).waitFor();
  assert.equal(results.prompts.length, 1);
  await page.locator('#prompt').fill('连续追问');
  await page.locator('#composer button[type="submit"]').click();
  await page.getByText('连续追问', { exact: true }).waitFor();
  assert.equal(results.create.length, 1);
  assert.notEqual(results.idempotencyKeys[0], results.idempotencyKeys[1]);
  await page.goto(`${origin}/#/fingpt?session=${specialist.id}`);
  await page.waitForURL('**/#/specialist?session=specialist-fixture');
  assert.equal(await page.locator('[data-qa-app]').count(), 0);
  assert.deepEqual(errors, []);
  console.log('PASS: QA legacy routing, same-origin bundle, mode, continuation, reload, citations and professional collaboration');
} finally {
  await browser?.close();
  server.close();
}
