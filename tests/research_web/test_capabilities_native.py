"""Pinned DSH source integration; actual provider and tool registrations, no model."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.tools import PIN, tool_catalog


def node(source, script, *args):
    result = subprocess.run(
        [
            "node",
            "--import",
            str(source / "node_modules/tsx/dist/loader.mjs"),
            "--input-type=module",
            "-e",
            script,
            *map(str, args),
        ],
        cwd=source,
        env={**os.environ, "TSX_TSCONFIG_PATH": str(source / "tsconfig.json")},
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def source():
    configured = os.environ.get("DSH_SOURCE_ROOT")
    if not configured:
        pytest.skip("DSH_SOURCE_ROOT required for native source validation")
    root = Path(configured)
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        == PIN
    )
    return root


def test_native_provider_discovers_loads_and_watches_only_product_root(
    source, tmp_path
):
    catalog = CapabilityCatalog(tmp_path)
    script = r"""
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const { FileSystemSkillProvider } = await import(pathToFileURL(join(process.cwd(), 'packages/skill/skill-filesystem/src/index.ts')));
const [root, nativeRoot] = process.argv.slice(1);
await mkdir(join(root, '.agents/skills/host-canary'), { recursive: true });
await writeFile(join(root, '.agents/skills/host-canary/SKILL.md'), '---\nname: host-canary\ndescription: forbidden\n---\nnot product');
const controller = new AbortController();
let invalidations=0;
const ctx={get(){return undefined;},logger:{warn(message){throw Error(message);}}};
const provider=new FileSystemSkillProvider(ctx,{signal:controller.signal,invalidate(){invalidations++;}},{includeDefaultRoots:false,customSkillDirs:[nativeRoot],watch:true,watchFollowSymlinks:false,watchStabilityThresholdMs:20,watchPollIntervalMs:10});
try {
  const candidates=await provider.list({cwd:root});
  assert.ok(Array.isArray(candidates));
  assert.equal(candidates.length,6);
  assert.ok(!candidates.some(c=>c.name==='host-canary'));
  const company=candidates.find(c=>c.name==='company-research');
  const loaded=await provider.get(company,{cwd:root});
  assert.equal(loaded.name,'company-research');
  assert.match(loaded.content,/resources\/capabilities\/company-research\/1\//);
  assert.equal(loaded.resourceBase.path,join(nativeRoot,'company-research'));
  const original=loaded.content;
  const workflow=await provider.get(candidates.find(c=>c.name==='fund-research-workflow'),{cwd:root});
  assert.match(workflow.content,/步骤模板（未执行）/);
  const stage=join(root,'new-skill');
  await mkdir(stage);await writeFile(join(stage,'SKILL.md'),'---\nname: rwb-test-v1\ndescription: 测试\n---\n版本一');
  await rename(stage,join(nativeRoot,'rwb-test-v1'));
  for(let i=0;i<100 && invalidations===0;i++) await new Promise(r=>setTimeout(r,20));
  assert.ok(invalidations>0,'native watcher must invalidate on new approved package');
  const updated=await provider.list({cwd:root});
  assert.ok(updated.some(c=>c.name==='rwb-test-v1'));
  assert.equal((await provider.get(company,{cwd:root})).content,original);
  const count=invalidations;await rename(join(nativeRoot,'rwb-test-v1'),join(root,'retained-v1'));
  for(let i=0;i<100 && invalidations===count;i++) await new Promise(r=>setTimeout(r,20));
  assert.ok(invalidations>count);
  assert.ok(!(await provider.list({cwd:root})).some(c=>c.name==='rwb-test-v1'));
  console.log(JSON.stringify({discovered:6,loaded:true,watch:true,hostRootExcluded:true}));
} finally {await provider.dispose();controller.abort();}
"""
    result = json.loads(node(source, script, tmp_path, catalog.native_root).strip())
    assert result == {
        "discovered": 6,
        "loaded": True,
        "watch": True,
        "hostRootExcluded": True,
    }


def test_tool_catalog_matches_actual_pinned_registrations(source):
    script = r"""
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const root=process.argv[1];
const tools=[];
const ctx={tools:{register(tool){tools.push(tool);return ()=>{};}},on(){return ()=>{};},effect(){},get(){return undefined;},logger:{info(){},warn(){}},systemPrompt:{section(){return ()=>{};}},subagents:{getProvider(){return {name:'spawn',capabilities:{depthLimit:true},prepareContinuable(){}};}}};
for(const path of ['packages/skill/tool-skill/src/index.ts','packages/subagent/tool-subagent-control/src/index.ts','packages/subagent/tool-subagent-control/src/list-agents.ts']){
  (await import(pathToFileURL(join(process.cwd(),path)))).apply(ctx);
}
(await import(pathToFileURL(join(process.cwd(),'packages/subagent/tool-subagent/src/index.ts')))).apply(ctx,{provider:'spawn',maxDepth:1,backgroundMode:'continuable'});
(await import(pathToFileURL(join(process.cwd(),'packages/subagent/tool-subagent-report/src/index.ts')))).installReportTool(ctx,ctx,'next-step');
const web=await import(pathToFileURL(join(process.cwd(),'packages/web/tool-web/src/index.ts')));
web.apply(ctx,{search:true,fetch:false,searchMaxResults:8,searchMaxQueries:4,fetchTimeoutMs:30000,searchTimeoutMs:60000,fetchMaxOutputChars:200000});
(await import(pathToFileURL(join(root,'app/research_web/runtime/research-tools.mjs')))).apply(ctx,{python:'/usr/bin/python3',runnerPath:'/tmp/never-run.py',researchRoot:'/tmp/never-used',timeoutSeconds:60,maxOutputBytes:262144});
const enabledTools=['datahub_search_assets','datahub_get_trading_calendar','datahub_get_market_bars','datahub_get_market_snapshot','datahub_get_index_data','datahub_get_financials','datahub_get_market_activity','datahub_get_factor_macro','datahub_get_fund_data','datahub_search_news','datahub_search_announcements','datahub_search_research','datahub_search_web'];
(await import(pathToFileURL(join(root,'app/research_web/runtime/public-data.mjs')))).apply(ctx,{researchRoot:'/tmp/never-used',enabledTools});
console.log(JSON.stringify(tools.map(t=>({id:t.name,parameters:t.parameters}))));
"""
    captured = json.loads(node(source, script, Path(__file__).parents[2]).strip())
    actual = {t["id"]: t["parameters"] for t in captured}
    public = {
        t["id"]: t["parameters"]
        for t in tool_catalog()["items"]
        if t.get("execution_surface") == "dsh_native"
    }
    assert set(public) == set(actual)
    for name, schema in public.items():
        properties = actual[name].get("properties", actual[name])
        assert set(schema["properties"]) == set(properties), name
        for key, value in schema["properties"].items():
            # DataHub has additional business validation layered over native JSON schema.
            assert value["type"] == properties[key]["type"]
