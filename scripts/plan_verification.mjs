#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const POLICY_PATH = ".agents/verification-policy.json";
const RISK_ORDER = ["docs-only", "local-only", "full-delivery"];
const LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4"];
const SIGNALS = new Set(["validation_failure", "unexpected_behavior"]);
const TOP_LEVEL_KEYS = new Set([
  "schemaVersion",
  "riskOrder",
  "levelOrder",
  "escalation",
  "catalogs",
  "rules",
  "fallback",
]);
const ESCALATION_KEYS = new Set(["highCouplingImpactThreshold", "targetLevel"]);
const CATALOG_KEYS = new Set(["tests", "documentation", "ci"]);
const CATALOG_ITEM_KEYS = new Set(["level", "execution", "value"]);
const RULE_KEYS = new Set([
  "id",
  "risk",
  "minimumLevel",
  "reason",
  "impact",
  "coupling",
  "match",
  "tests",
  "documentation",
  "ci",
]);
const MATCH_REQUIRED_KEYS = new Set(["files", "prefixes", "segments", "suffixes"]);
const MATCH_OPTIONAL_KEYS = new Set(["excludePrefixes"]);
const FALLBACK_KEYS = new Set([
  "risk",
  "minimumLevel",
  "reason",
  "impact",
  "coupling",
  "tests",
  "documentation",
  "ci",
]);
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

function assertMatchKeys(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("POLICY_ERROR", `invalid ${label}`);
  const keys = Object.keys(value);
  if ([...MATCH_REQUIRED_KEYS].some(key => !keys.includes(key)) ||
      keys.some(key => !MATCH_REQUIRED_KEYS.has(key) && !MATCH_OPTIONAL_KEYS.has(key))) {
    fail("POLICY_ERROR", `invalid ${label} keys`);
  }
}

function assertIdentifier(value, label) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) fail("POLICY_ERROR", `invalid ${label}`);
  return value;
}

function assertLevel(value, label) {
  if (!LEVEL_ORDER.includes(value)) fail("POLICY_ERROR", `invalid ${label}`);
  return value;
}

function assertStringArray(value, label, validate, {nonEmpty = false} = {}) {
  if (!Array.isArray(value) || (nonEmpty && value.length === 0)) fail("POLICY_ERROR", `invalid ${label}`);
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
    assertExactKeys(catalogValue, CATALOG_ITEM_KEYS, `${label} item`);
    const level = assertLevel(catalogValue.level, `${label} level`);
    if (catalogValue.execution !== "local" && catalogValue.execution !== "external") {
      fail("POLICY_ERROR", `invalid ${label} execution`);
    }
    if (typeof catalogValue.value !== "string" || catalogValue.value.trim().length === 0) {
      fail("POLICY_ERROR", `invalid ${label} value`);
    }
    result.set(id, {level, execution: catalogValue.execution, value: catalogValue.value});
  }
  return result;
}

function validateReferences(ids, catalog, label) {
  assertStringArray(ids, label, item => assertIdentifier(item, label));
  if (ids.some(id => !catalog.has(id))) fail("POLICY_ERROR", `unknown ${label} reference`);
}

function parseSelection(value, catalogs, label, {withMatch}) {
  assertExactKeys(value, withMatch ? RULE_KEYS : FALLBACK_KEYS, label);
  const reason = assertIdentifier(value.reason, `${label} reason`);
  const minimumLevel = assertLevel(value.minimumLevel, `${label} minimum level`);
  const impact = assertStringArray(value.impact, `${label} impact`, item => assertIdentifier(item, `${label} impact`), {
    nonEmpty: true,
  });
  if (value.coupling !== "low" && value.coupling !== "high") fail("POLICY_ERROR", `invalid ${label} coupling`);
  if (!RISK_ORDER.includes(value.risk)) fail("POLICY_ERROR", `invalid ${label} risk`);
  validateReferences(value.tests, catalogs.tests, `${label} tests`);
  validateReferences(value.documentation, catalogs.documentation, `${label} documentation`);
  validateReferences(value.ci, catalogs.ci, `${label} CI`);

  let match;
  if (withMatch) {
    assertMatchKeys(value.match, `${label} match`);
    match = {
      files: assertStringArray(value.match.files, `${label} files`, validateMatchPath),
      prefixes: assertStringArray(value.match.prefixes, `${label} prefixes`, validatePrefix),
      segments: assertStringArray(value.match.segments, `${label} segments`, validateSegment),
      suffixes: assertStringArray(value.match.suffixes, `${label} suffixes`, validateSuffix),
      excludePrefixes: assertStringArray(
        value.match.excludePrefixes === undefined ? [] : value.match.excludePrefixes,
        `${label} exclude prefixes`,
        validatePrefix,
      ),
    };
    if ([match.files, match.prefixes, match.segments, match.suffixes].every(items => items.length === 0)) {
      fail("POLICY_ERROR", `${label} has no matchers`);
    }
  }

  return {...value, reason, minimumLevel, impact, match};
}

function parsePolicy(raw) {
  let value;
  try {
    value = JSON.parse(raw);
  } catch {
    fail("POLICY_ERROR", "verification policy is not valid JSON");
  }
  assertExactKeys(value, TOP_LEVEL_KEYS, "verification policy");
  if (value.schemaVersion !== 2) fail("POLICY_ERROR", "unsupported verification policy schema");
  if (!Array.isArray(value.riskOrder) || value.riskOrder.length !== RISK_ORDER.length ||
      value.riskOrder.some((risk, index) => risk !== RISK_ORDER[index])) {
    fail("POLICY_ERROR", "invalid risk order");
  }
  if (!Array.isArray(value.levelOrder) || value.levelOrder.length !== LEVEL_ORDER.length ||
      value.levelOrder.some((level, index) => level !== LEVEL_ORDER[index])) {
    fail("POLICY_ERROR", "invalid level order");
  }
  assertExactKeys(value.escalation, ESCALATION_KEYS, "escalation policy");
  if (!Number.isInteger(value.escalation.highCouplingImpactThreshold) ||
      value.escalation.highCouplingImpactThreshold < 2) {
    fail("POLICY_ERROR", "invalid high-coupling impact threshold");
  }
  const targetLevel = assertLevel(value.escalation.targetLevel, "escalation target level");
  if (LEVEL_ORDER.indexOf(targetLevel) < 1) fail("POLICY_ERROR", "invalid escalation target level");

  assertExactKeys(value.catalogs, CATALOG_KEYS, "catalogs");
  const catalogs = {
    tests: parseCatalog(value.catalogs.tests, "test catalog"),
    documentation: parseCatalog(value.catalogs.documentation, "documentation catalog"),
    ci: parseCatalog(value.catalogs.ci, "CI catalog"),
  };

  if (!Array.isArray(value.rules) || value.rules.length === 0) fail("POLICY_ERROR", "verification rules are required");
  const ruleIds = new Set();
  const rules = value.rules.map((rule, index) => {
    const parsed = parseSelection(rule, catalogs, `rule ${index}`, {withMatch: true});
    const id = assertIdentifier(rule.id, `rule ${index} id`);
    if (ruleIds.has(id)) fail("POLICY_ERROR", `invalid rule ${index}`);
    ruleIds.add(id);
    return {...parsed, id};
  });

  const fallback = parseSelection(value.fallback, catalogs, "fallback", {withMatch: false});
  if (fallback.risk !== "full-delivery" || fallback.minimumLevel !== "L4" ||
      fallback.reason !== "unknown_path" || fallback.coupling !== "high") {
    fail("POLICY_ERROR", "fallback must fail closed");
  }
  return {
    riskOrder: value.riskOrder,
    levelOrder: value.levelOrder,
    escalation: {...value.escalation, targetLevel},
    catalogs,
    rules,
    delegatedPrefixes: [...new Set(
      rules.flatMap(rule => rule.match.excludePrefixes),
    )].sort((left, right) => right.length - left.length),
    fallback,
  };
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
  const options = {changedFiles: [], signals: []};
  const signalSet = new Set();
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument !== "--project" && argument !== "--changed-file" && argument !== "--signal") {
      fail("ARGUMENT_ERROR", "unknown option");
    }
    const value = args[index + 1];
    if (!value || value.startsWith("--")) fail("ARGUMENT_ERROR", `${argument} requires a value`);
    if (argument === "--project") {
      if (options.project !== undefined) fail("ARGUMENT_ERROR", "--project may only be provided once");
      options.project = value;
    } else if (argument === "--changed-file") {
      options.changedFiles.push(value);
    } else {
      if (!SIGNALS.has(value)) fail("ARGUMENT_ERROR", "unsupported escalation signal");
      if (!signalSet.has(value)) {
        signalSet.add(value);
        options.signals.push(value);
      }
    }
    index += 1;
  }
  if (!options.project) fail("ARGUMENT_ERROR", "--project is required");
  if (options.changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one --changed-file is required");
  return options;
}

function matches(match, changedFile) {
  if (match.excludePrefixes.some(prefix => changedFile.startsWith(prefix))) return false;
  const segments = changedFile.split("/");
  return match.files.includes(changedFile) ||
    match.prefixes.some(prefix => changedFile.startsWith(prefix)) ||
    match.segments.some(segment => segments.includes(segment)) ||
    match.suffixes.some(suffix => changedFile.endsWith(suffix));
}

function ownsDelegatedPrefix(match, prefix) {
  return match.files.some(file => file.startsWith(prefix)) ||
    match.prefixes.some(candidate => candidate.startsWith(prefix));
}

function appendUnique(target, seen, values) {
  for (const value of values) {
    if (seen.has(value)) continue;
    seen.add(value);
    target.push(value);
  }
}

function selectedCatalogItems(catalog, ids, category, maximumLevelIndex) {
  const items = [];
  for (const id of ids) {
    const entry = catalog.get(id);
    if (LEVEL_ORDER.indexOf(entry.level) > maximumLevelIndex) continue;
    items.push({id, level: entry.level, execution: entry.execution, category, value: entry.value});
  }
  return items;
}

function nextLevel(level) {
  const index = LEVEL_ORDER.indexOf(level);
  return LEVEL_ORDER[Math.min(index + 1, LEVEL_ORDER.length - 1)];
}

export function planVerification({projectRoot, changedFiles, signals = []}) {
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
  const normalizedSignals = [];
  const seenSignals = new Set();
  for (const signal of signals) {
    if (!SIGNALS.has(signal)) fail("ARGUMENT_ERROR", "unsupported escalation signal");
    if (!seenSignals.has(signal)) {
      seenSignals.add(signal);
      normalizedSignals.push(signal);
    }
  }

  const policy = loadPolicy(root);
  let riskIndex = 0;
  let levelIndex = 0;
  const reasons = [];
  const reasonKeys = new Set();
  const impact = [];
  const impactKeys = new Set();
  const ruleIds = [];
  const ruleSeen = new Set();
  const impactIds = [];
  const impactSeen = new Set();
  const highCouplingImpactIds = new Set();
  const gateIds = {tests: [], documentation: [], ci: []};
  const gateSeen = {tests: new Set(), documentation: new Set(), ci: new Set()};
  const uncoveredRisks = [];

  for (const changedFile of normalizedFiles) {
    const delegatedPrefix = policy.delegatedPrefixes.find(prefix => changedFile.startsWith(prefix));
    const candidateRules = delegatedPrefix
      ? policy.rules.filter(rule => ownsDelegatedPrefix(rule.match, delegatedPrefix))
      : policy.rules;
    const matchedRules = candidateRules.filter(rule => matches(rule.match, changedFile));
    const selections = matchedRules.length > 0 ? matchedRules : [{id: "fallback", ...policy.fallback}];
    for (const selection of selections) {
      riskIndex = Math.max(riskIndex, policy.riskOrder.indexOf(selection.risk));
      levelIndex = Math.max(levelIndex, policy.levelOrder.indexOf(selection.minimumLevel));
      const reason = {path: changedFile, rule: selection.id, code: selection.reason};
      const reasonKey = JSON.stringify(reason);
      if (!reasonKeys.has(reasonKey)) {
        reasonKeys.add(reasonKey);
        reasons.push(reason);
      }
      const impactRecord = {
        path: changedFile,
        rule: selection.id,
        reason: selection.reason,
        modules: [...selection.impact],
        coupling: selection.coupling,
        minimumLevel: selection.minimumLevel,
      };
      const impactKey = JSON.stringify(impactRecord);
      if (!impactKeys.has(impactKey)) {
        impactKeys.add(impactKey);
        impact.push(impactRecord);
      }
      if (!ruleSeen.has(selection.id)) {
        ruleSeen.add(selection.id);
        ruleIds.push(selection.id);
      }
      for (const moduleId of selection.impact) {
        if (!impactSeen.has(moduleId)) {
          impactSeen.add(moduleId);
          impactIds.push(moduleId);
        }
        if (selection.coupling === "high") highCouplingImpactIds.add(moduleId);
      }
      for (const category of Object.keys(gateIds)) {
        appendUnique(gateIds[category], gateSeen[category], selection[category]);
      }
      if (selection.id === "fallback" && !uncoveredRisks.includes("unknown_impact_boundary")) {
        uncoveredRisks.push("unknown_impact_boundary");
      }
    }
  }

  const escalations = [];
  if (highCouplingImpactIds.size >= policy.escalation.highCouplingImpactThreshold) {
    const targetIndex = policy.levelOrder.indexOf(policy.escalation.targetLevel);
    if (targetIndex > levelIndex) {
      const fromLevel = policy.levelOrder[levelIndex];
      levelIndex = targetIndex;
      escalations.push({
        code: "multiple_high_coupling_modules",
        fromLevel,
        toLevel: policy.levelOrder[levelIndex],
        impacts: [...highCouplingImpactIds],
      });
    }
  }
  for (const signal of normalizedSignals) {
    const fromLevel = policy.levelOrder[levelIndex];
    const toLevel = nextLevel(fromLevel);
    levelIndex = policy.levelOrder.indexOf(toLevel);
    escalations.push({code: signal, fromLevel, toLevel, impacts: []});
  }

  const requiredLevel = policy.levelOrder[levelIndex];
  const tests = selectedCatalogItems(policy.catalogs.tests, gateIds.tests, "tests", levelIndex);
  const documentation = selectedCatalogItems(
    policy.catalogs.documentation,
    gateIds.documentation,
    "documentation",
    levelIndex,
  );
  const ci = selectedCatalogItems(policy.catalogs.ci, gateIds.ci, "ci", levelIndex);
  const validationsByLevel = Object.fromEntries(policy.levelOrder.map(level => [level, []]));
  for (const item of [...tests, ...documentation, ...ci]) validationsByLevel[item.level].push(item);

  const selectedValidations = [...tests, ...documentation, ...ci];
  const requiredValidationIds = selectedValidations.filter(item => item.execution === "local").map(item => item.id);
  const externalGateIds = selectedValidations.filter(item => item.execution === "external").map(item => item.id);

  return {
    schemaVersion: 2,
    risk: policy.riskOrder[riskIndex],
    requiredLevel,
    changeSummary: {
      fileCount: normalizedFiles.length,
      ruleIds,
      impactIds,
    },
    changedFiles: normalizedFiles,
    impact,
    reasons,
    escalations,
    uncoveredRisks,
    validationsByLevel,
    tests,
    documentation,
    ci,
    receiptTemplate: {
      plannedLevel: requiredLevel,
      changedFiles: normalizedFiles,
      requiredValidationIds,
      externalGateIds,
    },
  };
}

function main(args) {
  const options = parseArgs(args);
  const result = planVerification({
    projectRoot: options.project,
    changedFiles: options.changedFiles,
    signals: options.signals,
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    const code = error instanceof PlannerError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof PlannerError ? error.message : "unexpected planner failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 2, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
