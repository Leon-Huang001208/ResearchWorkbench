import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function read(relative) {
  return fs.readFileSync(path.join(root, relative), "utf8");
}

test("incremental validation skill has discoverable trigger-only frontmatter", () => {
  const skill = read(".agents/skills/incremental-validation/SKILL.md");
  assert.match(skill, /^---\nname: incremental-validation\ndescription: Use when [^\n]+\n---/);
  assert.doesNotMatch(skill.split("---")[1], /runs|executes|generates|records/i);
});

test("skill requires the complete plan execute escalate receipt loop", () => {
  const skill = read(".agents/skills/incremental-validation/SKILL.md");
  for (const required of [
    "complete changed set",
    "scripts/plan_verification.mjs",
    "validationsByLevel",
    "--signal validation_failure",
    "--signal unexpected_behavior",
    "scripts/validate_verification_receipt.mjs",
    "uncoveredRisks",
    "external",
  ]) {
    assert.match(skill, new RegExp(required.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
  assert.doesNotMatch(skill, /src-tauri|requirements\/|core\//);
});

test("skill README documents inputs outputs safety and three examples", () => {
  const readme = read(".agents/skills/incremental-validation/README.md");
  for (const heading of ["## Inputs", "## Outputs", "## Safety boundaries", "## Examples"]) {
    assert.match(readme, new RegExp(heading));
  }
  assert.equal((readme.match(/^### Example /gm) ?? []).length, 3);
  assert.match(readme, /cannot publish/i);
  assert.match(readme, /cannot execute planned commands/i);
  assert.match(readme, /cannot downgrade an L4 plan/i);
});

test("workflow and development map document L0-L4 and receipt ownership", () => {
  const workflow = read("docs/AGENT_WORKFLOW.md");
  const map = read("docs/DEVELOPMENT_MAP.md");
  for (const level of ["L0", "L1", "L2", "L3", "L4"]) assert.match(workflow, new RegExp(level));
  assert.match(workflow, /Change → Impact → Validation/);
  assert.match(workflow, /--signal validation_failure/);
  assert.match(workflow, /validate_verification_receipt\.mjs/);
  assert.match(workflow, /external/);
  assert.match(map, /validate_verification_receipt\.mjs/);
  assert.match(map, /verification_receipt\.test\.mjs/);
  assert.match(map, /incremental-validation/);
});

test("Claude compatibility command remains a thin policy-free entrypoint", () => {
  const command = read(".claude/commands/verify-task.md");
  assert.match(command, /plan_verification\.mjs/);
  assert.match(command, /validate_verification_receipt\.mjs/);
  assert.match(command, /requiredLevel/);
  assert.match(command, /validationsByLevel/);
  assert.doesNotMatch(command, /src-tauri|requirements\/|core\//);
});
