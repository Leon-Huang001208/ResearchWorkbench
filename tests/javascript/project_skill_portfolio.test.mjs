import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

const root = path.resolve(import.meta.dirname, "../..");
const skillRoot = path.join(root, ".agents", "skills");
const migrated = ["cls", "cnstock", "data-connector-development"];
const retained = ["wind-find-finance-skill", "wind-mcp-skill"];
const forbidden = /(^|\/)(?:\.env|config\.ya?ml|.*\.lock|logs?|output|outputs|test_output|__pycache__|chroma_db|data)(\/|$)|\.(?:pyc|sqlite3|bin|xlsx)$/i;

function files(directory, relative = "") {
  return fs.readdirSync(path.join(directory, relative), {withFileTypes: true})
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap(entry => {
      const next = path.posix.join(relative.split(path.sep).join("/"), entry.name);
      return entry.isDirectory() ? files(directory, next) : [next];
    });
}

test("keeps migrated data Skills project-owned and free of runtime state", () => {
  for (const name of [...migrated, ...retained]) {
    assert.equal(fs.existsSync(path.join(skillRoot, name, "SKILL.md")), true, name);
  }
  for (const name of migrated) {
    const discovered = files(path.join(skillRoot, name));
    assert.equal(discovered.some(file => forbidden.test(file)), false, `${name}: ${discovered.join(",")}`);
  }
});

test("documents the legacy Connector and current DataHub boundary", () => {
  const connector = fs.readFileSync(path.join(skillRoot, "data-connector-development", "SKILL.md"), "utf8");
  assert.match(connector, /ResearchWorkbench.*legacy ingestion/s);
  assert.match(connector, /Research Web DataHub Provider/);
  assert.doesNotMatch(connector, /\baf data\b|AlphaFoundry/);
  for (const name of ["cls", "cnstock"]) {
    const source = fs.readFileSync(path.join(skillRoot, name, "SKILL.md"), "utf8");
    assert.match(source, /legacy/i);
    assert.match(source, /DataHub Provider/);
  }
});
