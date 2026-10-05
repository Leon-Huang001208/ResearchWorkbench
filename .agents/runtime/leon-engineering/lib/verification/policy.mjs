import fs from "node:fs";

import {fail} from "./errors.mjs";
import {normalizeRepositoryPath, safeRegularFile} from "./path-safety.mjs";

export const DEFAULT_POLICY_PATH = ".agents/verification-policy.json";
export const LEGACY_TIERS = ["read-only", "local-only", "isolated", "full-delivery"];
export const RISK_ORDER = ["docs-only", "local-only", "full-delivery"];
export const LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4"];
export const PLATFORM_ORDER = [
  "generic",
  "linux",
  "macos",
  "windows",
  "cross-platform",
  "real-machine-required",
];
export const STATUS_ORDER = [
  "PASS",
  "FAIL",
  "SKIPPED",
  "NOT_REQUIRED",
  "NOT_RUN",
  "BLOCKED",
  "MANUAL_REQUIRED",
];
export const SIGNALS = new Set(["validation_failure", "unexpected_behavior"]);

const IDENTIFIER = /^[a-z0-9][a-z0-9_-]*$/;
const TOP_V2 = new Set(["schemaVersion", "riskOrder", "levelOrder", "escalation", "catalogs", "rules", "fallback"]);
const TOP_V3 = new Set([...TOP_V2, "platformOrder", "statusOrder"]);
const ESCALATION_KEYS = new Set(["highCouplingImpactThreshold", "targetLevel"]);
const CATALOG_KEYS_V2 = new Set(["tests", "documentation", "ci"]);
const CATALOG_KEYS_V3 = new Set([...CATALOG_KEYS_V2, "realMachine"]);
const CATALOG_ITEM_V2 = new Set(["level", "execution", "value"]);
const CATALOG_ITEM_V3 = new Set(["level", "lane", "gate", "platforms", "value"]);
const RULE_KEYS_V2 = new Set([
  "id", "risk", "minimumLevel", "reason", "impact", "coupling", "match", "tests", "documentation", "ci",
]);
const RULE_KEYS_V3 = new Set([...RULE_KEYS_V2, "platforms", "realMachine"]);
const FALLBACK_KEYS_V2 = new Set([
  "risk", "minimumLevel", "reason", "impact", "coupling", "tests", "documentation", "ci",
]);
const FALLBACK_KEYS_V3 = new Set([...FALLBACK_KEYS_V2, "platforms", "realMachine"]);
const MATCH_REQUIRED_KEYS = new Set(["files", "prefixes", "segments", "suffixes"]);
const MATCH_OPTIONAL_KEYS = new Set(["excludePrefixes"]);

function assertObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("POLICY_ERROR", `invalid ${label}`);
}

function assertExactKeys(value, expected, label) {
  assertObject(value, label);
  const keys = Object.keys(value);
  if (keys.length !== expected.size || keys.some(key => !expected.has(key))) {
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

function stringList(value, label, validate, {nonEmpty = false} = {}) {
  if (!Array.isArray(value) || (nonEmpty && value.length === 0)) fail("POLICY_ERROR", `invalid ${label}`);
  const seen = new Set();
  for (const item of value) {
    if (typeof item !== "string" || item.length === 0 || seen.has(item)) fail("POLICY_ERROR", `invalid ${label}`);
    validate?.(item, label);
    seen.add(item);
  }
  return value;
}

function validateMatchPath(value, label) {
  try {
    normalizeRepositoryPath(value, "POLICY_ERROR");
  } catch {
    fail("POLICY_ERROR", `invalid ${label}`);
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

function orderedPlatforms(value, label) {
  stringList(value, label, undefined, {nonEmpty: true});
  let previous = -1;
  for (const platform of value) {
    const index = PLATFORM_ORDER.indexOf(platform);
    if (index === -1 || index <= previous) fail("POLICY_ERROR", `invalid ${label}`);
    previous = index;
  }
  return value;
}

function parseV1(value) {
  if (value.schemaVersion !== 1 || !value.verifiers || typeof value.verifiers !== "object" || !Array.isArray(value.rules)) {
    fail("POLICY_ERROR", "invalid verification policy");
  }
  const verifiers = {};
  for (const [id, verifier] of Object.entries(value.verifiers)) {
    if (!/^[a-z0-9][a-z0-9-]{0,79}$/.test(id) || !verifier || typeof verifier !== "object" || Array.isArray(verifier)) {
      fail("POLICY_ERROR", "invalid verification policy verifier");
    }
    if (!new Set(["test", "lint"]).has(verifier.kind) || !Array.isArray(verifier.argv) || verifier.argv.length === 0 ||
        verifier.argv.some(item => typeof item !== "string" || item.length === 0)) {
      fail("POLICY_ERROR", "invalid verification policy verifier");
    }
    verifiers[id] = {
      id,
      kind: verifier.kind,
      argv: [...verifier.argv],
      cwd: verifier.cwd === undefined || verifier.cwd === "." ? "." : normalizeRepositoryPath(verifier.cwd, "POLICY_ERROR"),
      appendChangedFiles: verifier.appendChangedFiles === true,
      extensions: stringList(verifier.extensions ?? [], "verifier extensions"),
    };
  }
  const rules = value.rules.map(rule => {
    assertObject(rule, "verification policy rule");
    if (typeof rule.name !== "string" || !rule.name.trim()) fail("POLICY_ERROR", "invalid verification policy rule");
    const minimumTier = rule.minimumTier ?? "read-only";
    if (!LEGACY_TIERS.includes(minimumTier)) fail("POLICY_ERROR", "invalid verification policy tier");
    const tests = stringList(rule.tests ?? [], "rule tests");
    const lints = stringList(rule.lints ?? [], "rule lints");
    for (const id of [...tests, ...lints]) if (!verifiers[id]) fail("POLICY_ERROR", "unknown verification policy verifier");
    return {
      name: rule.name.trim(),
      prefixes: stringList(rule.prefixes ?? [], "rule prefixes").map(prefix => normalizeRepositoryPath(prefix, "POLICY_ERROR")),
      minimumTier,
      tests,
      lints,
      documentation: stringList(rule.documentation ?? [], "rule documentation"),
      ci: stringList(rule.ci ?? [], "rule ci"),
      gates: stringList(rule.gates ?? [], "rule gates"),
    };
  });
  return {schemaVersion: 1, verifiers, rules};
}

function parseCatalogV2(value, label) {
  assertObject(value, label);
  const result = new Map();
  for (const [id, item] of Object.entries(value)) {
    assertIdentifier(id, `${label} id`);
    assertExactKeys(item, CATALOG_ITEM_V2, `${label} item`);
    const level = assertLevel(item.level, `${label} level`);
    if (!new Set(["local", "external"]).has(item.execution)) fail("POLICY_ERROR", `invalid ${label} execution`);
    if (typeof item.value !== "string" || item.value.trim().length === 0) fail("POLICY_ERROR", `invalid ${label} value`);
    result.set(id, {level, execution: item.execution, value: item.value});
  }
  return result;
}

function parseCatalogV3(value, label, lane, gate) {
  assertObject(value, label);
  const result = new Map();
  for (const [id, item] of Object.entries(value)) {
    assertIdentifier(id, `${label} id`);
    assertExactKeys(item, CATALOG_ITEM_V3, `${label} item`);
    const level = assertLevel(item.level, `${label} level`);
    if (item.lane !== lane || item.gate !== gate) fail("POLICY_ERROR", `invalid ${label} lane or gate`);
    const platforms = orderedPlatforms(item.platforms, `${label} platforms`);
    if (typeof item.value !== "string" || item.value.trim().length === 0) fail("POLICY_ERROR", `invalid ${label} value`);
    result.set(id, {level, lane, gate, platforms: [...platforms], value: item.value});
  }
  return result;
}

function validateReferences(ids, catalog, label) {
  stringList(ids, label, item => assertIdentifier(item, label));
  if (ids.some(id => !catalog.has(id))) fail("POLICY_ERROR", `unknown ${label} reference`);
}

function parseMatch(value, label) {
  assertObject(value, label);
  const keys = Object.keys(value);
  if ([...MATCH_REQUIRED_KEYS].some(key => !keys.includes(key)) ||
      keys.some(key => !MATCH_REQUIRED_KEYS.has(key) && !MATCH_OPTIONAL_KEYS.has(key))) {
    fail("POLICY_ERROR", `invalid ${label} keys`);
  }
  const match = {
    files: stringList(value.files, `${label} files`, validateMatchPath),
    prefixes: stringList(value.prefixes, `${label} prefixes`, validatePrefix),
    segments: stringList(value.segments, `${label} segments`, validateSegment),
    suffixes: stringList(value.suffixes, `${label} suffixes`, validateSuffix),
    excludePrefixes: stringList(
      value.excludePrefixes === undefined ? [] : value.excludePrefixes,
      `${label} exclude prefixes`,
      validatePrefix,
    ),
  };
  if ([match.files, match.prefixes, match.segments, match.suffixes].every(items => items.length === 0)) {
    fail("POLICY_ERROR", `${label} has no matchers`);
  }
  return match;
}

function parseSelection(value, catalogs, label, schemaVersion, withMatch) {
  const expected = schemaVersion === 3
    ? (withMatch ? RULE_KEYS_V3 : FALLBACK_KEYS_V3)
    : (withMatch ? RULE_KEYS_V2 : FALLBACK_KEYS_V2);
  assertExactKeys(value, expected, label);
  const reason = assertIdentifier(value.reason, `${label} reason`);
  const minimumLevel = assertLevel(value.minimumLevel, `${label} minimum level`);
  const impact = stringList(value.impact, `${label} impact`, item => assertIdentifier(item, `${label} impact`), {nonEmpty: true});
  if (!RISK_ORDER.includes(value.risk)) fail("POLICY_ERROR", `invalid ${label} risk`);
  if (!new Set(["low", "high"]).has(value.coupling)) fail("POLICY_ERROR", `invalid ${label} coupling`);
  validateReferences(value.tests, catalogs.tests, `${label} tests`);
  validateReferences(value.documentation, catalogs.documentation, `${label} documentation`);
  validateReferences(value.ci, catalogs.ci, `${label} CI`);
  if (schemaVersion === 3) validateReferences(value.realMachine, catalogs.realMachine, `${label} real machine`);
  return {
    ...value,
    reason,
    minimumLevel,
    impact: [...impact],
    platforms: schemaVersion === 3 ? [...orderedPlatforms(value.platforms, `${label} platforms`)] : [],
    realMachine: schemaVersion === 3 ? [...value.realMachine] : [],
    match: withMatch ? parseMatch(value.match, `${label} match`) : undefined,
  };
}

function parseModern(value, schemaVersion) {
  assertExactKeys(value, schemaVersion === 3 ? TOP_V3 : TOP_V2, "verification policy");
  if (value.schemaVersion !== schemaVersion) fail("POLICY_ERROR", "unsupported verification policy schema");
  if (JSON.stringify(value.riskOrder) !== JSON.stringify(RISK_ORDER)) fail("POLICY_ERROR", "invalid risk order");
  if (JSON.stringify(value.levelOrder) !== JSON.stringify(LEVEL_ORDER)) fail("POLICY_ERROR", "invalid level order");
  if (schemaVersion === 3) {
    if (JSON.stringify(value.platformOrder) !== JSON.stringify(PLATFORM_ORDER)) fail("POLICY_ERROR", "invalid platform order");
    if (JSON.stringify(value.statusOrder) !== JSON.stringify(STATUS_ORDER)) fail("POLICY_ERROR", "invalid status order");
  }
  assertExactKeys(value.escalation, ESCALATION_KEYS, "escalation policy");
  if (!Number.isInteger(value.escalation.highCouplingImpactThreshold) || value.escalation.highCouplingImpactThreshold < 2) {
    fail("POLICY_ERROR", "invalid high-coupling impact threshold");
  }
  const targetLevel = assertLevel(value.escalation.targetLevel, "escalation target level");
  if (LEVEL_ORDER.indexOf(targetLevel) < 1) fail("POLICY_ERROR", "invalid escalation target level");

  assertExactKeys(value.catalogs, schemaVersion === 3 ? CATALOG_KEYS_V3 : CATALOG_KEYS_V2, "catalogs");
  const catalogs = schemaVersion === 3 ? {
    tests: parseCatalogV3(value.catalogs.tests, "test catalog", "local", "merge"),
    documentation: parseCatalogV3(value.catalogs.documentation, "documentation catalog", "local", "merge"),
    ci: parseCatalogV3(value.catalogs.ci, "CI catalog", "ci", "merge"),
    realMachine: parseCatalogV3(value.catalogs.realMachine, "real-machine catalog", "real-machine", "release"),
  } : {
    tests: parseCatalogV2(value.catalogs.tests, "test catalog"),
    documentation: parseCatalogV2(value.catalogs.documentation, "documentation catalog"),
    ci: parseCatalogV2(value.catalogs.ci, "CI catalog"),
  };
  if (!Array.isArray(value.rules) || value.rules.length === 0) fail("POLICY_ERROR", "verification rules are required");
  const ruleIds = new Set();
  const rules = value.rules.map((rule, index) => {
    const parsed = parseSelection(rule, catalogs, `rule ${index}`, schemaVersion, true);
    const id = assertIdentifier(rule.id, `rule ${index} id`);
    if (ruleIds.has(id)) fail("POLICY_ERROR", `duplicate rule id: ${id}`);
    ruleIds.add(id);
    return {...parsed, id};
  });
  const fallback = parseSelection(value.fallback, catalogs, "fallback", schemaVersion, false);
  if (fallback.risk !== "full-delivery" || fallback.minimumLevel !== "L4" || fallback.reason !== "unknown_path" || fallback.coupling !== "high") {
    fail("POLICY_ERROR", "fallback must fail closed");
  }
  return {
    schemaVersion,
    riskOrder: [...RISK_ORDER],
    levelOrder: [...LEVEL_ORDER],
    platformOrder: schemaVersion === 3 ? [...PLATFORM_ORDER] : [],
    statusOrder: schemaVersion === 3 ? [...STATUS_ORDER] : [],
    escalation: {...value.escalation, targetLevel},
    catalogs,
    rules,
    delegatedPrefixes: [...new Set(rules.flatMap(rule => rule.match.excludePrefixes))]
      .sort((left, right) => right.length - left.length),
    fallback,
  };
}

export function parseVerificationPolicy(value) {
  assertObject(value, "verification policy");
  if (value.schemaVersion === 1) return parseV1(value);
  if (value.schemaVersion === 2 || value.schemaVersion === 3) return parseModern(value, value.schemaVersion);
  fail("POLICY_ERROR", "unsupported verification policy schema");
}

export function loadVerificationPolicy({projectRoot, policyPath = DEFAULT_POLICY_PATH}) {
  const destination = safeRegularFile(projectRoot, policyPath, "POLICY_ERROR");
  let value;
  try {
    value = JSON.parse(fs.readFileSync(destination, "utf8"));
  } catch {
    fail("POLICY_ERROR", "verification policy is not valid JSON");
  }
  return parseVerificationPolicy(value);
}
