"""Offline native-macOS contract tests for the research script boundary."""

import importlib.util
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "app/research_web/sandbox.py"
PYTHON = Path(sys.executable)


def load_runner():
    assert SOURCE.is_file(), "research sandbox runner has not been implemented"
    spec = importlib.util.spec_from_file_location("research_sandbox_tested", SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_session(root):
    session = root / "sessions" / str(uuid4())
    for name in ("inputs", "outputs", "tmp", "resources"):
        (session / name).mkdir(parents=True)
    return session


def test_runner_contract_exists():
    assert callable(load_runner().run_script)


@pytest.fixture
def prepared(tmp_path):
    if sys.platform != "darwin":
        pytest.skip("native macOS Seatbelt evidence only")
    module = load_runner()
    root = tmp_path / "research"
    session = make_session(root)
    config = module.SandboxConfig(research_root=root, python=PYTHON)
    return module, root, session, config


def test_reads_inputs_resources_and_writes_only_outputs_tmp(prepared):
    module, _root, session, config = prepared
    (session / "inputs/a.txt").write_text("input")
    (session / "resources/r.txt").write_text("resource")
    code = """
from pathlib import Path
import tempfile
assert Path('inputs/a.txt').read_text() == 'input'
assert Path('resources/r.txt').read_text() == 'resource'
Path('outputs/result.txt').write_text('output')
with tempfile.NamedTemporaryFile() as f:
    assert '/tmp/' in f.name
print('success')
"""
    result = module.run_script(config, session, code)
    assert result.status == "completed", result
    assert result.stdout == "success\n"
    assert (session / "outputs/result.txt").read_text() == "output"


def test_rejects_host_sibling_inputs_links_and_network(prepared):
    module, root, session, config = prepared
    outer = root / "index.json"
    outer.write_text("nonsecret-host-canary")
    sibling = make_session(root)
    other = sibling / "inputs/canary.txt"
    other.write_text("sibling-canary")
    input_file = session / "inputs/canary.txt"
    input_file.write_text("input-canary")
    resource_file = session / "resources/canary.txt"
    resource_file.write_text("resource-canary")
    (session / "outputs/escape").symlink_to(outer)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        code = f"""
import os, socket, errno
from pathlib import Path
def denied(fn):
    try: fn()
    except OSError as exc: assert exc.errno in (errno.EPERM, errno.EACCES), exc
    else: raise AssertionError('sandbox escape succeeded')
denied(lambda: Path({str(outer)!r}).read_text())
denied(lambda: Path({str(outer)!r}).write_text('escape'))
denied(lambda: Path({'/System/Volumes/Data' + str(outer)!r}).read_text())
denied(lambda: Path({str(other)!r}).read_text())
denied(lambda: Path({str(other)!r}).write_text('escape'))
denied(lambda: Path('inputs/canary.txt').write_text('escape'))
denied(lambda: Path('resources/canary.txt').write_text('escape'))
denied(lambda: Path('outputs/escape').read_text())
denied(lambda: Path('outputs/escape').write_text('escape'))
denied(lambda: Path('inputs/new.txt').write_text('escape'))
denied(lambda: Path('new-at-session-root.txt').write_text('escape'))
denied(lambda: os.link({str(outer)!r}, 'outputs/hardlink'))
denied(lambda: os.link('inputs/canary.txt', 'outputs/input-hardlink'))
denied(lambda: socket.create_connection(('127.0.0.1', {listener.getsockname()[1]}), 1))
print('boundaries-passed')
"""
        result = module.run_script(config, session, code)
    assert result.status == "completed", result
    assert result.stdout == "boundaries-passed\n"
    assert outer.read_text() == "nonsecret-host-canary"
    assert input_file.read_text() == "input-canary"
    assert resource_file.read_text() == "resource-canary"


def test_does_not_inherit_secret_or_startup_environment(prepared, monkeypatch):
    module, _root, session, config = prepared
    monkeypatch.setenv("DATABASE_URL", "fake-sensitive-canary")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-sensitive-canary")
    monkeypatch.setenv("BASH_ENV", "fake-startup-canary")
    result = module.run_script(
        config, session, "import os,json; print(json.dumps(sorted(os.environ)))"
    )
    assert result.status == "completed", result
    assert set(json.loads(result.stdout)) == set(module.child_environment(session))
    assert "DATABASE_URL" not in result.stdout


def test_rejects_fork_and_exec_process_escape(prepared):
    module, _root, session, config = prepared
    code = """
import os, sys, errno
try: os.fork()
except OSError as exc: assert exc.errno in (errno.EPERM, errno.EACCES)
else: raise AssertionError('fork escaped')
try: pid = os.posix_spawn(sys.executable, [sys.executable, '-I', '-S', '-B', '-c', 'raise SystemExit(0)'], {}, setsid=True)
except OSError as exc: assert exc.errno in (errno.EPERM, errno.EACCES)
else:
    os.waitpid(pid, 0)
    raise AssertionError('posix_spawn with a new session escaped')
try: os.execv('/bin/echo', ['echo', 'escaped'])
except OSError as exc: assert exc.errno in (errno.EPERM, errno.EACCES)
else: raise AssertionError('exec escaped')
print('no-process-escape')
"""
    result = module.run_script(config, session, code)
    assert result.status == "completed", result
    assert result.stdout == "no-process-escape\n"


def test_timeout_and_output_limit_are_bounded(prepared):
    module, root, session, config = prepared
    config = module.SandboxConfig(
        research_root=root, python=PYTHON, timeout_seconds=0.3, max_output_bytes=1024
    )
    started = time.monotonic()
    result = module.run_script(config, session, "while True: pass")
    assert result.status == "timed_out", result
    assert time.monotonic() - started < 5
    result = module.run_script(config, session, "while True: print('x' * 10000, flush=True)")
    assert result.status == "output_limit", result
    assert len(result.stdout.encode()) + len(result.stderr.encode()) <= 1024


def test_rejects_untrusted_workdir_and_symlink(prepared):
    module, root, session, config = prepared
    with pytest.raises(module.SandboxError):
        module.run_script(config, root, "print('never')")
    with pytest.raises(module.SandboxError):
        module.run_script(config, root / "sessions/../../outside", "print('never')")
    (session / "tmp").rmdir()
    (session / "tmp").symlink_to(root)
    with pytest.raises(module.SandboxError):
        module.run_script(config, session, "print('never')")


def test_fails_closed_on_other_platforms_and_bad_limits(prepared, monkeypatch):
    module, root, session, config = prepared
    for timeout in (0, 61, float("nan"), float("inf")):
        with pytest.raises(module.SandboxError):
            module.run_script(module.SandboxConfig(root, PYTHON, timeout), session, "print(1)")
    for code in ("", " " * 10, "中" * 30_000):
        with pytest.raises(module.SandboxError):
            module.run_script(config, session, code)
    monkeypatch.setattr(module.sys, "platform", "unsupported")
    with pytest.raises(module.SandboxError, match="native macOS"):
        module.run_script(config, session, "print('never')")


def test_explicit_venv_document_libraries_import(prepared):
    module, _root, session, config = prepared
    result = module.run_script(
        config,
        session,
        "import docx,pdfplumber,openpyxl,matplotlib; "
        "matplotlib.use('Agg'); import matplotlib.pyplot as plt; "
        "docx.Document().save('outputs/report.docx'); "
        "openpyxl.Workbook().save('outputs/report.xlsx'); "
        "plt.plot([1,2]); plt.savefig('outputs/chart.png'); print('document-libraries-ready')",
    )
    assert result.status == "completed", result
    assert result.stdout == "document-libraries-ready\n"
    assert (session / "outputs/report.docx").read_bytes().startswith(b"PK")
    assert (session / "outputs/report.xlsx").read_bytes().startswith(b"PK")
    assert (session / "outputs/chart.png").read_bytes().startswith(b"\x89PNG")


def test_trusted_resource_import_does_not_require_cwd_read_permission(prepared):
    module, _root, session, config = prepared
    (session / "resources/helper_canary.py").write_text("VALUE = 42\n")
    result = module.run_script(config, session, "from helper_canary import VALUE; print(VALUE)")
    assert result.status == "completed", result
    assert result.stdout == "42\n"


def test_native_tool_contract_and_trusted_cwd(tmp_path):
    plugin = SOURCE.parent / "runtime/research-tools.mjs"
    assert plugin.is_file(), "native research tool has not been implemented"
    # Native tool integration is exercised with a minimal context, not a model call.
    config_json = json.dumps(
        {"python": str(PYTHON), "runnerPath": str(SOURCE), "researchRoot": str(tmp_path)}
    )
    program = (
        f"import {{ apply }} from {json.dumps(plugin.as_uri())};\nconst config = {config_json};"
        + """
let tool;
apply({ tools: {register(t) {tool=t;}}, logger: {info(){},warn(){},error(){}}}, config);
if(tool.name!=='af_run_script') throw Error('missing native tool');
for(const code of ['', '中'.repeat(30000)]) {
  try { await tool.execute({code},{signal:new AbortController().signal}); throw Error('unbounded source accepted'); }
  catch(e) { if(!String(e).includes('bounded code')) throw e; }
}
try { await tool.execute({code:'print(1)'},{signal:new AbortController().signal}); throw Error('untrusted call accepted'); }
catch(e) { if(!String(e).includes('trusted')) throw e; }
console.log('native-tool-ok');
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "native-tool-ok\n"


def test_native_tool_schemas_match_pinned_dsh_converter(tmp_path):
    dsh_source = os.environ.get("DSH_SOURCE_ROOT")
    if not dsh_source:
        pytest.skip("set DSH_SOURCE_ROOT to the pinned built DSH checkout")
    converter = Path(dsh_source) / "packages/core/tools/lib/index.js"
    assert converter.is_file(), "explicit DSH_SOURCE_ROOT must contain the built schema converter"
    plugin = SOURCE.parent / "runtime/research-tools.mjs"
    config_json = json.dumps(
        {"python": str(PYTHON), "runnerPath": str(SOURCE), "researchRoot": str(tmp_path)}
    )
    program = (
        f"import {{ apply }} from {json.dumps(plugin.as_uri())};\n"
        "import { assertSupportedJsonSchema, validateJsonSchemaValue, jsonSchemaToTs, jsonSchemaToPy } "
        f"from {json.dumps(converter.as_uri())};\nconst config = {config_json};" + """
let tool;
apply({tools:{register(t){tool=t;}},logger:{info(){},warn(){},error(){}}},config);
// Use the same implementation ToolRuntime.register invokes, not a local mock.
assertSupportedJsonSchema(tool.output.schema);
assertSupportedJsonSchema(tool.parameters);
const result = {status:'completed',stdout:'',stderr:'',exit_code:0,error:null};
for (const value of [result, {...result,status:'failed',exit_code:null,error:'rejected'}]) {
  const errors = validateJsonSchemaValue(tool.output.schema,value);
  if(errors.length) throw Error(errors.join('; '));
}
for (const value of [{...result,exit_code:'0'}, {...result,error:1}]) {
  if(!validateJsonSchemaValue(tool.output.schema,value).length) throw Error('invalid output accepted');
}
for(const schema of [tool.parameters,tool.output.schema]) {
  if(jsonSchemaToTs(schema)==='unknown') throw Error('TypeScript SDK schema degraded to unknown');
  if(jsonSchemaToPy(schema)==='Any') throw Error('Python SDK schema degraded to Any');
}
console.log('pinned-dsh-schemas-ok');
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "pinned-dsh-schemas-ok\n"


def test_native_tool_runs_inherited_workspace_and_cancels(prepared):
    _module, root, session, _config = prepared
    plugin = SOURCE.parent / "runtime/research-tools.mjs"
    config_json = json.dumps(
        {
            "python": str(PYTHON),
            "runnerPath": str(SOURCE),
            "researchRoot": str(root),
            "timeoutSeconds": 5,
        }
    )
    program = (
        f"import {{ apply }} from {json.dumps(plugin.as_uri())};\nconst config = {config_json}; const cwd = {json.dumps(str(session))};"
        + """
let tool;
const parent = {header:{id:'parent',cwd}};
const child = {header:{id:'child',cwd,parentSession:'parent'}};
const ctx = {tools:{register(t){tool=t;}},sessions:{get(id){return id==='parent'?parent:undefined;}},logger:{info(){},warn(){},error(){}}};
apply(ctx,config);
const result = await tool.execute({code:"print('原生工具-success')"},{agent:{session:child},signal:new AbortController().signal});
if(result.status!=='completed'||result.stdout!=='原生工具-success\\n') throw Error(JSON.stringify(result));
parent.header.cwd = '/not-this-workspace';
try {await tool.execute({code:'print(1)'},{agent:{session:child},signal:new AbortController().signal}); throw Error('ancestor mismatch accepted');}
catch(e) {if(!String(e).includes('ancestor')) throw e;}
parent.header.cwd = cwd;
const controller=new AbortController();
setTimeout(()=>controller.abort(),150);
try {await tool.execute({code:'while True: pass'},{agent:{session:child},signal:controller.signal}); throw Error('cancel not enforced');}
catch(e) {if(!String(e).match(/cancel|abort/i)) throw e;}
console.log('native-inheritance-and-cancel-passed');
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "native-inheritance-and-cancel-passed\n"


def test_cancel_reaps_script_after_it_closes_output_streams(prepared):
    _module, root, session, _config = prepared
    plugin = SOURCE.parent / "runtime/research-tools.mjs"
    config_json = json.dumps(
        {
            "python": str(PYTHON),
            "runnerPath": str(SOURCE),
            "researchRoot": str(root),
            "timeoutSeconds": 8,
        }
    )
    program = (
        f"import {{ apply }} from {json.dumps(plugin.as_uri())};\n"
        "import { existsSync, readFileSync } from 'node:fs';\n"
        "import { setTimeout as pause } from 'node:timers/promises';\n"
        f"const config = {config_json}; const cwd = {json.dumps(str(session))};" + """
let tool;
apply({tools:{register(t){tool=t;}},logger:{info(){},warn(){},error(){}}},config);
const controller = new AbortController();
const execution = tool.execute({code:"import os,time; from pathlib import Path; Path('outputs/started').write_text(str(os.getpid())); os.close(1); os.close(2); time.sleep(4); Path('outputs/after-cancel').write_text('bad')"},{agent:{session:{header:{id:'root',cwd}}},signal:controller.signal});
const result = execution.then(value=>({value}),error=>({error}));
const deadline = Date.now()+5000;
while(!existsSync(cwd+'/outputs/started')) {
  if(Date.now()>deadline) throw Error('script never started');
  await pause(10);
}
const pid = Number(readFileSync(cwd+'/outputs/started','utf8'));
controller.abort();
const stopped = await result;
await pause(4200);
if(existsSync(cwd+'/outputs/after-cancel')) throw Error('cancelled script continued writing');
try { process.kill(pid,0); throw Error('cancelled script process survived'); }
catch(error) { if(error.code!=='ESRCH') throw error; }
if(!stopped.error || !String(stopped.error).includes('cancel')) throw Error('cancel was not reported');
console.log('closed-stream-cancel-reaped');
"""
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "closed-stream-cancel-reaped\n"
