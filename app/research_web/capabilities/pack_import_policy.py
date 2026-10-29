"""Frozen stdlib-only import admission shared by Host and the Native launcher.

The actual validator import graph binds module-time optional imports, including
relative/transitive modules. Unbound lazy/dynamic imports are denied by the fixed
Native finder; this does not claim to enable arbitrary remote resolver code.
"""

from __future__ import annotations

import ast
import importlib.util
import logging
import sys
import sysconfig
import types
from importlib.machinery import EXTENSION_SUFFIXES, BuiltinImporter, FrozenImporter, PathFinder
from pathlib import Path

log = logging.getLogger(__name__)
SCHEMA = "research_pack_import_policy_v1"
LOCAL_MODULES = {
    "calculate": "calculate.py",
    "pack_native": "pack_native.py",
    "pack_import_policy": "pack_import_policy.py",
    "core": "core/__init__.py",
    "core.observability": "core/observability.py",
    "rwb_pack_core": "rwb_pack_core/__init__.py",
    **{
        "rwb_pack_core." + name: "rwb_pack_core/" + name + ".py"
        for name in (
            "atoms",
            "bundles",
            "contracts",
            "limited",
            "record_contracts",
            "format_profile",
        )
    },
}


def module_files(dependencies):
    modules = {}
    for dependency in dependencies:
        base = Path(dependency["origin"])
        for relative in dependency["roots"]:
            root = base / relative
            paths = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in paths:
                if not path.is_file() or "__pycache__" in path.parts:
                    continue
                name = path.relative_to(base).as_posix()
                if name.endswith(".py"):
                    name = name[:-3]
                else:
                    suffix = next((s for s in EXTENSION_SUFFIXES if name.endswith(s)), None)
                    if suffix is None:
                        continue
                    name = name[: -len(suffix)]
                package = name.endswith("/__init__")
                if package:
                    name = name[: -len("/__init__")]
                name = name.replace("/", ".")
                if name in modules:
                    previous = modules[name][0]
                    if previous.suffix == ".py" and path.suffix != ".py":
                        modules[name] = (path, package)
                    elif previous.suffix != ".py" and path.suffix == ".py":
                        continue
                    else:
                        raise ValueError("ambiguous dependency module")
                else:
                    modules[name] = (path, package)
    return modules


def _import_facts(source, name, package, filename):
    """Return immutable syntax facts; current resolution is never captured here."""
    tree = ast.parse(source, filename=filename)
    imports = []
    dynamic = False

    def visit(node, lazy=False):
        nonlocal dynamic
        lazy = lazy or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
        if isinstance(node, ast.Import):
            imports.extend((alias.name, lazy) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                base = importlib.util.resolve_name("." * node.level + base, package)
            imports.append((base, lazy))
            imports.extend((base + "." + alias.name, lazy) for alias in node.names)
        elif isinstance(node, ast.Call) and (
            isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            or isinstance(node.func, ast.Attribute)
            and node.func.attr == "import_module"
        ):
            if not lazy:
                raise ValueError("dynamic module-time import is not closed")
            dynamic = True
        for child in ast.iter_child_nodes(node):
            visit(child, lazy)

    visit(tree)
    return tuple(imports), dynamic


def build_policy(dependencies, *, _source_facts=None):
    """Bind module-time optional imports; block unbound lazy/dynamic imports.

    Function bodies are inspected for managed/stdlib reachability too, but an
    unbound lazy root is *denied* at actual Native import, never assumed safe.
    Remote schema resolution is separately forbidden by the frozen profile.
    """
    modules = module_files(dependencies)
    roots = sorted(name for name in modules if "." not in name)
    pending, visited, absent, blocked, standard = list(roots), set(), set(), set(), set()
    dynamic = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path, is_package = modules[name]
        if path.suffix != ".py":
            continue
        # Always observe current bytes, even inside the same admission pair.
        source = path.read_bytes()
        package = name if is_package else name.rpartition(".")[0]
        key = (name, package, source)
        facts = None if _source_facts is None else _source_facts.get(key)
        if facts is None:
            facts = _import_facts(source, name, package, str(path))
            if _source_facts is not None:
                _source_facts[key] = facts
        imports, has_dynamic = facts
        if has_dynamic:
            dynamic.add(name)
        for imported, lazy in imports:
            root = imported.split(".")[0]
            if root in roots:
                parts = imported.split(".")
                pending.extend(
                    candidate
                    for size in range(1, len(parts) + 1)
                    if (candidate := ".".join(parts[:size])) in modules
                )
            elif root in sys.stdlib_module_names:
                standard.add(root)
            elif root:
                (blocked if lazy else absent).add(root)
    return {
        "schema": SCHEMA,
        "roots": roots,
        "reachable_modules": sorted(visited),
        "absent": sorted(absent),
        "blocked_lazy": sorted(blocked - absent),
        "dynamic_modules_guarded": sorted(dynamic),
        "stdlib_roots": sorted(standard),
        "native_imports": "managed_or_stdlib_only_v1",
    }


def _stdlib_origin(spec):
    if spec is None:
        return False
    if spec.origin in {"built-in", "frozen"}:
        return True
    if not spec.origin:
        return False
    path = Path(spec.origin).resolve(strict=True)
    stdlib = Path(sysconfig.get_path("stdlib")).resolve(strict=True)
    return path.is_relative_to(stdlib) and not {"site-packages", "dist-packages"}.intersection(
        path.parts
    )


def _standard_check(names):
    for name in names:
        spec = importlib.util.find_spec(name)
        search = (
            BuiltinImporter.find_spec(name)
            or FrozenImporter.find_spec(name)
            or PathFinder.find_spec(name)
        )
        if not _stdlib_origin(spec) or not _stdlib_origin(search):
            raise ValueError("stdlib dependency origin shadowed")
        module = sys.modules.get(name)
        if (
            module is not None
            and spec.origin not in {"built-in", "frozen"}
            and getattr(module, "__file__", None) != spec.origin
        ):
            raise ValueError("preloaded stdlib dependency shadowed")


def _bound_module(name, module, modules):
    if name not in modules or module is None:
        raise ValueError("unbound preloaded dependency module")
    expected, package = modules[name]
    cache = getattr(module, "__cached__", None)
    if cache is not None and (
        expected.suffix != ".py" or cache != importlib.util.cache_from_source(str(expected))
    ):
        raise ValueError("preloaded dependency cache outside closed roots")
    spec = getattr(module, "__spec__", None)
    if (
        getattr(module, "__file__", None) != str(expected)
        or spec is None
        or spec.origin != str(expected)
        or package
        and list(getattr(module, "__path__", [])) != [str(expected.parent)]
    ):
        raise ValueError("preloaded dependency origin shadowed")


def _references(module, modules, roots, checked_code):
    # A module table can be restored while an imported validator still retains
    # a shadow module/function/class object. Validate the actual references too.
    code_origins = {str(item[0]) for item in modules.values()}
    for value in list(vars(module).values()):
        if isinstance(value, types.ModuleType):
            owner = value.__name__
            if owner.split(".")[0] in roots:
                _bound_module(owner, value, modules)
            elif not _stdlib_origin(getattr(value, "__spec__", None)):
                raise ValueError("unbound referenced dependency module")
        elif isinstance(value, (types.FunctionType, type)):
            owner = getattr(value, "__module__", "") or ""
            if owner.split(".")[0] not in roots | sys.stdlib_module_names:
                raise ValueError("unbound referenced dependency object")
            functions = (
                [value] if isinstance(value, types.FunctionType) else list(vars(value).values())
            )
            for function in functions:
                if isinstance(function, (staticmethod, classmethod)):
                    function = function.__func__
                if isinstance(function, property):
                    function = function.fget
                if not isinstance(function, types.FunctionType):
                    continue
                filename = function.__code__.co_filename
                # Bound attrs/typing generators synthesize methods. Their source
                # generator is already in the byte-bound managed/stdlib roots.
                if filename.startswith("<") or filename in code_origins or filename in checked_code:
                    continue
                origin = types.SimpleNamespace(origin=filename)
                if not _stdlib_origin(origin):
                    raise ValueError("referenced function code outside closed origins")
                checked_code.add(filename)


def verify_policy(policy, dependencies, *, _source_facts=None):
    """Check current search resolution and every already-loaded root/submodule.

    This runs before Native calculation imports and again on Host binding. A
    removed shadow sys.path entry does not hide a previously imported module.
    """
    try:
        if policy.get("schema") != SCHEMA or policy != build_policy(
            dependencies, _source_facts=_source_facts
        ):
            raise ValueError("dependency import policy changed")
        modules = module_files(dependencies)
        for name in policy["roots"]:
            expected, package = modules[name]
            spec = importlib.util.find_spec(name)
            search = PathFinder.find_spec(name)
            if (
                spec is None
                or search is None
                or spec.origin != str(expected)
                or search.origin != str(expected)
            ):
                raise ValueError("dependency search origin shadowed")
            if package and list(spec.submodule_search_locations or []) != [str(expected.parent)]:
                raise ValueError("dependency search package path shadowed")
        checked_code = set()
        for name, module in list(sys.modules.items()):
            if name.split(".")[0] not in policy["roots"]:
                continue
            _bound_module(name, module, modules)
            _references(module, modules, set(policy["roots"]), checked_code)
        _standard_check(policy["stdlib_roots"])
        for name in policy["absent"]:
            if name in sys.modules or importlib.util.find_spec(name) is not None:
                raise ValueError("unbound optional dependency available")
    except (OSError, ValueError, TypeError, ImportError, SyntaxError) as exc:
        log.warning("research_pack_import_policy_rejected error_type=%s", type(exc).__name__)
        raise ValueError("pack_import_policy_unverified") from exc


class _NativeImports:
    """Per-process Native finder; never installed into the Host process."""

    def __init__(self, modules, scripts, absent):
        self.modules = modules
        self.absent = set(absent)
        self.scripts = Path(scripts)

    def find_spec(self, fullname, path=None, target=None):
        root = fullname.split(".")[0]
        if root in sys.stdlib_module_names:
            spec = (
                BuiltinImporter.find_spec(fullname)
                or FrozenImporter.find_spec(fullname)
                or PathFinder.find_spec(fullname, path)
            )
            if spec is None:
                raise ModuleNotFoundError(fullname)
            if not _stdlib_origin(spec):
                raise ValueError("pack_import_policy_unverified")
            return spec
        spec = PathFinder.find_spec(fullname, path)
        if root in self.absent and spec is None:
            raise ModuleNotFoundError(fullname)
        if fullname in self.modules:
            if spec is None or spec.origin != str(self.modules[fullname][0]):
                raise ValueError("pack_import_policy_unverified")
            return spec
        if (
            fullname in LOCAL_MODULES
            and spec is not None
            and spec.origin == str(self.scripts / LOCAL_MODULES[fullname])
        ):
            return spec
        log.warning("research_pack_native_import_rejected module=%s", fullname)
        raise ValueError("pack_import_policy_unverified")


def install_native(policy, dependencies, scripts):
    """Called by the fixed launcher before calculate/jsonschema can execute."""
    verify_policy(policy, dependencies)
    _standard_check(set(sys.modules) & sys.stdlib_module_names)
    modules = module_files(dependencies)
    # Cached modules bypass meta finders. A fresh -I Native process may contain
    # only Python bootstrap modules, this frozen helper and its stdlib imports.
    for name, module in list(sys.modules.items()):
        root = name.split(".")[0]
        if (
            root in sys.stdlib_module_names
            or name in modules
            or root in {"__main__", "pack_import_policy"}
        ):
            continue
        spec = getattr(module, "__spec__", None)
        if _stdlib_origin(spec):
            continue
        log.warning("research_pack_native_bootstrap_rejected module=%s", name)
        raise ValueError("pack_import_policy_unverified")
    sys.meta_path.insert(0, _NativeImports(modules, scripts, policy["absent"]))
