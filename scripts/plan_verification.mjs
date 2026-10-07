#!/usr/bin/env node

import fs from "node:fs";
import {fileURLToPath} from "node:url";

import {
  VerificationError,
  planGitVerification,
  planVerification as sharedPlanVerification,
  safeProjectRoot,
  safeRegularFile,
} from "../.agents/runtime/leon-engineering/lib/verification/index.mjs";

export function planVerification(options) {
  if (options.task !== undefined) validateProjectTaskContext(options.task);
  return sharedPlanVerification(options);
}

function fail(code, message) {
  throw new VerificationError(code, message);
}

export function validateProjectTaskContext(task, actualHost = {darwin: "macos", linux: "linux", win32: "windows"}[process.platform]) {
  if (!task || typeof task !== "object" || Array.isArray(task)) fail("ARGUMENT_ERROR", "task context must be an object");
  if (!["macos", "linux", "windows"].includes(actualHost) || task.hostPlatform !== actualHost) {
    fail("ARGUMENT_ERROR", "task platform must match the actual host");
  }
  if (task.taskKind === "feature-development" && actualHost !== "macos") {
    fail("ARGUMENT_ERROR", "RWB feature development requires macos");
  }
  if (!["feature-development", "platform-adaptation"].includes(task.taskKind)) fail("ARGUMENT_ERROR", "unsupported task kind");
  return task;
}

function parseArgs(args) {
  const options = {changedFiles: [], signals: []};
  const signalSet = new Set();
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (!["--project", "--changed-file", "--signal", "--base", "--task-context"].includes(argument)) {
      fail("ARGUMENT_ERROR", "unknown option");
    }
    const value = args[index + 1];
    if (!value || value.startsWith("--")) fail("ARGUMENT_ERROR", `${argument} requires a value`);
    if (["--project", "--base", "--task-context"].includes(argument)) {
      const key = {"--project": "projectRoot", "--base": "base", "--task-context": "taskContext"}[argument];
      if (options[key] !== undefined) fail("ARGUMENT_ERROR", `${argument} may only be provided once`);
      options[key] = value;
    } else if (argument === "--changed-file") {
      options.changedFiles.push(value);
    } else {
      if (!new Set(["validation_failure", "unexpected_behavior"]).has(value)) {
        fail("ARGUMENT_ERROR", "unsupported escalation signal");
      }
      if (!signalSet.has(value)) {
        signalSet.add(value);
        options.signals.push(value);
      }
    }
    index += 1;
  }
  if (!options.projectRoot) fail("ARGUMENT_ERROR", "--project is required");
  if (options.taskContext && !options.base) fail("ARGUMENT_ERROR", "--task-context requires --base");
  if (!options.base && options.changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one --changed-file is required");
  return options;
}

function planFromArgs(args) {
  const {taskContext, ...options} = parseArgs(args);
  if (!options.base) return planVerification(options);
  if (options.changedFiles.length === 0) delete options.changedFiles;
  if (taskContext) {
    const root = safeProjectRoot(options.projectRoot);
    const file = safeRegularFile(root, taskContext, "PATH_ERROR");
    let task;
    try {task = JSON.parse(fs.readFileSync(file, "utf8"));}
    catch {fail("ARGUMENT_ERROR", "task context must contain valid JSON");}
    options.task = validateProjectTaskContext(task);
  }
  const plan = planGitVerification(options);
  if (options.task && plan.schemaVersion !== 4) fail("RUNTIME_ERROR", "platform task requires managed runtime plan v4");
  return plan;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {
    process.stdout.write(`${JSON.stringify(planFromArgs(process.argv.slice(2)), null, 2)}\n`);
  } catch (error) {
    const code = error instanceof VerificationError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof VerificationError ? error.message : "unexpected planner failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 3, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
