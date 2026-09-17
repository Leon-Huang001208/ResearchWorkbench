#!/usr/bin/env node
/** Validate Markdown classification, authority ownership, links and stale commands. */

import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {fileURLToPath} from "node:url";

export const MANIFEST_PATH = "docs/documentation-governance.json";
const VALID_STATUSES = new Set(["current", "generated", "historical", "package-internal", "cleanup-candidate"]);

function normalizeRelative(value, label) {
  if (typeof value !== "string" || value.length === 0 || path.isAbsolute(value) || /[\x00-\x1f]/.test(value)) {
    throw new Error(`invalid ${label}`);
  }
  const normalized = path.posix.normalize(value.replaceAll("\\", "/"));
  if (normalized === "." || normalized === ".." || normalized.startsWith("../")) throw new Error(`unsafe ${label}`);
  return normalized;
}

function safeRoot(projectRoot) {
  const root = fs.realpathSync(projectRoot);
  if (!fs.statSync(root).isDirectory()) throw new Error("project root is not a directory");
  return root;
}

function safeTarget(root, relative, {missing = "error"} = {}) {
  const normalized = normalizeRelative(relative, "repository path");
  const destination = path.resolve(root, normalized);
  if (destination !== root && !destination.startsWith(`${root}${path.sep}`)) throw new Error("repository path escapes root");
  if (!fs.existsSync(destination)) {
    if (missing === "null") return null;
    throw new Error(`missing repository path: ${normalized}`);
  }
  return destination;
}

function loadManifest(root) {
  const destination = safeTarget(root, MANIFEST_PATH);
  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(destination, "utf8"));
  } catch {
    throw new Error("invalid documentation governance manifest");
  }
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest) || manifest.schemaVersion !== 1) {
    throw new Error("invalid documentation governance schema");
  }
  if (!Array.isArray(manifest.statuses) || manifest.statuses.length !== VALID_STATUSES.size ||
      manifest.statuses.some(status => !VALID_STATUSES.has(status))) {
    throw new Error("invalid documentation governance statuses");
  }
  if (!Array.isArray(manifest.rules) || manifest.rules.length === 0) throw new Error("documentation rules are required");
  for (const rule of manifest.rules) {
    if (!rule || typeof rule !== "object" || Array.isArray(rule) || !VALID_STATUSES.has(rule.status) ||
        typeof rule.purpose !== "string" || rule.purpose.trim().length === 0) {
      throw new Error("invalid documentation rule");
    }
    const matchers = ["exact", "prefix"].filter(key => Object.hasOwn(rule, key));
    if (matchers.length !== 1) throw new Error("documentation rule requires exactly one matcher");
    rule[matchers[0]] = normalizeRelative(rule[matchers[0]], "documentation rule matcher");
  }
  if (!Array.isArray(manifest.authorities) || !Array.isArray(manifest.forbiddenCurrentPatterns)) {
    throw new Error("documentation authorities and forbidden patterns are required");
  }
  return manifest;
}

function trackedMarkdown(root) {
  const output = execFileSync(
    "git",
    ["-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "*.md"],
    {encoding: "utf8"},
  );
  return output.split("\0").filter(Boolean).sort();
}

function classify(file, rules) {
  return rules.find(rule => rule.exact === file || (rule.prefix && file.startsWith(rule.prefix))) ?? null;
}

function stripCodeFences(markdown) {
  return markdown.replace(/```[\s\S]*?```/g, "").replace(/~~~[\s\S]*?~~~/g, "");
}

function headingSlug(value) {
  return value.trim().toLowerCase()
    .replace(/<[^>]*>/g, "")
    .replace(/[`*_~]/g, "")
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function headingAnchors(markdown) {
  const counts = new Map();
  const anchors = new Set();
  for (const line of markdown.split(/\r?\n/)) {
    const match = line.match(/^#{1,6}\s+(.+?)\s*#*$/);
    if (!match) continue;
    const base = headingSlug(match[1]);
    if (!base) continue;
    const count = counts.get(base) ?? 0;
    counts.set(base, count + 1);
    anchors.add(count === 0 ? base : `${base}-${count}`);
  }
  return anchors;
}

function markdownLinks(markdown) {
  const links = [];
  const text = stripCodeFences(markdown);
  const pattern = /!?(?:\[[^\]]*\])\(([^)]+)\)/g;
  for (const match of text.matchAll(pattern)) {
    let target = match[1].trim();
    if (target.startsWith("<") && target.endsWith(">")) target = target.slice(1, -1);
    if (target.includes(' "')) target = target.split(' "', 1)[0];
    links.push(target);
  }
  return links;
}

function checkLinks(root, file, markdown, violations) {
  for (const rawTarget of markdownLinks(markdown)) {
    if (!rawTarget || /^(?:https?:|mailto:|data:|codex:|app:)/i.test(rawTarget)) continue;
    const [rawPath, rawAnchor = ""] = rawTarget.split("#", 2);
    let decodedPath;
    let decodedAnchor;
    try {
      decodedPath = decodeURIComponent(rawPath);
      decodedAnchor = decodeURIComponent(rawAnchor);
    } catch {
      violations.push({code: "link_invalid_encoding", path: file, target: rawTarget});
      continue;
    }
    const targetRelative = decodedPath
      ? path.posix.normalize(path.posix.join(path.posix.dirname(file), decodedPath))
      : file;
    if (targetRelative === ".." || targetRelative.startsWith("../")) {
      violations.push({code: "link_outside_repository", path: file, target: rawTarget});
      continue;
    }
    const destination = safeTarget(root, targetRelative, {missing: "null"});
    if (!destination) {
      violations.push({code: "link_missing", path: file, target: rawTarget});
      continue;
    }
    if (decodedAnchor && fs.statSync(destination).isFile() && destination.endsWith(".md")) {
      const anchors = headingAnchors(fs.readFileSync(destination, "utf8"));
      if (!anchors.has(decodedAnchor.toLowerCase())) {
        violations.push({code: "anchor_missing", path: file, target: rawTarget});
      }
    }
  }
}

function appendLog(root, result) {
  const logs = path.join(root, "logs");
  fs.mkdirSync(logs, {recursive: true});
  fs.appendFileSync(path.join(logs, "documentation-governance.jsonl"), `${JSON.stringify({
    timestamp: new Date().toISOString(),
    files: result.files,
    current: result.current,
    violations: result.violations.map(item => item.code)
  })}\n`);
}

export function checkDocumentationGovernance({projectRoot, markdownFiles} = {}) {
  const root = safeRoot(projectRoot);
  const manifest = loadManifest(root);
  const files = markdownFiles ? [...markdownFiles].sort() : trackedMarkdown(root);
  const violations = [];
  const classified = new Map();

  for (const file of files) {
    const normalized = normalizeRelative(file, "Markdown path");
    const rule = classify(normalized, manifest.rules);
    if (!rule) {
      violations.push({code: "markdown_unclassified", path: normalized});
      continue;
    }
    classified.set(normalized, rule.status);
  }

  const topics = new Set();
  for (const authority of manifest.authorities) {
    if (!authority || typeof authority.topic !== "string" || authority.topic.trim().length === 0) {
      violations.push({code: "authority_invalid", path: MANIFEST_PATH});
      continue;
    }
    const authorityPath = normalizeRelative(authority.path, "authority path");
    if (topics.has(authority.topic)) violations.push({code: "authority_duplicate", path: authorityPath, topic: authority.topic});
    topics.add(authority.topic);
    if (classified.get(authorityPath) !== "current") {
      violations.push({code: "authority_not_current", path: authorityPath, topic: authority.topic});
    }
  }

  const currentFiles = [...classified].filter(([, status]) => status === "current").map(([file]) => file);
  for (const file of currentFiles) {
    const destination = safeTarget(root, file, {missing: "null"});
    if (!destination || !fs.statSync(destination).isFile()) {
      violations.push({code: "current_document_missing", path: file});
      continue;
    }
    const markdown = fs.readFileSync(destination, "utf8");
    checkLinks(root, file, markdown, violations);
    for (const forbidden of manifest.forbiddenCurrentPatterns) {
      if (!forbidden || typeof forbidden.id !== "string" || typeof forbidden.text !== "string" || !forbidden.text) {
        violations.push({code: "forbidden_pattern_invalid", path: MANIFEST_PATH});
      } else if (markdown.includes(forbidden.text)) {
        violations.push({code: "retired_content_current", path: file, pattern: forbidden.id});
      }
    }
  }

  for (const [file, status] of classified) {
    if (status !== "historical" || !file.startsWith("docs/archive/") || file === "docs/archive/README.md") continue;
    const destination = safeTarget(root, file, {missing: "null"});
    if (!destination || !fs.readFileSync(destination, "utf8").startsWith("> **历史归档**：")) {
      violations.push({code: "historical_banner_missing", path: file});
    }
  }

  return {schemaVersion: 1, projectRoot: root, files: files.length, current: currentFiles.length, violations};
}

function parseArgs(args) {
  const options = {};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--project") {
      const value = args[index + 1];
      if (!value || value.startsWith("--")) throw new Error("--project requires a value");
      options.projectRoot = value;
      index += 1;
    } else throw new Error(`unknown option: ${argument}`);
  }
  if (!options.projectRoot) throw new Error("--project requires a value");
  return options;
}

function main(args) {
  const options = parseArgs(args);
  const result = checkDocumentationGovernance(options);
  appendLog(result.projectRoot, result);
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.violations.length > 0) process.exitCode = 1;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`documentation governance failed: ${error.message}\n`);
    process.exitCode = 1;
  }
}
