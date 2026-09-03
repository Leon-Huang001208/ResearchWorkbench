"""Bounded inert imports. No extractall, subprocess, installer or network access."""

import base64
import binascii
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import PurePosixPath

import yaml

from core.observability import get_logger

from .models import CapabilityError, issue

log = get_logger(__name__)
MAX_COMPRESSED = 10 * 1024 * 1024
MAX_FILE = 10 * 1024 * 1024
MAX_EXPANDED = 30 * 1024 * 1024
MAX_FILES = 128
EXTENSIONS = {
    ".md",
    ".txt",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".svg",
    ".pdf",
    ".py",
    ".j2",
}
TEXT_EXTENSIONS = EXTENSIONS - {".png", ".jpg", ".jpeg", ".webp", ".gif", ".pdf"}
FORBIDDEN_NAMES = {
    "setup.py",
    "install.py",
    "conftest.py",
    "sitecustomize.py",
    "usercustomize.py",
    "pyproject.toml",
    "package.json",
    "makefile",
    "dockerfile",
}


def valid_path(name):
    path = PurePosixPath(name)
    if (
        not name
        or len(name) > 240
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or path.is_absolute()
        or any(p in {"", ".", ".."} or p.startswith(".") for p in name.split("/"))
        or any(ord(c) < 32 for c in name)
        or path.suffix.lower() not in EXTENSIONS
        or path.name.lower() in FORBIDDEN_NAMES
        or (
            path.suffix.lower() == ".py"
            and (
                len(path.parts) != 2
                or path.parts[0] != "scripts"
                or re.search(r"install|setup|bootstrap", path.name, re.IGNORECASE)
            )
        )
    ):
        raise CapabilityError("包文件路径或类型不允许", "unsafe_file")
    return path


def encode_file(name, raw):
    path = valid_path(name)
    if len(raw) > MAX_FILE:
        raise CapabilityError("单文件超过 10 MiB", "file_limit")
    if raw.startswith(
        (b"MZ", b"\x7fELF", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"PK\x03\x04", b"\x1f\x8b")
    ):
        raise CapabilityError("不允许二进制可执行文件或嵌套压缩包", "unsafe_file")
    if path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CapabilityError("文本文件必须为 UTF-8", "invalid_encoding") from exc
        if b"\x00" in raw:
            raise CapabilityError("文本包含二进制内容", "unsafe_file")
    return {
        "path": name,
        "base64": base64.b64encode(raw).decode("ascii"),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def decode_file(file):
    try:
        return base64.b64decode(file["base64"], validate=True)
    except (ValueError, TypeError, KeyError, binascii.Error) as exc:
        raise CapabilityError("包文件编码损坏", "package_corrupt") from exc


def normalize_files(files):
    result, issues, seen, total = [], [], set(), 0
    for item in files:
        name = item.get("path", "")
        try:
            if (
                not isinstance(name, str)
                or name.casefold() in seen
                or name.casefold() in {"skill.md", "capability.json", "workflow.json"}
            ):
                raise CapabilityError("文件名重复或占用包元数据名称", "duplicate_file")
            seen.add(name.casefold())
            raw = (
                item["content"].encode("utf-8")
                if isinstance(item.get("content"), str)
                else decode_file(item)
            )
            total += len(raw)
            if total > MAX_EXPANDED or len(result) >= MAX_FILES - 3:
                raise CapabilityError("包展开大小或文件数量超限", "package_limit")
            result.append(encode_file(name, raw))
        except CapabilityError as exc:
            issues.append(issue(exc.code, str(exc), name))
    return result, issues


def frontmatter(raw):
    matched = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)\Z", raw, re.DOTALL)
    if not matched:
        raise CapabilityError("SKILL.md 缺少 YAML frontmatter", "frontmatter_invalid")
    try:
        # Reject aliases and duplicate keys instead of silently choosing values.
        if len(matched[1]) > 65536:
            raise ValueError("frontmatter too large")
        depth = 0
        for token in yaml.scan(matched[1]):
            if isinstance(token, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)):
                raise TypeError("aliases")
            if isinstance(
                token,
                (
                    yaml.tokens.BlockMappingStartToken,
                    yaml.tokens.BlockSequenceStartToken,
                    yaml.tokens.FlowMappingStartToken,
                    yaml.tokens.FlowSequenceStartToken,
                ),
            ):
                depth += 1
                if depth > 20:
                    raise ValueError("frontmatter too deep")
            elif isinstance(
                token,
                (
                    yaml.tokens.BlockEndToken,
                    yaml.tokens.FlowMappingEndToken,
                    yaml.tokens.FlowSequenceEndToken,
                ),
            ):
                depth -= 1
        node = yaml.compose(matched[1], Loader=yaml.SafeLoader)
        if not isinstance(node, yaml.MappingNode) or len({k.value for k, _ in node.value}) != len(
            node.value
        ):
            raise ValueError("mapping")
        data = yaml.safe_load(matched[1])
        if not isinstance(data, dict):
            raise TypeError("mapping")
        if not isinstance(data.get("name"), str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", data["name"]
        ):
            raise ValueError("name")
        if (
            not isinstance(data.get("description"), str)
            or not data["description"].strip()
            or not matched[2].strip()
        ):
            raise ValueError("description/body")
        for key in ("disableModelInvocation", "modelInvocable", "userInvocable"):
            if key in data:
                raise ValueError(key)
        # Product publication requires both surfaces; imports retain conflicting policy.
        if data.get("disable-model-invocation", False) not in (False, "false") or data.get(
            "user-invocable", True
        ) not in (True, "true"):
            raise ValueError("invocation policy")
        return data, matched[2].strip()
    except (yaml.YAMLError, ValueError, TypeError, RecursionError) as exc:
        raise CapabilityError(
            "SKILL.md 元数据、调用策略或正文不兼容；请手动修正", "frontmatter_invalid"
        ) from exc


def import_package(filename, raw):
    if len(raw) > MAX_COMPRESSED:
        raise CapabilityError("导入包超过 10 MiB", "package_limit", 413)
    files, issues = {}, []
    if filename == "SKILL.md":
        files[filename] = raw
    elif filename.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_EXPANDED:
                    issues.append(issue("package_limit", "ZIP 展开超过 30 MiB 或 128 个条目"))
                else:
                    seen = set()
                    for entry in entries:
                        name = entry.filename
                        try:
                            mode = entry.external_attr >> 16
                            if (
                                stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                                or entry.flag_bits & 1
                            ):
                                raise CapabilityError(
                                    "ZIP 链接、特殊文件或加密文件不允许", "unsafe_file"
                                )
                            if entry.is_dir():
                                valid_path(name.rstrip("/") + "/placeholder.md")
                                continue
                            if stat.S_IFMT(mode) == stat.S_IFDIR:
                                raise CapabilityError("ZIP 文件类型与名称冲突", "unsafe_file")
                            if name.casefold() in seen:
                                raise CapabilityError("ZIP 文件名大小写冲突", "duplicate_file")
                            seen.add(name.casefold())
                            valid_path(name)
                            if entry.file_size > MAX_FILE:
                                raise CapabilityError("单文件超过 10 MiB", "file_limit")
                            with archive.open(entry) as stream:
                                data = stream.read(MAX_FILE + 1)
                            encode_file(name, data)
                            files[name] = data
                        except CapabilityError as exc:
                            issues.append(issue(exc.code, str(exc), name))
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
            issues.append(issue("invalid_archive", "ZIP 无法安全读取：" + type(exc).__name__))
    else:
        raise CapabilityError("只支持 SKILL.md 或 ZIP", "unsupported_import")
    metadata, steps, kind = {}, [], "skill"
    try:
        if "capability.json" in files:
            metadata = json.loads(files.pop("capability.json"))
            if not isinstance(metadata, dict):
                raise ValueError("metadata")
        if "workflow.json" in files:
            workflow = json.loads(files.pop("workflow.json"))
            steps, kind = workflow["steps"], "workflow"
            if not isinstance(steps, list):
                raise ValueError("steps")
        instructions = files.pop("SKILL.md", b"").decode("utf-8")
    except (UnicodeDecodeError, ValueError, KeyError, TypeError, RecursionError) as exc:
        issues.append(issue("metadata_invalid", "包元数据无法读取：" + type(exc).__name__))
        metadata, steps, instructions = {}, [], ""
    resource_files = [
        {"path": name, "base64": base64.b64encode(data).decode("ascii")}
        for name, data in files.items()
    ]
    log.info("capability_import_parsed", file_count=len(resource_files), issue_count=len(issues))
    return {
        "kind": kind,
        "metadata": metadata,
        "instructions": instructions,
        "files": resource_files,
        "steps": steps,
    }, issues
