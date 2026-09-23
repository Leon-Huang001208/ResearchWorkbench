#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const LEVEL_ORDER = ["L0", "L1", "L2", "L3", "L4"];
const PLAN_KEYS = new Set([
  "schemaVersion",
  "risk",
  "requiredLevel",
  "changeSummary",
  "changedFiles",
  "impact",
  "reasons",
  "escalations",
  "uncoveredRisks",
  "validationsByLevel",
  "tests",
  "documentation",
  "ci",
  "receiptTemplate",
]);
const CHANGE_SUMMARY_KEYS = new Set(["fileCount", "ruleIds", "impactIds"]);
const IMPACT_KEYS = new Set(["path", "rule", "reason", "modules", "coupling", "minimumLevel"]);
const VALIDATION_KEYS = new Set(["id", "level", "execution", "category", "value"]);
const TEMPLATE_KEYS = new Set(["plannedLevel", "changedFiles", "requiredValidationIds", "externalGateIds"]);
const RECEIPT_KEYS = new Set([
  "schemaVersion",
  "changeSummary",
  "changedFiles",
  "plannedLevel",
  "actualLevel",
  "impact",
  "executed",
  "external",
  "result",
  "uncoveredRisks",
  "escalation",
]);
const EXECUTION_KEYS = new Set(["id", "level", "status", "durationSeconds", "evidence"]);
const EXTERNAL_KEYS = new Set(["id", "status", "evidence"]);
const ESCALATION_KEYS = new Set(["required", "targetLevel", "reasons"]);
const IDENTIFIER = /^[a-z0-9][a-z0-9_-]*$/;

class ReceiptError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

function fail(code, message) {
  throw new ReceiptError(code, message);
}

function assertExactKeys(value, expected, label, code) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code, `invalid ${label}`);
  const keys = Object.keys(value);
  if (keys.length !== expected.size || keys.some(key => !expected.has(key))) fail(code, `invalid ${label} keys`);
}

function assertIdentifier(value, label, code) {
  if (typeof value !== "string" || !IDENTIFIER.test(value)) fail(code, `invalid ${label}`);
  return value;
}

function assertLevel(value, label, code) {
  if (!LEVEL_ORDER.includes(value)) fail(code, `invalid ${label}`);
  return value;
}

function assertStringArray(value, label, code, {identifiers = false} = {}) {
  if (!Array.isArray(value)) fail(code, `invalid ${label}`);
  const seen = new Set();
  for (const item of value) {
    if (typeof item !== "string" || item.length === 0 || seen.has(item)) fail(code, `invalid ${label}`);
    if (identifiers) assertIdentifier(item, label, code);
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

function safeProjectRoot(projectValue) {
  if (typeof projectValue !== "string" || projectValue.length === 0) fail("PATH_ERROR", "invalid project directory");
  let metadata;
  try {
    metadata = fs.lstatSync(projectValue);
  } catch {
    fail("PATH_ERROR", "project directory is unavailable");
  }
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) fail("PATH_ERROR", "project directory must be a real directory");
  try {
    return fs.realpathSync(projectValue);
  } catch {
    fail("PATH_ERROR", "project directory cannot be resolved");
  }
}

function assertNoSymlinkComponents(root, relative, {required, code = "PATH_ERROR"}) {
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

function assertRegularEvidence(root, relative, code) {
  assertNoSymlinkComponents(root, relative, {required: true, code});
  let metadata;
  try {
    metadata = fs.statSync(path.join(root, relative));
  } catch {
    fail(code, "evidence file is unavailable");
  }
  if (!metadata.isFile()) fail(code, "evidence must be a regular file");
}

function readJson(root, relative, code) {
  const normalized = normalizeRepositoryPath(relative);
  assertNoSymlinkComponents(root, normalized, {required: true});
  const destination = path.join(root, normalized);
  let metadata;
  let raw;
  try {
    metadata = fs.statSync(destination);
    raw = fs.readFileSync(destination, "utf8");
  } catch {
    fail("PATH_ERROR", "input file is unavailable");
  }
  if (!metadata.isFile()) fail("PATH_ERROR", "input must be a regular file");
  try {
    return JSON.parse(raw);
  } catch {
    fail(code, "input is not valid JSON");
  }
}

function parseArgs(args) {
  const options = {};
  const names = new Map([
    ["--project", "project"],
    ["--plan", "plan"],
    ["--receipt", "receipt"],
  ]);
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    const name = names.get(argument);
    if (!name) fail("ARGUMENT_ERROR", "unknown option");
    const value = args[index + 1];
    if (!value || value.startsWith("--")) fail("ARGUMENT_ERROR", `${argument} requires a value`);
    if (options[name] !== undefined) fail("ARGUMENT_ERROR", `${argument} may only be provided once`);
    options[name] = value;
    index += 1;
  }
  for (const [option, name] of names) {
    if (!options[name]) fail("ARGUMENT_ERROR", `${option} is required`);
  }
  return options;
}

function parsePlan(value) {
  const code = "PLAN_ERROR";
  assertExactKeys(value, PLAN_KEYS, "plan", code);
  if (value.schemaVersion !== 2) fail(code, "unsupported plan schema");
  if (!["docs-only", "local-only", "full-delivery"].includes(value.risk)) fail(code, "invalid plan risk");
  assertLevel(value.requiredLevel, "required level", code);
  assertExactKeys(value.changeSummary, CHANGE_SUMMARY_KEYS, "change summary", code);
  if (!Number.isInteger(value.changeSummary.fileCount) || value.changeSummary.fileCount < 1) {
    fail(code, "invalid change summary file count");
  }
  assertStringArray(value.changeSummary.ruleIds, "change summary rule IDs", code, {identifiers: true});
  assertStringArray(value.changeSummary.impactIds, "change summary impact IDs", code, {identifiers: true});
  assertStringArray(value.changedFiles, "changed files", code);
  for (const changedFile of value.changedFiles) normalizeRepositoryPath(changedFile, code);
  if (value.changeSummary.fileCount !== value.changedFiles.length) fail(code, "change summary does not match changed files");

  if (!Array.isArray(value.impact) || value.impact.length === 0) fail(code, "invalid impact assessment");
  for (const item of value.impact) {
    assertExactKeys(item, IMPACT_KEYS, "impact item", code);
    normalizeRepositoryPath(item.path, code);
    if (!value.changedFiles.includes(item.path)) fail(code, "impact path is outside changed files");
    assertIdentifier(item.rule, "impact rule", code);
    assertIdentifier(item.reason, "impact reason", code);
    assertStringArray(item.modules, "impact modules", code, {identifiers: true});
    if (item.modules.length === 0 || !["low", "high"].includes(item.coupling)) fail(code, "invalid impact item");
    assertLevel(item.minimumLevel, "impact minimum level", code);
  }
  if (!Array.isArray(value.reasons) || !Array.isArray(value.escalations)) fail(code, "invalid plan reasoning");
  assertStringArray(value.uncoveredRisks, "uncovered risks", code);

  assertExactKeys(value.validationsByLevel, new Set(LEVEL_ORDER), "validations by level", code);
  const validations = new Map();
  for (const level of LEVEL_ORDER) {
    const items = value.validationsByLevel[level];
    if (!Array.isArray(items)) fail(code, `invalid ${level} validations`);
    for (const item of items) {
      assertExactKeys(item, VALIDATION_KEYS, "validation item", code);
      const id = assertIdentifier(item.id, "validation ID", code);
      if (item.level !== level || !["local", "external"].includes(item.execution) ||
          !["tests", "documentation", "ci"].includes(item.category) ||
          typeof item.value !== "string" || item.value.length === 0 || validations.has(id)) {
        fail(code, "invalid validation item");
      }
      validations.set(id, item);
    }
  }
  for (const category of ["tests", "documentation", "ci"]) {
    if (!Array.isArray(value[category])) fail(code, `invalid ${category}`);
    for (const item of value[category]) {
      const expected = validations.get(item.id);
      if (!expected || expected.category !== category || JSON.stringify(item) !== JSON.stringify(expected)) {
        fail(code, `invalid ${category} projection`);
      }
    }
  }

  assertExactKeys(value.receiptTemplate, TEMPLATE_KEYS, "receipt template", code);
  if (value.receiptTemplate.plannedLevel !== value.requiredLevel ||
      JSON.stringify(value.receiptTemplate.changedFiles) !== JSON.stringify(value.changedFiles)) {
    fail(code, "receipt template does not match plan");
  }
  const requiredValidationIds = assertStringArray(
    value.receiptTemplate.requiredValidationIds,
    "required validation IDs",
    code,
    {identifiers: true},
  );
  const externalGateIds = assertStringArray(
    value.receiptTemplate.externalGateIds,
    "external gate IDs",
    code,
    {identifiers: true},
  );
  for (const id of [...requiredValidationIds, ...externalGateIds]) {
    if (!validations.has(id)) fail(code, "receipt template references unknown validation");
  }
  if (requiredValidationIds.some(id => externalGateIds.includes(id))) fail(code, "receipt template IDs overlap");
  const projected = [...value.tests, ...value.documentation, ...value.ci];
  const expectedRequiredIds = projected.filter(item => item.execution === "local").map(item => item.id);
  const expectedExternalIds = projected.filter(item => item.execution === "external").map(item => item.id);
  if (JSON.stringify(requiredValidationIds) !== JSON.stringify(expectedRequiredIds) ||
      JSON.stringify(externalGateIds) !== JSON.stringify(expectedExternalIds)) {
    fail(code, "receipt template omits or misclassifies a validation");
  }
  return {...value, validations};
}

function parseReceipt(value, root, plan) {
  const code = "RECEIPT_ERROR";
  assertExactKeys(value, RECEIPT_KEYS, "receipt", code);
  if (value.schemaVersion !== 1) fail(code, "unsupported receipt schema");
  assertExactKeys(value.changeSummary, CHANGE_SUMMARY_KEYS, "receipt change summary", code);
  assertStringArray(value.changedFiles, "receipt changed files", code);
  for (const changedFile of value.changedFiles) normalizeRepositoryPath(changedFile, code);
  assertLevel(value.plannedLevel, "receipt planned level", code);
  assertLevel(value.actualLevel, "receipt actual level", code);
  if (!Array.isArray(value.impact)) fail(code, "invalid receipt impact");
  if (!["passed", "failed", "blocked"].includes(value.result)) fail(code, "invalid receipt result");
  assertStringArray(value.uncoveredRisks, "receipt uncovered risks", code);
  assertExactKeys(value.escalation, ESCALATION_KEYS, "receipt escalation", code);
  if (typeof value.escalation.required !== "boolean") fail(code, "invalid receipt escalation");
  assertStringArray(value.escalation.reasons, "receipt escalation reasons", code);
  if (value.escalation.required) {
    assertLevel(value.escalation.targetLevel, "receipt escalation target", code);
    if (value.escalation.reasons.length === 0) fail(code, "escalation reasons are required");
  } else if (value.escalation.targetLevel !== null || value.escalation.reasons.length !== 0) {
    fail(code, "unexpected escalation detail");
  }

  if (JSON.stringify(value.changeSummary) !== JSON.stringify(plan.changeSummary) ||
      JSON.stringify(value.changedFiles) !== JSON.stringify(plan.changedFiles) ||
      value.plannedLevel !== plan.requiredLevel || JSON.stringify(value.impact) !== JSON.stringify(plan.impact)) {
    fail(code, "receipt does not match plan");
  }
  if (value.actualLevel !== value.plannedLevel) {
    fail(code, "actual level must match the planned level");
  }
  for (const risk of plan.uncoveredRisks) {
    if (!value.uncoveredRisks.includes(risk)) fail(code, "receipt omits a planned uncovered risk");
  }

  if (!Array.isArray(value.executed)) fail(code, "invalid executed validations");
  const executed = new Map();
  let hasFailure = false;
  for (const item of value.executed) {
    assertExactKeys(item, EXECUTION_KEYS, "executed validation", code);
    const id = assertIdentifier(item.id, "executed validation ID", code);
    const planned = plan.validations.get(id);
    if (!planned || executed.has(id) || item.level !== planned.level ||
        !["passed", "failed", "unexpected", "blocked"].includes(item.status) ||
        typeof item.durationSeconds !== "number" || !Number.isFinite(item.durationSeconds) ||
        item.durationSeconds < 0) {
      fail(code, "invalid executed validation");
    }
    const evidence = normalizeRepositoryPath(item.evidence, code);
    assertRegularEvidence(root, evidence, code);
    if (item.status === "failed" || item.status === "unexpected" || item.status === "blocked") hasFailure = true;
    executed.set(id, item);
  }
  for (const id of plan.receiptTemplate.requiredValidationIds) {
    if (!executed.has(id)) fail(code, "required validation was not executed");
  }

  if (!Array.isArray(value.external)) fail(code, "invalid external gates");
  const external = new Map();
  const notRunExternal = [];
  for (const item of value.external) {
    assertExactKeys(item, EXTERNAL_KEYS, "external gate", code);
    const id = assertIdentifier(item.id, "external gate ID", code);
    if (!plan.receiptTemplate.externalGateIds.includes(id) || external.has(id) ||
        !["passed", "failed", "not_run", "not_required"].includes(item.status)) {
      fail(code, "invalid external gate");
    }
    const evidence = normalizeRepositoryPath(item.evidence, code);
    assertRegularEvidence(root, evidence, code);
    if (item.status === "failed") hasFailure = true;
    if (item.status === "not_run") notRunExternal.push(id);
    if (plan.risk === "full-delivery" && item.status === "not_required") {
      fail(code, "full-delivery external gate cannot be not required");
    }
    external.set(id, item);
  }
  for (const id of plan.receiptTemplate.externalGateIds) {
    if (!external.has(id)) fail(code, "external gate is missing");
  }

  if (hasFailure) {
    if (value.result === "passed") fail(code, "failed validation cannot produce a passed receipt");
    if (!value.escalation.required) fail(code, "failure requires escalation");
    const requiredTarget = LEVEL_ORDER[Math.min(
      LEVEL_ORDER.indexOf(plan.requiredLevel) + 1,
      LEVEL_ORDER.length - 1,
    )];
    if (LEVEL_ORDER.indexOf(value.escalation.targetLevel) < LEVEL_ORDER.indexOf(requiredTarget)) {
      fail(code, "escalation target is insufficient");
    }
  } else if (value.result === "failed") {
    fail(code, "failed receipt has no failed validation");
  }

  if (plan.risk === "full-delivery" && notRunExternal.length > 0) {
    if (value.result !== "blocked") fail(code, "unrun full-delivery gate must block the receipt");
    for (const id of notRunExternal) {
      if (!value.uncoveredRisks.includes(`external_gate_not_run:${id}`)) {
        fail(code, "unrun external gate is not recorded as a risk");
      }
    }
  } else if (!hasFailure && value.result !== "passed") {
    fail(code, "receipt result is inconsistent with validation results");
  }

  return value;
}

export function validateVerificationReceipt({projectRoot, planPath, receiptPath}) {
  const root = safeProjectRoot(projectRoot);
  const plan = parsePlan(readJson(root, planPath, "PLAN_ERROR"));
  const receipt = parseReceipt(readJson(root, receiptPath, "RECEIPT_ERROR"), root, plan);
  return {
    schemaVersion: 1,
    valid: true,
    result: receipt.result,
    plannedLevel: plan.requiredLevel,
    actualLevel: receipt.actualLevel,
    executedCount: receipt.executed.length,
    escalationRequired: receipt.escalation.required,
  };
}

function main(args) {
  const options = parseArgs(args);
  const result = validateVerificationReceipt({
    projectRoot: options.project,
    planPath: options.plan,
    receiptPath: options.receipt,
  });
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    const code = error instanceof ReceiptError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof ReceiptError ? error.message : "unexpected receipt validation failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 1, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
