import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const plannerPath = path.join(repositoryRoot, "scripts/plan_verification.mjs");

function catalog(level, value, execution = "local") {
  return {level, execution, value};
}

function rule({id, risk, minimumLevel, reason, impact, coupling, match, tests = [], documentation = [], ci = []}) {
  return {id, risk, minimumLevel, reason, impact, coupling, match, tests, documentation, ci};
}

function policy() {
  return {
    schemaVersion: 2,
    riskOrder: ["docs-only", "local-only", "full-delivery"],
    levelOrder: ["L0", "L1", "L2", "L3", "L4"],
    escalation: {highCouplingImpactThreshold: 2, targetLevel: "L3"},
    catalogs: {
      tests: {
        "verification-policy-contracts": catalog("L1", "node --test tests/javascript/verification_policy.test.mjs"),
        "verification-receipt-contracts": catalog("L1", "node --test tests/javascript/verification_receipt.test.mjs"),
        "incremental-validation-skill-contracts": catalog(
          "L1",
          "node --test tests/javascript/incremental_validation_skill.test.mjs",
        ),
        "research-web-framework-collectors": catalog("L1", "python -m pytest tests/research_web/test_framework_collectors.py --confcutdir=tests/research_web"),
        "research-web-frameworks-ui": catalog("L1", "node --test tests/javascript/research_web_frameworks_ui.test.mjs"),
        "project-constraints-local": catalog(
          "L2",
          "node .agents/project-constraints.mjs --project . --changed-file <repeat-for-complete-changed-set>",
        ),
        "research-web-architecture": catalog("L1", "node --test tests/javascript/research_web_architecture.test.mjs"),
        "research-web-api": catalog(
          "L1",
          "python -m pytest tests/research_web/test_api.py --confcutdir=tests/research_web",
        ),
        "research-web-ui": catalog(
          "L1",
          "node --test tests/javascript/research_web_ui.test.mjs tests/javascript/research_web_capabilities_ui.test.mjs",
        ),
        "research-web-service-manager": catalog(
          "L1",
          "python -m pytest tests/research_web/test_service_manager.py --confcutdir=tests/research_web",
        ),
        "research-web-installation": catalog(
          "L1",
          "python -m pytest tests/research_web/test_setup_web.py --confcutdir=tests/research_web",
        ),
        "research-web-local-integrations": catalog(
          "L1",
          "python -m pytest tests/research_web/test_local_integrations.py --confcutdir=tests/research_web",
        ),
        "research-web-frameworks-python": catalog("L2", "python -m pytest tests/research_web/test_frameworks.py --confcutdir=tests/research_web"),
        "research-web-framework-smoke": catalog(
          "L3",
          "python -m pytest tests/research_web/test_frameworks.py::test_catalog_and_framework_data_use_versioned_specific_contracts --confcutdir=tests/research_web",
        ),
        "research-web-critical-smoke": catalog("L3", "python -m pytest tests/research_web/test_protocol.py --confcutdir=tests/research_web"),
        "research-web-verification-full": catalog(
          "L4",
          "node --test tests/javascript/research_web_architecture.test.mjs tests/javascript/documentation_governance.test.mjs tests/javascript/actions_quota_governance.test.mjs",
        ),
      },
      documentation: {
        "documentation-governance": catalog("L0", "node scripts/check_documentation_governance.mjs --project ."),
        "python-file-index": catalog("L0", "python scripts/generate_py_file_index.py --check"),
        "desktop-packaging": catalog("L4", "docs/desktop_packaging.md", "external"),
      },
      ci: {
        "project-constraints": catalog("L4", ".github/workflows/project-constraints.yml", "external"),
        "research-web-checks": catalog("L4", ".github/workflows/research-web-checks.yml", "external"),
        "research-web-bootstrap": catalog(
          "L4",
          ".github/workflows/research-web-bootstrap.yml#macos-14",
          "external",
        ),
        "native-windows-desktop": catalog("L4", ".github/workflows/desktop-verify.yml#windows-2022", "external"),
      },
    },
    rules: [
      rule({
        id: "desktop",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "desktop_change",
        impact: ["desktop-platform"],
        coupling: "high",
        match: {
          files: [],
          prefixes: ["src-tauri/", "desktop/", "scripts/desktop/", "services/desktop_platform/"],
          segments: [],
          suffixes: [],
        },
        tests: [],
        documentation: ["desktop-packaging"],
        ci: ["project-constraints", "native-windows-desktop"],
      }),
      rule({
        id: "contract",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "public_contract_change",
        impact: ["public-contract"],
        coupling: "high",
        match: {files: [], prefixes: ["contracts/"], segments: ["contracts"], suffixes: []},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "schema",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "schema_change",
        impact: ["schema-boundary"],
        coupling: "high",
        match: {files: [], prefixes: ["schemas/"], segments: ["schemas", "migrations"], suffixes: [".schema.json"]},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "dependency",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "dependency_change",
        impact: ["dependency-graph"],
        coupling: "high",
        match: {files: ["package.json", "pyproject.toml"], prefixes: ["requirements/"], segments: [], suffixes: [".lock"]},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "research-web-ci",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "research_web_ci_change",
        impact: ["research-web-verification"],
        coupling: "high",
        match: {
          files: [
            ".github/workflows/research-web-bootstrap.yml",
            ".github/workflows/research-web-windows-verify.yml",
            "tests/javascript/actions_quota_governance.test.mjs",
          ],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: [
          "verification-policy-contracts",
          "verification-receipt-contracts",
          "incremental-validation-skill-contracts",
          "research-web-verification-full",
          "research-web-local-integrations",
          "project-constraints-local",
        ],
        documentation: ["documentation-governance"],
        ci: ["project-constraints", "research-web-checks", "research-web-bootstrap"],
      }),
      rule({
        id: "ci",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "ci_change",
        impact: ["verification-system"],
        coupling: "high",
        match: {
          files: [
            ".agents/verification-policy.json",
            "scripts/plan_verification.mjs",
            "scripts/validate_verification_receipt.mjs",
            "tests/javascript/verification_policy.test.mjs",
            "tests/javascript/verification_receipt.test.mjs",
            "tests/javascript/incremental_validation_skill.test.mjs",
          ],
          prefixes: [".agents/skills/incremental-validation/", ".github/workflows/"],
          segments: [],
          suffixes: [],
        },
        tests: [
          "verification-policy-contracts",
          "verification-receipt-contracts",
          "incremental-validation-skill-contracts",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "core",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "core_abstraction_change",
        impact: ["core-abstraction"],
        coupling: "high",
        match: {files: [], prefixes: ["core/"], segments: ["_shared"], suffixes: []},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "data-model",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "data_model_change",
        impact: ["data-model"],
        coupling: "high",
        match: {files: [], prefixes: ["data_layer/models/", "models/", "migrations/"], segments: ["migrations"], suffixes: []},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "security",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "security_change",
        impact: ["security-boundary"],
        coupling: "high",
        match: {files: ["SECURITY.md"], prefixes: ["security/"], segments: ["security"], suffixes: []},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "release",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "release_change",
        impact: ["release-boundary"],
        coupling: "high",
        match: {files: [], prefixes: ["release/", "scripts/release/"], segments: ["release"], suffixes: []},
        tests: ["research-web-verification-full"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "critical-chain",
        risk: "local-only",
        minimumLevel: "L3",
        reason: "critical_chain_change",
        impact: ["critical-chain"],
        coupling: "high",
        match: {files: [], prefixes: [], segments: ["parser", "parsers", "workflow", "workflows", "agents", "orchestration"], suffixes: []},
        tests: ["research-web-architecture", "research-web-critical-smoke"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "framework-artifacts",
        risk: "docs-only",
        minimumLevel: "L0",
        reason: "framework_artifact_change",
        impact: ["framework-artifacts"],
        coupling: "low",
        match: {files: [], prefixes: ["outputs/frameworks-v1/"], segments: [], suffixes: []},
        tests: [],
        documentation: [],
        ci: [],
      }),
      rule({
        id: "documentation",
        risk: "docs-only",
        minimumLevel: "L0",
        reason: "documentation_only",
        impact: ["documentation"],
        coupling: "low",
        match: {files: ["README.md"], prefixes: ["docs/", ".ai/reports/", ".claude/commands/"], segments: [], suffixes: [".md"]},
        tests: [],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints"],
      }),
      rule({
        id: "research-web-local-integrations",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_local_integrations_change",
        impact: ["research-web-local-integrations"],
        coupling: "low",
        match: {
          files: ["tests/research_web/test_local_integrations.py"],
          prefixes: ["app/research_web/local_integrations/"],
          segments: [],
          suffixes: [],
        },
        tests: ["research-web-local-integrations", "research-web-architecture"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_change",
        impact: ["research-web"],
        coupling: "low",
        match: {files: [], prefixes: ["app/research_web/", "app/web/"], segments: [], suffixes: []},
        tests: ["research-web-architecture", "project-constraints-local", "research-web-verification-full"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web-api",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_api_change",
        impact: ["research-web-api"],
        coupling: "low",
        match: {
          files: ["app/research_web/service.py", "tests/research_web/test_api.py"],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: ["research-web-api", "research-web-architecture", "project-constraints-local"],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web-ui-core",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_ui_change",
        impact: ["research-web-ui"],
        coupling: "low",
        match: {
          files: [
            "app/research_web/ui/app.mjs",
            "app/research_web/ui/composer.mjs",
            "tests/javascript/research_web_ui.test.mjs",
            "tests/javascript/research_web_capabilities_ui.test.mjs",
          ],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: ["research-web-ui", "research-web-architecture", "project-constraints-local"],
        documentation: ["documentation-governance"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web-service-manager",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_service_manager_change",
        impact: ["research-web-service-lifecycle"],
        coupling: "low",
        match: {
          files: ["tests/research_web/test_service_manager.py"],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: [
          "research-web-service-manager",
          "research-web-architecture",
          "project-constraints-local",
          "research-web-critical-smoke",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web-service-lifecycle-delivery",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "research_web_service_lifecycle_delivery",
        impact: ["research-web-service-lifecycle"],
        coupling: "high",
        match: {
          files: ["app/research_web/service_manager.py"],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: [
          "research-web-service-manager",
          "research-web-architecture",
          "project-constraints-local",
          "research-web-critical-smoke",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks", "research-web-bootstrap"],
      }),
      rule({
        id: "research-web-installation",
        risk: "full-delivery",
        minimumLevel: "L4",
        reason: "research_web_installation_change",
        impact: ["web-installation"],
        coupling: "high",
        match: {
          files: [
            "rwb",
            "rwb.cmd",
            "setup-web.sh",
            "setup-web.cmd",
            "scripts/setup_web.py",
            "tests/research_web/test_setup_web.py",
          ],
          prefixes: [],
          segments: [],
          suffixes: [],
        },
        tests: [
          "research-web-installation",
          "research-web-architecture",
          "project-constraints-local",
          "research-web-critical-smoke",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks", "research-web-bootstrap"],
      }),
      rule({
        id: "research-web-framework-backend",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_framework_backend_change",
        impact: ["framework-backend"],
        coupling: "high",
        match: {
          files: [
            "tests/research_web/test_frameworks.py",
            "tests/research_web/test_framework_collectors.py",
            "tests/research_web/test_workbench_operations.py",
          ],
          prefixes: ["app/research_web/frameworks/"],
          segments: [],
          suffixes: [],
        },
        tests: [
          "research-web-framework-collectors",
          "research-web-architecture",
          "research-web-frameworks-python",
          "project-constraints-local",
          "research-web-framework-smoke",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
      rule({
        id: "research-web-framework-ui",
        risk: "local-only",
        minimumLevel: "L1",
        reason: "research_web_framework_ui_change",
        impact: ["framework-ui"],
        coupling: "high",
        match: {
          files: [
            "app/research_web/ui/frameworks.mjs",
            "tests/e2e/research_web_goldar_v0.mjs",
            "tests/javascript/research_web_frameworks_ui.test.mjs",
            "tests/javascript/research_web_workbench.test.mjs",
          ],
          prefixes: ["app/research_web/ui/frameworks/"],
          segments: [],
          suffixes: [],
        },
        tests: [
          "research-web-frameworks-ui",
          "research-web-architecture",
          "research-web-frameworks-python",
          "project-constraints-local",
          "research-web-framework-smoke",
          "research-web-verification-full",
        ],
        documentation: ["documentation-governance", "python-file-index"],
        ci: ["project-constraints", "research-web-checks"],
      }),
    ],
    fallback: {
      risk: "full-delivery",
      minimumLevel: "L4",
      reason: "unknown_path",
      impact: ["unknown-boundary"],
      coupling: "high",
      tests: ["research-web-verification-full"],
      documentation: ["documentation-governance"],
      ci: ["project-constraints"],
    },
  };
}

test("every focused Research Web Python catalog isolates the repository root conftest", () => {
  const actual = JSON.parse(fs.readFileSync(
    path.join(repositoryRoot, ".agents/verification-policy.json"),
    "utf8",
  ));
  const catalogs = Object.entries(actual.catalogs.tests).filter(([, item]) => (
    item.execution === "local"
    && item.value.startsWith("python -m pytest tests/research_web/")
  ));

  assert.equal(catalogs.length, 8);
  for (const [id, item] of catalogs) {
    assert.match(
      item.value,
      / --confcutdir=tests\/research_web(?: |$)/,
      `${id} must not load the repository root conftest`,
    );
  }
});

function fixture(t, value = policy()) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "rwb-verification-policy-"));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  fs.mkdirSync(path.join(root, ".agents"), {recursive: true});
  fs.writeFileSync(path.join(root, ".agents/verification-policy.json"), `${JSON.stringify(value, null, 2)}\n`);
  return root;
}

function run(project, changedFiles, signals = []) {
  const args = [plannerPath, "--project", project];
  for (const changedFile of changedFiles) args.push("--changed-file", changedFile);
  for (const signal of signals) args.push("--signal", signal);
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
  assert.equal(plan.requiredLevel, "L1");
  const ids = gateIds(plan).join(" ").toLowerCase();
  for (const forbidden of ["desktop", "windows", "tauri", "sidecar", "installer"]) {
    assert.equal(ids.includes(forbidden), false, `${forbidden} leaked into Web-only plan`);
  }
  assert.deepEqual(plan.tests.map(item => item.id), [
    "research-web-architecture",
    "research-web-ui",
    "research-web-api",
  ]);
});

test("framework source selects architecture and all framework-specific tests", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "app/research_web/ui/frameworks/goldar.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L3");
  assert.deepEqual(plan.tests.map(item => item.id), [
    "research-web-architecture",
    "project-constraints-local",
    "research-web-framework-collectors",
    "research-web-frameworks-python",
    "research-web-framework-smoke",
    "research-web-frameworks-ui",
  ]);
  const ids = gateIds(plan).join(" ").toLowerCase();
  for (const forbidden of ["desktop", "windows", "tauri", "sidecar", "installer"]) {
    assert.equal(ids.includes(forbidden), false, `${forbidden} leaked into framework plan`);
  }
});

test("known framework test files use the framework-specific local closure", () => {
  const plan = success(run(repositoryRoot, [
    "tests/research_web/test_frameworks.py",
    "tests/research_web/test_framework_collectors.py",
    "tests/javascript/research_web_frameworks_ui.test.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L3");
  assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
    "research-web-framework-collectors",
    "research-web-architecture",
    "research-web-frameworks-python",
    "project-constraints-local",
    "research-web-framework-smoke",
    "research-web-frameworks-ui",
  ]));
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
});

test("service lifecycle changes require the focused test and GitHub macOS bootstrap", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/service_manager.py",
    "tests/research_web/test_service_manager.py",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(plan.tests.some(item => item.id === "research-web-service-manager"), true);
  assert.deepEqual(new Set(plan.receiptTemplate.externalGateIds), new Set([
    "project-constraints",
    "research-web-checks",
    "research-web-bootstrap",
  ]));
  assert.equal(
    plan.ci.find(item => item.id === "research-web-bootstrap").value,
    ".github/workflows/research-web-bootstrap.yml#macos-14",
  );
});

test("session catalog source and test use the focused API closure", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/service.py",
    "tests/research_web/test_api.py",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L1");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
    "research-web-architecture",
    "research-web-api",
  ]));
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});

test("core UI source and tests use the focused UI closure", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/ui/app.mjs",
    "app/research_web/ui/composer.mjs",
    "tests/javascript/research_web_ui.test.mjs",
    "tests/javascript/research_web_capabilities_ui.test.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L1");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
    "research-web-architecture",
    "research-web-ui",
  ]));
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});

test("Web installation code and tests require the focused test plus native bootstrap CI", () => {
  const plan = success(run(repositoryRoot, [
    "scripts/setup_web.py",
    "tests/research_web/test_setup_web.py",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(
    plan.receiptTemplate.requiredValidationIds.includes("research-web-installation"),
    true,
  );
  assert.deepEqual(new Set(plan.receiptTemplate.externalGateIds), new Set([
    "project-constraints",
    "research-web-checks",
    "research-web-bootstrap",
  ]));
});

for (const file of [
  ".github/workflows/research-web-bootstrap.yml",
  ".github/workflows/research-web-windows-verify.yml",
  "tests/javascript/actions_quota_governance.test.mjs",
]) {
  test(`focused Research Web CI path requires exactly the macOS external gates: ${file}`, () => {
    const plan = success(run(repositoryRoot, [file]));
    assert.equal(plan.risk, "full-delivery");
    assert.equal(plan.requiredLevel, "L4");
    assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
    assert.equal(plan.tests.some(item => item.id === "research-web-local-integrations"), true);
    assert.deepEqual(new Set(plan.receiptTemplate.externalGateIds), new Set([
      "project-constraints",
      "research-web-checks",
      "research-web-bootstrap",
    ]));
    const bootstrap = plan.ci.find((item) => item.id === "research-web-bootstrap");
    assert.equal(bootstrap.value, ".github/workflows/research-web-bootstrap.yml#macos-14");
    assert.equal(bootstrap.execution, "external");
  });
}

for (const file of [
  "tests/research_web/test_local_integrations.py",
  "app/research_web/local_integrations/manager.py",
]) {
  test(`local integrations path independently selects only its focused local closure: ${file}`, () => {
    const plan = success(run(repositoryRoot, [file]));
    assert.equal(plan.risk, "local-only");
    assert.equal(plan.requiredLevel, "L1");
    assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
    assert.deepEqual(new Set(plan.tests.map(item => item.id)), new Set([
      "research-web-local-integrations",
      "research-web-architecture",
    ]));
    assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
    assert.deepEqual(plan.ci, []);
  });
}

test("unmapped test files still fail closed", () => {
  const plan = success(run(repositoryRoot, ["tests/research_web/test_unmapped_component.py"]));
  assert.equal(plan.risk, "full-delivery");
  assert.deepEqual(plan.reasons, [{
    path: "tests/research_web/test_unmapped_component.py",
    rule: "fallback",
    code: "unknown_path",
  }]);
});

test("high-risk paths keep full delivery while retaining framework tests", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "requirements/web.lock",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.tests.some(item => item.id === "research-web-verification-full"), true);
  assert.equal(plan.tests.some(item => item.id === "research-web-framework-collectors"), true);
  assert.equal(plan.reasons.some(item => item.code === "dependency_change"), true);
});

test("framework gates remain ordered and deduplicated across repeated paths", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/service.py",
    "tests/research_web/test_frameworks.py",
    "app/research_web/frameworks/service.py",
  ]));
  assert.deepEqual(plan.changedFiles, [
    "app/research_web/frameworks/service.py",
    "tests/research_web/test_frameworks.py",
  ]);
  assert.equal(plan.requiredLevel, "L1");
  assert.deepEqual(plan.tests.map(item => item.id), [
    "research-web-architecture",
    "research-web-framework-collectors",
  ]);
  for (const collection of [plan.tests, plan.documentation, plan.ci]) {
    const ids = collection.map(item => item.id);
    assert.equal(new Set(ids).size, ids.length);
  }
});

test("documentation changes only select documentation-related checks", () => {
  const plan = success(run(repositoryRoot, ["docs/AGENT_WORKFLOW.md"]));
  assert.equal(plan.risk, "docs-only");
  assert.equal(plan.requiredLevel, "L0");
  assert.deepEqual(plan.tests, []);
  assert.deepEqual(plan.documentation.map(item => item.id), ["documentation-governance", "python-file-index"]);
  assert.deepEqual(plan.ci, []);
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
    assert.equal(plan.requiredLevel, "L4", changedFile);
    assert.equal(plan.reasons.some(item => item.code === reason), true, changedFile);
  }
});

test("core shared utility and data model changes require L4", () => {
  const cases = new Map([
    ["core/contracts/runtime.py", "core_abstraction_change"],
    ["app/research_web/skills/_shared/evidence-protocol.md", "core_abstraction_change"],
    ["data_layer/models/research.py", "data_model_change"],
    ["migrations/019_result.sql", "data_model_change"],
  ]);
  for (const [changedFile, reason] of cases) {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.requiredLevel, "L4", changedFile);
    assert.equal(plan.reasons.some(item => item.code === reason), true, changedFile);
  }
});

test("known parser workflow and agent orchestration changes require L3", () => {
  for (const changedFile of [
    "app/research_web/parsers/request.py",
    "app/research_web/workflows/report.py",
    "app/research_web/agents/coordinator.py",
    "app/research_web/orchestration/runner.py",
  ]) {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.requiredLevel, "L3", changedFile);
    assert.equal(plan.reasons.some(item => item.code === "critical_chain_change"), true, changedFile);
  }
});

test("small framework renderer change selects L1 without L4", () => {
  const plan = success(run(repositoryRoot, ["app/research_web/ui/frameworks/goldar.mjs"]));
  assert.equal(plan.requiredLevel, "L1");
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-frameworks-ui",
  ]);
  assert.deepEqual(plan.validationsByLevel.L4, []);
  assert.equal(
    [...plan.tests, ...plan.documentation].every(item => item.execution === "local"),
    true,
  );
  assert.equal(plan.ci.some(item => item.id === "native-windows-desktop"), false);
});

test("cross-module framework change escalates high coupling impacts to L3", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/frameworks/goldar/store.py",
    "app/research_web/ui/frameworks/goldar.mjs",
  ]));
  assert.equal(plan.requiredLevel, "L3");
  assert.equal(
    plan.escalations.some(item => item.code === "multiple_high_coupling_modules"),
    true,
  );
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-frameworks-python",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3.map(item => item.id), [
    "research-web-framework-smoke",
  ]);
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
});

test("tracked framework artifacts and supporting tests stay in the known L3 closure", () => {
  const plan = success(run(repositoryRoot, [
    "outputs/frameworks-v1/verification.json",
    "tests/e2e/research_web_goldar_v0.mjs",
    "tests/javascript/research_web_workbench.test.mjs",
    "tests/research_web/test_workbench_operations.py",
  ]));
  assert.equal(plan.requiredLevel, "L3");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(plan.changeSummary.impactIds.includes("framework-artifacts"), true);
  assert.equal(plan.changeSummary.impactIds.includes("framework-backend"), true);
  assert.equal(plan.changeSummary.impactIds.includes("framework-ui"), true);
});

for (const changedFile of [
  "app/research_web/datahub/providers_akshare.py",
  "tests/research_web/test_datahub_catalog.py",
]) {
  test(`AKShare provider path uses the bounded L2 DataHub closure: ${changedFile}`, () => {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.risk, "local-only");
    assert.equal(plan.requiredLevel, "L2");
    assert.deepEqual(plan.changeSummary.ruleIds, ["research-web-datahub-public-provider"]);
    assert.deepEqual(plan.changeSummary.impactIds, ["datahub-public-provider"]);
    assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
    assert.deepEqual(plan.validationsByLevel.L0.map(item => item.id), [
      "documentation-governance",
      "python-file-index",
    ]);
    assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
      "research-web-architecture",
      "research-web-datahub-public-provider",
    ]);
    assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
      "project-constraints-local",
      "research-web-datahub-core",
    ]);
    assert.deepEqual(plan.validationsByLevel.L3, []);
    assert.deepEqual(plan.validationsByLevel.L4, []);
    assert.equal(
      plan.tests.find(item => item.id === "research-web-datahub-public-provider")?.value,
      "python -m pytest tests/research_web/test_datahub_catalog.py --confcutdir=tests/research_web",
    );
  });
}

test("AKShare provider source and test merge into one bounded L2 closure", () => {
  const changedFiles = [
    "app/research_web/datahub/providers_akshare.py",
    "tests/research_web/test_datahub_catalog.py",
  ];
  const plan = success(run(repositoryRoot, changedFiles));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L2");
  assert.deepEqual(plan.changedFiles, changedFiles);
  assert.equal(plan.changeSummary.fileCount, 2);
  assert.deepEqual(plan.changeSummary.ruleIds, ["research-web-datahub-public-provider"]);
  assert.deepEqual(plan.changeSummary.impactIds, ["datahub-public-provider"]);
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.deepEqual(plan.escalations, []);
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-datahub-public-provider",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-datahub-core",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3, []);
  assert.deepEqual(plan.validationsByLevel.L4, []);
});

for (const {changedFile, ruleIds, impactIds, level0Ids} of [
  {
    changedFile: "app/research_web/ui/asset-workspace.mjs",
    ruleIds: ["research-web", "research-web-asset-workbench-ui"],
    impactIds: ["research-web", "asset-workbench-ui"],
    level0Ids: ["documentation-governance", "python-file-index"],
  },
  {
    changedFile: "tests/javascript/research_web_workbench.test.mjs",
    ruleIds: ["research-web-asset-workbench-ui"],
    impactIds: ["asset-workbench-ui"],
    level0Ids: ["documentation-governance"],
  },
]) {
  test(`asset Workbench UI path selects only its direct L1 closure: ${changedFile}`, () => {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.risk, "local-only");
    assert.equal(plan.requiredLevel, "L1");
    assert.deepEqual(plan.changeSummary.ruleIds, ruleIds);
    assert.deepEqual(plan.changeSummary.impactIds, impactIds);
    assert.deepEqual(plan.validationsByLevel.L0.map(item => item.id), level0Ids);
    assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
      "research-web-architecture",
      "research-web-asset-workbench-ui",
    ]);
    assert.deepEqual(plan.validationsByLevel.L2, []);
    assert.deepEqual(plan.validationsByLevel.L3, []);
    assert.deepEqual(plan.validationsByLevel.L4, []);
    assert.equal(plan.changeSummary.impactIds.includes("framework-ui"), false);
    assert.equal(plan.tests.some(item => item.id.startsWith("research-web-framework")), false);
    assert.equal(
      plan.tests.find(item => item.id === "research-web-asset-workbench-ui")?.value,
      "node --test tests/javascript/research_web_workbench.test.mjs",
    );
  });
}

test("asset Workbench UI source and test merge without framework validation", () => {
  const changedFiles = [
    "app/research_web/ui/asset-workspace.mjs",
    "tests/javascript/research_web_workbench.test.mjs",
  ];
  const plan = success(run(repositoryRoot, changedFiles));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L1");
  assert.deepEqual(plan.changedFiles, changedFiles);
  assert.equal(plan.changeSummary.fileCount, 2);
  assert.deepEqual(plan.changeSummary.ruleIds, [
    "research-web",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.changeSummary.impactIds, [
    "research-web",
    "asset-workbench-ui",
  ]);
  assert.deepEqual(plan.escalations, []);
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2, []);
  assert.deepEqual(plan.validationsByLevel.L3, []);
  assert.deepEqual(plan.validationsByLevel.L4, []);
  assert.equal(plan.changeSummary.impactIds.includes("framework-ui"), false);
  assert.equal(plan.tests.some(item => item.id.startsWith("research-web-framework")), false);
});

test("AKShare plus asset UI escalates to the bounded L3 user path", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/datahub/providers_akshare.py",
    "app/research_web/ui/asset-workspace.mjs",
  ]));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L3");
  assert.deepEqual(plan.changeSummary.ruleIds, [
    "research-web-datahub-public-provider",
    "research-web",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.changeSummary.impactIds, [
    "datahub-public-provider",
    "research-web",
    "asset-workbench-ui",
  ]);
  assert.deepEqual(plan.escalations, [{
    code: "multiple_high_coupling_modules",
    fromLevel: "L2",
    toLevel: "L3",
    impacts: ["datahub-public-provider", "asset-workbench-ui"],
  }]);
  assert.deepEqual(plan.validationsByLevel.L0.map(item => item.id), [
    "documentation-governance",
    "python-file-index",
  ]);
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-datahub-public-provider",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-datahub-core",
    "research-web-asset-workspace-python",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3.map(item => item.id), [
    "research-web-asset-workspace-smoke",
  ]);
  assert.deepEqual(plan.validationsByLevel.L4, []);
  assert.deepEqual(plan.receiptTemplate.requiredValidationIds, [
    "research-web-architecture",
    "research-web-datahub-public-provider",
    "project-constraints-local",
    "research-web-datahub-core",
    "research-web-asset-workspace-smoke",
    "research-web-asset-workbench-ui",
    "research-web-asset-workspace-python",
    "documentation-governance",
    "python-file-index",
  ]);
  assert.deepEqual(plan.receiptTemplate.externalGateIds, []);
  assert.equal(
    plan.tests.find(item => item.id === "research-web-asset-workspace-smoke")?.value,
    "python -m pytest tests/research_web/test_asset_workspace.py::test_asset_observation_tracks_each_block_and_freezes_handoff_context --confcutdir=tests/research_web",
  );
});

test("unregistered DataHub boundaries remain L4 fallback paths", () => {
  const currentDataHubPythonFiles = fs.readdirSync(
    path.join(repositoryRoot, "app/research_web/datahub"),
    {withFileTypes: true},
  ).filter(entry => (
    entry.isFile()
    && entry.name.endsWith(".py")
    && entry.name !== "providers_akshare.py"
  )).map(entry => `app/research_web/datahub/${entry.name}`).sort();
  const fallbackPaths = [...new Set([
    ...currentDataHubPythonFiles,
    "app/research_web/datahub/future_provider.py",
    "tests/research_web/test_datahub_wind.py",
  ])];

  assert.equal(currentDataHubPythonFiles.length > 0, true);
  assert.equal(fallbackPaths.includes("app/research_web/datahub/providers_akshare.py"), false);
  assert.equal(fallbackPaths.includes("app/research_web/datahub/future_provider.py"), true);
  assert.equal(fallbackPaths.includes("tests/research_web/test_datahub_wind.py"), true);
  for (const changedFile of fallbackPaths) {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.risk, "full-delivery", changedFile);
    assert.equal(plan.requiredLevel, "L4", changedFile);
    assert.deepEqual(plan.changeSummary.ruleIds, ["fallback"], changedFile);
    assert.deepEqual(plan.reasons, [{
      path: changedFile,
      rule: "fallback",
      code: "unknown_path",
    }], changedFile);
    assert.deepEqual(plan.uncoveredRisks, ["unknown_impact_boundary"], changedFile);
  }
});

for (const {changedFile, ruleIds, impactIds} of [
  {
    changedFile: "app/research_web/asset_workspace.py",
    ruleIds: ["research-web", "research-web-asset-workbench-backend"],
    impactIds: ["research-web", "asset-workbench-backend"],
  },
  {
    changedFile: "app/research_web/asset_routes.py",
    ruleIds: ["research-web", "research-web-asset-workbench-backend"],
    impactIds: ["research-web", "asset-workbench-backend"],
  },
  {
    changedFile: "tests/research_web/test_asset_workspace.py",
    ruleIds: ["research-web-asset-workbench-backend"],
    impactIds: ["asset-workbench-backend"],
  },
]) {
  test(`asset Workbench backend path uses L2 direct contracts: ${changedFile}`, () => {
    const plan = success(run(repositoryRoot, [changedFile]));
    assert.equal(plan.risk, "local-only");
    assert.equal(plan.requiredLevel, "L2");
    assert.deepEqual(plan.changeSummary.ruleIds, ruleIds);
    assert.deepEqual(plan.changeSummary.impactIds, impactIds);
    assert.deepEqual(plan.validationsByLevel.L0.map(item => item.id), [
      "documentation-governance",
      "python-file-index",
    ]);
    assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
      "research-web-architecture",
      "research-web-asset-workbench-ui",
    ]);
    assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
      "project-constraints-local",
      "research-web-asset-workspace-python",
    ]);
    assert.deepEqual(plan.validationsByLevel.L3, []);
    assert.deepEqual(plan.validationsByLevel.L4, []);
    assert.equal(
      plan.tests.find(item => item.id === "research-web-asset-workspace-python")?.value,
      "python -m pytest tests/research_web/test_asset_workspace.py --confcutdir=tests/research_web",
    );
  });
}

test("asset Workbench backend source and test merge into one L2 direct closure", () => {
  const changedFiles = [
    "app/research_web/asset_workspace.py",
    "tests/research_web/test_asset_workspace.py",
  ];
  const plan = success(run(repositoryRoot, changedFiles));
  assert.equal(plan.risk, "local-only");
  assert.equal(plan.requiredLevel, "L2");
  assert.deepEqual(plan.changedFiles, changedFiles);
  assert.equal(plan.changeSummary.fileCount, 2);
  assert.deepEqual(plan.changeSummary.ruleIds, [
    "research-web",
    "research-web-asset-workbench-backend",
  ]);
  assert.deepEqual(plan.changeSummary.impactIds, [
    "research-web",
    "asset-workbench-backend",
  ]);
  assert.deepEqual(plan.escalations, []);
  assert.deepEqual(plan.validationsByLevel.L1.map(item => item.id), [
    "research-web-architecture",
    "research-web-asset-workbench-ui",
  ]);
  assert.deepEqual(plan.validationsByLevel.L2.map(item => item.id), [
    "project-constraints-local",
    "research-web-asset-workspace-python",
  ]);
  assert.deepEqual(plan.validationsByLevel.L3, []);
  assert.deepEqual(plan.validationsByLevel.L4, []);
});

test("AKShare provider keeps its catalog when a dependency change requires L4", () => {
  const plan = success(run(repositoryRoot, [
    "app/research_web/datahub/providers_akshare.py",
    "requirements/web.lock",
  ]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.deepEqual(plan.changeSummary.ruleIds, [
    "research-web-datahub-public-provider",
    "dependency",
  ]);
  assert.deepEqual(plan.changeSummary.impactIds, [
    "datahub-public-provider",
    "dependency-graph",
  ]);
  assert.equal(plan.reasons.some(item => item.code === "dependency_change"), true);
  assert.equal(
    plan.tests.find(item => item.id === "research-web-datahub-public-provider")?.value,
    "python -m pytest tests/research_web/test_datahub_catalog.py --confcutdir=tests/research_web",
  );
  assert.equal(plan.receiptTemplate.externalGateIds.includes("project-constraints"), true);
  assert.equal(plan.receiptTemplate.externalGateIds.includes("research-web-checks"), true);
});

test("verification policy change cannot fall below L4", () => {
  const plan = success(run(repositoryRoot, [".agents/verification-policy.json"]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.deepEqual(plan.uncoveredRisks, []);
  assert.equal(plan.receiptTemplate.requiredValidationIds.includes("research-web-verification-full"), true);
  assert.equal(plan.receiptTemplate.externalGateIds.includes("project-constraints"), true);
  const full = plan.tests.find(item => item.id === "research-web-verification-full").value;
  assert.doesNotMatch(full, /verification_policy|verification_receipt|incremental_validation_skill/);
});

test("incremental validation workflow contract is a known L4 policy path", () => {
  const plan = success(run(repositoryRoot, ["tests/javascript/incremental_validation_skill.test.mjs"]));
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.reasons.some(item => item.code === "unknown_path"), false);
  assert.equal(plan.receiptTemplate.requiredValidationIds.includes("incremental-validation-skill-contracts"), true);
});

test("runtime failure signals escalate one level each and deduplicate", () => {
  const changed = ["app/research_web/ui/frameworks/goldar.mjs"];
  const failed = success(run(repositoryRoot, changed, ["validation_failure", "validation_failure"]));
  assert.equal(failed.requiredLevel, "L2");
  assert.deepEqual(failed.escalations.map(item => item.code), ["validation_failure"]);
  assert.equal(failed.validationsByLevel.L2.some(item => item.id === "research-web-frameworks-python"), true);

  const unexpected = success(run(repositoryRoot, changed, ["validation_failure", "unexpected_behavior"]));
  assert.equal(unexpected.requiredLevel, "L3");
  assert.deepEqual(unexpected.escalations.map(item => item.code), [
    "validation_failure",
    "unexpected_behavior",
  ]);
  assert.equal(unexpected.validationsByLevel.L3.some(item => item.id === "research-web-framework-smoke"), true);
});

test("unknown runtime escalation signals fail explicitly", t => {
  const root = fixture(t);
  failure(run(root, ["docs/example.md"], ["not_a_signal"]), "ARGUMENT_ERROR");
});

test("desktop changes require native Windows and desktop packaging gates", () => {
  const plan = success(run(repositoryRoot, ["src-tauri/tauri.conf.json"]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.equal(plan.documentation.some(item => item.id === "desktop-packaging"), true);
  assert.equal(plan.ci.some(item => item.id === "native-windows-desktop"), true);
  assert.equal(plan.documentation.find(item => item.id === "desktop-packaging").execution, "external");
  assert.equal(plan.ci.every(item => item.execution === "external"), true);
});

test("unknown paths fail closed without pretending to be desktop changes", () => {
  const plan = success(run(repositoryRoot, ["unmapped/new-area.txt"]));
  assert.equal(plan.risk, "full-delivery");
  assert.equal(plan.requiredLevel, "L4");
  assert.deepEqual(plan.reasons, [{path: "unmapped/new-area.txt", rule: "fallback", code: "unknown_path"}]);
  assert.equal(gateIds(plan).some(id => id === "native-windows-desktop" || id === "desktop-packaging"), false);
  assert.deepEqual(plan.uncoveredRisks, ["unknown_impact_boundary"]);
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

test("excludePrefixes delegates excluded paths to fallback without overriding other rules", t => {
  const value = policy();
  const generic = value.rules.find(item => item.id === "research-web");
  assert.ok(generic);
  generic.match.excludePrefixes = ["app/research_web/datahub/"];
  value.rules.push(rule({
    id: "known-datahub",
    risk: "local-only",
    minimumLevel: "L2",
    reason: "known_datahub_change",
    impact: ["known-datahub"],
    coupling: "high",
    match: {
      files: ["app/research_web/datahub/providers_akshare.py"],
      prefixes: [],
      segments: [],
      suffixes: [],
    },
    tests: ["research-web-architecture"],
  }));
  const root = fixture(t, value);

  const known = success(run(root, ["app/research_web/datahub/providers_akshare.py"]));
  assert.equal(known.requiredLevel, "L2");
  assert.deepEqual(known.changeSummary.ruleIds, ["known-datahub"]);

  const unknown = success(run(root, ["app/research_web/datahub/new_provider.py"]));
  assert.equal(unknown.requiredLevel, "L4");
  assert.deepEqual(unknown.reasons, [{
    path: "app/research_web/datahub/new_provider.py",
    rule: "fallback",
    code: "unknown_path",
  }]);
  assert.deepEqual(unknown.uncoveredRisks, ["unknown_impact_boundary"]);
});

test("excludePrefixes remains optional but rejects unsafe or unknown match fields", t => {
  success(run(fixture(t), ["src-tauri/tauri.conf.json"]));

  for (const excludePrefixes of [
    null,
    ["../datahub/"],
    ["/absolute/datahub/"],
    ["app\\research_web\\datahub\\"],
    ["app/research_web/datahub"],
    ["app/research_web/datahub/", "app/research_web/datahub/"],
  ]) {
    const value = policy();
    value.rules[0].match.excludePrefixes = excludePrefixes;
    failure(run(fixture(t, value), ["src-tauri/tauri.conf.json"]), "POLICY_ERROR");
  }

  const unknownMatchField = policy();
  unknownMatchField.rules[0].match.unexpectedExclusion = [];
  failure(run(fixture(t, unknownMatchField), ["src-tauri/tauri.conf.json"]), "POLICY_ERROR");
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
  injected.catalogs.documentation["documentation-governance"].value =
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
