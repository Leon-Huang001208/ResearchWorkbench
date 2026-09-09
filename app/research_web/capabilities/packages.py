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
from xml.etree import ElementTree

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
        (
            b"MZ",
            b"\x7fELF",
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xce",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"PK\x03\x04",
            b"PK\x05\x06",
            b"PK\x07\x08",
            b"\x1f\x8b",
            b"\xfd7zXZ\x00",
            b"BZh",
            b"7z\xbc\xaf\x27\x1c",
            b"Rar!",
        )
    ):
        raise CapabilityError("不允许二进制可执行文件或嵌套压缩包", "unsafe_file")
    if path.suffix.lower() in TEXT_EXTENSIONS:
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CapabilityError("文本文件必须为 UTF-8", "invalid_encoding") from exc
        if b"\x00" in raw:
            raise CapabilityError("文本包含二进制内容", "unsafe_file")
    suffix = path.suffix.lower()
    if (suffix not in TEXT_EXTENSIONS or suffix == ".svg") and not media_evidence(suffix, raw):
        raise CapabilityError("资源内容不符合声明的图片/PDF 格式", "invalid_media")
    return {
        "path": name,
        "base64": base64.b64encode(raw).decode("ascii"),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def media_evidence(suffix, raw):
    """Bounded container evidence only: no rendering, decompression or code execution."""
    if suffix == ".png":
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
            return False
        position, chunks = 8, []
        while position + 12 <= len(raw):
            size = int.from_bytes(raw[position : position + 4], "big")
            end = position + 12 + size
            if end > len(raw):
                return False
            kind = raw[position + 4 : position + 8]
            body = raw[position + 8 : end - 4]
            if binascii.crc32(kind + body) != int.from_bytes(raw[end - 4 : end], "big"):
                return False
            if not chunks and (
                kind != b"IHDR"
                or size != 13
                or not int.from_bytes(body[:4], "big")
                or not int.from_bytes(body[4:8], "big")
            ):
                return False
            chunks.append(kind)
            if kind == b"IEND":
                return size == 0 and end == len(raw) and b"IDAT" in chunks
            position = end
        return False
    if suffix in {".jpg", ".jpeg"}:
        if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9"):
            return False
        position, frame = 2, False
        while position + 4 <= len(raw):
            if raw[position] != 0xFF:
                return False
            marker = raw[position + 1]
            if marker == 0xFF:
                position += 1
                continue
            size = int.from_bytes(raw[position + 2 : position + 4], "big")
            if size < 2 or position + 2 + size > len(raw):
                return False
            if marker in {
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            }:
                frame = size >= 8 and all(
                    (
                        int.from_bytes(raw[position + 5 : position + 7], "big"),
                        int.from_bytes(raw[position + 7 : position + 9], "big"),
                    )
                )
            if marker == 0xDA:
                return bool(frame and size >= 6 and position + 2 + size < len(raw) - 2)
            position += 2 + size
        return False
    if suffix == ".gif":
        if (
            len(raw) < 35
            or raw[:6] not in {b"GIF87a", b"GIF89a"}
            or not int.from_bytes(raw[6:8], "little")
            or not int.from_bytes(raw[8:10], "little")
        ):
            return False
        position = 13 + (3 * 2 ** ((raw[10] & 7) + 1) if raw[10] & 0x80 else 0)
        image = False
        while 0 <= position < len(raw):
            marker = raw[position]
            if marker == 0x3B:
                return image and position == len(raw) - 1
            if marker == 0x21:  # inert extension sub-blocks
                position = gif_blocks_end(raw, position + 2)
            elif marker == 0x2C and position + 10 < len(raw):
                if not int.from_bytes(
                    raw[position + 5 : position + 7], "little"
                ) or not int.from_bytes(raw[position + 7 : position + 9], "little"):
                    return False
                packed = raw[position + 9]
                position += 10 + (3 * 2 ** ((packed & 7) + 1) if packed & 0x80 else 0)
                if position + 1 >= len(raw) or not 2 <= raw[position] <= 8 or not raw[position + 1]:
                    return False
                position = gif_blocks_end(raw, position + 1)
                image = True
            else:
                return False
        return False
    if suffix == ".webp":
        if (
            raw[:4] != b"RIFF"
            or raw[8:12] != b"WEBP"
            or len(raw) != int.from_bytes(raw[4:8], "little") + 8
        ):
            return False
        position, image = 12, False
        while position + 8 <= len(raw):
            kind = raw[position : position + 4]
            size = int.from_bytes(raw[position + 4 : position + 8], "little")
            body = raw[position + 8 : position + 8 + size]
            if kind == b"VP8 ":
                image |= len(body) >= 10 and body[3:6] == b"\x9d\x01\x2a"
            elif kind == b"VP8L":
                image |= len(body) >= 5 and body[0] == 0x2F
            elif kind == b"ANMF":
                image |= len(body) > 24 and body[16:20] in {b"VP8 ", b"VP8L", b"ALPH"}
            position += 8 + size + size % 2
        return bool(image and position == len(raw))
    if suffix == ".pdf":
        # Recognize both classic xref tables and modern xref-stream object headers.
        ending = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*\Z", raw)
        if not re.match(rb"%PDF-[12]\.\d[\r\n]", raw) or not ending:
            return False
        offset = int(ending[1]) if len(ending[1]) < 12 else len(raw)
        return (
            offset < ending.start()
            and b"endobj" in raw[:offset]
            and bool(re.match(rb"(?:xref\s|\d+\s+\d+\s+obj\b)", raw[offset:]))
        )
    if suffix == ".svg":
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            return False
        try:
            root = ElementTree.fromstring(raw)
            return root.tag in {"svg", "{http://www.w3.org/2000/svg}svg"}
        except (ElementTree.ParseError, ValueError, LookupError):
            return False
    return False


def gif_blocks_end(raw, position):
    while position < len(raw):
        size = raw[position]
        position += 1
        if not size:
            return position
        position += size
    return -1


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
            folded = name.casefold()
            if any(
                folded.startswith(previous + "/") or previous.startswith(folded + "/")
                for previous in seen | {"skill.md", "capability.json", "workflow.json"}
            ):
                raise CapabilityError("文件与目录路径前缀冲突", "path_conflict")
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
                    seen, directories = set(), set()
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
                                directory = name.rstrip("/").casefold()
                                if any(
                                    directory == previous or directory.startswith(previous + "/")
                                    for previous in seen
                                ):
                                    raise CapabilityError("ZIP 文件与目录路径冲突", "path_conflict")
                                directories.add(directory)
                                continue
                            if stat.S_IFMT(mode) == stat.S_IFDIR:
                                raise CapabilityError("ZIP 文件类型与名称冲突", "unsafe_file")
                            if name.casefold() in seen:
                                raise CapabilityError("ZIP 文件名大小写冲突", "duplicate_file")
                            if any(
                                directory == name.casefold()
                                or directory.startswith(name.casefold() + "/")
                                for directory in directories
                            ):
                                raise CapabilityError("ZIP 文件与目录路径冲突", "path_conflict")
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
