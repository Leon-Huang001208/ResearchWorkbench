"""Additional fail-closed import and publication recovery checks."""

import hashlib
import io
import stat
import zipfile

import pytest
from test_capabilities import api as api_fixture
from test_capabilities import candidate, create

from app.research_web.capabilities.catalog import CapabilityCatalog
from app.research_web.capabilities.models import CapabilityError

api = api_fixture


def check_script(client, content):
    value = candidate()
    value["files"] = [{"path": "scripts/research.py", "content": content}]
    value["reviewed_scripts"] = [hashlib.sha256(content.encode()).hexdigest()]
    row = create(client, value)
    return client.post(f"/api/research/capabilities/{row['id']}/check").json()


def test_reviewed_script_cannot_spawn_host_processes(api, tmp_path):
    client, _, _ = api
    marker = tmp_path / "must-not-exist"
    content = "import subprocess\n" f"subprocess.run(['touch', {str(marker)!r}], check=True)\n"
    check = check_script(client, content)

    runtime_issues = [
        item for item in check["issues"] if item["code"] == "runtime_incompatible_script"
    ]
    assert not check["valid"]
    assert runtime_issues
    assert "禁止派生进程" in runtime_issues[0]["message"]
    assert "宿主命令" in runtime_issues[0]["message"]
    assert not marker.exists()


@pytest.mark.parametrize(
    "content",
    [
        "import subprocess as process_module",
        "from subprocess import run as launch",
        "import subprocess\nlauncher = subprocess.run",
        "import os as host_os\nlaunch = host_os.system",
        "from os import popen as host_popen\nlaunch = host_popen",
        "import os\nlaunch = os.spawnlp",
        "from os import posix_spawn as launch\ncopy = launch",
        "import os\nlaunch = os.forkpty",
        "from os import execve as replace_process\nlaunch = replace_process",
        "import pty as pseudo_terminal\nlaunch = pseudo_terminal.spawn",
        "from pty import spawn as launch\ncopy = launch",
        "import asyncio as aio\nlaunch = aio.create_subprocess_exec",
        "from asyncio import create_subprocess_shell as launch\ncopy = launch",
        "from os import *",
        "from pty import *",
        "from asyncio import *",
    ],
    ids=[
        "subprocess-module-alias",
        "subprocess-from-import",
        "subprocess-callable-transfer",
        "os-system-alias",
        "os-popen-from-import",
        "os-spawn-family",
        "os-posix-spawn-family",
        "os-fork-family",
        "os-exec-family-from-import",
        "pty-spawn-alias",
        "pty-spawn-from-import",
        "asyncio-exec-alias",
        "asyncio-shell-from-import",
        "os-star-import",
        "pty-star-import",
        "asyncio-star-import",
    ],
)
def test_reviewed_script_rejects_incompatible_runtime_entrypoints(api, content):
    client, _, _ = api

    check = check_script(client, content)

    assert "runtime_incompatible_script" in {item["code"] for item in check["issues"]}


@pytest.mark.parametrize(
    "content",
    [
        "class Local:\n    run = staticmethod(lambda *args: None)\nsubprocess = Local()\nsubprocess.run([])",
        "class Local:\n    system = staticmethod(lambda *args: None)\nos = Local()\nos.system('safe')",
        "class Local:\n    spawn = staticmethod(lambda *args: None)\npty = Local()\npty.spawn('safe')",
        "class Local:\n    create_subprocess_exec = staticmethod(lambda *args: None)\nasyncio = Local()\nasyncio.create_subprocess_exec('safe')",
    ],
    ids=["subprocess-shadow", "os-shadow", "pty-shadow", "asyncio-shadow"],
)
def test_host_process_names_without_matching_import_are_allowed(api, content):
    client, _, _ = api

    check = check_script(client, content)

    assert "runtime_incompatible_script" not in {item["code"] for item in check["issues"]}
    assert check["valid"]


def test_import_binding_shadowing_remains_conservatively_blocked(api):
    """Publication checks deliberately do not attempt complete Python scope analysis."""

    client, _, _ = api
    content = (
        "import os\n"
        "class Local:\n"
        "    system = staticmethod(lambda *args: None)\n"
        "os = Local()\n"
        "os.system('still conservatively blocked')"
    )

    check = check_script(client, content)

    assert "runtime_incompatible_script" in {item["code"] for item in check["issues"]}


@pytest.mark.parametrize(
    "name,content,expected_codes",
    [
        ("scripts/install_hook.py", "print('installer')", {"unsafe_file"}),
        (
            "scripts/research.py",
            "import ensurepip\nensurepip.bootstrap()",
            {"installer_forbidden"},
        ),
        (
            "scripts/research.py",
            "import subprocess\nsubprocess.run(['pip', 'install', 'evil'])",
            {"installer_forbidden", "runtime_incompatible_script"},
        ),
    ],
)
def test_installer_scripts_remain_invalid_even_if_reviewed(api, name, content, expected_codes):
    client, _, _ = api
    value = candidate()
    value["files"] = [{"path": name, "content": content}]
    value["reviewed_scripts"] = [hashlib.sha256(content.encode()).hexdigest()]
    row = create(client, value)
    check = client.post(f"/api/research/capabilities/{row['id']}/check").json()
    codes = {item["code"] for item in check["issues"]}
    assert not check["valid"]
    assert codes >= expected_codes


def test_symlink_directory_entry_and_nested_yaml_fail_closed(api):
    client, _, _ = api
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("SKILL.md", candidate()["instructions"])
        zf.writestr("capability.json", __import__("json").dumps(candidate()["metadata"]))
        info = zipfile.ZipInfo("link/")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zf.writestr(info, "/etc")
    row = client.post(
        "/api/research/capabilities/import", files={"file": ("candidate.zip", archive.getvalue())}
    ).json()
    assert row["status"] == "invalid"
    value = candidate(name="嵌套异常", slug="nested")
    value["instructions"] = (
        "---\nname: nested\ndescription: nested\nmetadata: "
        + "[" * 1200
        + "1"
        + "]" * 1200
        + "\n---\n内容"
    )
    cid = create(client, value)["id"]
    result = client.post(f"/api/research/capabilities/{cid}/check")
    assert result.status_code == 200 and not result.json()["valid"]


def test_version_detail_is_original_and_persisted(api):
    client, _, service = api
    cid = create(client)["id"]
    base = f"/api/research/capabilities/{cid}"
    client.post(base + "/publish")
    value = candidate()
    value["instructions"] += "\n第二版待发布"
    client.patch(base + "/draft", json=value)
    version = client.get(base + "/versions/1")
    assert version.status_code == 200
    assert version.json()["instructions"] == candidate()["instructions"]
    restored = CapabilityCatalog(service.store.root)
    assert restored.detail(cid)["draft"]["instructions"] == value["instructions"]
    restored.data["pending"] = {"id": cid, "version": 2, "status": "uncertain"}
    restored.save()
    with pytest.raises(CapabilityError, match="未确认"):
        CapabilityCatalog(service.store.root).prepare_native_root()


def test_declared_input_types_whitespace_and_invalid_base64_are_reported(api):
    client, _, _ = api
    value = candidate()
    value["files"] = [{"path": "document.md", "base64": None}]
    row = create(client, value)
    assert (
        client.post(f"/api/research/capabilities/{row['id']}/check").json()["status"] == "invalid"
    )


def test_workflow_linked_version_must_still_be_current(api):
    client, _, service = api
    cid = create(client)["id"]
    client.post(f"/api/research/capabilities/{cid}/publish")
    value = candidate(name="关联工作流", slug="linked-flow")
    value.update(
        kind="workflow",
        instructions="",
        steps=[{"title": "执行研究", "instruction": "使用关联Skill", "skill_id": cid, "tools": []}],
    )
    flow = create(client, value)["id"]
    assert client.post(f"/api/research/capabilities/{flow}/publish").status_code == 200
    client.patch(f"/api/research/capabilities/{cid}/draft", json=candidate())
    assert client.post(f"/api/research/capabilities/{cid}/publish").status_code == 200
    with pytest.raises(CapabilityError, match="关联版本"):
        service.capabilities.selection(flow)
