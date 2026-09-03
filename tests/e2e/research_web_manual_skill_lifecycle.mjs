/** Scoped live UI mutations on one acceptance-only Skill; no model/tool calls. */
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';

const origin=new URL(process.env.ALPHAFOUNDRY_WEB_URL || 'http://127.0.0.1:8088');
if (!['localhost','127.0.0.1'].includes(origin.hostname) || origin.protocol!=='http:') throw new Error('Local acceptance only');
const name='验收·手动导入样本'; const slug='ui-import-sample-20260903';
const output=path.resolve('outputs/research-web-ui-acceptance/manual-skill');
const log=path.resolve('logs/research-web-manual-skill-lifecycle.jsonl');
const sourceSession='793dc010-bb08-429d-957a-c858c6654d39';
const sourceFile='ebcedea5342a8bcef06c8a96';
let browser; let capabilityId; const mutations=[];
try {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  const {chromium}=await import(process.env.ALPHAFOUNDRY_PLAYWRIGHT_MODULE || 'playwright-core');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const context=await browser.newContext({viewport:{width:1600,height:1000},acceptDownloads:true});
  const catalog=await (await context.request.get(`${origin.origin}/api/research/capabilities`)).json();
  assert.ok(!catalog.items.some(item=>(item.name===name || item.metadata?.slug===slug) && item.id!==process.env.ALPHAFOUNDRY_ACCEPTANCE_DRAFT),'Acceptance name exists; do not overwrite or auto-repeat');
  const source=await context.request.get(`${origin.origin}/api/research/sessions/${sourceSession}/files/${sourceFile}/download`);
  assert.equal(source.status(),200); const sourceBytes=await source.body();
  assert.match(sourceBytes.toString('utf8'),/ui-sample-report-verified/);
  await writeFile(path.join(output,'SKILL.md'),sourceBytes);
  const page=await context.newPage(); const errors=[];
  page.on('pageerror',error=>errors.push(error.name));
  await page.route('**/*',async route=>{
    const request=route.request();
    if (!['GET','HEAD'].includes(request.method())) {
      const pathname=new URL(request.url()).pathname;
      if (!pathname.startsWith('/api/research/capabilities')) {errors.push('blocked_non_capability_write'); await route.abort(); return;}
      mutations.push({method:request.method(),path:pathname});
    }
    await route.continue();
  });
  await page.goto(`${origin.origin}/?acceptance=manual-skill#/skills`);
  await page.getByRole('heading',{name:'能力中心',exact:true}).waitFor();
  const resume=process.env.ALPHAFOUNDRY_ACCEPTANCE_DRAFT;
  let candidate;
  if (resume) {
    assert.match(resume,/^[a-f0-9]{32}$/);
    candidate=await (await context.request.get(`${origin.origin}/api/research/capabilities/${resume}`)).json();
    assert.equal(candidate.source,'import'); assert.equal(candidate.origin?.sha256,createHash('sha256').update(sourceBytes).digest('hex'));
    await page.locator(`[data-skill-detail="${resume}"]`).click();
  } else {
    const imported=page.waitForResponse(r=>r.url().endsWith('/capabilities/import') && r.request().method()==='POST');
    await page.locator('#cap-import-file').setInputFiles(path.join(output,'SKILL.md'));
    const importedResponse=await imported; candidate=await importedResponse.json(); capabilityId=candidate.id;
    assert.equal(importedResponse.status(),201);
  }
  capabilityId=candidate.id;
  if (candidate.version===null) {
  assert.equal(candidate.enabled,false); assert.equal(candidate.version,null);
  if (!resume) assert.equal(candidate.checks.valid,false);
  await page.getByRole('button',{name:'编辑草稿',exact:true}).click();
  await page.locator('#cap-name').fill(name); await page.locator('#cap-slug').fill(slug);
  await page.locator('#cap-category').fill('资料研究');
  await page.locator('#cap-description').fill('手动导入的样本统计研究指令，用于验证可审查的版本与文件交付。');
  await page.locator('#cap-scenarios').fill('固定样本统计与HTML交付验收');
  await page.locator('#cap-instructions').fill(sourceBytes.toString('utf8').replace('name: ui-sample-report-verified',`name: ${slug}`));
  // Bare SKILL.md has no product schema. Enter one explicit text input and defaults.
  const inputs=await page.locator('[data-input-remove]').count();
  for(let index=inputs-1;index>=0;index--) await page.locator(`[data-input-remove="${index}"]`).click();
  await page.getByRole('button',{name:'添加输入',exact:true}).click();
  await page.locator('#cap-input-0-name').fill('values'); await page.locator('#cap-input-0-label').fill('数值列表与问题');
  await page.locator('#cap-input-0-type').selectOption('text');
  for(const format of ['md','html','docx','xlsx','png']) await page.locator(`#cap-default-${format}`).setChecked(format==='html');
  await page.locator('input[name="required_tools"][value="af_run_script"]').check();
  await page.locator('#cap-dependencies').fill('');
  await page.getByRole('button',{name:'保存草稿',exact:true}).click();
  const detail=page.getByRole('region',{name:'能力详情',exact:true});
  await detail.getByRole('heading',{name,exact:true}).waitFor();
  await page.getByRole('button',{name:'检查草稿',exact:true}).click();
  await detail.getByRole('heading',{name:/静态检查通过/}).waitFor();
  const publish=async version=>{
    const pending=page.waitForResponse(r=>r.url().endsWith(`/${capabilityId}/publish`) && r.request().method()==='POST');
    await page.getByRole('button',{name:'发布新版本',exact:true}).click();
    const response=await pending; assert.equal(response.status(),200);
    const value=await response.json(); assert.equal(value.version,version); assert.equal(value.enabled,true);
    await page.getByText('新版本已发布并启用。',{exact:true}).waitFor();
    return value;
  };
  await publish(1);
  await page.getByRole('button',{name:'编辑草稿',exact:true}).click();
  await page.locator('#cap-description').fill('手动导入样本统计 v2：明确列出计算口径，保持HTML交付。');
  await page.locator('#cap-instructions').fill(`${sourceBytes.toString('utf8').replace('name: ui-sample-report-verified',`name: ${slug}`)}\n\n## 第二版补充\n报告必须明确列出输入值、样本数、总和及平均值公式。\n`);
  await page.getByRole('button',{name:'保存草稿',exact:true}).click();
  await page.getByText('草稿已保存；未发布，当前启用版本不变。',{exact:true}).waitFor();
  await page.getByRole('button',{name:'检查草稿',exact:true}).click();
  await detail.getByRole('heading',{name:/静态检查通过/}).waitFor();
  await publish(2);
  } else {
    assert.equal(candidate.version,2); assert.equal(candidate.metadata.slug,slug);
    assert.equal(candidate.name,name); assert.equal(candidate.enabled,true);
  }
  const v1Content=await (await context.request.get(`${origin.origin}/api/research/capabilities/${capabilityId}/versions/1`)).json();
  const v2Content=await (await context.request.get(`${origin.origin}/api/research/capabilities/${capabilityId}/versions/2`)).json();
  assert.ok(v1Content.instructions); assert.ok(v2Content.instructions);
  assert.notEqual(v1Content.instructions,v2Content.instructions);
  await page.getByRole('button',{name:'停用',exact:true}).click();
  await page.getByText('能力已停用。',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'放入研究草稿',exact:true}).isEnabled(),false);
  await page.getByRole('button',{name:'查看版本',exact:true}).click();
  await page.locator('.version-row').filter({hasText:'v1'}).getByRole('button',{name:'回滚到此版本',exact:true}).click();
  await page.getByText('已明确切回所选历史版本；旧版本未改写。',{exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'能力中心',exact:true}).waitFor();
  await page.getByRole('searchbox',{name:'搜索能力名称和简介',exact:true}).fill(name);
  const card=page.locator('.skill-card').filter({has:page.getByRole('heading',{name,exact:true})});
  await card.getByRole('button',{name:'查看详情',exact:true}).click();
  await page.getByRole('button',{name:'查看版本',exact:true}).click();
  await page.locator('.version-row').filter({hasText:'v1 · 当前'}).waitFor();
  await page.screenshot({path:path.join(output,'rollback-version.png'),fullPage:true});
  const promise=page.waitForEvent('download');
  await page.getByRole('link',{name:'导出 v1 ZIP',exact:true}).click();
  const download=await promise; const target=path.join(output,'export-v1.zip'); await download.saveAs(target);
  const exported=await readFile(target); assert.ok(exported.length>0); assert.equal(exported.subarray(0,2).toString(),'PK');
  const latest=await (await context.request.get(`${origin.origin}/api/research/capabilities/${capabilityId}`)).json();
  assert.equal(latest.version,1); assert.equal(latest.enabled,true);
  assert.equal(latest.description,v1Content.metadata.description); assert.deepEqual(errors,[]);
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'passed',capabilityId,sourceSession,sourceFile,version:1,sourceSha256:createHash('sha256').update(sourceBytes).digest('hex'),exportSha256:createHash('sha256').update(exported).digest('hex'),checks:['manual_import_invalid_preserved','form_corrected_schema','published_v1','published_edited_v2','disabled','rollback_v1','refresh_persisted','browser_export'],mutations,modelCalls:0},null,2));
  await writeFile(log,JSON.stringify({event:'manual_skill_lifecycle',status:'passed',capabilityId})+'\n');
  console.log(`Manual Skill lifecycle passed: ${capabilityId}`);
} catch(error) {
  await mkdir(output,{recursive:true}); await mkdir(path.dirname(log),{recursive:true});
  await writeFile(path.join(output,'receipt.json'),JSON.stringify({status:'failed',capabilityId,error:error.message,mutations},null,2));
  await writeFile(log,JSON.stringify({event:'manual_skill_lifecycle',status:'failed',capabilityId,error_type:error.name})+'\n');
  console.error(error.message); process.exitCode=1;
} finally {if(browser) await browser.close();}
