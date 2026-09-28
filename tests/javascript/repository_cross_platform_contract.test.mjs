import assert from "node:assert/strict";
import {spawnSync} from "node:child_process";
import path from "node:path";
import test from "node:test";
import {fileURLToPath} from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

function git(args) {
  return spawnSync("git", args, {cwd: repositoryRoot, encoding: "utf8"});
}

function attributes(files) {
  const result = git(["check-attr", "text", "eol", "--", ...files]);
  assert.equal(result.status, 0, result.stderr);
  const values = new Map(files.map(file => [file, {}]));
  for (const line of result.stdout.trim().split("\n")) {
    const match = line.match(/^(.*): (text|eol): (.*)$/);
    assert.ok(match, `unexpected git check-attr output: ${line}`);
    values.get(match[1])[match[2]] = match[3];
  }
  return values;
}

function isIgnored(file) {
  return git(["check-ignore", "--no-index", "--quiet", "--", file]).status === 0;
}

test("portable text families have explicit stable line endings", () => {
  const lf = [
    "contracts/example.py",
    "contracts/example.js",
    "contracts/example.mjs",
    "contracts/example.ts",
    "contracts/example.json",
    "contracts/example.yml",
    "contracts/example.yaml",
    "contracts/example.md",
    "contracts/example.sh",
  ];
  const crlf = [
    "contracts/example.cmd",
    "contracts/example.bat",
    "contracts/example.ps1",
  ];
  const values = attributes([...lf, ...crlf]);

  for (const file of lf) {
    assert.deepEqual(values.get(file), {text: "set", eol: "lf"}, file);
  }
  for (const file of crlf) {
    assert.deepEqual(values.get(file), {text: "set", eol: "crlf"}, file);
  }
});

test("vendored hash-sensitive trees remain byte stable", () => {
  const files = [
    "vendor/cjpy/0.5.2/manifest.json",
    "vendor/dsh-tabbit/0.3.4/manifest.json",
  ];
  const values = attributes(files);
  for (const file of files) {
    assert.equal(values.get(file).text, "unset", file);
  }
});

test("machine-local environments state logs data and secrets stay outside Git", () => {
  for (const file of [
    ".venv/bin/python",
    ".venv.broken-20260911/bin/python",
    ".venv-task/bin/python",
    ".codex/config.toml",
    ".superpowers/sdd/example/progress.md",
    "node_modules/example/index.js",
    "logs/runtime.log",
    "data/local.sqlite3",
    ".data/postgresql/PG_VERSION",
    ".secrets/vendor.key",
    ".env.local",
  ]) {
    assert.equal(isIgnored(file), true, file);
  }

  for (const file of [".env.example", "README.md"]) {
    assert.equal(isIgnored(file), false, file);
  }
});
