import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import {execFileSync} from "node:child_process";
import {fileURLToPath} from "node:url";

import {safeRegularFile} from "./path-safety.mjs";

const MODULE_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const SOURCE_ROOT = path.resolve(MODULE_DIRECTORY, "../..");

function sha256(content) {
  return crypto.createHash("sha256").update(content).digest("hex");
}

function managedManifest() {
  const file = path.join(SOURCE_ROOT, "manifest.json");
  if (!fs.existsSync(file)) return null;
  const metadata = fs.lstatSync(file);
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error("invalid managed runtime manifest");
  const value = JSON.parse(fs.readFileSync(file, "utf8"));
  if (value?.adapter !== "leon-engineering-project-runtime" || typeof value.frameworkVersion !== "string" ||
      !/^[0-9a-f]{40}$/.test(value.sourceCommit ?? "")) {
    throw new Error("invalid managed runtime manifest");
  }
  return value;
}

function frameworkVersion() {
  const plugin = path.join(SOURCE_ROOT, ".claude-plugin", "plugin.json");
  if (fs.existsSync(plugin)) return JSON.parse(fs.readFileSync(plugin, "utf8")).version;
  const manifest = managedManifest();
  if (!manifest) throw new Error("framework identity is unavailable");
  return manifest.frameworkVersion;
}

function frameworkCommit() {
  const manifest = managedManifest();
  if (manifest) return manifest.sourceCommit;
  try {
    return execFileSync("git", ["-C", SOURCE_ROOT, "rev-parse", "HEAD"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function frameworkSha256() {
  const hash = crypto.createHash("sha256");
  const files = fs.readdirSync(MODULE_DIRECTORY, {withFileTypes: true})
    .filter(entry => entry.isFile() && entry.name.endsWith(".mjs"))
    .map(entry => entry.name)
    .sort();
  for (const file of files) {
    hash.update(file);
    hash.update("\0");
    hash.update(fs.readFileSync(path.join(MODULE_DIRECTORY, file)));
    hash.update("\0");
  }
  return hash.digest("hex");
}

export function createPlanBinding({projectRoot, policyPath, plan, changeSet}) {
  const policyFile = safeRegularFile(projectRoot, policyPath, "POLICY_ERROR");
  return {
    source: "git",
    baseCommit: changeSet.baseCommit,
    headCommit: changeSet.headCommit,
    changeSetSha256: changeSet.digest,
    policySha256: sha256(fs.readFileSync(policyFile)),
    frameworkVersion: frameworkVersion(),
    frameworkCommit: frameworkCommit(),
    frameworkSha256: frameworkSha256(),
    planSha256: sha256(JSON.stringify(plan)),
  };
}
