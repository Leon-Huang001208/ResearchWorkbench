import fs from "node:fs";
import path from "node:path";

import {fail} from "./errors.mjs";

export function normalizeRepositoryPath(value, code = "PATH_ERROR") {
  if (typeof value !== "string" || value.length === 0 || /[\x00-\x1f\\]/.test(value) || path.posix.isAbsolute(value)) {
    fail(code, "invalid repository-relative path");
  }
  const normalized = path.posix.normalize(value);
  if (normalized === "." || normalized === ".." || normalized.startsWith("../") || normalized !== value) {
    fail(code, "unsafe repository-relative path");
  }
  return normalized;
}

export function safeProjectRoot(projectRoot, code = "PROJECT_ERROR") {
  if (typeof projectRoot !== "string" || projectRoot.length === 0) fail(code, "invalid project directory");
  let metadata;
  try {
    metadata = fs.lstatSync(projectRoot);
  } catch {
    fail(code, "project directory is unavailable");
  }
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) fail(code, "project directory must be a real directory");
  try {
    return fs.realpathSync(projectRoot);
  } catch {
    fail(code, "project directory cannot be resolved");
  }
}

export function assertNoSymlinkComponents(root, relative, {required = true, code = "PATH_ERROR"} = {}) {
  const normalized = normalizeRepositoryPath(relative, code);
  let current = root;
  for (let index = 0; index < normalized.split("/").length; index += 1) {
    const component = normalized.split("/")[index];
    current = path.join(current, component);
    let metadata;
    try {
      metadata = fs.lstatSync(current);
    } catch (error) {
      if (error?.code === "ENOENT" && !required) return normalized;
      fail(code, "required repository path is unavailable");
    }
    if (metadata.isSymbolicLink()) fail(code, "symbolic links are not allowed");
    if (index < normalized.split("/").length - 1 && !metadata.isDirectory()) {
      fail(code, "repository path component is not a directory");
    }
  }
  return normalized;
}

export function safeRegularFile(root, relative, code = "PATH_ERROR") {
  const normalized = assertNoSymlinkComponents(root, relative, {required: true, code});
  const destination = path.join(root, normalized);
  let metadata;
  try {
    metadata = fs.statSync(destination);
  } catch {
    fail(code, "required repository file is unavailable");
  }
  if (!metadata.isFile()) fail(code, "repository path must be a regular file");
  return destination;
}
