#!/usr/bin/env node
/** Read-only task/delivery projection. Metadata records facts; it cannot grant acceptance. */
import fs from "node:fs";
import {fileURLToPath} from "node:url";
import {
  VerificationError,
  safeProjectRoot,
  safeRegularFile,
  validateVerificationReceipt,
} from "../.agents/runtime/leon-engineering/lib/verification/index.mjs";

const SHA = /^[a-f0-9]{40}$/;
const HASH = /^[a-f0-9]{64}$/;
const DELIVERY_KEYS = new Set(["candidateCommit", "branch", "pr", "mergeCommit", "runtimeUpdated", "sourceRevision", "reportCommit", "diagramIdentities"]);
function fail(code, message) {throw new VerificationError(code, message);}

function readInput(root, relative) {
  const file = safeRegularFile(root, relative, "PATH_ERROR");
  try {return JSON.parse(fs.readFileSync(file, "utf8"));}
  catch {fail("INPUT_ERROR", "summary input must contain valid JSON");}
}

function deliveryMetadata(value, candidateCommit) {
  if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).some(key => !DELIVERY_KEYS.has(key))) {
    fail("DELIVERY_ERROR", "unsupported delivery metadata fields");
  }
  if (value.candidateCommit !== candidateCommit || !SHA.test(value.candidateCommit)) fail("DELIVERY_ERROR", "delivery candidate does not match plan");
  if (typeof value.branch !== "string" || !value.branch || !/^[A-Za-z0-9_./-]+$/.test(value.branch) || typeof value.runtimeUpdated !== "boolean") {
    fail("DELIVERY_ERROR", "delivery branch and runtimeUpdated must be explicit");
  }
  for (const key of ["mergeCommit", "sourceRevision", "reportCommit"]) {
    if (value[key] !== undefined && value[key] !== null && !SHA.test(value[key])) fail("DELIVERY_ERROR", "invalid recorded revision");
  }
  if (value.pr !== undefined && value.pr !== null) {
    if (typeof value.pr !== "string" || !/^https:\/\/github\.com\/Leon-Huang001208\/ResearchWorkbench\/pull\/[1-9][0-9]*$/.test(value.pr)) fail("DELIVERY_ERROR", "invalid recorded pull request");
  }
  const diagrams = value.diagramIdentities ?? [];
  if (!Array.isArray(diagrams) || new Set(diagrams.map(diagram => diagram?.id)).size !== diagrams.length) fail("DELIVERY_ERROR", "invalid recorded diagram identities");
  for (const diagram of diagrams) {
    if (!diagram || typeof diagram !== "object" || Array.isArray(diagram) || Object.keys(diagram).length !== 3 || Object.keys(diagram).some(key => !["id", "specificationSha256", "artifactSha256"].includes(key)) || !/^[a-z0-9-]+$/.test(diagram.id) || !HASH.test(diagram.specificationSha256) || !HASH.test(diagram.artifactSha256)) {
      fail("DELIVERY_ERROR", "invalid recorded diagram identity");
    }
  }
  return {candidateCommit: value.candidateCommit, branch: value.branch, pr: value.pr ?? null, mergeCommit: value.mergeCommit ?? null, runtimeUpdated: value.runtimeUpdated, sourceRevision: value.sourceRevision ?? null, reportCommit: value.reportCommit ?? null, diagramIdentities: diagrams};
}

export function summarizeVerificationDelivery({projectRoot, planPath, receiptPath, deliveryPath}) {
  const root = safeProjectRoot(projectRoot);
  const plan = readInput(root, planPath), receipt = readInput(root, receiptPath), delivery = readInput(root, deliveryPath);
  if (plan?.schemaVersion !== 4 || receipt?.schemaVersion !== 3) fail("PROTOCOL_ERROR", "delivery summary requires plan v4 and receipt v3");
  const validated = validateVerificationReceipt({projectRoot: root, planPath, receiptPath});
  const recorded = deliveryMetadata(delivery, plan.task.candidateCommit);
  return {
    schemaVersion: 1,
    objective: plan.task.objective,
    acceptanceScope: plan.task.acceptanceScope,
    hostPlatform: plan.task.hostPlatform,
    taskKind: plan.task.taskKind,
    candidateCommit: plan.task.candidateCommit,
    candidateBaseCommit: plan.task.candidateBaseCommit,
    changedFiles: plan.changedFiles,
    result: validated.result,
    hostAcceptance: validated.hostAcceptance,
    platformHandoffs: validated.platformHandoffs,
    aggregateAcceptance: validated.aggregateAcceptance,
    mergeReady: validated.mergeReady,
    releaseReady: validated.releaseReady,
    branch: recorded.branch,
    pr: recorded.pr,
    mergeCommit: recorded.mergeCommit,
    runtimeUpdated: recorded.runtimeUpdated,
    sourceRevision: recorded.sourceRevision,
    reportCommit: recorded.reportCommit,
    diagramIdentities: recorded.diagramIdentities,
    ciCheckouts: receipt.external,
    deliveryMetadataVerified: false,
  };
}

function parseArgs(args) {
  const names = new Map([["--project", "projectRoot"], ["--plan", "planPath"], ["--receipt", "receiptPath"], ["--delivery", "deliveryPath"]]);
  const options = {};
  for (let index = 0; index < args.length; index += 2) {
    const key = names.get(args[index]), value = args[index + 1];
    if (!key || !value || value.startsWith("--") || options[key] !== undefined) fail("ARGUMENT_ERROR", "summary requires each named input once");
    options[key] = value;
  }
  if (Object.keys(options).length !== names.size) fail("ARGUMENT_ERROR", "summary requires project, plan, receipt and delivery inputs");
  return options;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {process.stdout.write(`${JSON.stringify(summarizeVerificationDelivery(parseArgs(process.argv.slice(2))), null, 2)}\n`);}
  catch (error) {
    const code = error instanceof VerificationError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof VerificationError ? error.message : "unexpected delivery summary failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 1, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
