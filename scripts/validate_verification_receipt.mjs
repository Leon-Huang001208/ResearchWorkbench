#!/usr/bin/env node

import fs from "node:fs";
import {fileURLToPath} from "node:url";

import {
  VerificationError,
  validateVerificationReceipt,
} from "../.agents/runtime/leon-engineering/lib/verification/index.mjs";

export {validateVerificationReceipt};

function fail(code, message) {
  throw new VerificationError(code, message);
}

function parseArgs(args) {
  const options = {};
  const names = new Map([
    ["--project", "projectRoot"],
    ["--plan", "planPath"],
    ["--receipt", "receiptPath"],
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
  for (const [option, name] of names) if (!options[name]) fail("ARGUMENT_ERROR", `${option} is required`);
  return options;
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url))) {
  try {
    process.stdout.write(`${JSON.stringify(validateVerificationReceipt(parseArgs(process.argv.slice(2))), null, 2)}\n`);
  } catch (error) {
    const code = error instanceof VerificationError ? error.code : "INTERNAL_ERROR";
    const message = error instanceof VerificationError ? error.message : "unexpected receipt validation failure";
    process.stderr.write(`${JSON.stringify({schemaVersion: 2, error: {code, message}})}\n`);
    process.exitCode = 1;
  }
}
