import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const plannerPath = path.join(repositoryRoot, "scripts/plan_verification.mjs");

function policy() {
  return {
    schemaVersion: 1,
    riskOrder: ["docs-only", "local-only", "full-delivery"],
    catalogs: {
      tests: {
        "research-web-architecture": "node --test tests/javascript/research_web_architecture.test.mjs",
      },
      documentation: {
        "documentation-governance": "node scripts/check_documentation_governance.mjs --project .",
        "python-file-index": "python scripts/generate_py_file_index.py --check",
        "desktop-packaging": "docs/desktop_packaging.md",
      },
      ci: {
        "project-constraints": ".github/workflows/project-constraints.yml",
        "research-web-checks": ".github/workflows/research-web-checks.yml",
        "native-windows-desktop": ".github/workflows/desktop-verify.yml#windows-2022",
      },
    },
    rules: [
      {
        id: "desktop",
        risk: "full-delivery",
        reason: "desktop_change",
        match: {
          files: [],
          prefixes: ["src-tauri/", "desktop/", "scripts/desktop/", "services/desktop_platform/"],
          segments: [],
          suffixes: [],
        },
        tests: [],
        documentation: ["desktop-packaging"],
        ci: ["project-constraints", "native-windows-desktop"],
      },
      {
        id: "contract",
        risk: "full-delivery",
        reason: "public_contract_change",
        match: {files: [], prefixes: ["contracts/"], segments: ["contracts"], suffixes: []},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "schema",
        risk: "full-delivery",
        reason: "schema_change",
        match: {files: [], prefixes: ["schemas/"], segments: ["schemas", "migrations"], suffixes: [".schema.json"]},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "dependency",
        risk: "full-delivery",
        reason: "dependency_change",
        match: {files: ["package.json", "pyproject.toml"], prefixes: ["requirements/"], segments: [], suffixes: [".lock"]},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "ci",
        risk: "full-delivery",
        reason: "ci_change",
        match: {files: [".agents/verification-policy.json"], prefixes: [".github/workflows/"], segments: [], suffixes: []},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "security",
        risk: "full-delivery",
        reason: "security_change",
        match: {files: ["SECURITY.md"], prefixes: ["security/"], segments: ["security"], suffixes: []},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "release",
        risk: "full-delivery",
        reason: "release_change",
        match: {files: [], prefixes: ["release/", "scripts/release/"], segments: ["release"], suffixes: []},
        tests: [],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      },
      {
        id: "documentation",
        risk: "docs-only",
        reason: "documentation_only",
        match: {files: ["README.md"], prefixes: ["docs/", ".ai/reports/", ".claude/commands/"], segments: [], suffixes: [".md"]},
        tests: [],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints"],
      },
      {
        id: "research-web",
        risk: "local-only",
        reason: "research_web_change",
        match: {files: [], prefixes: ["app/research_web/", "app/web/"], segments: [], suffixes: []},
        tests: ["research-web-architecture"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      },
    ],
    fallback: {
      risk: "full-delivery",
      reason: "unknown_path",
      tests: [],
      documentation: ["documentation-governance"],
      ci: ["project-constraints"],
    },
  };
}

function fixture(t, value = policy()) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rwb-verification-policy-"));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  fs.mkdirSync(path.join(root, ".agents"), {recursive: true});
  fs.writeFileSync(path.join(root, ".agents/verification-policy.json"), `${JSON.stringify(value, null, 2)}\n`);
  return root;
}

function run(project, changedFiles) {
  const args = [plannerPath, "--project", project];
  for (const changedFile of changedFiles) args.push("--changed-file", changedFile);
  return spawnSync(process.execPath, args, {encoding: "utf8"});
}

function success(result) {
  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stderr, "");
  return JSON.parse(result.stdout);
}

function failure(result, code) {
  assert.notEqual(result.status, 0, result.stdout);
  const payload = JSON.parse(result.stderr);
  assert.equal(payload.error.code, code);
  assert.equal(result.stdout, "");
  return payload;
}

function gateIds(plan) {
  return [...plan.tests, ...plan.documentation, ...plan.ci].map(item => item.id);
}

test("pure Research Web UI and Python changes never add desktop gates", () => {
  const plan = success(run(repositoryRoot, ["app/research_web/ui/app.mjs", "app/research_web/service.py"]));
  assert.equal(plan.risk, "local-only");
  const ids = gateIds(plan).join(" ").toLowerCase();
  for (const forbidden of ["desktop", "windows", "tauri", "sidecar", "installer"]) {
    assert.equal(ids.includes(forbidden), false, `${forbidden} leaked into Web-only plan`);
  }
  assert.deepEqual(plan.tests.map(item => item.id), ["research-web-architecture"]);
});

test("documentation changes only select documentation-related checks", () => {
  const plan = success(run(repositoryRoot, ["docs/AGENT_WORKFLOW.md"]));
  assert.equal(plan.risk, "docs-only");
  assert.deepEqual(plan.tests, []);
  assert.deepEqual(plan.documentation.map(item => item.id), ["documentation-governance", "python-file-index"]);
  assert.deepEqual(plan.ci.map(item => item.id), ["project-constraints"]);
});

test("contract schema dependency CI security and release changes require full delivery", () => {
  const cases = new Map([
    ["contracts/public-api.json", "public_contract_change"],
    ["schemas/result.schema.json", "schema_change"],
    ["requirements/web.lock", "dependency_change"],
    [".github/workflows/checks.yml", "ci_change"],
    ["security/policy.md", "security_change"],
    ["release/manifest.json", "release_change"],
  ]);
  for (const [changedFile, reason] of cases) {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.risk, "full-delivery", changedFile);
    assert.equal(plan.reasons.some(item => item.code === reason), true, changedFile);
  }
});

test("desktop changes require native Windows and desktop packaging gates", () => {
  const plan = success(run(repositoryRoot, ["src-tauri/tauri.conf.json"]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.documentation.some(item => item.id === "desktop-packaging"), true);
  assert.equal(plan.ci.some(item => item.id === "native-windows-desktop"), true);
});

test("unknown paths fail closed without pretending to be desktop changes", () => {
  const plan = success(run(repositoryRoot, ["unmapped/new-area.txt"]));
  assert.equal(plan.risk, "full-delivery");
  assert.deepEqual(plan.reasons, [{path: "unmapped/new-area.txt", rule: "fallback", code: "unknown_path"}]);
  assert.equal(gateIds(plan).some(id => id === "native-windows-desktop" || id === "desktop-packaging"), false);
});

test("multiple changed files deduplicate inputs and gates while keeping highest risk", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/ui/app.mjs",
    "app/research_web/ui/app.mjs",
    "requirements/web.lock",
    "docs/AGENT_WORKFLOW.md",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.deepEqual(plan.changedFiles, [
    "app/research_web/ui/app.mjs",
    "requirements/web.lock",
    "docs/AGENT_WORKFLOW.md",
  ]);
  for (const collection of [plan.tests, plan.documentation, plan.ci]) {
    const ids = collection.map(item => item.id);
    assert.equal(new Set(ids).size, ids.length);
  }
});

test("invalid JSON and weakened schemas fail with stable policy errors", t => {
  const invalidJson = fixture(t);
  fs.writeFileSync(path.join(invalidJson, ".agents/verification-policy.json"), "{broken\n");
  failure(run(invalidJson, ["docs/example.md"]), "POLICY_ERROR");

  const unknownKey = policy();
  unknownKey.extra = true;
  failure(run(fixture(t, unknownKey), ["docs/example.md"]), "POLICY_ERROR");

  const weakFallback = policy();
  weakFallback.fallback.risk = "local-only";
  failure(run(fixture(t, weakFallback), ["docs/example.md"]), "POLICY_ERROR");
});

test("a symlinked policy file fails explicitly", t => {
  const root = fixture(t);
  const policyPath = path.join(root, ".agents/verification-policy.json");
  const realPolicy = path.join(root, "outside-policy.json");
  fs.renameSync(policyPath, realPolicy);
  fs.symlinkSync(realPolicy, policyPath);
  failure(run(root, ["docs/example.md"]), "POLICY_ERROR");
});

test("a symlinked changed path fails explicitly", t => {
  const root = fixture(t);
  const target = path.join(root, "outside.txt");
  const changed = path.join(root, "docs/example.md");
  fs.mkdirSync(path.dirname(changed), {recursive: true});
  fs.writeFileSync(target, "outside\n");
  fs.symlinkSync(target, changed);
  failure(run(root, ["docs/example.md"]), "PATH_ERROR");
});

test("absolute traversal and backslash paths fail explicitly", t => {
  const root = fixture(t);
  for (const changedFile of ["../outside.txt", path.join(root, "outside.txt"), "docs\\example.md"]) {
    failure(run(root, [changedFile]), "PATH_ERROR");
  }
});

test("the planner never executes commands stored in the policy", t => {
  const root = fixture(t);
  const marker = path.join(root, "executed.txt");
  const injected = policy();
  injected.catalogs.documentation["documentation-governance"] =
    `node -e "require('node:fs').writeFileSync(${JSON.stringify(marker)}, 'executed')"`;
  fs.writeFileSync(path.join(root, ".agents/verification-policy.json"), `${JSON.stringify(injected, null, 2)}\n`);
  const plan = success(run(root, ["docs/example.md"]));
  assert.equal(plan.documentation[0].value.includes("writeFileSync"), true);
  assert.equal(fs.existsSync(marker), false);
});

test("missing required CLI arguments use stable argument errors", t => {
  const root = fixture(t);
  const result = spawnSync(process.execPath, [plannerPath, "--project", root], {encoding: "utf8"});
  failure(result, "ARGUMENT_ERROR");
});
