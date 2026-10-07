"""Derive production package assets only after the pinned full-build verification."""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import shutil
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research_web.staged_runtime import verify_staged_runtime, write_staged_manifest

log = logging.getLogger(__name__)
EXCLUDED = frozenset(
    {
        ".git",
        ".github",
        "tests",
        "test",
        "__tests__",
        "fixtures",
        "__fixtures__",
        "benchmarks",
        "benchmark",
        "bench",
        "website",
        "examples",
        "coverage",
        ".cache",
        "__pycache__",
    }
)


def _excluded(relative: Path, published_roots: tuple[Path, ...] = ()) -> bool:
    document_parts = [
        index for index, part in enumerate(relative.parts) if part.lower() in {"doc", "docs"}
    ]
    published_document = bool(document_parts) and any(
        relative.is_relative_to(root) and len(root.parts) <= min(document_parts)
        for root in published_roots
    )
    return (
        any(part.lower() in EXCLUDED for part in relative.parts)
        or (bool(document_parts) and not published_document)
        or any(token in relative.name.lower() for token in (".spec.", ".test.", ".bench."))
        or relative.name.lower().startswith(("readme", "changelog", "contributing"))
    )


def _package_assets(package: Path, *, workspace: bool):
    metadata = json.loads((package / "package.json").read_text())
    declared = metadata.get("files")
    # Only unambiguous directory declarations establish a published runtime
    # subtree. Glob/negative rules do not exempt doc/docs from filtering; this
    # does not use third-party `files` to reselect its installed tarball payload.
    published_roots = ()
    if isinstance(declared, list) and all(
        isinstance(rule, str)
        and rule
        and not rule.startswith("!")
        and not any(token in rule for token in ("*", "?", "[", "\\"))
        and Path(rule).parts
        and not Path(rule).is_absolute()
        and ".." not in Path(rule).parts
        for rule in declared
    ):
        published_roots = tuple(
            Path(rule) for rule in declared if Path(rule).parts and (package / rule).is_dir()
        )
    # Workspace package `files` fields are the upstream publish contract. Installed
    # third-party production packages already are published tarballs; keep their
    # runtime payload (including native binaries), while excluding development data.
    rules = metadata.get("files") if workspace else None
    chosen = {package / "package.json"}
    if rules is not None:
        if not isinstance(rules, list) or not all(isinstance(rule, str) for rule in rules):
            raise ValueError("invalid package files")
        for rule in rules:
            if rule.startswith("!"):
                continue
            if Path(rule).is_absolute() or ".." in Path(rule).parts:
                raise ValueError("unsafe package rule")
            for item in package.glob(rule):
                chosen.update(item.rglob("*") if item.is_dir() else [item])
        negatives = [rule[1:] for rule in rules if rule.startswith("!")]
        chosen = {
            path
            for path in chosen
            if not any(
                fnmatch.fnmatch(path.relative_to(package).as_posix(), rule) for rule in negatives
            )
        }
    else:
        for directory, folders, files in os.walk(package, followlinks=False):
            folders[:] = [
                name
                for name in folders
                if name != "node_modules"
                and not _excluded((Path(directory) / name).relative_to(package), published_roots)
            ]
            chosen.update(Path(directory) / name for name in files)
    chosen.update(path for path in package.glob("LICENSE*") if path.is_file())
    return metadata, sorted(
        path
        for path in chosen
        if not _excluded(path.relative_to(package), published_roots)
        and "node_modules" not in path.relative_to(package).parts
        and (path.is_file() or path.is_symlink())
    )


def stage_assets(source: Path, output: Path, verified: dict) -> None:
    """Copy the declared production dependency graph; never mutate the checkout."""
    try:
        if source.absolute() != source.resolve(strict=True) or output.exists():
            raise ValueError("unsafe staging roots")
        output.mkdir(parents=True)
        queue = [source / "apps/cli"]
        visited = set()
        while queue:
            package = queue.pop()
            if package in visited:
                continue
            if not package.is_relative_to(source):
                raise ValueError("package escape")
            visited.add(package)
            relative = package.relative_to(source)
            metadata, assets = _package_assets(
                package, workspace="node_modules" not in relative.parts
            )
            for asset in assets:
                if not asset.resolve(strict=True).is_relative_to(source):
                    raise ValueError("asset escape")
                target = output / asset.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                if asset.is_symlink():
                    link = os.readlink(asset)
                    if Path(link).is_absolute():
                        raise ValueError("absolute link")
                    target.symlink_to(link)
                else:
                    shutil.copy2(asset, target)
            optional = metadata.get("optionalDependencies", {})
            peers = metadata.get("peerDependencies", {})
            dependencies = {**metadata.get("dependencies", {}), **optional, **peers}
            for name in sorted(dependencies):
                if (
                    not isinstance(name, str)
                    or name.startswith(("/", "."))
                    or ".." in Path(name).parts
                ):
                    raise ValueError("invalid dependency")
                alias = None
                for parent in (package, *package.parents):
                    if not parent.is_relative_to(source):
                        break
                    candidate = parent / "node_modules" / name
                    if os.path.lexists(candidate):
                        alias = candidate
                        break
                if alias is None:
                    optional_peer = metadata.get("peerDependenciesMeta", {}).get(name, {})
                    if name in optional or optional_peer.get("optional"):
                        continue
                    raise ValueError(f"missing dependency {name}")
                resolved = alias.resolve(strict=True)
                if not resolved.is_relative_to(source):
                    raise ValueError("dependency escape")
                if alias != resolved:
                    target = output / alias.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if not os.path.lexists(target):
                        relative_target = os.path.relpath(
                            output / resolved.relative_to(source), target.parent
                        )
                        target.symlink_to(relative_target)
                queue.append(resolved)
        # Native loaders may resolve a selected optional platform package from
        # another package's anchor, relying on pnpm's root or private hoist tree.
        # Preserve only aliases to entities already selected by the production
        # graph; never stage an additional development dependency through hoists.
        for hoisted in (source / "node_modules", source / "node_modules/.pnpm/node_modules"):
            if not os.path.lexists(hoisted):
                continue
            if hoisted.resolve(strict=True) != hoisted or not hoisted.is_dir():
                raise ValueError("unsafe hoist root")
            aliases = []
            for item in sorted(hoisted.iterdir()):
                if item.name.startswith("@") and item.is_dir() and not item.is_symlink():
                    aliases.extend(sorted(item.iterdir()))
                else:
                    aliases.append(item)
            for alias in aliases:
                if not alias.is_symlink():
                    continue
                resolved = alias.resolve()
                if resolved not in visited:
                    continue
                if alias.resolve(strict=True) != resolved:
                    raise ValueError("hoist alias changed")
                target = output / alias.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                relative_target = os.path.relpath(
                    output / resolved.relative_to(source), target.parent
                )
                if os.path.lexists(target):
                    if not target.is_symlink() or target.resolve(
                        strict=True
                    ) != output / resolved.relative_to(source):
                        raise ValueError("conflicting hoist alias")
                else:
                    target.symlink_to(relative_target)
        shutil.copy2(source / "package.json", output / "package.json")
        for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
            if (source / name).is_file():
                shutil.copy2(source / name, output / name)
        # Existing launcher retains its public Git identity check without history.
        for name in ("objects", "refs"):
            (output / ".git" / name).mkdir(parents=True)
        (output / ".git/HEAD").write_text(verified["commit"] + "\n")
        write_staged_manifest(output, verified)
        verify_staged_runtime(output, required=True)
        log.info("docker_dsh_staged packages=%d", len(visited))
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        log.error("docker_dsh_staging_failed error_type=%s", type(exc).__name__)
        raise RuntimeError("dsh_staging_invalid") from exc


def main() -> None:
    from scripts.setup_web import SetupWebInstaller

    logging.basicConfig(level=logging.INFO)
    source = Path("/opt/rwb/dsh")
    installer = SetupWebInstaller(project_root=Path("/opt/rwb"), data_home=Path("/tmp/rwb-build"))
    verified = installer.verify_dsh_source(source)
    stage_assets(source, Path("/opt/rwb/dsh-runtime"), verified)


if __name__ == "__main__":
    main()
