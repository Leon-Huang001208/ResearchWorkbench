import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import {fail} from "./errors.mjs";
import {normalizeRepositoryPath, safeProjectRoot} from "./path-safety.mjs";

const ORIGIN_ORDER = new Map([
  ["committed", 0],
  ["staged", 1],
  ["unstaged", 2],
  ["untracked", 3],
]);

function git(root, args, code = "GIT_ERROR") {
  try {
    return execFileSync("git", ["-C", root, ...args], {
      encoding: "utf8",
      maxBuffer: 16 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch {
    fail(code, code === "BASELINE_ERROR" ? "invalid Git baseline" : "Git change discovery failed");
  }
}

function gitBytes(root, args) {
  try {
    return execFileSync("git", ["-C", root, ...args], {
      encoding: "buffer",
      maxBuffer: 64 * 1024 * 1024,
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch {
    fail("GIT_ERROR", "Git change content discovery failed");
  }
}

function normalizeStatus(status) {
  if (status.startsWith("A")) return "added";
  if (status.startsWith("D")) return "deleted";
  if (status.startsWith("M")) return "modified";
  if (status.startsWith("T")) return "type-changed";
  if (status.startsWith("U")) return "unmerged";
  return "changed";
}

function parseNameStatus(output, origin) {
  const tokens = output.split("\0");
  if (tokens.at(-1) === "") tokens.pop();
  const entries = [];
  for (let index = 0; index < tokens.length;) {
    const rawStatus = tokens[index++];
    if (/^[RC][0-9]*$/.test(rawStatus)) {
      const previousPath = normalizeRepositoryPath(tokens[index++]);
      const nextPath = normalizeRepositoryPath(tokens[index++]);
      const copied = rawStatus.startsWith("C");
      entries.push({
        path: previousPath,
        status: copied ? "copied-from" : "renamed-from",
        origin,
        nextPath,
      });
      entries.push({
        path: nextPath,
        status: copied ? "copied-to" : "renamed-to",
        origin,
        previousPath,
      });
      continue;
    }
    if (index >= tokens.length) fail("GIT_ERROR", "invalid Git name-status output");
    entries.push({path: normalizeRepositoryPath(tokens[index++]), status: normalizeStatus(rawStatus), origin});
  }
  return entries;
}

function sortEntries(entries) {
  return entries.sort((left, right) => left.path.localeCompare(right.path, "en") ||
    ORIGIN_ORDER.get(left.origin) - ORIGIN_ORDER.get(right.origin) ||
    left.status.localeCompare(right.status));
}

export function discoverGitChangeSet({projectRoot, base}) {
  const root = safeProjectRoot(projectRoot);
  if (typeof base !== "string" || base.length === 0 || base.startsWith("-")) fail("BASELINE_ERROR", "invalid Git baseline");
  const repositoryRoot = git(root, ["rev-parse", "--show-toplevel"]).trim();
  if (safeProjectRoot(repositoryRoot) !== root) fail("GIT_ERROR", "project root must be the Git worktree root");
  const baseCommit = git(root, ["rev-parse", "--verify", `${base}^{commit}`], "BASELINE_ERROR").trim();
  const headCommit = git(root, ["rev-parse", "--verify", "HEAD^{commit}"], "BASELINE_ERROR").trim();
  const entries = sortEntries([
    ...parseNameStatus(git(root, ["diff", "--name-status", "-z", "--find-renames", `${baseCommit}...${headCommit}`]), "committed"),
    ...parseNameStatus(git(root, ["diff", "--cached", "--name-status", "-z", "--find-renames"]), "staged"),
    ...parseNameStatus(git(root, ["diff", "--name-status", "-z", "--find-renames"]), "unstaged"),
    ...git(root, ["ls-files", "--others", "--exclude-standard", "-z"])
      .split("\0")
      .filter(Boolean)
      .map(file => ({path: normalizeRepositoryPath(file), status: "untracked", origin: "untracked"})),
  ]);
  const changedFiles = [...new Set(entries.map(entry => entry.path))].sort((left, right) => left.localeCompare(right, "en"));
  if (changedFiles.length === 0) fail("EMPTY_CHANGE_SET", "Git change set is empty");
  const contentHash = crypto.createHash("sha256");
  for (const [label, bytes] of [
    ["committed", gitBytes(root, ["diff", "--binary", `${baseCommit}...${headCommit}`])],
    ["staged", gitBytes(root, ["diff", "--cached", "--binary"])],
    ["unstaged", gitBytes(root, ["diff", "--binary"])],
  ]) {
    contentHash.update(label);
    contentHash.update("\0");
    contentHash.update(bytes);
    contentHash.update("\0");
  }
  for (const entry of entries.filter(item => item.origin === "untracked")) {
    const destination = path.join(root, entry.path);
    const metadata = fs.lstatSync(destination);
    if (metadata.isSymbolicLink() || !metadata.isFile()) fail("PATH_ERROR", "untracked evidence must be a regular file");
    contentHash.update(entry.path);
    contentHash.update("\0");
    contentHash.update(fs.readFileSync(destination));
    contentHash.update("\0");
  }
  const contentSha256 = contentHash.digest("hex");
  const digest = crypto.createHash("sha256")
    .update(JSON.stringify({baseCommit, headCommit, entries, contentSha256}))
    .digest("hex");
  return {baseCommit, headCommit, entries, changedFiles, digest};
}

export function assertCompleteChangedSet({discovered, explicitPaths}) {
  if (!discovered || !Array.isArray(discovered.changedFiles)) fail("INCOMPLETE_CHANGE_SET", "invalid discovered change set");
  if (explicitPaths === undefined) return [...discovered.changedFiles];
  if (!Array.isArray(explicitPaths) || explicitPaths.length === 0) {
    fail("INCOMPLETE_CHANGE_SET", "explicit changed set does not match Git discovery");
  }
  const explicit = [...new Set(explicitPaths.map(file => normalizeRepositoryPath(file)))].sort((left, right) => left.localeCompare(right, "en"));
  if (JSON.stringify(explicit) !== JSON.stringify(discovered.changedFiles)) {
    fail("INCOMPLETE_CHANGE_SET", "explicit changed set does not match Git discovery");
  }
  return [...discovered.changedFiles];
}
