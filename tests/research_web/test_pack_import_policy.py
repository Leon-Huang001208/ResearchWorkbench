"""Real fresh imports cannot execute outside the frozen validator closure unnoticed."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("shadow", ["path", "preloaded", "submodule", "optional"])
def test_actual_optional_and_preloaded_shadow_markers_are_rejected(tmp_path, shadow):
    import idna

    package = tmp_path / "idna"
    shutil.copytree(Path(idna.__file__).parent, package)
    marker = tmp_path / "executed"
    target = package / ("core.py" if shadow == "submodule" else "__init__.py")
    with target.open("a") as stream:
        stream.write(f"\nopen({str(marker)!r},'w').write('actual execution')\n")
    root = str(Path(__file__).parents[2])
    code = f"import sys,json,importlib.util\nsys.path.insert(0,{root!r})\n"
    if shadow == "submodule":
        code += (
            "import idna\n"
            f"spec=importlib.util.spec_from_file_location('idna.core',{str(target)!r})\n"
            "module=importlib.util.module_from_spec(spec)\n"
            "sys.modules['idna.core']=module\nspec.loader.exec_module(module)\n"
        )
    elif shadow == "optional":
        (tmp_path / "fqdn.py").write_text(
            f"open({str(marker)!r},'w').write('actual execution')\nclass FQDN: pass\n"
        )
        code += f"sys.path.insert(0,{str(tmp_path)!r})\nimport fqdn\n"
        # Keep idna at its genuine origin, isolate the other optional-import hole.
        shutil.rmtree(package)
    else:
        code += f"sys.path.insert(0,{str(tmp_path)!r})\nimport idna\n"
        if shadow == "preloaded":
            code += "sys.path.pop(0)\n"
    code += """from app.research_web.capabilities.pack_dependencies import runtime_identity
from app.research_web.capabilities.models import CapabilityError
try:
    runtime_identity()
except CapabilityError as error:
    print(json.dumps({'rejected':error.code}))
else:
    print(json.dumps({'rejected':None}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "actual execution"
    assert json.loads(result.stdout.splitlines()[-1])["rejected"] == "pack_runtime_unverified"


def test_stdlib_shadow_used_by_validator_is_rejected(tmp_path):
    import ipaddress

    target = tmp_path / "ipaddress.py"
    marker = tmp_path / "stdlib-executed"
    target.write_text(
        Path(ipaddress.__file__).read_text() + f"\nopen({str(marker)!r},'w').write('executed')\n"
    )
    code = f"""import sys,json
sys.path.insert(0,{str(tmp_path)!r})
import ipaddress
sys.path.insert(0,{str(Path(__file__).parents[2])!r})
from app.research_web.capabilities.pack_dependencies import runtime_identity
from app.research_web.capabilities.models import CapabilityError
try:
    runtime_identity()
except CapabilityError as error:
    print(json.dumps({{'rejected':error.code}}))
else:
    print(json.dumps({{'rejected':None}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "executed"
    assert json.loads(result.stdout.splitlines()[-1])["rejected"] == "pack_runtime_unverified"


def test_identity_does_not_mutate_other_host_imports():
    from jsonschema import FormatChecker

    from app.research_web.capabilities.models import CapabilityError
    from app.research_web.capabilities.pack_dependencies import runtime_identity

    before_path = list(sys.path)
    before_modules = dict(sys.modules)
    before_checkers = dict(FormatChecker.checkers)
    try:
        runtime_identity()
    except CapabilityError:
        pass
    assert sys.path == before_path
    assert all(sys.modules.get(name) is module for name, module in before_modules.items())
    assert FormatChecker.checkers == before_checkers


@pytest.mark.parametrize("attempt", ["valid", "lazy_remote", "dynamic", "preloaded"])
def test_native_guard_closes_actual_imports_in_fresh_process(tmp_path, attempt):
    from app.research_web.capabilities import pack_import_policy
    from app.research_web.capabilities.pack_dependencies import runtime_identity

    runtime = runtime_identity()
    (tmp_path / "runtime.json").write_text(json.dumps(runtime))
    (tmp_path / "pack_import_policy.py").write_bytes(Path(pack_import_policy.__file__).read_bytes())
    before = "import requests\n" if attempt == "preloaded" else ""
    after = {
        "valid": "from jsonschema import FormatChecker\nFormatChecker().check('example.com','idn-hostname')",
        "lazy_remote": "import requests",
        "dynamic": "import importlib\nimportlib.import_module('requests')",
        "preloaded": "pass",
    }[attempt]
    code = f"""import json,sys
{before}
sys.path.insert(0,{str(tmp_path)!r})
from pack_import_policy import install_native
value=json.load(open({str(tmp_path / 'runtime.json')!r}))
try:
    install_native(value['import_policy'],value['dependencies'],{str(tmp_path)!r})
{os.linesep.join('    '+line for line in after.splitlines())}
except ValueError as error:
    print(json.dumps({{'rejected':str(error)}}))
else:
    print(json.dumps({{'rejected':None}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["rejected"] == (
        None if attempt == "valid" else "pack_import_policy_unverified"
    )


def test_search_shadow_is_rejected_even_when_genuine_package_is_preloaded(tmp_path):
    import idna

    shutil.copytree(Path(idna.__file__).parent, tmp_path / "idna")
    code = f"""import sys,json,idna
sys.path.insert(0,{str(tmp_path)!r})
sys.path.insert(0,{str(Path(__file__).parents[2])!r})
from app.research_web.capabilities.pack_dependencies import runtime_identity
from app.research_web.capabilities.models import CapabilityError
try:
    runtime_identity()
except CapabilityError as error:
    print(json.dumps({{'rejected':error.code}}))
else:
    print(json.dumps({{'rejected':None}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[-1])["rejected"] == "pack_runtime_unverified"


def test_relative_transitive_and_dynamic_source_have_explicit_import_policy(tmp_path):
    from app.research_web.capabilities.pack_import_policy import build_policy

    package = tmp_path / "validator_fixture"
    package.mkdir()
    (package / "__init__.py").write_text("from . import child\n")
    (package / "child.py").write_text("import absent_transitive\n")
    dependencies = [{"origin": str(tmp_path), "roots": ["validator_fixture"]}]
    policy = build_policy(dependencies)
    assert policy["reachable_modules"] == ["validator_fixture", "validator_fixture.child"]
    assert policy["absent"] == ["absent_transitive"]
    (package / "child.py").write_text("import importlib\nimportlib.import_module('external')\n")
    with pytest.raises(ValueError, match="dynamic module-time import is not closed"):
        build_policy(dependencies)
    (package / "child.py").write_text(
        "import importlib\ndef lazy():\n return importlib.import_module('external')\n"
    )
    policy = build_policy(dependencies)
    assert policy["dynamic_modules_guarded"] == ["validator_fixture.child"]
    assert policy["native_imports"] == "managed_or_stdlib_only_v1"


def test_format_retained_shadow_object_is_rejected_after_module_table_is_restored(tmp_path):
    import idna

    package = tmp_path / "idna"
    shutil.copytree(Path(idna.__file__).parent, package)
    marker = tmp_path / "retained-marker"
    with (package / "__init__.py").open("a") as stream:
        stream.write(f"\nopen({str(marker)!r},'w').write('executed')\n")
    code = f"""import sys,json
sys.path.insert(0,{str(tmp_path)!r})
import jsonschema,idna
sys.path.pop(0)
for name in list(sys.modules):
    if name == 'idna' or name.startswith('idna.'):
        del sys.modules[name]
import idna
sys.path.insert(0,{str(Path(__file__).parents[2])!r})
from app.research_web.capabilities.pack_dependencies import runtime_identity
from app.research_web.capabilities.models import CapabilityError
try:
    runtime_identity()
except CapabilityError as error:
    print(json.dumps({{'rejected':error.code}}))
else:
    print(json.dumps({{'rejected':None}}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", code],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "executed"
    assert json.loads(result.stdout.splitlines()[-1])["rejected"] == "pack_runtime_unverified"
