import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {checkResearchArchitecture, MAP_PATH, writeCheckLog} from "../scripts/check_research_architecture.mjs";

const CONFIGURATION_PATH = ".agents/project-constraints.json";
const TOP_LEVEL_KEYS = new Set(["schemaVersion", "requiredFiles", "changeRules", "contentRules", "dependencyRules", "ciRules", "researchArchitectureMap", "readmeReview"]);
const README_REVIEW_CONFIGURATION_KEYS = new Set(["receipt", "readme", "sourcePrefixes", "sourceFiles"]);
const README_REVIEW_RECEIPT_KEYS = new Set(["schemaVersion", "disposition", "summary", "reason"]);

function isWithin(root, candidate) {
  return candidate === root || candidate.startsWith(`${root}${path.sep}`);
}

function normalizeRelative(value, field) {
  if (typeof value !== "string" || value.length === 0 || path.isAbsolute(value)) throw new Error(`invalid ${field}`);
  const normalized = path.normalize(value).split(path.sep).join("/");
  if (normalized === "." || normalized === ".." || normalized.startsWith("../")) throw new Error(`unsafe ${field}`);
  return normalized;
}

function rootDirectory(projectRoot) {
  const root = fs.realpathSync(projectRoot);
  if (!fs.statSync(root).isDirectory()) throw new Error("project root is not a directory");
  return root;
}

function safeTarget(root, relative, {missing = "error", label = "constraints target"} = {}) {
  const normalized = normalizeRelative(relative, label);
  const destination = path.resolve(root, normalized);
  if (!isWithin(root, destination)) throw new Error(`unsafe ${label}`);
  let current = root;
  for (const part of normalized.split("/")) {
    current = path.join(current, part);
    if (!fs.existsSync(current)) return missing === "null" ? null : (() => { throw new Error(`missing ${label}`); })();
    if (fs.lstatSync(current).isSymbolicLink()) throw new Error(`invalid ${label}`);
  }
  return destination;
}

function assertStringArray(value, field) {
  if (!Array.isArray(value)) throw new Error(`invalid ${field}`);
  return value.map(item => normalizeRelative(item, field));
}

function assertTextArray(value, field) {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string" || item.length === 0)) {
    throw new Error(`invalid ${field}`);
  }
  return value;
}

function assertRule(rule, field, validator) {
  if (!rule || typeof rule !== "object" || Array.isArray(rule)) throw new Error(`invalid ${field}`);
  if (typeof rule.name !== "string" || rule.name.trim().length === 0) throw new Error(`invalid ${field} name`);
  return validator(rule);
}

function assertExactKeys(value, expected, field) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`invalid ${field}`);
  const keys = Object.keys(value);
  if (keys.length !== expected.size || keys.some(key => !expected.has(key))) throw new Error(`invalid ${field}`);
}

function loadConfiguration(root) {
  const file = safeTarget(root, CONFIGURATION_PATH, {label: "constraints file"});
  let configuration;
  try {
    configuration = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    throw new Error("invalid constraints configuration");
  }
  if (!configuration || typeof configuration !== "object" || Array.isArray(configuration)) {
    throw new Error("invalid constraints configuration");
  }
  for (const key of Object.keys(configuration)) if (!TOP_LEVEL_KEYS.has(key)) throw new Error("unknown constraints configuration key");
  if (configuration.schemaVersion !== 1) throw new Error("invalid constraints schema version");
  const requiredFiles = assertStringArray(configuration.requiredFiles ?? [], "required files");
  const changeRules = (configuration.changeRules ?? []).map(rule => assertRule(rule, "change rule", item => ({
    name: item.name.trim(),
    sourcePrefixes: assertStringArray(item.sourcePrefixes, "change rule source prefixes"),
    requiredDocuments: assertStringArray(item.requiredDocuments, "change rule required documents")
  })));
  const contentRules = (configuration.contentRules ?? []).map(rule => assertRule(rule, "content rule", item => ({
    name: item.name.trim(),
    sourcePrefixes: assertStringArray(item.sourcePrefixes, "content rule source prefixes"),
    extensions: assertTextArray(item.extensions, "content rule extensions"),
    requireAll: assertTextArray(item.requireAll, "content rule required content")
  })));
  const dependencyRules = (configuration.dependencyRules ?? []).map(rule => assertRule(rule, "dependency rule", item => ({
    name: item.name.trim(),
    sourcePrefixes: assertStringArray(item.sourcePrefixes, "dependency rule source prefixes"),
    extensions: assertTextArray(item.extensions, "dependency rule extensions"),
    forbiddenPatterns: assertTextArray(item.forbiddenPatterns, "dependency rule forbidden patterns")
  })));
  const ciRules = (configuration.ciRules ?? []).map(rule => assertRule(rule, "CI rule", item => ({
    name: item.name.trim(),
    workflow: normalizeRelative(item.workflow, "CI workflow"),
    requireAll: assertTextArray(item.requireAll, "CI rule required content")
  })));
  let readmeReview;
  if (configuration.readmeReview !== undefined) {
    assertExactKeys(configuration.readmeReview, README_REVIEW_CONFIGURATION_KEYS, "README review configuration");
    readmeReview = {
      receipt: normalizeRelative(configuration.readmeReview.receipt, "README review receipt"),
      readme: normalizeRelative(configuration.readmeReview.readme, "README path"),
      sourcePrefixes: assertStringArray(configuration.readmeReview.sourcePrefixes, "README review source prefixes"),
      sourceFiles: assertStringArray(configuration.readmeReview.sourceFiles, "README review source files")
    };
    if (readmeReview.sourcePrefixes.some(prefix => !prefix.endsWith("/"))) throw new Error("invalid README review source prefixes");
  }
  const researchArchitectureMap = configuration.researchArchitectureMap;
  if (researchArchitectureMap !== undefined && researchArchitectureMap !== MAP_PATH) throw new Error("invalid research architecture map");
  return {requiredFiles, changeRules, contentRules, dependencyRules, ciRules, researchArchitectureMap, readmeReview};
}

function violation(code, rule, pathValue, message) {
  return {code, rule, path: pathValue, message};
}

function matchesPrefix(file, prefixes) {
  return prefixes.some(prefix => file === prefix.slice(0, -1) || file.startsWith(prefix));
}

function readReadmeReview(root, rule, violations) {
  try {
    const file = safeTarget(root, rule.receipt, {label: "README review receipt"});
    if (!fs.statSync(file).isFile()) throw new Error("receipt is not a regular file");
    const receipt = JSON.parse(fs.readFileSync(file, "utf8"));
    assertExactKeys(receipt, README_REVIEW_RECEIPT_KEYS, "README review receipt");
    if (receipt.schemaVersion !== 1 || !["updated", "unchanged"].includes(receipt.disposition)) throw new Error("invalid README review receipt");
    if (typeof receipt.summary !== "string" || receipt.summary.trim().length === 0) throw new Error("invalid README review summary");
    if (typeof receipt.reason !== "string" || receipt.reason.trim().length === 0) throw new Error("invalid README review reason");
    return receipt;
  } catch {
    violations.push(violation("readme_review_invalid", "README 复核回执", rule.receipt, "README 复核回执必须是仓库内普通 JSON 文件，并严格满足四字段 schema"));
    return null;
  }
}

export function checkProjectConstraints({projectRoot, changedFiles = []}) {
  const root = rootDirectory(projectRoot);
  if (!Array.isArray(changedFiles)) throw new Error("invalid changed files");
  const checkedFiles = [...new Set(changedFiles.map(file => normalizeRelative(file, "changed file")))];
  const configuration = loadConfiguration(root);
  const violations = [];

  for (const file of configuration.requiredFiles) {
    try {
      if (!safeTarget(root, file, {missing: "null", label: "required file"})) {
        violations.push(violation("required_file_missing", "必需项目文件", file, `缺少必需文件：${file}`));
      }
    } catch {
      violations.push(violation("required_file_invalid", "必需项目文件", file, `必需文件不是安全的仓库内路径：${file}`));
    }
  }
  if (configuration.readmeReview) {
    const rule = configuration.readmeReview;
    const receipt = readReadmeReview(root, rule, violations);
    const reviewRequired = checkedFiles.some(file => matchesPrefix(file, rule.sourcePrefixes) || rule.sourceFiles.includes(file));
    const reviewChanged = checkedFiles.includes(rule.receipt);
    if (reviewRequired && !reviewChanged) {
      violations.push(violation("readme_review_not_changed", "README 复核回执", rule.receipt, `改动 ${rule.sourcePrefixes.concat(rule.sourceFiles).join("、")} 时必须同步更新 README 复核回执`));
    }
    if (receipt && reviewChanged && receipt.disposition === "updated" && !checkedFiles.includes(rule.readme)) {
      violations.push(violation("readme_not_changed", "README 复核回执", rule.readme, `README 复核结论为 updated 时必须同步更新：${rule.readme}`));
    }
  }
  for (const rule of configuration.changeRules) {
    if (checkedFiles.some(file => matchesPrefix(file, rule.sourcePrefixes)) && !checkedFiles.some(file => rule.requiredDocuments.includes(file))) {
      violations.push(violation("required_document_changed", rule.name, rule.requiredDocuments.join(","), `改动 ${rule.sourcePrefixes.join("、")} 时必须同时更新：${rule.requiredDocuments.join("、")}`));
    }
  }
  for (const rule of configuration.contentRules) {
    for (const file of checkedFiles) {
      if (!matchesPrefix(file, rule.sourcePrefixes) || !rule.extensions.some(extension => file.endsWith(extension))) continue;
      const target = safeTarget(root, file, {missing: "null", label: "changed file"});
      if (!target) continue;
      const content = fs.readFileSync(target, "utf8");
      const missing = rule.requireAll.filter(text => !content.includes(text));
      if (missing.length > 0) {
        violations.push(violation("required_content_missing", rule.name, file, `文件缺少约束内容：${missing.join("、")}`));
      }
    }
  }
  for (const rule of configuration.dependencyRules) {
    for (const file of checkedFiles) {
      if (!matchesPrefix(file, rule.sourcePrefixes) || !rule.extensions.some(extension => file.endsWith(extension))) continue;
      const target = safeTarget(root, file, {missing: "null", label: "changed file"});
      if (!target) continue;
      const content = fs.readFileSync(target, "utf8");
      const forbidden = rule.forbiddenPatterns.filter(text => content.includes(text));
      if (forbidden.length > 0) {
        violations.push(violation("forbidden_dependency", rule.name, file, `文件包含禁止依赖：${forbidden.join("、")}`));
      }
    }
  }
  for (const rule of configuration.ciRules) {
    const workflow = safeTarget(root, rule.workflow, {missing: "null", label: "CI workflow"});
    if (!workflow) {
      violations.push(violation("ci_workflow_missing", rule.name, rule.workflow, `缺少 CI 工作流：${rule.workflow}`));
      continue;
    }
    const content = fs.readFileSync(workflow, "utf8");
    const missing = rule.requireAll.filter(text => !content.includes(text));
    if (missing.length > 0) {
      violations.push(violation("ci_content_missing", rule.name, rule.workflow, `CI 工作流缺少约束文本：${missing.join("、")}`));
    }
  }
  if (configuration.researchArchitectureMap) {
    const architecture = checkResearchArchitecture({projectRoot: root, changedFiles: checkedFiles});
    violations.push(...architecture.violations);
    writeCheckLog(root, architecture);
  }
  return {schemaVersion: 1, projectRoot: root, checkedFiles, violations};
}

function parseArgs(args) {
  const options = {changedFiles: []};
  for (let index = 0; index < args.length; index += 1) {
    const argument = args[index];
    if (argument === "--project" || argument === "--changed-file") {
      const value = args[index + 1];
      if (!value || value.startsWith("--")) throw new Error(`${argument} requires a value`);
      if (argument === "--project") options.project = value;
      else options.changedFiles.push(value);
      index += 1;
    } else {
      throw new Error(`unknown option: ${argument}`);
    }
  }
  if (!options.project) throw new Error("--project requires a value");
  return options;
}

function main(args) {
  const options = parseArgs(args);
  const result = checkProjectConstraints({projectRoot: options.project, changedFiles: options.changedFiles});
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  if (result.violations.length > 0) process.exitCode = 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    process.stderr.write(`project constraints failed: ${error.message}\n`);
    process.exitCode = 1;
  }
}
