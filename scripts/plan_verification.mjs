#!/usr/bin/env node

import fs from "node:fs";
import {fileURLToPath} from "node:url";

import {
  VerificationError,
  planVerification,
} from "../.agents/runtime/leon-engineering/lib/verification/index.mjs";

export {planVerification};

function fail(code, message) {
  throw new VerificationError(code, message);
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
      if (options.projectRoot !== undefined) fail("ARGUMENT_ERROR", "--project may only be provided once");
      options.projectRoot = value;
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
  if (options.changedFiles.length === 0) fail("ARGUMENT_ERROR", "at least one --changed-file is required");
  return options;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {
    process.stdout.write(`${JSON.stringify(planVerification(parseArgs(process.argv.slice(2))), null, 2)}\n`);
  } catch (error) {
    const code = error instanceof VerificationError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof VerificationError ? error.message : "unexpected planner failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 3, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
