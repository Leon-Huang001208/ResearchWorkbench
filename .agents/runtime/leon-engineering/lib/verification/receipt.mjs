import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";

import {fail} from "./errors.mjs";
import {planGitVerification, planVerification} from "./planner.mjs";
import {LEVEL_ORDER, SIGNALS, STATUS_ORDER} from "./policy.mjs";
import {assertNoSymlinkComponents, normalizeRepositoryPath, safeProjectRoot} from "./path-safety.mjs";

const LEGACY_RECEIPT_KEYS = new Set([
  "schemaVersion", "changeSummary", "changedFiles", "plannedLevel", "actualLevel", "impact", "executed", "external",
  "result", "uncoveredRisks", "escalation",
]);
const BOUND_RECEIPT_KEYS = new Set([
  "schemaVersion", "binding", "changeSummary", "changedFiles", "plannedLevel", "actualLevel", "components", "platforms",
  "impact", "executed", "external", "realMachine", "result", "mergeReady", "releaseReady", "uncoveredRisks", "escalation",
]);
const UNBOUND_RECEIPT_KEYS = new Set([...BOUND_RECEIPT_KEYS].filter(key => key !== "binding"));
const LEGACY_EXECUTION_KEYS = new Set(["id", "level", "status", "durationSeconds", "evidence"]);
const EXECUTION_KEYS = new Set(["id", "level", "status", "durationSeconds", "source", "evidence"]);
const LEGACY_EXTERNAL_KEYS = new Set(["id", "status", "evidence"]);
const EXTERNAL_KEYS = new Set(["id", "status", "source", "evidence"]);
const ESCALATION_KEYS = new Set(["required", "targetLevel", "reasons"]);
const PLAN_V2_KEYS = new Set([
  "schemaVersion", "risk", "requiredLevel", "changeSummary", "changedFiles", "impact", "reasons", "escalations",
  "uncoveredRisks", "validationsByLevel", "tests", "documentation", "ci", "receiptTemplate",
]);
const PLAN_V3_KEYS = new Set([
  "schemaVersion", "risk", "requiredLevel", "components", "platforms", "changeSummary", "changedFiles", "impact",
  "reasons", "escalations", "uncoveredRisks", "validationsByLevel", "tests", "documentation", "ci", "local",
  "realMachine", "receiptTemplate",
]);
const PLAN_V3_BOUND_KEYS = new Set([...PLAN_V3_KEYS, "changeSet", "binding"]);
const VALIDATION_V2_KEYS = new Set(["id", "level", "execution", "category", "value"]);
const VALIDATION_V3_KEYS = new Set(["id", "level", "lane", "gate", "platforms", "category", "value"]);

function assertExactKeys(value, expected, label, code = "RECEIPT_ERROR") {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail(code, `invalid ${label}`);
  const keys = Object.keys(value);
  if (keys.length !== expected.size || keys.some(key => !expected.has(key))) fail(code, `invalid ${label} keys`);
}

function assertStringArray(value, label, code = "RECEIPT_ERROR") {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string" || item.length === 0)) {
    fail(code, `invalid ${label}`);
  }
  if (new Set(value).size !== value.length) fail(code, `invalid ${label}`);
  return value;
}

function assertLevel(value, label, code = "RECEIPT_ERROR") {
  if (!LEVEL_ORDER.includes(value)) fail(code, `invalid ${label}`);
  return value;
}

function gitCommonRoot(root) {
  let relative;
  try {
    relative = execFileSync("git", ["-C", root, "rev-parse", "--git-common-dir"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    fail("PATH_ERROR", "Git common directory is unavailable");
  }
  const destination = path.resolve(root, relative);
  const metadata = fs.lstatSync(destination);
  if (metadata.isSymbolicLink() || !metadata.isDirectory()) fail("PATH_ERROR", "invalid Git common directory");
  return fs.realpathSync(destination);
}

function resolveInput(root, inputPath) {
  if (typeof inputPath !== "string" || inputPath.length === 0) fail("PATH_ERROR", "invalid input path");
  let base = root;
  let relative = inputPath;
  if (path.isAbsolute(inputPath)) {
    base = gitCommonRoot(root);
    const inputMetadata = fs.lstatSync(inputPath);
    if (inputMetadata.isSymbolicLink()) fail("PATH_ERROR", "input cannot be a symbolic link");
    const candidate = fs.realpathSync(inputPath);
    if (candidate !== base && !candidate.startsWith(`${base}${path.sep}`)) {
      fail("PATH_ERROR", "absolute input must be inside the Git common directory");
    }
    relative = path.relative(base, candidate).split(path.sep).join("/");
  }
  const normalized = assertNoSymlinkComponents(base, normalizeRepositoryPath(relative), {
    required: true,
    code: "PATH_ERROR",
  });
  const destination = path.join(base, normalized);
  if (!fs.statSync(destination).isFile()) fail("PATH_ERROR", "input must be a regular file");
  return destination;
}

function readJson(root, inputPath, code) {
  const destination = resolveInput(root, inputPath);
  try {
    return JSON.parse(fs.readFileSync(destination, "utf8"));
  } catch {
    fail(code, "input is not valid JSON");
  }
}

function evidenceFile(root, relative) {
  const normalized = assertNoSymlinkComponents(root, normalizeRepositoryPath(relative, "RECEIPT_ERROR"), {
    required: true,
    code: "RECEIPT_ERROR",
  });
  if (!fs.statSync(path.join(root, normalized)).isFile()) fail("RECEIPT_ERROR", "evidence must be a regular file");
}

function validatePlanStructure(plan) {
  const expectedKeys = plan?.schemaVersion === 2 ? PLAN_V2_KEYS
    : plan?.schemaVersion === 3 && plan.binding ? PLAN_V3_BOUND_KEYS
      : plan?.schemaVersion === 3 ? PLAN_V3_KEYS
        : null;
  if (!expectedKeys) fail("PLAN_ERROR", "unsupported plan schema");
  assertExactKeys(plan, expectedKeys, "plan", "PLAN_ERROR");
  assertLevel(plan.requiredLevel, "plan required level", "PLAN_ERROR");
  assertStringArray(plan.changedFiles, "plan changed files", "PLAN_ERROR");
  assertStringArray(plan.uncoveredRisks, "plan uncovered risks", "PLAN_ERROR");
  if (!plan.changeSummary || plan.changeSummary.fileCount !== plan.changedFiles.length ||
      !Array.isArray(plan.impact) || plan.impact.length === 0 || !Array.isArray(plan.reasons) ||
      !Array.isArray(plan.escalations)) {
    fail("PLAN_ERROR", "invalid plan change summary or reasoning");
  }
  for (const changedFile of plan.changedFiles) normalizeRepositoryPath(changedFile, "PLAN_ERROR");
  for (const item of plan.impact) {
    if (!plan.changedFiles.includes(item?.path)) fail("PLAN_ERROR", "impact path is outside changed files");
  }
  if (plan.schemaVersion === 3) {
    assertStringArray(plan.components, "plan components", "PLAN_ERROR");
    assertStringArray(plan.platforms, "plan platforms", "PLAN_ERROR");
  }
  if (!plan.validationsByLevel || typeof plan.validationsByLevel !== "object" ||
      Object.keys(plan.validationsByLevel).sort().join(",") !== [...LEVEL_ORDER].sort().join(",")) {
    fail("PLAN_ERROR", "invalid validations by level");
  }
  const validations = new Map();
  for (const level of LEVEL_ORDER) {
    const items = plan.validationsByLevel[level];
    if (!Array.isArray(items)) fail("PLAN_ERROR", `invalid ${level} validations`);
    for (const item of items) {
      assertExactKeys(item, plan.schemaVersion === 3 ? VALIDATION_V3_KEYS : VALIDATION_V2_KEYS, "validation item", "PLAN_ERROR");
      if (item.level !== level || validations.has(item.id)) fail("PLAN_ERROR", "invalid validation item");
      validations.set(item.id, item);
    }
  }
  for (const category of ["tests", "documentation", "ci", ...(plan.schemaVersion === 3 ? ["realMachine"] : [])]) {
    if (!Array.isArray(plan[category])) fail("PLAN_ERROR", `invalid ${category} projection`);
    for (const item of plan[category]) {
      const expected = validations.get(item.id);
      if (!expected || expected.category !== category || JSON.stringify(item) !== JSON.stringify(expected)) {
        fail("PLAN_ERROR", `invalid ${category} projection`);
      }
    }
  }
  if (!plan.receiptTemplate || plan.receiptTemplate.plannedLevel !== plan.requiredLevel ||
      JSON.stringify(plan.receiptTemplate.changedFiles) !== JSON.stringify(plan.changedFiles)) {
    fail("PLAN_ERROR", "receipt template does not match plan");
  }
  const projected = [...plan.tests, ...plan.documentation, ...plan.ci, ...(plan.realMachine ?? [])];
  const required = projected.filter(item => plan.schemaVersion === 2 ? item.execution === "local" : item.lane === "local")
    .map(item => item.id);
  const external = projected.filter(item => plan.schemaVersion === 2 ? item.execution === "external" : item.lane === "ci")
    .map(item => item.id);
  const release = plan.schemaVersion === 3 ? projected.filter(item => item.lane === "real-machine").map(item => item.id) : [];
  if (JSON.stringify(plan.receiptTemplate.requiredValidationIds) !== JSON.stringify(required) ||
      JSON.stringify(plan.receiptTemplate.externalGateIds) !== JSON.stringify(external) ||
      (plan.schemaVersion === 3 && JSON.stringify(plan.receiptTemplate.releaseGateIds) !== JSON.stringify(release))) {
    fail("PLAN_ERROR", "receipt template omits or misclassifies a validation");
  }
  if (plan.schemaVersion === 3) {
    const local = projected.filter(item => item.lane === "local");
    if (JSON.stringify(plan.local) !== JSON.stringify(local)) fail("PLAN_ERROR", "invalid local projection");
  }
  return plan;
}

function canonicalPlan(root, plan) {
  validatePlanStructure(plan);
  if (!plan.binding && !fs.existsSync(path.join(root, ".agents", "verification-policy.json"))) return plan;
  const signals = Array.isArray(plan.escalations)
    ? plan.escalations.map(item => item?.code).filter(code => SIGNALS.has(code))
    : [];
  let canonical;
  try {
    canonical = plan.schemaVersion === 3 && plan.binding
      ? planGitVerification({
        projectRoot: root,
        base: plan.binding.baseCommit,
        changedFiles: plan.changedFiles,
        signals,
      })
      : planVerification({projectRoot: root, changedFiles: plan.changedFiles, signals});
  } catch {
    fail("PLAN_ERROR", "plan cannot be reproduced from the current policy and change set");
  }
  if (JSON.stringify(plan) !== JSON.stringify(canonical)) fail("PLAN_ERROR", "plan does not match the current policy, binding, or change set");
  return canonical;
}

function validationMap(plan) {
  const values = [...plan.tests, ...plan.documentation, ...plan.ci, ...(plan.realMachine ?? [])];
  return new Map(values.map(item => [item.id, item]));
}

function validateEscalation(value) {
  assertExactKeys(value, ESCALATION_KEYS, "receipt escalation");
  if (typeof value.required !== "boolean") fail("RECEIPT_ERROR", "invalid receipt escalation");
  assertStringArray(value.reasons, "receipt escalation reasons");
  if (value.required) {
    assertLevel(value.targetLevel, "receipt escalation target");
    if (value.reasons.length === 0) fail("RECEIPT_ERROR", "escalation reasons are required");
  } else if (value.targetLevel !== null || value.reasons.length !== 0) {
    fail("RECEIPT_ERROR", "unexpected escalation detail");
  }
}

function requirePlanMatch(receipt, plan, fields) {
  for (const field of fields) {
    if (JSON.stringify(receipt[field]) !== JSON.stringify(plan[field])) fail("RECEIPT_ERROR", "receipt does not match plan");
  }
  if (receipt.plannedLevel !== plan.requiredLevel || receipt.actualLevel !== receipt.plannedLevel) {
    fail("RECEIPT_ERROR", "receipt level does not match plan");
  }
  for (const risk of plan.uncoveredRisks) {
    if (!receipt.uncoveredRisks.includes(risk)) fail("RECEIPT_ERROR", "receipt omits a planned uncovered risk");
  }
}

function validateLegacyReceipt(receipt, root, plan) {
  assertExactKeys(receipt, LEGACY_RECEIPT_KEYS, "receipt");
  if (receipt.schemaVersion !== 1) fail("RECEIPT_ERROR", "unsupported receipt schema");
  assertStringArray(receipt.changedFiles, "receipt changed files");
  assertStringArray(receipt.uncoveredRisks, "receipt uncovered risks");
  validateEscalation(receipt.escalation);
  requirePlanMatch(receipt, plan, ["changeSummary", "changedFiles", "impact"]);
  if (!new Set(["passed", "failed", "blocked"]).has(receipt.result)) fail("RECEIPT_ERROR", "invalid receipt result");
  const validations = validationMap(plan);
  const executed = new Map();
  let hasFailure = false;
  for (const item of receipt.executed ?? []) {
    assertExactKeys(item, LEGACY_EXECUTION_KEYS, "executed validation");
    const expected = validations.get(item.id);
    if (!expected || executed.has(item.id) || item.level !== expected.level ||
        !new Set(["passed", "failed", "unexpected", "blocked"]).has(item.status) ||
        typeof item.durationSeconds !== "number" || !Number.isFinite(item.durationSeconds) || item.durationSeconds < 0) {
      fail("RECEIPT_ERROR", "invalid executed validation");
    }
    evidenceFile(root, item.evidence);
    if (item.status !== "passed") hasFailure = true;
    executed.set(item.id, item);
  }
  for (const id of plan.receiptTemplate.requiredValidationIds) {
    if (!executed.has(id)) fail("RECEIPT_ERROR", "required validation was not executed");
  }
  const external = new Map();
  const notRun = [];
  for (const item of receipt.external ?? []) {
    assertExactKeys(item, LEGACY_EXTERNAL_KEYS, "external gate");
    if (!plan.receiptTemplate.externalGateIds.includes(item.id) || external.has(item.id) ||
        !new Set(["passed", "failed", "not_run", "not_required"]).has(item.status)) {
      fail("RECEIPT_ERROR", "invalid external gate");
    }
    evidenceFile(root, item.evidence);
    if (item.status === "failed") hasFailure = true;
    if (item.status === "not_run") notRun.push(item.id);
    if (plan.risk === "full-delivery" && item.status === "not_required") {
      fail("RECEIPT_ERROR", "full-delivery external gate cannot be not required");
    }
    external.set(item.id, item);
  }
  for (const id of plan.receiptTemplate.externalGateIds) if (!external.has(id)) fail("RECEIPT_ERROR", "external gate is missing");
  if (hasFailure && receipt.result === "passed") fail("RECEIPT_ERROR", "failed validation cannot produce a passed receipt");
  if (hasFailure && !receipt.escalation.required) fail("RECEIPT_ERROR", "failure requires escalation");
  if (hasFailure) {
    const target = LEVEL_ORDER[Math.min(LEVEL_ORDER.indexOf(plan.requiredLevel) + 1, LEVEL_ORDER.length - 1)];
    if (LEVEL_ORDER.indexOf(receipt.escalation.targetLevel) < LEVEL_ORDER.indexOf(target)) {
      fail("RECEIPT_ERROR", "escalation target is insufficient");
    }
  } else if (receipt.result === "failed" || receipt.escalation.required) {
    fail("RECEIPT_ERROR", "receipt result is inconsistent with validation results");
  }
  if (plan.risk === "full-delivery" && notRun.length > 0) {
    if (receipt.result !== "blocked") fail("RECEIPT_ERROR", "unrun full-delivery gate must block the receipt");
    for (const id of notRun) {
      if (!receipt.uncoveredRisks.includes(`external_gate_not_run:${id}`)) {
        fail("RECEIPT_ERROR", "unrun external gate is not recorded as a risk");
      }
    }
  } else if (!hasFailure && receipt.result !== "passed") {
    fail("RECEIPT_ERROR", "receipt result is inconsistent with validation results");
  }
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

function validateReceiptV2(receipt, root, plan) {
  const bound = Boolean(plan.binding);
  assertExactKeys(receipt, bound ? BOUND_RECEIPT_KEYS : UNBOUND_RECEIPT_KEYS, "receipt");
  if (receipt.schemaVersion !== 2 || plan.schemaVersion !== 3) fail("RECEIPT_ERROR", "receipt v2 requires plan v3");
  assertStringArray(receipt.changedFiles, "receipt changed files");
  assertStringArray(receipt.components, "receipt components");
  assertStringArray(receipt.platforms, "receipt platforms");
  assertStringArray(receipt.uncoveredRisks, "receipt uncovered risks");
  validateEscalation(receipt.escalation);
  requirePlanMatch(receipt, plan, [
    ...(bound ? ["binding"] : []),
    "changeSummary", "changedFiles", "components", "platforms", "impact",
  ]);
  if (!new Set(["PASS", "FAIL", "BLOCKED"]).has(receipt.result) ||
      typeof receipt.mergeReady !== "boolean" || typeof receipt.releaseReady !== "boolean") {
    fail("RECEIPT_ERROR", "invalid receipt result or readiness");
  }
  const validations = validationMap(plan);
  const executed = new Map();
  for (const item of receipt.executed ?? []) {
    assertExactKeys(item, bound ? EXECUTION_KEYS : LEGACY_EXECUTION_KEYS, "executed validation");
    const expected = validations.get(item.id);
    if (!expected || expected.lane !== "local" || !plan.receiptTemplate.requiredValidationIds.includes(item.id) ||
        executed.has(item.id) || item.level !== expected.level || !STATUS_ORDER.includes(item.status) ||
        item.status === "NOT_REQUIRED" || (bound && item.source !== "runner") ||
        typeof item.durationSeconds !== "number" || !Number.isFinite(item.durationSeconds) || item.durationSeconds < 0) {
      fail("RECEIPT_ERROR", "invalid executed validation");
    }
    evidenceFile(root, item.evidence);
    executed.set(item.id, item);
  }
  for (const id of plan.receiptTemplate.requiredValidationIds) {
    if (!executed.has(id)) fail("RECEIPT_ERROR", "required validation was not executed");
  }
  const external = new Map();
  for (const item of receipt.external ?? []) {
    assertExactKeys(item, bound ? EXTERNAL_KEYS : LEGACY_EXTERNAL_KEYS, "external gate");
    const expected = validations.get(item.id);
    if (!expected || expected.lane !== "ci" || !plan.receiptTemplate.externalGateIds.includes(item.id) ||
        external.has(item.id) || !STATUS_ORDER.includes(item.status) || item.status === "NOT_REQUIRED" ||
        (bound && item.source !== "ci")) {
      fail("RECEIPT_ERROR", "invalid external gate");
    }
    evidenceFile(root, item.evidence);
    external.set(item.id, item);
  }
  for (const id of plan.receiptTemplate.externalGateIds) if (!external.has(id)) fail("RECEIPT_ERROR", "external gate is missing");
  const realMachine = new Map();
  for (const item of receipt.realMachine ?? []) {
    assertExactKeys(item, bound ? EXTERNAL_KEYS : LEGACY_EXTERNAL_KEYS, "real-machine gate");
    const expected = validations.get(item.id);
    if (!expected || expected.lane !== "real-machine" || !plan.receiptTemplate.releaseGateIds.includes(item.id) ||
        realMachine.has(item.id) || !STATUS_ORDER.includes(item.status) || item.status === "NOT_REQUIRED" ||
        (bound && item.source !== "manual")) {
      fail("RECEIPT_ERROR", "invalid real-machine gate");
    }
    evidenceFile(root, item.evidence);
    realMachine.set(item.id, item);
  }
  for (const id of plan.receiptTemplate.releaseGateIds) if (!realMachine.has(id)) fail("RECEIPT_ERROR", "real-machine gate is missing");

  const localItems = plan.receiptTemplate.requiredValidationIds.map(id => executed.get(id));
  const ciItems = plan.receiptTemplate.externalGateIds.map(id => external.get(id));
  const realItems = plan.receiptTemplate.releaseGateIds.map(id => realMachine.get(id));
  const mergeItems = [...localItems, ...ciItems];
  const mergeReady = mergeItems.every(item => item.status === "PASS");
  const releaseReady = mergeReady && realItems.every(item => item.status === "PASS");
  if (receipt.mergeReady !== mergeReady || receipt.releaseReady !== releaseReady) {
    fail("RECEIPT_ERROR", "readiness projection is inconsistent with evidence");
  }
  const hasFailure = [...mergeItems, ...realItems].some(item => item.status === "FAIL");
  if (hasFailure) {
    if (receipt.result !== "FAIL") fail("RECEIPT_ERROR", "failed validation must produce a failed receipt");
    if (!receipt.escalation.required) fail("RECEIPT_ERROR", "failure requires escalation");
    const target = LEVEL_ORDER[Math.min(LEVEL_ORDER.indexOf(plan.requiredLevel) + 1, LEVEL_ORDER.length - 1)];
    if (LEVEL_ORDER.indexOf(receipt.escalation.targetLevel) < LEVEL_ORDER.indexOf(target)) {
      fail("RECEIPT_ERROR", "escalation target is insufficient");
    }
  } else {
    if (receipt.escalation.required) fail("RECEIPT_ERROR", "non-failing receipt cannot require escalation");
    const expectedResult = mergeReady ? "PASS" : "BLOCKED";
    if (receipt.result !== expectedResult) fail("RECEIPT_ERROR", "positive receipt is inconsistent with evidence");
  }
  for (const item of ciItems) {
    if (item.status === "NOT_RUN" && !receipt.uncoveredRisks.includes(`external_gate_not_run:${item.id}`)) {
      fail("RECEIPT_ERROR", "unrun external gate is not recorded as a risk");
    }
  }
  for (const item of realItems) {
    if (item.status === "MANUAL_REQUIRED" && !receipt.uncoveredRisks.includes(`real_machine_manual_required:${item.id}`)) {
      fail("RECEIPT_ERROR", "manual real-machine gate is not recorded as a risk");
    }
    if (item.status === "NOT_RUN" && !receipt.uncoveredRisks.includes(`real_machine_not_run:${item.id}`)) {
      fail("RECEIPT_ERROR", "unrun real-machine gate is not recorded as a risk");
    }
  }
  return {
    schemaVersion: 2,
    valid: true,
    result: receipt.result,
    plannedLevel: plan.requiredLevel,
    actualLevel: receipt.actualLevel,
    mergeReady,
    releaseReady,
    executedCount: receipt.executed.length,
    externalCount: receipt.external.length,
    realMachineCount: receipt.realMachine.length,
    escalationRequired: receipt.escalation.required,
  };
}

export function validateVerificationReceipt({projectRoot, planPath, receiptPath}) {
  const root = safeProjectRoot(projectRoot);
  const plan = canonicalPlan(root, readJson(root, planPath, "PLAN_ERROR"));
  const receipt = readJson(root, receiptPath, "RECEIPT_ERROR");
  if (receipt.schemaVersion === 1) return validateLegacyReceipt(receipt, root, plan);
  if (receipt.schemaVersion === 2 && plan.schemaVersion === 3) return validateReceiptV2(receipt, root, plan);
  fail("RECEIPT_ERROR", "unsupported receipt schema");
}
