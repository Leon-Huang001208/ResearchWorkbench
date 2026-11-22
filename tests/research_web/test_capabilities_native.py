"""Pinned DSH source integration; actual provider and tool registrations, no model."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.seeds import RECEIPT_GATED_SKILLS
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
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == PIN
    return root


def test_clean_catalog_native_candidates_match_enabled_capabilities(tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    rows = catalog.list()["items"]
    enabled = {row["native_name"] for row in rows if row["status"] == "enabled"}
    disabled = {row["native_name"] for row in rows if row["id"] in RECEIPT_GATED_SKILLS}

    assert disabled
    assert all(row["status"] == "disabled" for row in rows if row["id"] in RECEIPT_GATED_SKILLS)
    native_root = catalog.prepare_native_root()
    candidates = {path.name for path in native_root.iterdir()}
    assert candidates == enabled
    assert candidates.isdisjoint(disabled)


def test_native_provider_discovers_loads_and_watches_only_product_root(source, tmp_path):
    catalog = CapabilityCatalog(tmp_path)
    rows = catalog.list()["items"]
    enabled_count = sum(row["status"] == "enabled" for row in rows)
    disabled_names = [row["native_name"] for row in rows if row["id"] in RECEIPT_GATED_SKILLS]
    script = r"""
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdir, rename } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const { FileSystemSkillProvider } = await import(pathToFileURL(join(process.cwd(), 'packages/skill/skill-filesystem/src/index.ts')));
const [root, nativeRoot, expectedCount, disabledJson] = process.argv.slice(1);
await mkdir(join(root, '.agents/skills/host-canary'), { recursive: true });
await writeFile(join(root, '.agents/skills/host-canary/SKILL.md'), '---\nname: host-canary\ndescription: forbidden\n---\nnot product');
const controller = new AbortController();
let invalidations=0;
const ctx={get(){return undefined;},logger:{warn(message){throw Error(message);}}};
const provider=new FileSystemSkillProvider(ctx,{signal:controller.signal,invalidate(){invalidations++;}},{includeDefaultRoots:false,customSkillDirs:[nativeRoot],watch:true,watchFollowSymlinks:false,watchStabilityThresholdMs:20,watchPollIntervalMs:10});
try {
  const candidates=await provider.list({cwd:root});
  assert.ok(Array.isArray(candidates));
  assert.equal(candidates.length,Number(expectedCount));
  assert.ok(JSON.parse(disabledJson).every(name=>!candidates.some(c=>c.name===name)));
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
  console.log(JSON.stringify({discovered:candidates.length,loaded:true,watch:true,hostRootExcluded:true}));
} finally {await provider.dispose();controller.abort();}
"""
    result = json.loads(
        node(
            source,
            script,
            tmp_path,
            catalog.native_root,
            enabled_count,
            json.dumps(disabled_names),
        ).strip()
    )
    assert result == {
        "discovered": enabled_count,
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
const ctx={tools:{register(tool){tools.push(tool);return ()=>{};}},on(){return ()=>{};},effect(){},get(){return undefined;},logger:{info(){},warn(){}},systemPrompt:{section(){return ()=>{};},getSectionOrder(){return 0;}},sessionProjections:{register(){return ()=>{};}},subagents:{resolveMaxDepth(value){return value??1;},getProvider(){return {name:'spawn',capabilities:{depthLimit:true},prepareContinuable(){}};},startContinuable(){throw Error('registration_fixture_execution_forbidden');}}};
for(const path of ['packages/skill/tool-skill/src/index.ts','packages/interaction/tool-ask-user/src/index.ts','packages/subagent/tool-subagent-control/src/index.ts','packages/subagent/tool-subagent-control/src/list-agents.ts']){
  (await import(pathToFileURL(join(process.cwd(),path)))).apply(ctx);
}
(await import(pathToFileURL(join(process.cwd(),'packages/subagent/tool-subagent/src/index.ts')))).apply(ctx,{provider:'spawn',maxDepth:1,backgroundMode:'continuable'});
(await import(pathToFileURL(join(root,'app/research_web/runtime/specialists.mjs')))).apply(ctx,{researchRoot:'/tmp/never-used',nativeLlmModule:join(process.cwd(),'packages/llm/llm/lib/index.js')});
const web=await import(pathToFileURL(join(process.cwd(),'packages/web/tool-web/src/index.ts')));
web.apply(ctx,{search:true,fetch:false,searchMaxResults:8,searchMaxQueries:4,fetchTimeoutMs:30000,searchTimeoutMs:60000,fetchMaxOutputChars:200000});
(await import(pathToFileURL(join(root,'app/research_web/runtime/research-tools.mjs')))).apply(ctx,{python:'/usr/bin/python3',runnerPath:'/tmp/never-run.py',researchRoot:'/tmp/never-used',timeoutSeconds:60,maxOutputBytes:262144});
const enabledTools=['datahub_search_assets','datahub_get_trading_calendar','datahub_get_market_bars','datahub_get_market_snapshot','datahub_get_index_data','datahub_get_financials','datahub_get_market_activity','datahub_get_factor_macro','datahub_get_fund_data','datahub_search_news','datahub_search_announcements','datahub_search_research','datahub_search_web','datahub_get_database_schema','datahub_query_table','datahub_get_external_data'];
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


def test_product_tool_catalog_matches_runtime_input_metadata_without_dsh_source() -> None:
    root = Path(__file__).parents[2]
    catalog = {row["id"]: row for row in tool_catalog()["items"]}
    data_tools = [
        name for name, row in catalog.items() if row["source"] == "runtime/public-data.mjs"
    ]
    enabled_tools = sorted(
        {
            required
            for name in data_tools
            for required in catalog[name].get("required_tools", [name])
        }
    )
    script = r"""
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const [root, enabledJson, python] = process.argv.slice(1);
const tools = [];
const ctx = {tools:{register(tool){tools.push(tool);}},logger:{info(){},warn(){}}};
const researchRoot = join(root,'__registration_only_never_used__');
(await import(pathToFileURL(join(root,'app/research_web/runtime/research-tools.mjs')))).apply(ctx,{
  python,runnerPath:join(researchRoot,'never-run.py'),researchRoot,
});
(await import(pathToFileURL(join(root,'app/research_web/runtime/public-data.mjs')))).apply(ctx,{
  researchRoot,enabledTools:JSON.parse(enabledJson),
});
console.log(JSON.stringify(tools.map(tool=>({id:tool.name,parameters:tool.parameters}))));
"""
    result = subprocess.run(
        [
            "node",
            "--input-type=module",
            "-e",
            script,
            str(root),
            json.dumps(enabled_tools),
            sys.executable,
        ],
        cwd=root,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    captured = json.loads(result.stdout)
    actual = {row["id"]: row["parameters"] for row in captured}
    assert len(actual) == len(captured)
    for name in [*data_tools, "research_run_script"]:
        declared = catalog[name]["parameters"]
        registered = actual[name]
        assert set(declared["properties"]) == set(registered["properties"]), name
        assert set(declared["required"]) == set(registered.get("required", [])), name
        for key, value in declared["properties"].items():
            assert value["type"] == registered["properties"][key]["type"], (name, key)
        for key in ("purpose", "quality"):
            if key in declared["properties"]:
                assert declared["properties"][key]["enum"] == registered["properties"][key]["enum"]


def test_knowledge_tool_catalog_keeps_unique_query_and_hit_registrations(source):
    script = r"""
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
const root = process.argv[1];
const tools = [];
const ctx = {tools:{register(tool){tools.push(tool);}},logger:{info(){},warn(){}}};
const plugin = await import(pathToFileURL(join(root,'app/research_web/runtime/research-tools.mjs')));
plugin.apply(ctx,{python:'/usr/bin/python3',runnerPath:'/tmp/never-run.py',researchRoot:'/tmp/never-used'});
console.log(JSON.stringify(tools.filter(tool=>['research_search_knowledge','research_read_knowledge'].includes(tool.name)).map(tool=>({id:tool.name,parameters:tool.parameters}))));
"""
    native = json.loads(node(source, script, Path(__file__).parents[2]))
    assert [item["id"] for item in native] == [
        "research_search_knowledge",
        "research_read_knowledge",
    ]
    for item, field in zip(native, ["query", "hit_id"], strict=True):
        entry = next(row for row in tool_catalog()["items"] if row["id"] == item["id"])
        assert entry["selectable"] is False
        assert entry["parameters"]["required"] == item["parameters"]["required"] == [field]
        assert set(entry["parameters"]["properties"]) == {field}
        assert set(item["parameters"]["properties"]) == {field}
        assert item["parameters"]["additionalProperties"] is False
        assert entry["parameters"]["properties"][field]["type"] == "string"
