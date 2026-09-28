import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const plannerPath = path.join(repositoryRoot, "scripts/plan_verification.mjs");
const validatorPath = path.join(repositoryRoot, "scripts/validate_verification_receipt.mjs");

function planFor(changedFiles) {
  const args = [plannerPath, "--project", repositoryRoot];
  for (const changedFile of changedFiles) args.push("--changed-file", changedFile);
  const result = spawnSync(process.execPath, args, {encoding: "utf8"});
  assert.equal(result.status, 0, result.stderr);
  return JSON.parse(result.stdout);
}

function validationMap(plan) {
  const result = new Map();
  for (const items of Object.values(plan.validationsByLevel)) {
    for (const item of items) result.set(item.id, item);
  }
  return result;
}

function validReceipt(plan) {
  const validations = validationMap(plan);
  const realMachine = plan.receiptTemplate.releaseGateIds.map(id => ({
    id,
    status: "MANUAL_REQUIRED",
    evidence: `logs/${id}-manual-required.log`,
  }));
  return {
    schemaVersion: 2,
    changeSummary: plan.changeSummary,
    changedFiles: plan.changedFiles,
    plannedLevel: plan.requiredLevel,
    actualLevel: plan.requiredLevel,
    components: plan.components,
    platforms: plan.platforms,
    impact: plan.impact,
    executed: plan.receiptTemplate.requiredValidationIds.map(id => ({
      id,
      level: validations.get(id).level,
      status: "PASS",
      durationSeconds: 1,
      evidence: `logs/${id}.log`,
    })),
    external: plan.receiptTemplate.externalGateIds.map(id => ({
      id,
      status: "PASS",
      evidence: `logs/${id}.log`,
    })),
    realMachine,
    result: "PASS",
    mergeReady: true,
    releaseReady: realMachine.length === 0,
    uncoveredRisks: [
      ...plan.uncoveredRisks,
      ...realMachine.map(item => `real_machine_manual_required:${item.id}`),
    ],
    escalation: {required: false, targetLevel: null, reasons: []},
  };
}

function fixture(t, {plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]), receipt} = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rwb-verification-receipt-"));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  fs.mkdirSync(path.join(root, "logs"), {recursive: true});
  const actualReceipt = receipt ?? validReceipt(plan);
  for (const item of [
    ...actualReceipt.executed,
    ...actualReceipt.external,
    ...(actualReceipt.realMachine ?? []),
  ]) {
    const evidencePath = path.join(root, item.evidence);
    fs.mkdirSync(path.dirname(evidencePath), {recursive: true});
    if (!fs.existsSync(evidencePath)) fs.writeFileSync(evidencePath, `${item.id}\n`);
  }
  fs.writeFileSync(path.join(root, "plan.json"), `${JSON.stringify(plan, null, 2)}\n`);
  fs.writeFileSync(path.join(root, "receipt.json"), `${JSON.stringify(actualReceipt, null, 2)}\n`);
  return {root, plan, receipt: actualReceipt};
}

function run(root, plan = "plan.json", receipt = "receipt.json") {
  return spawnSync(process.execPath, [
    validatorPath,
    "--project",
    root,
    "--plan",
    plan,
    "--receipt",
    receipt,
  ], {encoding: "utf8"});
}

function success(result) {
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
  return JSON.parse(result.stdout);
}

function failure(result, code) {
  assert.notEqual(result.status, 0, result.stdout);
  if (result.stderr.includes("MODULE_NOT_FOUND")) assert.fail("receipt validator is missing");
  const payload = JSON.parse(result.stderr);
  assert.equal(payload.error.code, code);
  assert.equal(result.stdout, "");
  return payload;
}

test("valid receipt proves every required validation and external gate", t => {
  const {root, plan} = fixture(t);
  const verdict = success(run(root));
  assert.deepEqual(verdict, {
    schemaVersion: 2,
    valid: true,
    result: "PASS",
    plannedLevel: plan.requiredLevel,
    actualLevel: plan.requiredLevel,
    executedCount: plan.receiptTemplate.requiredValidationIds.length,
    externalCount: plan.receiptTemplate.externalGateIds.length,
    realMachineCount: plan.receiptTemplate.releaseGateIds.length,
    escalationRequired: false,
    mergeReady: true,
    releaseReady: true,
  });
});

test("case G keeps required Windows CI NOT_RUN and blocks merge readiness", t => {
  const plan = planFor(["setup-web.cmd"]);
  const receipt = validReceipt(plan);
  const windows = receipt.external.find(item => item.id === "research-web-windows-verify");
  assert.ok(windows);
  windows.status = "NOT_RUN";
  windows.evidence = "logs/research-web-windows-verify-not-run.log";
  receipt.result = "BLOCKED";
  receipt.mergeReady = false;
  receipt.releaseReady = false;
  receipt.uncoveredRisks.push("external_gate_not_run:research-web-windows-verify");

  const {root} = fixture(t, {plan, receipt});
  const verdict = success(run(root));
  assert.equal(verdict.result, "BLOCKED");
  assert.equal(verdict.mergeReady, false);
  assert.equal(verdict.releaseReady, false);
});

test("case H separates passed Windows CI from manual real-machine release evidence", t => {
  const plan = planFor(["src-tauri/tauri.conf.json"]);
  const receipt = validReceipt(plan);
  assert.equal(receipt.external.find(item => item.id === "native-windows-desktop")?.status, "PASS");
  assert.deepEqual(receipt.realMachine, [{
    id: "windows-desktop-installation",
    status: "MANUAL_REQUIRED",
    evidence: "logs/windows-desktop-installation-manual-required.log",
  }]);

  const {root} = fixture(t, {plan, receipt});
  const verdict = success(run(root));
  assert.equal(verdict.result, "PASS");
  assert.equal(verdict.mergeReady, true);
  assert.equal(verdict.releaseReady, false);
});

test("receipt v2 rejects noncanonical and false-positive status projections", t => {
  const plan = planFor(["setup-web.cmd"]);

  const notRequired = validReceipt(plan);
  notRequired.external[0].status = "NOT_REQUIRED";
  failure(run(fixture(t, {plan, receipt: notRequired}).root), "RECEIPT_ERROR");

  const lowercase = validReceipt(plan);
  lowercase.executed[0].status = "passed";
  failure(run(fixture(t, {plan, receipt: lowercase}).root), "RECEIPT_ERROR");

  const falseReady = validReceipt(plan);
  falseReady.external.find(item => item.id === "research-web-windows-verify").status = "NOT_RUN";
  falseReady.result = "BLOCKED";
  falseReady.releaseReady = false;
  falseReady.uncoveredRisks.push("external_gate_not_run:research-web-windows-verify");
  failure(run(fixture(t, {plan, receipt: falseReady}).root), "RECEIPT_ERROR");

  const missingLane = validReceipt(plan);
  missingLane.external.pop();
  failure(run(fixture(t, {plan, receipt: missingLane}).root), "RECEIPT_ERROR");
});

test("real-machine PASS requires regular evidence", t => {
  const plan = planFor(["src-tauri/tauri.conf.json"]);
  const receipt = validReceipt(plan);
  receipt.realMachine[0].status = "PASS";
  receipt.realMachine[0].evidence = "logs/windows-real-machine-pass.log";
  receipt.uncoveredRisks = receipt.uncoveredRisks.filter(
    risk => risk !== "real_machine_manual_required:windows-desktop-installation",
  );
  receipt.releaseReady = true;
  const {root} = fixture(t, {plan, receipt});
  fs.rmSync(path.join(root, receipt.realMachine[0].evidence));
  failure(run(root), "RECEIPT_ERROR");
});

test("legacy plan v2 and receipt v1 remain valid without rewriting", t => {
  const plan = JSON.parse(fs.readFileSync(
    path.join(repositoryRoot, ".ai/reports/incremental-validation-v2-small-plan.json"),
    "utf8",
  ));
  const receipt = JSON.parse(fs.readFileSync(
    path.join(repositoryRoot, ".ai/reports/incremental-validation-v2-small-receipt.json"),
    "utf8",
  ));
  const {root} = fixture(t, {plan, receipt});
  const verdict = success(run(root));
  assert.deepEqual(verdict, {
    schemaVersion: 1,
    valid: true,
    result: "passed",
    plannedLevel: "L1",
    actualLevel: "L1",
    executedCount: 4,
    escalationRequired: false,
  });
});

test("missing required validation is rejected", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed.pop();
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("tampered plan cannot remove a required validation from its receipt template", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  plan.receiptTemplate.requiredValidationIds.pop();
  const {root} = fixture(t, {plan, receipt: validReceipt(plan)});
  failure(run(root), "PLAN_ERROR");
});

test("changed-file and impact mismatches are rejected", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const changedReceipt = validReceipt(plan);
  changedReceipt.changedFiles = ["docs/README.md"];
  const changed = fixture(t, {plan, receipt: changedReceipt});
  failure(run(changed.root), "RECEIPT_ERROR");

  const impactReceipt = validReceipt(plan);
  impactReceipt.impact = [];
  const impact = fixture(t, {plan, receipt: impactReceipt});
  failure(run(impact.root), "RECEIPT_ERROR");
});

test("unknown validation id and level mismatch are rejected", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const unknownReceipt = validReceipt(plan);
  unknownReceipt.executed.push({
    id: "unplanned-suite",
    level: "L4",
    status: "PASS",
    durationSeconds: 1,
    evidence: "logs/unplanned-suite.log",
  });
  const unknown = fixture(t, {plan, receipt: unknownReceipt});
  failure(run(unknown.root), "RECEIPT_ERROR");

  const levelReceipt = validReceipt(plan);
  levelReceipt.executed[0].level = "L4";
  const level = fixture(t, {plan, receipt: levelReceipt});
  failure(run(level.root), "RECEIPT_ERROR");
});

test("actual level below planned level is rejected", t => {
  const plan = planFor([".agents/verification-policy.json"]);
  const receipt = validReceipt(plan);
  receipt.actualLevel = "L3";
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("actual level above planned level requires a newly planned receipt", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.actualLevel = "L4";
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("failed validation cannot be reported as passed", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed[0].status = "FAIL";
  receipt.escalation = {required: true, targetLevel: "L2", reasons: ["validation_failure"]};
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("blocked validation cannot be reported as passed", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed[0].status = "BLOCKED";
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("failed validation requires next-level escalation", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed[0].status = "FAIL";
  receipt.result = "FAIL";
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("insufficient escalation target is rejected", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed[0].status = "FAIL";
  receipt.result = "FAIL";
  receipt.escalation = {required: true, targetLevel: "L1", reasons: ["validation_failure"]};
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("full-delivery external gate that was not run forces blocked result", t => {
  const plan = planFor([".agents/verification-policy.json"]);
  const receipt = validReceipt(plan);
  receipt.external[0].status = "NOT_RUN";
  receipt.external[0].evidence = "logs/project-constraints-not-run.log";
  receipt.result = "BLOCKED";
  receipt.mergeReady = false;
  receipt.releaseReady = false;
  receipt.uncoveredRisks.push(`external_gate_not_run:${receipt.external[0].id}`);
  const {root} = fixture(t, {plan, receipt});
  const verdict = success(run(root));
  assert.equal(verdict.result, "BLOCKED");
});

test("symlinked plan and receipt inputs fail explicitly", t => {
  const first = fixture(t);
  fs.renameSync(path.join(first.root, "plan.json"), path.join(first.root, "real-plan.json"));
  fs.symlinkSync("real-plan.json", path.join(first.root, "plan.json"));
  failure(run(first.root), "PATH_ERROR");

  const second = fixture(t);
  fs.renameSync(path.join(second.root, "receipt.json"), path.join(second.root, "real-receipt.json"));
  fs.symlinkSync("real-receipt.json", path.join(second.root, "receipt.json"));
  failure(run(second.root), "PATH_ERROR");
});

test("schema drift and unsafe input paths fail explicitly", t => {
  const {root, receipt} = fixture(t);
  receipt.extra = true;
  fs.writeFileSync(path.join(root, "receipt.json"), `${JSON.stringify(receipt)}\n`);
  failure(run(root), "RECEIPT_ERROR");
  failure(run(root, "../plan.json"), "PATH_ERROR");
});

test("evidence references must be regular files", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const receipt = validReceipt(plan);
  receipt.executed[0].evidence = "logs";
  const {root} = fixture(t, {plan, receipt});
  failure(run(root), "RECEIPT_ERROR");
});

test("commands stored in a plan are never executed", t => {
  const plan = planFor(["app/research_web/ui/frameworks/goldar.mjs"]);
  const marker = path.join(os.tmpdir(), `rwb-receipt-marker-${process.pid}-${Date.now()}`);
  t.after(() => fs.rmSync(marker, {force: true}));
  const command = `node -e "require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'executed')"`;
  plan.tests[0].value = command;
  plan.validationsByLevel[plan.tests[0].level].find(item => item.id === plan.tests[0].id).value = command;
  const {root} = fixture(t, {plan, receipt: validReceipt(plan)});
  success(run(root));
  assert.equal(fs.existsSync(marker), false);
});
