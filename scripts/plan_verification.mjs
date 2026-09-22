#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const POLICY_PATH = ".agents/verification-policy.json";
const RISK_ORDER = ["docs-only", "local-only", "full-delivery"];
const TOP_LEVEL_KEYS = new Set(["schemaVersion", "riskOrder", "catalogs", "rules", "fallback"]);
const CATALOG_KEYS = new Set(["tests", "documentation", "ci"]);
const RULE_KEYS = new Set(["id", "risk", "reason", "match", "tests", "documentation", "ci"]);
const MATCH_KEYS = new Set(["files", "prefixes", "segments", "suffixes"]);
const FALLBACK_KEYS = new Set(["risk", "reason", "tests", "documentation", "ci"]);
const IDENTIFIER = /^[a-z0-9][a-z0-9_-]*$/;

class PlannerError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function fail(code, message) {
  throw new PlannerError(code, message);
}

function assertExactKeys(value, expected, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("POLICY_ERROR", `invalid ${label}`);
  const keys = Object.keys(value);
  if (keys.length !== expected.size || keys.some(key => !expected.has(key))) {
    fail("POLICY_ERROR", `invalid ${label} keys`);
  }
}

function assertIdentifier(value, label) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) fail("POLICY_ERROR", `invalid ${label}`);
  return value;
}

function assertStringArray(value, label, validate) {
  if (!Array.isArray(value)) fail("POLICY_ERROR", `invalid ${label}`);
  const seen = new Set();
  for (const item of value) {
    if (typeof item !== "string" || item.length === 0 || seen.has(item)) fail("POLICY_ERROR", `invalid ${label}`);
    validate?.(item, label);
    seen.add(item);
  }
  return value;
}

function normalizeRepositoryPath(value, code = "PATH_ERROR") {
  if (typeof value !== "string" || value.length === 0 || /[\x00-\x1f\\]/.test(value) || path.posix.isAbsolute(value)) {
    fail(code, "invalid repository-relative path");
  }
  const normalized = path.posix.normalize(value);
  if (normalized === "." || normalized === ".." || normalized.startsWith("../") || normalized !== value) {
    fail(code, "unsafe repository-relative path");
  }
  return normalized;
}

function validateMatchPath(value, label) {
  try {
    normalizeRepositoryPath(value, "POLICY_ERROR");
  } catch (error) {
    if (error instanceof PlannerError) fail("POLICY_ERROR", `invalid ${label}`);
    throw error;
  }
}

function validatePrefix(value, label) {
  if (!value.endsWith("/")) fail("POLICY_ERROR", `invalid ${label}`);
  validateMatchPath(value.slice(0, -1), label);
}

function validateSegment(value, label) {
  if (/[/\\\x00-\x1f]/.test(value) || value === "." || value === "..") fail("POLICY_ERROR", `invalid ${label}`);
}

function validateSuffix(value, label) {
  if (!value.startsWith(".") || /[/\\\x00-\x1f]/.test(value)) fail("POLICY_ERROR", `invalid ${label}`);
}

function safeProjectRoot(projectValue) {
  if (typeof projectValue !== "string" || projectValue.length === 0) fail("PROJECT_ERROR", "invalid project directory");
  let metadata;
  try {
    metadata = fs.lstatSync(projectValue);
  } catch {
    fail("PROJECT_ERROR", "project directory is unavailable");
  }
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) fail("PROJECT_ERROR", "project directory must be a real directory");
  try {
    return fs.realpathSync(projectValue);
  } catch {
    fail("PROJECT_ERROR", "project directory cannot be resolved");
  }
}

function assertNoSymlinkComponents(root, relative, {required, code}) {
  const parts = relative.split("/");
  let current = root;
  for (let index = 0; index < parts.length; index += 1) {
    current = path.join(current, parts[index]);
    let metadata;
    try {
      metadata = fs.lstatSync(current);
    } catch (error) {
      if (error?.code === "ENOENT" && !required) return;
      fail(code, "required repository path is unavailable");
    }
    if (metadata.isSymbolicLink()) fail(code, "symbolic links are not allowed");
    if (index < parts.length - 1 && !metadata.isDirectory()) fail(code, "repository path component is not a directory");
  }
}

function parseCatalog(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("POLICY_ERROR", `invalid ${label}`);
  const result = new Map();
  for (const [id, catalogValue] of Object.entries(value)) {
    assertIdentifier(id, `${label} id`);
    if (typeof catalogValue !== "string" || catalogValue.trim().length === 0) fail("POLICY_ERROR", `invalid ${label} value`);
    result.set(id, catalogValue);
  }
  return result;
}

function validateReferences(ids, catalog, label) {
  assertStringArray(ids, label, item => assertIdentifier(item, label));
  if (ids.some(id => !catalog.has(id))) fail("POLICY_ERROR", `unknown ${label} reference`);
}

function parsePolicy(raw) {
  let value;
  try {
    value = JSON.parse(raw);
  } catch {
    fail("POLICY_ERROR", "verification policy is not valid JSON");
  }
  assertExactKeys(value, TOP_LEVEL_KEYS, "verification policy");
  if (value.schemaVersion !== 1) fail("POLICY_ERROR", "unsupported verification policy schema");
  if (!Array.isArray(value.riskOrder) || value.riskOrder.length !== RISK_ORDER.length ||
      value.riskOrder.some((risk, index) => risk !== RISK_ORDER[index])) {
    fail("POLICY_ERROR", "invalid risk order");
  }

  assertExactKeys(value.catalogs, CATALOG_KEYS, "catalogs");
  const catalogs = {
    tests: parseCatalog(value.catalogs.tests, "test catalog"),
    documentation: parseCatalog(value.catalogs.documentation, "documentation catalog"),
    ci: parseCatalog(value.catalogs.ci, "CI catalog"),
  };

  if (!Array.isArray(value.rules) || value.rules.length === 0) fail("POLICY_ERROR", "verification rules are required");
  const ruleIds = new Set();
  const rules = value.rules.map((rule, index) => {
    assertExactKeys(rule, RULE_KEYS, `rule ${index}`);
    const id = assertIdentifier(rule.id, `rule ${index} id`);
    const reason = assertIdentifier(rule.reason, `rule ${index} reason`);
    if (ruleIds.has(id) || !RISK_ORDER.includes(rule.risk)) fail("POLICY_ERROR", `invalid rule ${index}`);
    ruleIds.add(id);
    assertExactKeys(rule.match, MATCH_KEYS, `rule ${id} match`);
    const match = {
      files: assertStringArray(rule.match.files, `rule ${id} files`, validateMatchPath),
      prefixes: assertStringArray(rule.match.prefixes, `rule ${id} prefixes`, validatePrefix),
      segments: assertStringArray(rule.match.segments, `rule ${id} segments`, validateSegment),
      suffixes: assertStringArray(rule.match.suffixes, `rule ${id} suffixes`, validateSuffix),
    };
    if (Object.values(match).every(items => items.length === 0)) fail("POLICY_ERROR", `rule ${id} has no matchers`);
    validateReferences(rule.tests, catalogs.tests, `rule ${id} tests`);
    validateReferences(rule.documentation, catalogs.documentation, `rule ${id} documentation`);
    validateReferences(rule.ci, catalogs.ci, `rule ${id} CI`);
    return {...rule, id, reason, match};
  });

  assertExactKeys(value.fallback, FALLBACK_KEYS, "fallback");
  if (value.fallback.risk !== "full-delivery" || value.fallback.reason !== "unknown_path") {
    fail("POLICY_ERROR", "fallback must fail closed");
  }
  validateReferences(value.fallback.tests, catalogs.tests, "fallback tests");
  validateReferences(value.fallback.documentation, catalogs.documentation, "fallback documentation");
  validateReferences(value.fallback.ci, catalogs.ci, "fallback CI");
  return {riskOrder: value.riskOrder, catalogs, rules, fallback: value.fallback};
}

function loadPolicy(root) {
  assertNoSymlinkComponents(root, POLICY_PATH, {required: true, code: "POLICY_ERROR"});
  const destination = path.join(root, POLICY_PATH);
  let metadata;
  let raw;
  try {
    metadata = fs.statSync(destination);
    raw = fs.readFileSync(destination, "utf8");
  } catch {
    fail("POLICY_ERROR", "verification policy is unavailable");
  }
  if (!metadata.isFile()) fail("POLICY_ERROR", "verification policy must be a regular file");
  return parsePolicy(raw);
}

function parseArgs(args) {
  const options = {changedFiles: []};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== "--project" && argument !== "--changed-file") fail("ARGUMENT_ERROR", "unknown option");
    const value = args[index + 1];
    if (!value || value.startsWith("--")) fail("ARGUMENT_ERROR", `${argument} requires a value`);
    if (argument === "--project") {
      if (options.project !== undefined) fail("ARGUMENT_ERROR", "--project may only be provided once");
      options.project = value;
    } else options.changedFiles.push(value);
    index += 1;
  }
  if (!options.project) fail("ARGUMENT_ERROR", "--project is required");
  if (options.changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one --changed-file is required");
  return options;
}

function matches(match, changedFile) {
  const segments = changedFile.split("/");
  return match.files.includes(changedFile) ||
    match.prefixes.some(prefix => changedFile.startsWith(prefix)) ||
    match.segments.some(segment => segments.includes(segment)) ||
    match.suffixes.some(suffix => changedFile.endsWith(suffix));
}

function appendUnique(target, seen, values) {
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    target.push(value);
  }
}

function catalogItems(catalog, ids) {
  return ids.map(id => ({id, value: catalog.get(id)}));
}

export function planVerification({projectRoot, changedFiles}) {
  const root = safeProjectRoot(projectRoot);
  const normalizedFiles = [];
  const seenFiles = new Set();
  for (const changedFile of changedFiles) {
    const normalized = normalizeRepositoryPath(changedFile);
    assertNoSymlinkComponents(root, normalized, {required: false, code: "PATH_ERROR"});
    if (!seenFiles.has(normalized)) {
      seenFiles.add(normalized);
      normalizedFiles.push(normalized);
    }
  }
  const policy = loadPolicy(root);
  let riskIndex = 0;
  const reasons = [];
  const reasonKeys = new Set();
  const gateIds = {tests: [], documentation: [], ci: []};
  const gateSeen = {tests: new Set(), documentation: new Set(), ci: new Set()};

  for (const changedFile of normalizedFiles) {
    const matchedRules = policy.rules.filter(rule => matches(rule.match, changedFile));
    const selections = matchedRules.length > 0 ? matchedRules : [{id: "fallback", ...policy.fallback}];
    for (const selection of selections) {
      riskIndex = Math.max(riskIndex, policy.riskOrder.indexOf(selection.risk));
      const reason = {path: changedFile, rule: selection.id, code: selection.reason};
      const reasonKey = JSON.stringify(reason);
      if (!reasonKeys.has(reasonKey)) {
        reasonKeys.add(reasonKey);
        reasons.push(reason);
      }
      for (const category of Object.keys(gateIds)) {
        appendUnique(gateIds[category], gateSeen[category], selection[category]);
      }
    }
  }

  return {
    schemaVersion: 1,
    risk: policy.riskOrder[riskIndex],
    changedFiles: normalizedFiles,
    reasons,
    tests: catalogItems(policy.catalogs.tests, gateIds.tests),
    documentation: catalogItems(policy.catalogs.documentation, gateIds.documentation),
    ci: catalogItems(policy.catalogs.ci, gateIds.ci),
  };
}

function main(args) {
  const options = parseArgs(args);
  const result = planVerification({projectRoot: options.project, changedFiles: options.changedFiles});
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    const code = error instanceof PlannerError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof PlannerError ? error.message : "unexpected planner failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 1, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
